from __future__ import annotations

import hashlib
import json as json_lib
import re
from pathlib import Path
from typing import Any

from builder_ii.config import Settings
from builder_ii.direct_chat import DirectChatResult, run_direct_chat
from builder_ii.model_client_registry import (
    validate_model_client_registry,
)
from builder_ii.model_routing_policy import (
    validate_model_execution_policy,
)
from builder_ii.price_book import (
    create_default_price_book,
    lookup_price_entry,
    price_book_ref,
    validate_price_book,
)
from builder_ii.token_accounting import build_cost_report

MODEL_CALL_ENVELOPE_KIND = "builder_ii.model_call_envelope"
MODEL_CALL_ENVELOPE_SCHEMA_VERSION = 1

MODEL_CALL_RECEIPT_KIND = "builder_ii.model_call_receipt"
MODEL_CALL_RECEIPT_SCHEMA_VERSION = 1

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

# Secret scanning regexes
SECRET_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9_]{32,}", re.IGNORECASE),
    re.compile(r"gsk_[a-zA-Z0-9_]{32,}", re.IGNORECASE),
    re.compile(r"AIza[a-zA-Z0-9_\-]{35}", re.IGNORECASE),
    re.compile(r"bearer\s+[a-zA-Z0-9_\-\.\~]{10,}", re.IGNORECASE),
    re.compile(r"ghp_[a-zA-Z0-9]{36}", re.IGNORECASE),
    re.compile(r"(?:api_key|apikey|secret|token)\s*[:=]\s*[\"'][a-zA-Z0-9_\-]{8,}[\"']", re.IGNORECASE),
]


def scan_for_secrets(text: str) -> list[str]:
    errors: list[str] = []
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            errors.append(f"Potential secret/credential pattern detected: {pattern.pattern}")
    return errors


def _digest(data: dict[str, Any]) -> str:
    raw = json_lib.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _default_authority_boundary(
    capability_state: str,
    *,
    performs_network_calls: bool = False,
) -> dict[str, Any]:
    return {
        "capability_state": capability_state,
        "executes_model": True,
        "executes_tools": False,
        "executes_shell": False,
        "invokes_goose": False,
        "constructs_deepagents": False,
        "constructs_subagents": False,
        "invokes_mcp": False,
        "performs_network_calls": performs_network_calls,
        "mutates_target_repo": False,
        "mutates_memory": False,
        "grants_authority": False,
        "artifact_is_authority": False,
        "requires_human_promotion_for_execution": True,
    }


def _default_governance(
    capability_state: str,
    *,
    network_calls_enabled: bool = False,
) -> dict[str, Any]:
    return {
        "capability_state": capability_state,
        "runtime_execution": "DISABLED",
        "goose_runtime_start": "DISABLED",
        "deepagents_runtime_start": "DISABLED",
        "agent_construction": "DISABLED",
        "subagent_construction": "DISABLED",
        "model_execution": "ENABLED_UNDER_ENVELOPE",
        "tool_execution": "DISABLED",
        "shell_execution": "DISABLED",
        "network_calls": "ENABLED_UNDER_ENVELOPE" if network_calls_enabled else "DISABLED",
        "source_writes": "DISABLED EXCEPT EXPLICIT ARTIFACT OUTPUT PATH",
        "target_repo_writes": "DISABLED",
        "memory_mutation": "DISABLED",
        "mcp_tool_calls": "DISABLED",
        "verification_execution": "DISABLED",
        "artifact_is_authority": False,
        "grants_authority": False,
        "requires_human_promotion_for_execution": True,
        "core_workbench_coupling": "NONE",
    }


