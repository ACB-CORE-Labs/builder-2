"""Frozen M1-v1 benchmark formulas, evidence schemas, and process measures."""

from __future__ import annotations

import hashlib
import json
import math
import platform
import re
import statistics
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

import psutil  # type: ignore[import-untyped]

MANIFEST_KIND = "builder_ii.model_runtime_benchmark_manifest"
REPORT_KIND = "builder_ii.model_runtime_benchmark_report"
SCHEMA_VERSION = 1
PROFILE = "m1-v1"
METHOD_CORRECTION_SHA256 = "13a7f09d2686c35d67227468e6be9883db81475bb287318686720c93e81d6453"
THRESHOLDS = {
    "default_local_model_footprint_min_bytes": 2 * 1024**3,
    "default_local_model_footprint_max_bytes": 7 * 1024**3,
    "control_plane_rss_max_bytes_exclusive": 1 * 1024**3,
    "idle_stratum_rss_max_bytes": 250 * 1024**2,
    "warm_ttft_overhead_max_percent": 20.0,
    "non_model_dispatch_p95_max_ms_exclusive": 150.0,
    "max_large_model_runtimes": 1,
}
METHODOLOGY = {
    "warm_ttft": {"discarded_warmups": 1, "paired_samples_min": 10,
                  "statistic": "median", "formula": "(governed-direct)/direct*100"},
    "non_model_dispatch": {"samples_min": 100, "statistics": ["p50", "p95", "max"],
                           "p95_method": "nearest_rank"},
    "local_model_memory": {
        "acceptance_metric": "macos_physical_footprint",
        "process_set": "validated model-server root and descendants",
        "aggregation": "macOS footprint de-duplicated total; maximum sampled value",
        "rss": "diagnostic only",
        "graphics_categories": "diagnostic subcomponents; never added to physical footprint",
        "method_correction_sha256": METHOD_CORRECTION_SHA256,
    },
    "control_plane": "Builder-II process tree excluding model server PID tree",
    "idle_stratum": "settled repeated RSS samples using maximum",
    "model_runtime_concurrency": "maximum Builder-II-managed large-model runtime count",
}


@dataclass(frozen=True)
class ModelMemorySample:
    physical_footprint_bytes: int
    rss_bytes: int
    graphics_memory_diagnostics: dict[str, int]
    measured_pids: tuple[int, ...]


_TOTAL_PATTERNS = (
    re.compile(r"^\s*(?:TOTAL|Physical footprint)\s*[:=]?\s*([0-9][0-9,]*)\s*(?:bytes)?\s*$", re.I | re.M),
    re.compile(r"^\s*([0-9][0-9,]*)\s+TOTAL\s*$", re.I | re.M),
)
_CATEGORY_NAMES = {
    "ioaccelerator": "ioaccelerator_bytes",
    "ioaccelerator (graphics)": "ioaccelerator_graphics_bytes",
    "owned physical footprint (unmapped) (graphics)": "owned_unmapped_graphics_bytes",
}


def parse_footprint_bytes(output: str) -> tuple[int, dict[str, int]]:
    """Parse macOS footprint byte output without adding category subledgers."""
    total: int | None = None
    for pattern in _TOTAL_PATTERNS:
        match = pattern.search(output)
        if match:
            total = int(match.group(1).replace(",", ""))
            break
    if total is None:
        raise ValueError("macOS footprint output did not contain a byte-valued total")
    diagnostics: dict[str, int] = {}
    for line in output.splitlines():
        normalized = " ".join(line.strip().split())
        for label, field in _CATEGORY_NAMES.items():
            if normalized.casefold().startswith(label.casefold()):
                numbers = re.findall(r"(?<![A-Za-z])[0-9][0-9,]*(?![A-Za-z])", normalized[len(label):])
                if numbers:
                    diagnostics[field] = int(numbers[-1].replace(",", ""))
    return total, diagnostics


def _validated_process_tree(pid: int, *, identity_check: Callable[[int], bool]) -> tuple[int, ...]:
    if not identity_check(pid):
        raise ValueError("model-server identity gate refused the root PID")
    try:
        root = psutil.Process(pid)
        create_time = root.create_time()
        children = root.children(recursive=True)
    except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
        raise ValueError("validated model-server PID is unavailable") from exc
    if not root.is_running() or root.create_time() != create_time or not identity_check(pid):
        raise ValueError("model-server PID exited, was reused, or changed identity")
    return (pid, *(child.pid for child in children if child.is_running()))


