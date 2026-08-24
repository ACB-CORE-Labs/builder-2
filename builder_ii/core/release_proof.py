from __future__ import annotations

import csv
import hashlib
import json
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Any

from builder_ii.core.release_manifest import (
    REQUIRED_RELEASE_LANES,
    create_artifact_ref,
    create_release_proof_bundle,
    validate_release_evidence,
    validate_release_proof_bundle,
    write_release_proof_bundle,
)
from builder_ii.governance.ledger.artifact_index_records import (
    create_artifact_index_record,
    validate_artifact_index_record,
    write_artifact_index_record,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_sha256(path: Path) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, text=True, capture_output=True).stdout.strip()


def _safe_files(directory: Path) -> list[Path]:
    if not directory.is_dir() or directory.is_symlink():
        raise ValueError(f"required directory is missing or symlinked: {directory}")
    files = sorted(path for path in directory.iterdir() if path.is_file())
    if any(path.is_symlink() for path in files):
        raise ValueError(f"symlinked evidence is forbidden: {directory}")
    return files


def _safe_relative_file(root: Path, relative: str) -> Path:
    candidate = root / relative
    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ValueError(f"unsafe bundle-relative path: {relative}")
    if candidate.is_symlink() or not candidate.is_file():
        raise ValueError(f"bundle file is missing or symlinked: {relative}")
    if not candidate.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"bundle path escapes root: {relative}")
    return candidate


def _payload_custody(output_dir: Path) -> list[dict[str, Any]]:
    excluded = {"release-proof-bundle.json"}
    records: list[dict[str, Any]] = []
    for path in sorted(item for item in output_dir.rglob("*") if item.is_file()):
        relative = path.relative_to(output_dir).as_posix()
        if relative in excluded:
            continue
        if path.is_symlink():
            raise ValueError(f"symlinked bundle payload is forbidden: {relative}")
        records.append({"path": relative, "size": path.stat().st_size, "sha256": sha256_file(path)})
    return records


def _ci_receipt_errors(receipt: Any, source_commit: Any) -> list[str]:
    if not isinstance(receipt, dict):
        return ["canonical CI receipt must be an object"]
    gates = receipt.get("gates", [])
    if (
        receipt.get("valid") is not True
        or receipt.get("overall_state") != "PASSED"
        or receipt.get("head_sha_stable") is not True
        or receipt.get("working_tree_clean") is not True
        or receipt.get("head_sha_before") != source_commit
        or receipt.get("head_sha_after") != source_commit
        or receipt.get("skipped") != []
        or not isinstance(gates, list)
        or not gates
        or any(gate.get("status") != "PASSED" or gate.get("skip_reason") is not None for gate in gates)
    ):
        return ["canonical CI receipt is not exact-tip green with zero blocking skips"]
    return []


def _distribution_record(path: Path) -> dict[str, Any]:
    base = {"filename": path.name, "size": path.stat().st_size, "sha256": sha256_file(path)}
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            names = sorted(archive.namelist())
            metadata_name = next(name for name in names if name.endswith(".dist-info/METADATA"))
            metadata = archive.read(metadata_name).decode("utf-8")
            if "Name: builder-ii" not in metadata or "Version: 1.0.0" not in metadata:
                raise ValueError("wheel metadata does not identify builder-ii 1.0.0")
            record_name = next(name for name in names if name.endswith(".dist-info/RECORD"))
            inventory = [row[0] for row in csv.reader(archive.read(record_name).decode().splitlines())]
            if sorted(inventory) != names:
                raise ValueError("wheel RECORD inventory does not equal wheel entries")
        return {"type": "wheel", **base, "record_inventory": inventory}
    if path.name.endswith(".tar.gz"):
        return {"type": "sdist", **base}
    raise ValueError(f"unsupported distribution: {path.name}")


