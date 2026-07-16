from __future__ import annotations

import hashlib
import json as json_lib
import uuid
from pathlib import Path
from typing import Any, cast

from builder_ii.config import Settings, load_settings
from builder_ii.context_pack import RepoTarget, repo_for_target, validate_context_pack_record_file
from builder_ii.model_client_registry import create_model_client_registry
from builder_ii.model_execution_gateway import ModelExecutionGateway
from builder_ii.model_routing_policy import (
    create_model_execution_policy,
    create_model_routing_policy,
    create_model_routing_recommendation,
)

CONTEXT_SUMMARY_KIND = "builder_ii.context_summary"
CONTEXT_SUMMARY_SCHEMA_VERSION = 1


def validate_context_summary(record: Any) -> list[str]:
    errors = []
    if not isinstance(record, dict):
        return ["context summary record must be a JSON object"]
    if record.get("kind") != CONTEXT_SUMMARY_KIND:
        errors.append(f"kind must be {CONTEXT_SUMMARY_KIND}")
    if record.get("schema_version") != CONTEXT_SUMMARY_SCHEMA_VERSION:
        errors.append(f"schema_version must be {CONTEXT_SUMMARY_SCHEMA_VERSION}")

    for f in (
        "source_paths",
        "source_hashes",
        "target_profile",
        "model_alias",
        "model_backend",
        "prompt_used",
        "summary",
        "known_omissions",
        "claim_boundary",
    ):
        if f not in record:
            errors.append(f"'{f}' is required")

    if not isinstance(record.get("source_paths"), list):
        errors.append("source_paths must be a list")
    if not isinstance(record.get("source_hashes"), dict):
        errors.append("source_hashes must be a dictionary")
    if not isinstance(record.get("known_omissions"), list):
        errors.append("known_omissions must be a list")
    if not isinstance(record.get("review_required"), bool) or record["review_required"] is not True:
        errors.append("review_required must be true")
    if record.get("artifact_is_authority") is not False:
        errors.append("artifact_is_authority must be false or NOT_AUTHORIZED")

    return errors


def _target_profile_from_record(record_data: dict[str, Any]) -> RepoTarget:
    target_profile = record_data.get("target", "generic")
    if target_profile not in ("core", "builder", "generic"):
        raise ValueError(f"Unsupported context summary target profile: {target_profile}")
    return cast(RepoTarget, target_profile)


def summarize_context_pack(
    context_pack_record_path: Path,
    *,
    model_id: str = "gpt-4o-stub",
    output_summary_path: Path | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    if settings is None:
        settings = load_settings()

    # 1. Validate input context pack record
    errors = validate_context_pack_record_file(context_pack_record_path)
    if errors:
        raise ValueError(f"Invalid context pack record: {errors}")

    record_data = json_lib.loads(context_pack_record_path.read_text(encoding="utf-8"))
    target_profile = _target_profile_from_record(record_data)

    # 2. Setup governed model execution
    registry = create_model_client_registry()
    # Ensure selected model is enabled in registry
    model_found = False
    model_risk = "local_network"
    for client in registry["clients"]:
        if client["model_id"] == model_id:
            client["enabled"] = True
            model_risk = client.get("risk_classification", "local_network")
            model_found = True

    if not model_found:
        raise ValueError(f"Model {model_id} is not supported in client registry.")

    # Recreate settings to allow cloud if model is cloud_external
    if model_risk == "cloud_external":
        settings = Settings(**{**settings.__dict__, "allow_cloud_models": True})

    policy = create_model_routing_policy()
    if model_risk == "cloud_external":
        for rule in policy["rules"]:
            rule["max_risk_classification"] = "cloud_external"

    recommendation = create_model_routing_recommendation(
        policy,
        registry,
        request={
            "required_model_id": model_id,
            "max_risk_classification": model_risk,
        },
    )
    execution_policy = create_model_execution_policy(recommendation, max_tokens=1024)

    # 3. Formulate compression prompt
    selected_files = record_data.get("selected_files", [])
    prompt = (
        f"Generate a high-level architectural summary of the following repository files:\n"
        f"{', '.join(selected_files)}\n\n"
        f"Identify the primary components, interfaces, and dependencies."
    )

    # Run model call
    gateway = ModelExecutionGateway(settings, registry, execution_policy)

    # We will write temporary envelope and receipt artifacts
    temp_dir = settings.project_root / ".builder" / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    unique_id = uuid.uuid4().hex
    envelope_path = temp_dir / f"summary_env_{unique_id}.json"
    receipt_path = temp_dir / f"summary_rec_{unique_id}.json"

    try:
        _, receipt = gateway.run_model_call(
            model_id=model_id,
            prompt=prompt,
            envelope_path=envelope_path,
            receipt_path=receipt_path,
        )
        summary_text = receipt["response_text"]
    finally:
        if envelope_path.exists():
            envelope_path.unlink()
        if receipt_path.exists():
            receipt_path.unlink()

    # Calculate file hashes for source_hashes
    source_hashes = {}
    repo_root = repo_for_target(settings, target_profile)
    for p in selected_files:
        fpath = repo_root / p
        if fpath.is_file():
            source_hashes[p] = hashlib.sha256(fpath.read_bytes()).hexdigest()
        else:
            source_hashes[p] = ""

    summary_artifact = {
        "kind": CONTEXT_SUMMARY_KIND,
        "schema_version": CONTEXT_SUMMARY_SCHEMA_VERSION,
        "source_paths": selected_files,
        "source_hashes": source_hashes,
        "target_profile": target_profile,
        "model_alias": model_id,
        "model_backend": "stub" if model_id == "gpt-4o-stub" else "mlx-lm",
        "prompt_used": prompt,
        "summary": summary_text,
        "known_omissions": ["hidden reasoning", "large non-text assets"],
        "claim_boundary": "This is a derived summary and is not a guarantee of correctness.",
        "review_required": True,
        "artifact_is_authority": False,
    }

    if output_summary_path is not None:
        output_summary_path.parent.mkdir(parents=True, exist_ok=True)
        output_summary_path.write_text(
            json_lib.dumps(summary_artifact, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    return summary_artifact
