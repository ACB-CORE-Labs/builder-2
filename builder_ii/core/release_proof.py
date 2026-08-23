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
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, text=True, capture_output=True
    ).stdout.strip()


def _safe_files(directory: Path) -> list[Path]:
    if not directory.is_dir() or directory.is_symlink():
        raise ValueError(f"required directory is missing or symlinked: {directory}")
    files = sorted(path for path in directory.iterdir() if path.is_file())
    if any(path.is_symlink() for path in files):
        raise ValueError(f"symlinked evidence is forbidden: {directory}")
    return files


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


def build_release_proof_bundle_directory(
    *, repo: Path, dist_dir: Path, evidence_dir: Path, output_dir: Path
) -> Path:
    repo = repo.resolve()
    output_dir = output_dir.resolve()
    if _git(repo, "status", "--porcelain"):
        raise ValueError("candidate repository must be clean before release proof construction")
    if output_dir.exists():
        shutil.rmtree(output_dir)
    (output_dir / "evidence").mkdir(parents=True)
    (output_dir / "dist").mkdir()

    evidence_by_lane: dict[str, Path] = {}
    for source in _safe_files(evidence_dir.resolve()):
        if source.suffix != ".json":
            continue
        data = json.loads(source.read_text(encoding="utf-8"))
        errors = validate_release_evidence(data)
        if errors:
            raise ValueError(f"invalid release evidence {source}: {errors}")
        lane = data["lane"]
        if lane in evidence_by_lane:
            raise ValueError(f"duplicate release evidence lane: {lane}")
        target = output_dir / "evidence" / source.name
        shutil.copyfile(source, target)
        evidence_by_lane[lane] = target
    missing = sorted(set(REQUIRED_RELEASE_LANES) - set(evidence_by_lane))
    if missing:
        raise ValueError(f"missing release evidence lanes: {', '.join(missing)}")

    distributions: list[dict[str, Any]] = []
    for source in _safe_files(dist_dir.resolve()):
        if source.suffix != ".whl" and not source.name.endswith(".tar.gz"):
            continue
        target = output_dir / "dist" / source.name
        shutil.copyfile(source, target)
        distributions.append(_distribution_record(target))

    archive_path = output_dir / "source.tar"
    archive_path.write_bytes(subprocess.run(["git", "-C", str(repo), "archive", "HEAD"], check=True, capture_output=True).stdout)

    index = create_artifact_index_record(output_dir / "evidence")
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
        for record in bundle.get("distributions", []):
            path = directory / "dist" / record.get("filename", "")
            if path.is_symlink() or not path.is_file():
                errors.append(f"distribution missing or symlinked: {path}")
            elif sha256_file(path) != record.get("sha256"):
                errors.append(f"distribution digest mismatch: {path.name}")
        for lane, record in bundle.get("evidence", {}).items():
            ref = record.get("ref", {})
            path = directory / ref.get("path", "")
            if path.is_symlink() or not path.is_file():
                errors.append(f"evidence missing or symlinked: {lane}")
                continue
            if canonical_json_sha256(path) != ref.get("sha256"):
                errors.append(f"evidence digest mismatch: {lane}")
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("lane") != lane or data.get("result") != "PASS":
                errors.append(f"evidence lane/result mismatch: {lane}")
            errors.extend(f"{lane}: {error}" for error in validate_release_evidence(data))
        index_path = directory / bundle.get("artifact_index_ref", {}).get("path", "")
        if not index_path.is_file() or canonical_json_sha256(index_path) != bundle.get("artifact_index_ref", {}).get("sha256"):
            errors.append("artifact index is missing or digest-mismatched")
        else:
            errors.extend(validate_artifact_index_record(json.loads(index_path.read_text(encoding="utf-8"))))
        archive = directory / "source.tar"
        if not archive.is_file() or sha256_file(archive) != bundle.get("source", {}).get("source_archive_sha256"):
            errors.append("source archive is missing or digest-mismatched")
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