def build_release_proof_bundle_directory(*, repo: Path, dist_dir: Path, evidence_dir: Path, output_dir: Path) -> Path:
    repo = repo.resolve()
    output_dir = output_dir.resolve()
    if _git(repo, "status", "--porcelain"):
        raise ValueError("candidate repository must be clean before release proof construction")
    if output_dir.exists():
        shutil.rmtree(output_dir)
    (output_dir / "evidence").mkdir(parents=True)
    (output_dir / "dist").mkdir()

    evidence_by_lane: dict[str, Path] = {}
    for evidence_source in _safe_files(evidence_dir.resolve()):
        if evidence_source.suffix != ".json":
            continue
        data = json.loads(evidence_source.read_text(encoding="utf-8"))
        errors = validate_release_evidence(data)
        if errors:
            raise ValueError(f"invalid release evidence {evidence_source}: {errors}")
        lane = data["lane"]
        if lane in evidence_by_lane:
            raise ValueError(f"duplicate release evidence lane: {lane}")
        target = output_dir / "evidence" / evidence_source.name
        shutil.copyfile(evidence_source, target)
        evidence_by_lane[lane] = target
    constituents = evidence_dir.resolve() / "constituents"
    if constituents.exists():
        if constituents.is_symlink() or not constituents.is_dir():
            raise ValueError("evidence constituents directory is symlinked or invalid")
        shutil.copytree(constituents, output_dir / "evidence" / "constituents", symlinks=False)
    missing = sorted(set(REQUIRED_RELEASE_LANES) - set(evidence_by_lane))
    if missing:
        raise ValueError(f"missing release evidence lanes: {', '.join(missing)}")

    distributions: list[dict[str, Any]] = []
    for dist_source in _safe_files(dist_dir.resolve()):
        if dist_source.suffix != ".whl" and not dist_source.name.endswith(".tar.gz"):
            continue
        target = output_dir / "dist" / dist_source.name
        shutil.copyfile(dist_source, target)
        distributions.append(_distribution_record(target))
    distribution_counts = {kind: sum(item["type"] == kind for item in distributions) for kind in ("wheel", "sdist")}
    for kind, count in distribution_counts.items():
        if count != 1:
            raise ValueError(f"candidate must contain exactly one {kind}; found {count}")

    archive_path = output_dir / "source.tar"
    archive_path.write_bytes(
        subprocess.run(["git", "-C", str(repo), "archive", "HEAD"], check=True, capture_output=True).stdout
    )

    index = create_artifact_index_record(output_dir / "evidence", recursive=True)
    index_errors = validate_artifact_index_record(index)
    if index_errors:
        raise ValueError(f"release evidence index is invalid: {index_errors}")
    index_path = output_dir / "artifact-index.json"
    write_artifact_index_record(index, index_path)

    source = {
        "commit": _git(repo, "rev-parse", "HEAD"),
        "parents": _git(repo, "show", "-s", "--format=%P", "HEAD").split(),
        "tree": _git(repo, "rev-parse", "HEAD^{tree}"),
        "clean": True,
        "uv_lock_sha256": sha256_file(repo / "uv.lock"),
        "source_archive_sha256": sha256_file(archive_path),
    }
    evidence = {
        lane: {
            "result": "PASS",
            "ref": create_artifact_ref(
                kind="builder_ii.release_evidence",
                path=path.relative_to(output_dir).as_posix(),
                sha256=canonical_json_sha256(path),
            ),
        }
        for lane, path in sorted(evidence_by_lane.items())
    }
    bundle = create_release_proof_bundle(
        source=source,
        distributions=distributions,
        supported_runtime={
            "python": ">=3.12.13,<3.13",
            "macos_apple_silicon": "SUPPORTED_MLX_PRIMARY",
            "linux": "SUPPORTED_NO_MLX_PARITY",
            "windows": "UNSUPPORTED_V1",
            "wsl2": "UNSUPPORTED_V1",
        },
        evidence=evidence,
        artifact_index_ref=create_artifact_ref(
            kind="builder_ii.artifact_index_record",
            path="artifact-index.json",
            sha256=canonical_json_sha256(index_path),
        ),
        payload_custody=_payload_custody(output_dir),
    )
    bundle_path = output_dir / "release-proof-bundle.json"
    write_release_proof_bundle(bundle, bundle_path)
    errors = validate_release_proof_bundle_directory(output_dir, repo=repo)
    if errors:
        raise ValueError(f"constructed release bundle failed independent validation: {errors}")
    return bundle_path