def validate_model_call_envelope(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["model call envelope must be a JSON object"]

    if data.get("kind") != MODEL_CALL_ENVELOPE_KIND:
        errors.append(f"kind must be {MODEL_CALL_ENVELOPE_KIND}")
    if data.get("schema_version") != MODEL_CALL_ENVELOPE_SCHEMA_VERSION:
        errors.append(f"schema_version must be {MODEL_CALL_ENVELOPE_SCHEMA_VERSION}")

    for str_field in ("session_id", "model_id", "client_id", "provider_id", "prompt_digest"):
        val = data.get(str_field)
        if not isinstance(val, str) or not val:
            errors.append(f"{str_field} must be a non-empty string")

    pd = data.get("prompt_digest", "")
    if pd and not _SHA256_RE.match(pd):
        errors.append("prompt_digest must be a valid SHA-256 digest")

    if not isinstance(data.get("max_tokens"), int) or data["max_tokens"] <= 0:
        errors.append("max_tokens must be a positive integer")

    temp = data.get("temperature")
    if temp is not None and not isinstance(temp, (int, float)):
        errors.append("temperature must be a number or null")

    for f_false in (
        "executes_tools",
        "executes_shell",
        "invokes_goose",
        "constructs_deepagents",
        "constructs_subagents",
        "invokes_mcp",
        "mutates_target_repo",
        "mutates_memory",
        "grants_authority",
        "artifact_is_authority",
    ):
        if data.get(f_false) is not False:
            errors.append(f"{f_false} must be false or NOT_AUTHORIZED")

    if data.get("executes_model") is not True:
        errors.append("executes_model must be true")

    if not isinstance(data.get("performs_network_calls"), bool):
        errors.append("performs_network_calls must be a boolean")

    if data.get("requires_human_promotion_for_execution") is not True:
        errors.append("requires_human_promotion_for_execution must be true")

    boundary = data.get("authority_boundary")
    if not isinstance(boundary, dict):
        errors.append("authority_boundary must be an object")
    else:
        if boundary.get("capability_state") != "model_call":
            errors.append("authority_boundary.capability_state must be model_call")
        if boundary.get("executes_model") is not True:
            errors.append("authority_boundary.executes_model must be true")
        for f_false in (
            "executes_tools",
            "executes_shell",
            "invokes_goose",
            "constructs_deepagents",
            "constructs_subagents",
            "invokes_mcp",
            "mutates_target_repo",
            "mutates_memory",
            "grants_authority",
            "artifact_is_authority",
        ):
            if boundary.get(f_false) is not False:
                errors.append(f"authority_boundary.{f_false} must be false or NOT_AUTHORIZED")
        # performs_network_calls in authority_boundary must match top-level
        top_network = data.get("performs_network_calls")
        if isinstance(top_network, bool) and boundary.get("performs_network_calls") != top_network:
            errors.append("authority_boundary.performs_network_calls must match top-level performs_network_calls")

    gov = data.get("governance")
    if not isinstance(gov, dict):
        errors.append("governance must be an object")
    else:
        if gov.get("model_execution") != "ENABLED_UNDER_ENVELOPE":
            errors.append("governance.model_execution must be ENABLED_UNDER_ENVELOPE")
        # network_calls must match whether network is involved
        top_network = data.get("performs_network_calls")
        expected_network_gov = "ENABLED_UNDER_ENVELOPE" if top_network else "DISABLED"
        if gov.get("network_calls") != expected_network_gov:
            errors.append(
                f"governance.network_calls must be {expected_network_gov} (based on performs_network_calls={top_network})"
            )
        for key in (
            "runtime_execution",
            "goose_runtime_start",
            "deepagents_runtime_start",
            "agent_construction",
            "subagent_construction",
            "tool_execution",
            "shell_execution",
            "target_repo_writes",
            "memory_mutation",
            "mcp_tool_calls",
            "verification_execution",
        ):
            if gov.get(key) != "DISABLED":
                errors.append(f"governance.{key} must be DISABLED or NOT_AUTHORIZED")

    return errors


def validate_model_call_receipt(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["model call receipt must be a JSON object"]

    if data.get("kind") != MODEL_CALL_RECEIPT_KIND:
        errors.append(f"kind must be {MODEL_CALL_RECEIPT_KIND}")
    if data.get("schema_version") != MODEL_CALL_RECEIPT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {MODEL_CALL_RECEIPT_SCHEMA_VERSION}")

    envelope_ref = data.get("envelope_ref")
    if not isinstance(envelope_ref, dict):
        errors.append("envelope_ref must be an object")
    else:
        if envelope_ref.get("kind") != MODEL_CALL_ENVELOPE_KIND:
            errors.append(f"envelope_ref.kind must be {MODEL_CALL_ENVELOPE_KIND}")
        if not isinstance(envelope_ref.get("sha256"), str) or not _SHA256_RE.match(envelope_ref["sha256"]):
            errors.append("envelope_ref.sha256 must be a valid SHA-256 digest")
        if envelope_ref.get("role") != "model_call_envelope":
            errors.append("envelope_ref.role must be model_call_envelope")

    if not isinstance(data.get("response_text"), str):
        errors.append("response_text must be a string")

    if "status" in data and data.get("status") not in ("succeeded", "failed"):
        errors.append("status must be succeeded or failed")

    response_sha256 = data.get("response_sha256")
    if response_sha256 is not None and (not isinstance(response_sha256, str) or not _SHA256_RE.match(response_sha256)):
        errors.append("response_sha256 must be a valid SHA-256 digest")

    cost = data.get("cost_report")
    if not isinstance(cost, dict):
        errors.append("cost_report must be an object")
    else:
        for f in ("input_tokens", "output_tokens", "total_tokens"):
            if not isinstance(cost.get(f), int) or cost[f] < 0:
                errors.append(f"cost_report.{f} must be a non-negative integer")
        accounting = cost.get("token_accounting")
        if accounting not in ("measured", "estimated"):
            errors.append("cost_report.token_accounting must be 'measured' or 'estimated'")
        if accounting == "measured":
            if not isinstance(cost.get("tokenizer_id"), str) or not cost.get("tokenizer_id"):
                errors.append("cost_report.tokenizer_id is required when token_accounting is measured")
            if not isinstance(cost.get("tokenizer_version"), str) or not cost.get("tokenizer_version"):
                errors.append("cost_report.tokenizer_version is required when token_accounting is measured")
        if accounting == "estimated" and not cost.get("estimated_reason"):
            errors.append("cost_report.estimated_reason is required when token_accounting is estimated")
        for usd_field in ("estimated_usd_input", "estimated_usd_output", "estimated_usd_total"):
            if usd_field in cost:
                val = cost.get(usd_field)
                if not isinstance(val, (int, float)) or isinstance(val, bool) or val < 0:
                    errors.append(f"cost_report.{usd_field} must be a non-negative number when present")

    if data.get("replay_declaration") != "non-deterministic-llm-completion":
        errors.append("replay_declaration must be non-deterministic-llm-completion")

    for f_false in (
        "executes_tools",
        "executes_shell",
        "invokes_goose",
        "constructs_deepagents",
        "constructs_subagents",
        "invokes_mcp",
        "mutates_target_repo",
        "mutates_memory",
        "grants_authority",
        "artifact_is_authority",
    ):
        if data.get(f_false) is not False:
            errors.append(f"{f_false} must be false or NOT_AUTHORIZED")

    if data.get("executes_model") is not True:
        errors.append("executes_model must be true")

    if data.get("requires_human_promotion_for_execution") is not True:
        errors.append("requires_human_promotion_for_execution must be true")

    return errors


def validate_model_call_receipt_file(path: Path) -> list[str]:
    if not path.is_file():
        return [f"file not found or not a file: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_model_call_receipt(data)


def _resolve_price_book(price_book: dict[str, Any] | None) -> dict[str, Any]:
    book = price_book if price_book is not None else create_default_price_book()
    errs = validate_price_book(book)
    if errs:
        raise ValueError(f"invalid price book: {'; '.join(errs)}")
    return book


def _cost_report_for_call(
    *,
    prompt: str,
    response_text: str,
    model_id: str,
    price_book: dict[str, Any],
) -> dict[str, Any]:
    entry = lookup_price_entry(price_book, model_id)
    input_rate = float(entry["input_usd_per_1k"]) if entry else 0.0
    output_rate = float(entry["output_usd_per_1k"]) if entry else 0.0
    tokenizer_id = str(entry["tokenizer_id"]) if entry and entry.get("tokenizer_id") else None
    return build_cost_report(
        prompt=prompt,
        response_text=response_text,
        model_id=model_id,
        input_usd_per_1k=input_rate,
        output_usd_per_1k=output_rate,
        currency=str((entry or {}).get("currency") or "USD"),
        price_book_ref=price_book_ref(price_book),
        tokenizer_id=tokenizer_id,
    )


class ModelExecutionGateway:
    def __init__(
        self,
        settings: Settings,
        registry: dict[str, Any],
        execution_policy: dict[str, Any],
        price_book: dict[str, Any] | None = None,
    ):
        reg_errs = validate_model_client_registry(registry)
        if reg_errs:
            raise ValueError(f"invalid model client registry: {'; '.join(reg_errs)}")
        pol_errs = validate_model_execution_policy(execution_policy)
        if pol_errs:
            raise ValueError(f"invalid model execution policy: {'; '.join(pol_errs)}")
        self.settings = settings
        self.registry = registry
        self.execution_policy = execution_policy
        self.price_book = _resolve_price_book(price_book)

    def run_model_call(
        self,
        *,
        model_id: str,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 256,
        temperature: float | None = None,
        envelope_path: Path,
        receipt_path: Path,
        approval_path: Path | None = None,
        ledger_bound: bool = False,
        budget: dict[str, Any] | None = None,
        events_dir: Path | None = None,
        session_id: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        # Fail closed on empty prompt or invalid outputs
        if not prompt.strip():
            raise ValueError("Prompt must not be empty")

        # Optional WRP MSDA preflight (off by default). Tool name is model_call; domain local.
        # Option A: annotate skip/enforced — never soft-enable product default-on.
        from builder_ii.wrp.msda_preflight import annotate_msda_preflight_result, assert_msda_preflight

        _msda_decision = assert_msda_preflight(
            tool="model_call",
            data_domain="local_workspace",
            risk="local_network",
        )
        _msda_preflight_annotation = annotate_msda_preflight_result(_msda_decision)

        # Secret scanning
        secret_errors = scan_for_secrets(prompt)
        if secret_errors:
            raise ValueError(f"Credential/secret leak detected in prompt: {'; '.join(secret_errors)}")

        # Retrieve client record
        client_record = None
        for client in self.registry.get("clients", []):
            if client.get("model_id") == model_id:
                client_record = client
                break

        if not client_record:
            raise ValueError(f"Model ID '{model_id}' not found in registry")

        if not client_record.get("enabled"):
            raise ValueError(f"Model '{model_id}' is disabled in client registry")

        if model_id not in self.execution_policy.get("allowed_models", []):
            raise ValueError(f"Model ID '{model_id}' is not authorized by the execution policy")

        if max_tokens > client_record.get("max_output_tokens", 0):
            raise ValueError(
                f"Requested max_tokens {max_tokens} exceeds client registry limit {client_record.get('max_output_tokens')}"
            )

        if max_tokens > self.execution_policy.get("max_tokens", 0):
            raise ValueError(
                f"Requested max_tokens {max_tokens} exceeds execution policy limit {self.execution_policy.get('max_tokens')}"
            )

        # Check policy risk classification constraints
        risk_level = client_record.get("risk_classification")
        is_stub_provider = client_record.get("provider_id") in (
            "openai_stub_provider",
            "anthropic_stub_provider",
        )
        human_approval_required = (
            risk_level in ("cloud_external", "cost_bearing", "credential_sensitive") and not is_stub_provider
        )
        human_approval_supplied = approval_path is not None and approval_path.is_file()
        if risk_level == "cloud_external":
            if not self.settings.allow_cloud_models:
                raise ValueError("Cloud/external model calls are disabled by environment configuration")
            if human_approval_required and not human_approval_supplied:
                raise ValueError(
                    "Cloud/external model calls require an explicit approval artifact via approval_path"
                )
        elif risk_level == "local_offline":
            raise ValueError("local_offline risk classification cannot perform network calls to execution backends")

        # Create envelope
        session_id = f"session-{_digest({'prompt': prompt})[:12]}"
        prompt_digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()

        performs_network = risk_level in ("local_network", "cloud_external")

        envelope = {
            "kind": MODEL_CALL_ENVELOPE_KIND,
            "schema_version": MODEL_CALL_ENVELOPE_SCHEMA_VERSION,
            "session_id": session_id,
            "model_id": model_id,
            "client_id": client_record.get("client_id"),
            "provider_id": client_record.get("provider_id"),
            "prompt_digest": prompt_digest,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "executes_model": True,
            "executes_tools": False,
            "executes_shell": False,
            "invokes_goose": False,
            "constructs_deepagents": False,
            "constructs_subagents": False,
            "invokes_mcp": False,
            "performs_network_calls": performs_network,
            "mutates_target_repo": False,
            "mutates_memory": False,
            "grants_authority": False,
            "artifact_is_authority": False,
            "requires_human_promotion_for_execution": True,
            "human_approval_required": human_approval_required,
            "human_approval_supplied": human_approval_supplied,
            "ledger_bound": ledger_bound,
            "authority_boundary": _default_authority_boundary("model_call", performs_network_calls=performs_network),
            "governance": _default_governance("model_call", network_calls_enabled=performs_network),
        }
        envelope["digest"] = _digest(envelope)

        env_errors = validate_model_call_envelope(envelope)
        if env_errors:
            raise ValueError(f"Generated envelope failed validation: {'; '.join(env_errors)}")

        envelope_path.parent.mkdir(parents=True, exist_ok=True)
        envelope_path.write_text(json_lib.dumps(envelope, indent=2, sort_keys=True), encoding="utf-8")

        # Budget preflight (optional until seam requires it).
        projected_cost = _cost_report_for_call(
            prompt=prompt,
            response_text="",
            model_id=model_id,
            price_book=self.price_book,
        )
        # Project max output conservatively using max_tokens as upper bound for debit check.
        if budget is not None:
            from builder_ii.model_budget import assert_budget_allows_call, project_call_cost

            projected = project_call_cost(
                prompt=prompt,
                max_output_tokens=max_tokens,
                model_id=model_id,
                price_book=self.price_book,
            )
            assert_budget_allows_call(budget, projected)

        # Execute call
        # If stub provider, return stub response
        if client_record.get("provider_id") in ("openai_stub_provider", "anthropic_stub_provider"):
            result_text = f"Mocked stub response for model '{model_id}' to: {prompt[:30]}..."
        else:
            # Run local offline/network call
            chat_res: DirectChatResult = run_direct_chat(
                self.settings,
                prompt=prompt,
                system_prompt=system_prompt if system_prompt else "Answer helpfully.",
                max_tokens=max_tokens,
                temperature=temperature,
                override_model_id=model_id,
            )
            if not chat_res.ok:
                envelope_ref = {
                    "kind": MODEL_CALL_ENVELOPE_KIND,
                    "path": str(envelope_path),
                    "sha256": envelope["digest"],
                    "role": "model_call_envelope",
                    "name": f"Model call envelope for {model_id}",
                    "required": True,
                }
                fail_cost = _cost_report_for_call(
                    prompt=prompt,
                    response_text="",
                    model_id=model_id,
                    price_book=self.price_book,
                )
                failure_receipt = {
                    "kind": MODEL_CALL_RECEIPT_KIND,
                    "schema_version": MODEL_CALL_RECEIPT_SCHEMA_VERSION,
                    "status": "failed",
                    "envelope_ref": envelope_ref,
                    "response_text": "",
                    "response_sha256": hashlib.sha256(b"").hexdigest(),
                    "response_storage_policy": "empty_failure_response",
                    "error_summary": str(chat_res.error or "model execution failed")[:500],
                    "cost_report": fail_cost,
                    "replay_declaration": "non-deterministic-llm-completion",
                    "executes_model": True,
                    "executes_tools": False,
                    "executes_shell": False,
                    "invokes_goose": False,
                    "constructs_deepagents": False,
                    "constructs_subagents": False,
                    "invokes_mcp": False,
                    "mutates_target_repo": False,
                    "mutates_memory": False,
                    "grants_authority": False,
                    "artifact_is_authority": False,
                    "requires_human_promotion_for_execution": True,
                    "ledger_bound": ledger_bound,
                    "authority_boundary": _default_authority_boundary(
                        "model_call", performs_network_calls=performs_network
                    ),
                    "governance": _default_governance("model_call", network_calls_enabled=performs_network),
                }
                failure_receipt["digest"] = _digest(failure_receipt)
                receipt_path.parent.mkdir(parents=True, exist_ok=True)
                receipt_path.write_text(
                    json_lib.dumps(failure_receipt, indent=2, sort_keys=True),
                    encoding="utf-8",
                )
                if ledger_bound and events_dir is not None:
                    from builder_ii.runtime_event_append import append_model_call_event

                    append_model_call_event(
                        events_dir=events_dir,
                        session_id=session_id or envelope.get("session_id") or "session-unknown",
                        event_type="model_call_failed",
                        envelope=envelope,
                        receipt=failure_receipt,
                        envelope_path=envelope_path,
                        receipt_path=receipt_path,
                        command_surface="ModelExecutionGateway.run_model_call",
                        message=f"Model call failed: {chat_res.error}",
                    )
                raise RuntimeError(f"Model execution failed: {chat_res.error}")
            result_text = chat_res.content

        # Create receipt
        envelope_ref = {
            "kind": MODEL_CALL_ENVELOPE_KIND,
            "path": str(envelope_path),
            "sha256": envelope["digest"],
            "role": "model_call_envelope",
            "name": f"Model call envelope for {model_id}",
            "required": True,
        }

        output_cap = int(self.execution_policy.get("max_response_chars", 4000))
        bounded_text = result_text[:output_cap]
        output_truncated = len(result_text) > len(bounded_text)

        cost_report = _cost_report_for_call(
            prompt=prompt,
            response_text=result_text,
            model_id=model_id,
            price_book=self.price_book,
        )
        # projected_cost used only for budget preflight above; silence unused if no budget.
        _ = projected_cost

        receipt = {
            "kind": MODEL_CALL_RECEIPT_KIND,
            "schema_version": MODEL_CALL_RECEIPT_SCHEMA_VERSION,
            "status": "succeeded",
            "envelope_ref": envelope_ref,
            "response_text": bounded_text,
            "response_sha256": hashlib.sha256(result_text.encode("utf-8")).hexdigest(),
            "response_text_truncated": output_truncated,
            "response_storage_policy": "bounded_inline_response_text",
            "cost_report": cost_report,
            "replay_declaration": "non-deterministic-llm-completion",
            "executes_model": True,
            "executes_tools": False,
            "executes_shell": False,
            "invokes_goose": False,
            "constructs_deepagents": False,
            "constructs_subagents": False,
            "invokes_mcp": False,
            "mutates_target_repo": False,
            "mutates_memory": False,
            "grants_authority": False,
            "artifact_is_authority": False,
            "requires_human_promotion_for_execution": True,
            "human_approval_required": human_approval_required,
            "human_approval_supplied": human_approval_supplied,
            "ledger_bound": ledger_bound,
            "output_truth_authority": False,
            "promotion_authority": False,
            "authority_boundary": _default_authority_boundary("model_call", performs_network_calls=performs_network),
            "governance": _default_governance("model_call", network_calls_enabled=performs_network),
        }
        if approval_path is not None and approval_path.is_file():
            approval_raw = approval_path.read_bytes()
            receipt["approval_ref"] = {
                "kind": "builder_ii.approval_record",
                "path": str(approval_path),
                "sha256": hashlib.sha256(approval_raw).hexdigest(),
                "role": "model_call_approval",
                "required": human_approval_required,
            }
        receipt["msda_preflight"] = _msda_preflight_annotation
        if budget is not None:
            from builder_ii.model_budget import budget_ref as _budget_ref

            receipt["budget_ref"] = _budget_ref(budget)
        receipt["digest"] = _digest(receipt)

        rec_errors = validate_model_call_receipt(receipt)
        if rec_errors:
            raise ValueError(f"Generated receipt failed validation: {'; '.join(rec_errors)}")

        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(json_lib.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")

        debited_budget: dict[str, Any] | None = None
        if budget is not None:
            from builder_ii.model_budget import debit_budget

            debited_budget = debit_budget(budget, cost_report)
            prior_ref = receipt.get("budget_ref")
            base_ref: dict[str, Any] = dict(prior_ref) if isinstance(prior_ref, dict) else {}
            receipt["budget_ref"] = {
                **base_ref,
                "post_debit_sha256": debited_budget.get("digest"),
                "budget_version": debited_budget.get("budget_version"),
            }
            # Keep pre-debit budget_ref fields on receipt; debited budget available on instance.
            self._last_debited_budget: dict[str, Any] | None = debited_budget
        else:
            self._last_debited_budget = None

        if ledger_bound and events_dir is not None:
            from builder_ii.runtime_event_append import append_model_call_event

            append_model_call_event(
                events_dir=events_dir,
                session_id=session_id or envelope.get("session_id") or "session-unknown",
                event_type="model_call_executed",
                envelope=envelope,
                receipt=receipt,
                envelope_path=envelope_path,
                receipt_path=receipt_path,
                command_surface="ModelExecutionGateway.run_model_call",
                message=f"Model call executed: {model_id}",
            )

        return envelope, receipt