def collect_model_memory(
    pid: int,
    *,
    identity_check: Callable[[int], bool],
    footprint_binary: Path = Path("/usr/bin/footprint"),
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> ModelMemorySample:
    """Measure a validated MLX server tree using footprint process-set de-duplication."""
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise RuntimeError("M1-v1 model footprint requires Apple Silicon macOS")
    if not footprint_binary.is_file():
        raise FileNotFoundError(f"macOS footprint binary not found: {footprint_binary}")
    pids = _validated_process_tree(pid, identity_check=identity_check)
    argv: list[str] = [str(footprint_binary), "--format", "bytes", "--unmapped"]
    for process_pid in pids:
        argv.extend(("--pid", str(process_pid)))
    result = runner(argv, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"macOS footprint failed closed: {detail}")
    if not identity_check(pid):
        raise ValueError("model-server identity drifted during footprint collection")
    physical, graphics = parse_footprint_bytes(result.stdout)
    return ModelMemorySample(
        physical_footprint_bytes=physical,
        rss_bytes=rss_tree(pid),
        graphics_memory_diagnostics=graphics,
        measured_pids=pids,
    )


def peak_model_memory(samples: Sequence[ModelMemorySample]) -> dict[str, Any]:
    if not samples:
        raise ValueError("model memory sampling requires at least one sample")
    peak_index = max(range(len(samples)), key=lambda index: samples[index].physical_footprint_bytes)
    return {
        "model_memory_acceptance_metric": "macos_physical_footprint",
        "model_physical_footprint": {
            "baseline_bytes": samples[0].physical_footprint_bytes,
            "steady_warm_bytes": samples[-1].physical_footprint_bytes,
            "peak_bytes": samples[peak_index].physical_footprint_bytes,
            "acceptance_bytes": samples[peak_index].physical_footprint_bytes,
        },
        "model_rss_diagnostic": {
            "baseline_bytes": samples[0].rss_bytes,
            "steady_warm_bytes": samples[-1].rss_bytes,
            "peak_bytes": max(sample.rss_bytes for sample in samples),
            "acceptance": False,
        },
        "graphics_memory_diagnostics": samples[peak_index].graphics_memory_diagnostics,
    }


def _digest(value: dict[str, Any]) -> str:
    body = {k: v for k, v in value.items() if k not in {"digest", "manifest_digest", "report_digest"}}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def percentile(values: Iterable[float], percentile_value: float) -> float:
    ordered = sorted(float(v) for v in values)
    if not ordered:
        raise ValueError("percentile requires at least one sample")
    if not 0 <= percentile_value <= 100:
        raise ValueError("percentile must be between 0 and 100")
    rank = (len(ordered) - 1) * percentile_value / 100
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    fraction = rank - low
    return ordered[low] + (ordered[high] - ordered[low]) * fraction


def nearest_rank_percentile(values: Iterable[float], percentile_value: float) -> float:
    ordered = sorted(float(v) for v in values)
    if not ordered:
        raise ValueError("percentile requires at least one sample")
    if not 0 < percentile_value <= 100:
        raise ValueError("nearest-rank percentile must be greater than zero and at most 100")
    return ordered[math.ceil(percentile_value / 100 * len(ordered)) - 1]


def rss_tree(pid: int, *, exclude_pids: Iterable[int] = ()) -> int:
    excluded = set(exclude_pids)
    root = psutil.Process(pid)
    processes = [root, *root.children(recursive=True)]
    return sum(p.memory_info().rss for p in processes if p.pid not in excluded and p.is_running())


def build_manifest(*, git_commit: str, git_tree: str, backend: str, provider: str,
                   client: str, model: str, route_digest: str, policy_digest: str,
                   budget_digest: str) -> dict[str, Any]:
    content = {
        "kind": MANIFEST_KIND, "schema_version": SCHEMA_VERSION, "profile": PROFILE,
        "git_commit": git_commit, "git_tree": git_tree,
        "platform": platform.platform(), "architecture": platform.machine(),
        "chip": platform.processor() or platform.machine(),
        "physical_ram_bytes": psutil.virtual_memory().total, "os": platform.system(),
        "python": sys.version.split()[0], "builder_ii_version": "0.1.0",
        "backend": backend, "provider": provider, "client": client, "model": model,
        "route_digest": route_digest, "policy_digest": policy_digest, "budget_digest": budget_digest,
        "methodology": json.loads(json.dumps(METHODOLOGY)),
        "thresholds": dict(THRESHOLDS), "artifact_is_authority": False,
        "grants_authority": False, "promotes": False,
    }
    content["manifest_digest"] = _digest(content)
    return content


def build_report(*, manifest: dict[str, Any], samples: dict[str, Any]) -> dict[str, Any]:
    if manifest.get("kind") != MANIFEST_KIND or manifest.get("manifest_digest") != _digest(manifest):
        raise ValueError("invalid benchmark manifest")
    direct = [float(v) for v in samples.get("warm_ttft_direct_ms", [])]
    governed = [float(v) for v in samples.get("warm_ttft_governed_ms", [])]
    dispatch = [float(v) for v in samples.get("non_model_dispatch_ms", [])]
    if len(direct) < 10 or len(governed) < 10 or len(direct) != len(governed):
        raise ValueError("warm TTFT requires at least 10 paired samples")
    if len(dispatch) < 100:
        raise ValueError("non-model dispatch requires at least 100 samples")
    if samples.get("model_memory_acceptance_metric") != "macos_physical_footprint":
        raise ValueError("model footprint acceptance metric must be macos_physical_footprint")
    direct_median = statistics.median(direct)
    governed_median = statistics.median(governed)
    if direct_median <= 0:
        raise ValueError("direct warm TTFT median must be positive")
    overhead = (governed_median - direct_median) / direct_median * 100
    measured = {
        "model_footprint_bytes": int(samples["model_physical_footprint"]["acceptance_bytes"]),
        "model_memory_acceptance_metric": samples.get("model_memory_acceptance_metric"),
        "model_physical_footprint": samples["model_physical_footprint"],
        "model_rss_diagnostic": samples.get("model_rss_diagnostic"),
        "graphics_memory_diagnostics": samples.get("graphics_memory_diagnostics", {}),
        "control_plane_rss_bytes": int(samples["control_plane_rss_bytes"]),
        "idle_stratum_rss_bytes": int(samples["idle_stratum_rss_bytes"]),
        "warm_ttft_direct_ms": direct_median, "warm_ttft_governed_ms": governed_median,
        "warm_ttft_overhead_percent": overhead,
        "non_model_dispatch_p50_ms": nearest_rank_percentile(dispatch, 50),
        "non_model_dispatch_p95_ms": nearest_rank_percentile(dispatch, 95),
        "non_model_dispatch_max_ms": max(dispatch),
        "max_large_model_runtime_count": int(samples["max_large_model_runtime_count"]),
        "cold_ttft_ms": samples.get("cold_ttft_ms"), "warm_ttft_ms": samples.get("warm_ttft_ms"),
        "throughput_tokens_per_second": samples.get("throughput_tokens_per_second"),
        "memory_peak_bytes": samples.get("memory_peak_bytes"),
        "delegation_overhead_ms": samples.get("delegation_overhead_ms"),
        "interruption_latency_ms": samples.get("interruption_latency_ms"),
        "resume_latency_ms": samples.get("resume_latency_ms"),
        "governed_tool_latency_ms": samples.get("governed_tool_latency_ms"),
    }
    checks = {
        "model_footprint": THRESHOLDS["default_local_model_footprint_min_bytes"] <= measured["model_footprint_bytes"] <= THRESHOLDS["default_local_model_footprint_max_bytes"],
        "control_plane_rss": measured["control_plane_rss_bytes"] < THRESHOLDS["control_plane_rss_max_bytes_exclusive"],
        "idle_stratum_rss": measured["idle_stratum_rss_bytes"] <= THRESHOLDS["idle_stratum_rss_max_bytes"],
        "warm_ttft_overhead": overhead <= THRESHOLDS["warm_ttft_overhead_max_percent"],
        "non_model_dispatch_p95": measured["non_model_dispatch_p95_ms"] < THRESHOLDS["non_model_dispatch_p95_max_ms_exclusive"],
        "large_model_runtime_count": measured["max_large_model_runtime_count"] <= THRESHOLDS["max_large_model_runtimes"],
    }
    content = {"kind": REPORT_KIND, "schema_version": SCHEMA_VERSION,
               "manifest_digest": manifest["manifest_digest"], "measurements": measured,
               "hard_threshold_results": checks, "overall_state": "PASS" if all(checks.values()) else "FAIL",
               "raw_samples": samples, "artifact_is_authority": False,
               "grants_authority": False, "promotes": False}
    content["report_digest"] = _digest(content)
    return content


def validate_manifest(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["manifest must be an object"]
    errors = []
    if value.get("kind") != MANIFEST_KIND:
        errors.append(f"kind must be {MANIFEST_KIND}")
    if value.get("profile") != PROFILE:
        errors.append(f"profile must be {PROFILE}")
    if value.get("thresholds") != THRESHOLDS:
        errors.append("thresholds differ from frozen M1-v1 thresholds")
    if value.get("methodology") != METHODOLOGY:
        errors.append("methodology differs from frozen M1-v1 methodology")
    if (value.get("artifact_is_authority") is not False
            or value.get("grants_authority") is not False
            or value.get("promotes") is not False):
        errors.append("benchmark evidence cannot grant authority or promote")
    if value.get("manifest_digest") != _digest(value):
        errors.append("manifest digest mismatch")
    return errors


def validate_report(value: Any, *, manifest: dict[str, Any] | None = None) -> list[str]:
    if not isinstance(value, dict):
        return ["report must be an object"]
    errors = []
    if value.get("kind") != REPORT_KIND:
        errors.append(f"kind must be {REPORT_KIND}")
    if (value.get("artifact_is_authority") is not False
            or value.get("grants_authority") is not False
            or value.get("promotes") is not False):
        errors.append("benchmark evidence cannot grant authority or promote")
    if value.get("report_digest") != _digest(value):
        errors.append("report digest mismatch")
    checks = value.get("hard_threshold_results")
    if not isinstance(checks, dict) or value.get("overall_state") != ("PASS" if checks and all(checks.values()) else "FAIL"):
        errors.append("overall_state does not derive from hard threshold results")
    if manifest is not None and value.get("manifest_digest") != manifest.get("manifest_digest"):
        errors.append("report does not bind manifest")
    return errors


def write_json(value: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