def validate_release_proof_bundle_directory(directory: Path, *, repo: Path | None = None) -> list[str]:
    directory = directory.resolve()
    errors: list[str] = []
    try:
        if directory.is_symlink() or not directory.is_dir():
            return [f"bundle directory is missing or symlinked: {directory}"]
        bundle_path = directory / "release-proof-bundle.json"
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        errors.extend(validate_release_proof_bundle(bundle))
        dist_files = [path for path in (directory / "dist").iterdir() if path.is_file()]
        expected_dist_names = [record.get("filename") for record in bundle.get("distributions", [])]
        if sorted(path.name for path in dist_files) != sorted(expected_dist_names):
            errors.append("distribution directory does not exactly match the bundle manifest")
        for record in bundle.get("distributions", []):
            path = directory / "dist" / record.get("filename", "")
            if path.is_symlink() or not path.is_file():
                errors.append(f"distribution missing or symlinked: {path}")
            elif sha256_file(path) != record.get("sha256"):
                errors.append(f"distribution digest mismatch: {path.name}")
        for lane, record in bundle.get("evidence", {}).items():
            ref = record.get("ref", {})
            try:
                path = _safe_relative_file(directory, ref.get("path", ""))
            except ValueError:
                errors.append(f"evidence missing or symlinked: {lane}")
                continue
            if canonical_json_sha256(path) != ref.get("sha256"):
                errors.append(f"evidence digest mismatch: {lane}")
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("lane") != lane or data.get("result") != "PASS":
                errors.append(f"evidence lane/result mismatch: {lane}")
            wheel_records = [item for item in bundle.get("distributions", []) if item.get("type") == "wheel"]
            wheel_sha = wheel_records[0].get("sha256") if len(wheel_records) == 1 else None
            errors.extend(
                f"{lane}: {error}"
                for error in validate_release_evidence(
                    data,
                    expected_source=bundle.get("source", {}),
                    expected_wheel_sha256=wheel_sha,
                )
            )
            claims = data.get("claims", {})
            refs = list(data.get("log_refs", []))
            refs.extend(value for key, value in claims.items() if key.endswith("_ref") and isinstance(value, dict))
            for ref_index, claim_ref in enumerate(refs):
                try:
                    claim_path = _safe_relative_file(directory, claim_ref.get("path", ""))
                    actual = (
                        canonical_json_sha256(claim_path) if claim_path.suffix == ".json" else sha256_file(claim_path)
                    )
                    if actual != claim_ref.get("sha256"):
                        errors.append(f"{lane}: referenced evidence digest mismatch at ref {ref_index}")
                    if claim_path.suffix == ".json" and claim_ref.get("kind"):
                        claim_data = json.loads(claim_path.read_text(encoding="utf-8"))
                        if claim_data.get("kind") != claim_ref.get("kind"):
                            errors.append(f"{lane}: referenced evidence kind mismatch at ref {ref_index}")
                        if lane == "local_ci" and claim_ref.get("kind") == "builder_ii.gate_battery_receipt":
                            source = bundle.get("source", {})
                            errors.extend(
                                f"local_ci: {error}" for error in _ci_receipt_errors(claim_data, source.get("commit"))
                            )
                except (ValueError, OSError, json.JSONDecodeError):
                    errors.append(f"{lane}: referenced evidence is missing or invalid at ref {ref_index}")
            if lane == "artifact_chain" and isinstance(claims, dict):
                chain_ref = claims.get("chain_report_ref", {})
                try:
                    chain_path = _safe_relative_file(directory, chain_ref.get("path", ""))
                    chain = json.loads(chain_path.read_text(encoding="utf-8"))
                    counts = chain.get("counts", {})
                    if chain.get("valid") is not True or chain.get("status") != "valid":
                        errors.append("artifact_chain: canonical chain report is not valid")
                    if counts.get("broken_links") != 0 or counts.get("native_invalid") != 0:
                        errors.append(
                            "artifact_chain: canonical chain report contains broken or native-invalid artifacts"
                        )
                except (ValueError, OSError, json.JSONDecodeError):
                    errors.append("artifact_chain: canonical chain report cannot be read")
        index_path = directory / bundle.get("artifact_index_ref", {}).get("path", "")
        if not index_path.is_file() or canonical_json_sha256(index_path) != bundle.get("artifact_index_ref", {}).get(
            "sha256"
        ):
            errors.append("artifact index is missing or digest-mismatched")
        else:
            errors.extend(validate_artifact_index_record(json.loads(index_path.read_text(encoding="utf-8"))))
        archive = directory / "source.tar"
        if not archive.is_file() or sha256_file(archive) != bundle.get("source", {}).get("source_archive_sha256"):
            errors.append("source archive is missing or digest-mismatched")
        custody = bundle.get("payload_custody", [])
        expected_paths = {item.get("path") for item in custody if isinstance(item, dict)}
        actual_paths = {
            path.relative_to(directory).as_posix()
            for path in directory.rglob("*")
            if path.is_file() and path.name != "release-proof-bundle.json"
        }
        if expected_paths != actual_paths:
            errors.append("payload custody does not exactly cover bundle constituent files")
        for item in custody:
            if not isinstance(item, dict):
                continue
            try:
                payload = _safe_relative_file(directory, item.get("path", ""))
                if payload.stat().st_size != item.get("size") or sha256_file(payload) != item.get("sha256"):
                    errors.append(f"payload custody mismatch: {item.get('path')}")
            except ValueError as exc:
                errors.append(str(exc))
        if repo is not None:
            repo = repo.resolve()
            source = bundle.get("source", {})
            if _git(repo, "rev-parse", "HEAD") != source.get("commit"):
                errors.append("candidate commit does not match bundle")
            if _git(repo, "rev-parse", "HEAD^{tree}") != source.get("tree"):
                errors.append("candidate tree does not match bundle")
            if sha256_file(repo / "uv.lock") != source.get("uv_lock_sha256"):
                errors.append("candidate uv.lock does not match bundle")
    except (OSError, ValueError, KeyError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        errors.append(f"bundle validation failed: {exc}")
    return errors
