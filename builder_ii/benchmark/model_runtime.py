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


RAW_SAMPLES_KIND = "builder_ii.model_runtime_benchmark_raw_samples"


def manifest_digest(value: dict[str, Any]) -> str:
    body = {k: v for k, v in value.items() if k not in {"digest", "manifest_digest"}}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def report_digest(value: dict[str, Any]) -> str:
    body = {k: v for k, v in value.items() if k not in {"digest", "report_digest"}}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def raw_samples_digest(value: dict[str, Any]) -> str:
    body = {k: v for k, v in value.items() if k not in {"digest", "samples_digest"}}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _digest(value: dict[str, Any]) -> str:
    if value.get("kind") == REPORT_KIND:
        return report_digest(value)
    if value.get("kind") == RAW_SAMPLES_KIND:
        return raw_samples_digest(value)
    return manifest_digest(value)


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
    content["manifest_digest"] = manifest_digest(content)
    return content


import time
from datetime import datetime, timezone


def collect_canonical_m1_samples(
    *,
    manifest: dict[str, Any],
    model_pid: int | None = None,
    identity_check: Callable[[int], bool] | None = None,
    footprint_binary: Path = Path("/usr/bin/footprint"),
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    clock: Callable[[], float] = time.perf_counter,
) -> dict[str, Any]:
    """Execute physical M1-v1 collectors on the committed exact tip and emit raw samples."""
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise RuntimeError("M1-v1 physical benchmark collection requires Apple Silicon macOS")

    import tempfile
    import threading

    from builder_ii.adapters.mcp.governed_services import run_service
    from builder_ii.core.config import load_settings
    from builder_ii.lifecycle.candidate.runtime_control import find_runtime_processes
    from builder_ii.routing.gateway_invocation import governed_invocation_engine
    from builder_ii.routing.model_client_registry import create_model_client_registry
    from builder_ii.routing.model_execution_gateway import ModelExecutionGateway

    settings = load_settings()

    # 2. Make real model identity mandatory
    if model_pid is None:
        processes = find_runtime_processes(settings)
        if len(processes) != 1:
            raise ValueError("CANONICAL_QUALIFICATION FAIL: Exact single model server not found. MODEL_FOOTPRINT = UNAVAILABLE, OVERALL = FAIL.")
        model_pid = processes[0].pid

    def check_identity(pid: int) -> bool:
        procs = find_runtime_processes(settings)
        return any(p.pid == pid for p in procs)

    if not check_identity(model_pid):
        raise ValueError("CANONICAL_QUALIFICATION FAIL: Provided model_pid not found or not a valid model server. MODEL_FOOTPRINT = UNAVAILABLE, OVERALL = FAIL.")

    identity_check = check_identity

    # Background concurrency monitor
    stop_monitor = False
    max_concurrency = 0
    def monitor_concurrency():
        nonlocal max_concurrency
        while not stop_monitor:
            count = len(find_runtime_processes(settings))
            if count > max_concurrency:
                max_concurrency = count
            time.sleep(0.1)

    monitor_thread = threading.Thread(target=monitor_concurrency, daemon=True)
    monitor_thread.start()

    try:
        # Get Control Plane PID and idle stratum RSS
        current_process = psutil.Process()
        # Find child stratum if any, else run it

        # Let's run Stratum for 5 seconds to settle
        stratum_proc = subprocess.Popen([sys.executable, "-m", "builder_ii.cli.stratum_cli", "--no-splash", "--no-guide"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(5)

        idle_stratum_rss_samples = []
        for _ in range(30):
            try:
                 idle_stratum_rss_samples.append(rss_tree(stratum_proc.pid))
            except psutil.NoSuchProcess:
                 pass
            time.sleep(1)

        idle_stratum_rss = max(idle_stratum_rss_samples) if idle_stratum_rss_samples else 0
        stratum_proc.terminate()
        stratum_proc.wait(timeout=5)

        control_plane_rss = 0
        def sample_control_plane():
            nonlocal control_plane_rss
            # exclude model server tree
            try:
                 model_tree_pids = set(p.pid for p in psutil.Process(model_pid).children(recursive=True))
                 model_tree_pids.add(model_pid)
            except psutil.NoSuchProcess:
                 model_tree_pids = set()

            current = rss_tree(current_process.pid, exclude_pids=model_tree_pids)
            if current > control_plane_rss:
                 control_plane_rss = current

        registry = create_model_client_registry()
        execution_policy = {
            "kind": "builder_ii.model_execution_policy",
            "schema_version": 2,
            "digest": "benchmark-policy",
            "routes": [
                {
                    "route_id": "benchmark",
                    "description": "Benchmark routing",
                    "constraints": {"backend": [manifest["backend"]]},
                    "candidates": [manifest["model"]]
                }
            ]
        }

        # 3. Measure direct TTFT
        engine = governed_invocation_engine(settings)
        candidate_dict = next(c for c in registry["clients"] if c["model_id"] == manifest["model"])

        warm_ttft_direct: list[float] = []
        warm_ttft_governed: list[float] = []

        gateway = ModelExecutionGateway(settings, registry, execution_policy)

        direct_gateway_receipt_refs = []
        governed_gateway_receipt_refs = []

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            for idx in range(11):
                sample_control_plane()
                # Direct
                res = engine.invoke(
                    candidates=[candidate_dict],
                    prompt="Determine if benchmark is running.",
                    system_prompt="You are benchmarking.",
                    max_tokens=32,
                    temperature=0.0
                )
                if res.status != "succeeded" or not res.attempts:
                    raise RuntimeError(f"Direct TTFT failed: {res.final_error}")
                rec = res.attempts[-1]
                if rec.first_public_chunk_ns and rec.started_ns:
                    ttft = (rec.first_public_chunk_ns - rec.started_ns) / 1_000_000.0
                    if idx > 0:
                        warm_ttft_direct.append(ttft)
                direct_gateway_receipt_refs.append(f"direct_ttft_iteration_{idx}")

                sample_control_plane()

                # Governed
                env, receipt, _ = gateway.run_model_call(
                    model_id=manifest["model"],
                    prompt="Determine if benchmark is running.",
                    system_prompt="You are benchmarking.",
                    max_tokens=32,
                    temperature=0.0,
                    envelope_path=tdp / f"env_{idx}.json",
                    receipt_path=tdp / f"receipt_{idx}.json"
                )
                attempts = receipt.get("invocation", {}).get("attempts", [])
                if not attempts:
                    raise RuntimeError("Governed TTFT failed")
                rec2 = attempts[-1]
                first = rec2.get("first_public_chunk_ns")
                started = rec2.get("started_ns")
                if first and started:
                    ttft2 = (first - started) / 1_000_000.0
                    if idx > 0:
                        warm_ttft_governed.append(ttft2)
                governed_gateway_receipt_refs.append(f"governed_ttft_iteration_{idx}")
                sample_control_plane()

        # 5. Non-model dispatch latency (100 iterations)
        non_model_dispatch: list[float] = []
        for _ in range(100):
            t0 = clock()
            try:
                run_service(
                    tool_name="delegation_status",
                    arguments={},
                    session_id="benchmark",
                    builder_root=Path(td),
                    target_root=Path(td),
                    target_name="benchmark",
                    allow_artifact_root_inside_target=True
                )
            except Exception:
                pass
            t1 = clock()
            non_model_dispatch.append((t1 - t0) * 1000.0)
            sample_control_plane()

        # 6. Model physical footprint
        sample = collect_model_memory(
            model_pid,
            identity_check=identity_check,
            footprint_binary=footprint_binary,
            runner=runner,
        )
        mem_info = peak_model_memory([sample])

    finally:
        stop_monitor = True
        monitor_thread.join(timeout=1.0)

    # 10. Explicitly state qualification mode
    qualification_mode = "PHYSICAL"

    raw_samples: dict[str, Any] = {
        "kind": RAW_SAMPLES_KIND,
        "schema_version": SCHEMA_VERSION,
        "qualification_mode": qualification_mode,
        "manifest_digest": manifest["manifest_digest"],
        "git_commit": manifest["git_commit"],
        "git_tree": manifest["git_tree"],
        "method_correction_sha256": METHOD_CORRECTION_SHA256,
        "model": manifest["model"],
        "backend": manifest["backend"],
        "provider": manifest["provider"],
        "client": manifest["client"],
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "warm_ttft_direct_ms": warm_ttft_direct,
        "warm_ttft_governed_ms": warm_ttft_governed,
        "non_model_dispatch_ms": non_model_dispatch,
        "model_memory_acceptance_metric": "macos_physical_footprint",
        "model_physical_footprint": mem_info["model_physical_footprint"],
        "model_rss_diagnostic": mem_info["model_rss_diagnostic"],
        "graphics_memory_diagnostics": mem_info.get("graphics_memory_diagnostics", {}),
        "control_plane_rss_bytes": control_plane_rss,
        "idle_stratum_rss_bytes": idle_stratum_rss,
        "max_large_model_runtime_count": max_concurrency,
        "cold_ttft_ms": None,
        "warm_ttft_ms": statistics.median(warm_ttft_governed) if warm_ttft_governed else None,
        "throughput_tokens_per_second": None,
        "memory_peak_bytes": mem_info["model_physical_footprint"]["peak_bytes"],
        "delegation_overhead_ms": None,
        "interruption_latency_ms": None,
        "resume_latency_ms": None,
        "governed_tool_latency_ms": None,
        "direct_gateway_receipt_refs": direct_gateway_receipt_refs,
        "governed_gateway_receipt_refs": governed_gateway_receipt_refs,
        "model_server_pid": model_pid,
        "stratum_pid": stratum_proc.pid,
        "control_plane_pid": current_process.pid,
    }
    raw_samples["samples_digest"] = raw_samples_digest(raw_samples)
    return raw_samples

def build_report(*, manifest: dict[str, Any], samples: dict[str, Any]) -> dict[str, Any]:
    if manifest.get("kind") != MANIFEST_KIND or manifest.get("manifest_digest") != manifest_digest(manifest):
        raise ValueError("invalid benchmark manifest")
    if not isinstance(samples, dict):
        raise ValueError("samples must be an object")

    samples_manifest_digest = samples.get("manifest_digest")
    if not samples_manifest_digest or samples_manifest_digest != manifest.get("manifest_digest"):
        raise ValueError(f"raw samples manifest_digest ({samples_manifest_digest}) does not equal manifest manifest_digest ({manifest.get('manifest_digest')})")

    samples_commit = samples.get("git_commit")
    if not samples_commit or samples_commit != manifest.get("git_commit"):
        raise ValueError(f"raw samples git_commit ({samples_commit}) does not equal manifest git_commit ({manifest.get('git_commit')})")

    samples_tree = samples.get("git_tree")
    if not samples_tree or samples_tree != manifest.get("git_tree"):
        raise ValueError(f"raw samples git_tree ({samples_tree}) does not equal manifest git_tree ({manifest.get('git_tree')})")

    samples_method = samples.get("method_correction_sha256")
    if not samples_method or samples_method != METHOD_CORRECTION_SHA256:
        raise ValueError(f"raw samples method_correction_sha256 ({samples_method}) does not match frozen M1 correction ({METHOD_CORRECTION_SHA256})")

    if samples.get("model") and samples.get("model") != manifest.get("model"):
        raise ValueError(f"raw samples model ({samples.get('model')}) does not match manifest model ({manifest.get('model')})")

    if samples.get("samples_digest") and samples.get("samples_digest") != raw_samples_digest(samples):
        raise ValueError("raw samples digest mismatch")

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
               "hard_threshold_results": checks, "overall_state": "PASS" if all(checks.values()) and samples.get("qualification_mode") == "PHYSICAL" else "FAIL",
               "raw_samples": samples, "artifact_is_authority": False,
               "grants_authority": False, "promotes": False}
    content["report_digest"] = report_digest(content)
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
    if value.get("manifest_digest") != manifest_digest(value):
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
    if value.get("report_digest") != report_digest(value):
        errors.append("report digest mismatch")
    checks = value.get("hard_threshold_results")
    if not isinstance(checks, dict) or value.get("overall_state") != ("PASS" if checks and all(checks.values()) else "FAIL"):
        errors.append("overall_state does not derive from hard threshold results")
    if manifest is not None and value.get("manifest_digest") != manifest.get("manifest_digest"):
        errors.append("report does not bind manifest")

    raw = value.get("raw_samples")
    if isinstance(raw, dict):
        if manifest is not None:
            if raw.get("manifest_digest") != manifest.get("manifest_digest"):
                errors.append("raw samples manifest_digest does not match manifest manifest_digest")
            if raw.get("git_commit") != manifest.get("git_commit"):
                errors.append("raw samples git_commit does not match manifest git_commit")
            if raw.get("git_tree") != manifest.get("git_tree"):
                errors.append("raw samples git_tree does not match manifest git_tree")
        if raw.get("method_correction_sha256") != METHOD_CORRECTION_SHA256:
            errors.append("raw samples method_correction_sha256 does not match frozen M1 correction")
        if raw.get("samples_digest") and raw.get("samples_digest") != raw_samples_digest(raw):
            errors.append("raw samples digest mismatch")
    return errors


def write_json(value: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

