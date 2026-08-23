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
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

import psutil  # type: ignore[import-untyped]

MANIFEST_KIND = "builder_ii.model_runtime_benchmark_manifest"
REPORT_KIND = "builder_ii.model_runtime_benchmark_report"
SCHEMA_VERSION = 1
PROFILE = "m1-v1"
METHOD_CORRECTION_SHA256 = "d2fbb444504f70f890f2fcc00451669880db98d2d76ed15936e006bb0276f0a5"
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
    "warm_ttft": {
        "discarded_warmups": 1,
        "paired_samples_min": 10,
        "statistic": "median",
        "formula": "(governed-direct)/direct*100",
    },
    "non_model_dispatch": {"samples_min": 100, "statistics": ["p50", "p95", "max"], "p95_method": "nearest_rank"},
    "local_model_memory": {
        "acceptance_metric": "macos_physical_footprint",
        "process_set": "validated model-server root and descendants",
        "aggregation": "macOS footprint de-duplicated total; maximum sampled value",
        "native_stdout_evidence": "persisted and SHA-256-bound for every sample",
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
    footprint_evidence_ref: dict[str, Any] | None = None


_TOTAL_PATTERNS = (
    re.compile(r"^\s*(?:TOTAL|Physical footprint)\s*[:=]?\s*([0-9][0-9,]*)\s*(?:bytes)?\s*$", re.I | re.M),
    re.compile(r"^\s*([0-9][0-9,]*)\s+TOTAL\s*$", re.I | re.M),
    re.compile(
        r"^\s*([0-9][0-9,]*)\s+B\s+[0-9][0-9,]*\s+B\s+[0-9][0-9,]*\s+B\s+[0-9][0-9,]*\s+TOTAL\s*$",
        re.I | re.M,
    ),
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
            if normalized.casefold().endswith(label.casefold()):
                numbers = re.findall(r"(?<![A-Za-z])[0-9][0-9,]*(?![A-Za-z])", normalized[: -len(label)])
                if numbers:
                    diagnostics[field] = int(numbers[0].replace(",", ""))
            elif normalized.casefold().startswith(label.casefold()):
                numbers = re.findall(r"(?<![A-Za-z])[0-9][0-9,]*(?![A-Za-z])", normalized[len(label) :])
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
    evidence_path: Path | None = None,
) -> ModelMemorySample:
    """Measure a validated MLX server tree using footprint process-set de-duplication."""
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise RuntimeError("M1-v1 model footprint requires Apple Silicon macOS")
    if footprint_binary != Path("/usr/bin/footprint"):
        raise ValueError("M1-v1 qualification permits only /usr/bin/footprint")
    if not footprint_binary.is_file():
        raise FileNotFoundError(f"macOS footprint binary not found: {footprint_binary}")
    pids = _validated_process_tree(pid, identity_check=identity_check)
    argv: list[str] = ["sudo", str(footprint_binary), "--format", "bytes", "--unmapped"]
    for process_pid in pids:
        argv.extend(("--pid", str(process_pid)))
    # sudo inherits the terminal. Python never requests, reads, pipes, or stores a
    # credential; authentication occurs only in sudo's native visible prompt.
    result = runner(argv, stdout=subprocess.PIPE, text=True, check=False, shell=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"macOS footprint failed closed: {detail}")
    if not identity_check(pid):
        raise ValueError("model-server identity drifted during footprint collection")
    evidence_ref: dict[str, Any] | None = None
    if evidence_path is not None:
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(result.stdout, encoding="utf-8")
        evidence_ref = {
            "path": str(evidence_path),
            "sha256": hashlib.sha256(evidence_path.read_bytes()).hexdigest(),
            "role": "macos_footprint_stdout",
            "required": True,
        }
    physical, graphics = parse_footprint_bytes(result.stdout)
    return ModelMemorySample(
        physical_footprint_bytes=physical,
        rss_bytes=rss_tree(pid),
        graphics_memory_diagnostics=graphics,
        measured_pids=pids,
        footprint_evidence_ref=evidence_ref,
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
    try:
        root = psutil.Process(pid)
        if not root.is_running() or root.status() == psutil.STATUS_ZOMBIE:
            raise ValueError(f"RSS root process is not live: pid={pid}")
        processes = [root, *root.children(recursive=True)]
    except (psutil.NoSuchProcess, psutil.ZombieProcess) as exc:
        raise ValueError(f"RSS root process is unavailable: pid={pid}") from exc

    total = 0
    for process in processes:
        if process.pid in excluded:
            continue
        try:
            if not process.is_running() or process.status() == psutil.STATUS_ZOMBIE:
                continue
            total += process.memory_info().rss
        except (psutil.NoSuchProcess, psutil.ZombieProcess):
            # A recursively discovered child may exit between enumeration and
            # sampling. It contributes no live RSS; root loss still fails above.
            continue
    return total


def build_manifest(
    *,
    git_commit: str,
    git_tree: str,
    backend: str,
    provider: str,
    client: str,
    model: str,
    route_digest: str,
    policy_digest: str,
    budget_digest: str,
) -> dict[str, Any]:
    content = {
        "kind": MANIFEST_KIND,
        "schema_version": SCHEMA_VERSION,
        "profile": PROFILE,
        "git_commit": git_commit,
        "git_tree": git_tree,
        "platform": platform.platform(),
        "architecture": platform.machine(),
        "chip": platform.processor() or platform.machine(),
        "physical_ram_bytes": psutil.virtual_memory().total,
        "os": platform.system(),
        "python": sys.version.split()[0],
        "builder_ii_version": "0.1.0",
        "backend": backend,
        "provider": provider,
        "client": client,
        "model": model,
        "route_digest": route_digest,
        "policy_digest": policy_digest,
        "budget_digest": budget_digest,
        "methodology": json.loads(json.dumps(METHODOLOGY)),
        "thresholds": dict(THRESHOLDS),
        "artifact_is_authority": False,
        "grants_authority": False,
        "promotes": False,
    }
    content["manifest_digest"] = manifest_digest(content)
    return content

def collect_canonical_m1_samples(
    *,
    manifest: dict[str, Any],
    output_dir: Path = Path(".builder/benchmark"),
    route: Any = None,
    route_sources: dict[str, Any] | None = None,
    obligations: Sequence[dict[str, Any]] | None = None,
    model_pid: int | None = None,
    identity_check: Callable[[int], bool] | None = None,
    footprint_binary: Path = Path("/usr/bin/footprint"),
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    clock: Callable[[], float] = time.perf_counter,
) -> dict[str, Any]:
    """Execute physical M1-v1 collectors on the committed exact tip and emit raw samples."""
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise RuntimeError("M1-v1 physical benchmark collection requires Apple Silicon macOS")

    import threading

    from builder_ii.adapters.mcp.governed_services import run_service
    from builder_ii.core.config import load_settings
    from builder_ii.core.orchestration_obligation import validate_orchestration_obligation
    from builder_ii.lifecycle.candidate.runtime_control import find_runtime_processes
    from builder_ii.routing.gateway_invocation import governed_invocation_engine
    from builder_ii.routing.model_execution_gateway import ModelExecutionGateway
    from builder_ii.routing.model_route_binding import advance_route_budget

    settings = load_settings()

    # 2. Make real model identity mandatory
    if model_pid is None:
        processes = find_runtime_processes(settings)
        if len(processes) != 1:
            raise ValueError(
                "CANONICAL_QUALIFICATION FAIL: Exact single model server not found. MODEL_FOOTPRINT = UNAVAILABLE, OVERALL = FAIL."
            )
        model_pid = processes[0].pid

    def check_identity(pid: int) -> bool:
        procs = find_runtime_processes(settings)
        return any(p.pid == pid for p in procs)

    if not check_identity(model_pid):
        raise ValueError(
            "CANONICAL_QUALIFICATION FAIL: Provided model_pid not found or not a valid model server. MODEL_FOOTPRINT = UNAVAILABLE, OVERALL = FAIL."
        )

    identity_check = check_identity
    if route is None or not isinstance(route_sources, dict):
        raise ValueError("canonical qualification requires a prevalidated WRP route and source artifacts")
    if not isinstance(obligations, Sequence) or len(obligations) != 2:
        raise ValueError("canonical qualification requires exactly two Deep Agents obligations")
    obligation_errors = [
        f"obligation[{index}]: {error}"
        for index, obligation in enumerate(obligations)
        for error in validate_orchestration_obligation(obligation)
    ]
    if obligation_errors:
        raise ValueError("invalid Deep Agents obligations: " + "; ".join(obligation_errors))
    if any(obligation.get("lane") != "deepagents" for obligation in obligations):
        raise ValueError("both benchmark obligations must bind the deepagents lane")
    if len({str(obligation.get("obligation_id")) for obligation in obligations}) != 2:
        raise ValueError("benchmark obligations must have distinct obligation_id values")

    # Background concurrency monitor
    stop_monitor = False
    max_concurrency = 0
    process_observations: list[dict[str, Any]] = []
    monitor_phase = "pre_workload"

    def monitor_concurrency():
        nonlocal max_concurrency
        while not stop_monitor:
            processes = find_runtime_processes(settings)
            roots = sorted({int(process.pid) for process in processes})
            count = len(roots)
            process_observations.append({"phase": monitor_phase, "validated_root_pids": roots})
            if count > max_concurrency:
                max_concurrency = count
            time.sleep(0.1)

    monitor_thread = threading.Thread(target=monitor_concurrency, daemon=True)
    monitor_thread.start()
    stratum_proc: subprocess.Popen[bytes] | None = None

    try:
        # Get Control Plane PID and idle stratum RSS
        current_process = psutil.Process()
        # Find child stratum if any, else run it

        # Five explicit one-second settle cycles, each with a liveness assertion.
        stratum_proc = subprocess.Popen(
            [sys.executable, "-m", "builder_ii.cli.stratum_cli", "--no-splash", "--no-guide"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for _ in range(5):
            time.sleep(1)
            if stratum_proc.poll() is not None:
                raise RuntimeError("STRATUM exited before its five settle cycles; idle RSS is UNAVAILABLE")
        idle_stratum_rss_samples = []
        for _ in range(30):
            if stratum_proc.poll() is not None:
                raise RuntimeError("STRATUM exited before 30 settled samples; idle RSS is UNAVAILABLE")
            idle_stratum_rss_samples.append(rss_tree(stratum_proc.pid))
            time.sleep(1)
        if len(idle_stratum_rss_samples) != 30:
            raise RuntimeError("STRATUM did not produce exactly 30 settled samples")
        idle_stratum_rss = max(idle_stratum_rss_samples)
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

        registry = dict(route_sources["registry"])
        execution_policy = dict(route_sources["execution_policy"])
        budget_direct = dict(route_sources["budget"])
        budget_governed = dict(route_sources["budget"])

        footprint_dir = output_dir / "footprint-evidence"
        footprint_sample_index = 0

        def sample_model_memory() -> ModelMemorySample:
            nonlocal footprint_sample_index
            evidence_path = footprint_dir / f"sample-{footprint_sample_index:02d}.txt"
            footprint_sample_index += 1
            return collect_model_memory(
                model_pid,
                identity_check=identity_check,
                footprint_binary=footprint_binary,
                runner=runner,
                evidence_path=evidence_path,
            )

        # 3. Measure direct TTFT
        warm_ttft_direct: list[float] = []
        warm_ttft_governed: list[float] = []

        memory_samples: list[ModelMemorySample] = [sample_model_memory()]
        gateway = ModelExecutionGateway(
            settings,
            registry,
            execution_policy,
            invocation_engine=governed_invocation_engine(settings),
        )
        memory_samples.append(sample_model_memory())

        direct_gateway_receipt_refs = []
        governed_gateway_receipt_refs = []
        ttft_pair_order: list[list[str]] = []
        direct_route = route
        governed_route = route

        evidence_dir = output_dir / "model-call-evidence"
        direct_dir = evidence_dir / "direct"
        governed_dir = evidence_dir / "governed"
        direct_dir.mkdir(parents=True, exist_ok=True)
        governed_dir.mkdir(parents=True, exist_ok=True)

        def evidence_ref(path: Path, *, role: str) -> dict[str, Any]:
            data = json.loads(path.read_text(encoding="utf-8"))
            return {
                "kind": data.get("kind"),
                "path": str(path),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "role": role,
                "required": True,
            }

        def measure_direct(idx: int) -> None:
            nonlocal budget_direct, direct_route
            sample_control_plane()
            direct_env = direct_dir / f"envelope-{idx:02d}.json"
            direct_receipt = direct_dir / f"receipt-{idx:02d}.json"
            direct_budget = direct_dir / f"budget-{idx:02d}.json"
            _env, receipt, debited = gateway.run_routed_model_call(
                route=direct_route,
                prompt="Determine if benchmark is running.",
                system_prompt="You are benchmarking.",
                budget=budget_direct,
                envelope_path=direct_env,
                receipt_path=direct_receipt,
                budget_path=direct_budget,
            )
            attempts = receipt.get("attempt_history") or []
            if receipt.get("status") != "succeeded" or not attempts or debited is None:
                raise RuntimeError("direct gateway TTFT evidence is unavailable")
            rec = attempts[-1]
            first, started = rec.get("first_public_chunk_ns"), rec.get("started_ns")
            if not isinstance(first, int) or not isinstance(started, int) or first < started:
                raise RuntimeError("direct gateway TTFT timestamps are unavailable")
            if idx > 0:
                warm_ttft_direct.append((first - started) / 1_000_000.0)
            direct_gateway_receipt_refs.append(evidence_ref(direct_receipt, role="direct_gateway_receipt"))
            budget_direct = debited
            direct_route = advance_route_budget(direct_route, budget_direct)

        def measure_governed(idx: int) -> None:
            nonlocal budget_governed, governed_route
            sample_control_plane()
            governed_sources = {**route_sources, "budget": budget_governed}
            node = {
                "payload": {
                    "route_sources": governed_sources,
                    "model_id": manifest["model"],
                    "prompt": "Determine if benchmark is running.",
                    "system_prompt": "You are benchmarking.",
                }
            }
            from builder_ii.wrp.gateway_nodes import _invoke_local_model_gateway

            governed_result = _invoke_local_model_gateway(
                node_id=f"benchmark-{idx:02d}",
                spec=node,
                plan_digest=manifest["manifest_digest"],
                approved_by="plan-set-5",
                msda_decision={"digest": manifest["manifest_digest"]},
                artifact_dir=governed_dir,
                prevalidated_gateway=gateway,
                prevalidated_route=governed_route,
            )
            receipt_path = governed_dir / manifest["manifest_digest"][:16] / f"benchmark-{idx:02d}" / "receipt.json"
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            attempts = receipt.get("attempt_history") or []
            if receipt.get("status") != "succeeded" or not attempts:
                raise RuntimeError("governed WRP TTFT evidence is unavailable")
            rec2 = attempts[-1]
            first = rec2.get("first_public_chunk_ns")
            started = rec2.get("started_ns")
            if not isinstance(first, int) or not isinstance(started, int) or first < started:
                raise RuntimeError("governed WRP TTFT timestamps are unavailable")
            if idx > 0:
                warm_ttft_governed.append((first - started) / 1_000_000.0)
            governed_gateway_receipt_refs.append(evidence_ref(receipt_path, role="governed_gateway_receipt"))
            debited_path = Path(str(governed_result["debited_budget_path"]))
            budget_governed = json.loads(debited_path.read_text(encoding="utf-8"))
            governed_route = advance_route_budget(governed_route, budget_governed)
            sample_control_plane()
            memory_samples.append(sample_model_memory())

        for idx in range(11):
            order = ["direct", "governed"] if idx % 2 == 0 else ["governed", "direct"]
            ttft_pair_order.append(order)
            for arm in order:
                (measure_direct if arm == "direct" else measure_governed)(idx)

        # 4. Execute the frozen two-worker Deep Agents + Goose shared-gateway workload.
        import httpx

        from builder_ii.adapters.deepagents.native_artifacts import validate_native_evidence_bundle
        from builder_ii.adapters.deepagents.native_runtime import NativeDeepAgentsRuntime, NativeRuntimeLimits
        from builder_ii.adapters.goose.model_gateway_adapter import (
            GooseGatewayContext,
            GooseModelGatewayAdapter,
            generate_loopback_credential,
        )

        monitor_phase = "deepagents"
        workload_dir = output_dir / "combined-runtime-evidence"
        native_dir = workload_dir / "deepagents"

        native = NativeDeepAgentsRuntime(
            gateway=gateway,
            route=governed_route,
            budget=budget_governed,
            obligations=obligations,
            output_dir=native_dir,
            session_id=f"{route.session_id}-benchmark-deepagents",
            authority_refs=[
                evidence_ref(Path(path), role=f"route_source_{name}")
                for name, path in route_sources.get("source_paths", {}).items()
            ],
            limits=NativeRuntimeLimits(active_workers=2, max_model_calls=16, max_tool_calls=16),
        )
        native_evidence = native.start(
            "Stage 1 only: delegate and complete both frozen obligations through the task tool. "
            "Do not call the governed echo or request HITL until both task results are available."
        )
        native_errors = validate_native_evidence_bundle(native_evidence)
        if native_errors or native_evidence.get("active_workers") != 2:
            raise RuntimeError("Deep Agents workload evidence failed: " + "; ".join(native_errors))
        if native_evidence.get("completed_task_count") != 2 or not all(
            item.get("delegated") and item.get("completed") for item in native_evidence.get("parent_child_chain", [])
        ):
            raise RuntimeError("Deep Agents workload did not complete exactly two obligations before HITL")
        native_evidence_path = native_dir / "native-deepagents-evidence.json"

        monitor_phase = "goose"
        goose_dir = workload_dir / "goose"
        goose_context = GooseGatewayContext(
            gateway=gateway,
            route=native.model.route,
            budget=native.model.budget,
            artifact_dir=goose_dir,
            local_credential=generate_loopback_credential(native.model.route.route_digest),
            close_gateway_on_close=False,
        )
        goose_pre_budget_digest = str(goose_context.budget.get("digest"))
        goose = GooseModelGatewayAdapter(goose_context)
        goose.start()
        try:
            response = httpx.post(
                goose.base_url + "/v1/chat/completions",
                headers={"Authorization": f"Bearer {goose_context.local_credential}"},
                json={
                    "model": goose_context.route.selected_candidate.model_id,
                    "messages": [{"role": "user", "content": "Prove gateway reuse."}],
                },
                timeout=120.0,
            )
            if response.status_code != 200:
                raise RuntimeError(f"Goose loopback traversal failed: HTTP {response.status_code}")
        finally:
            goose.close()
        goose_receipts = sorted(goose_dir.glob("*-receipt.json"))
        if len(goose_receipts) != 1:
            raise RuntimeError("Goose loopback must emit exactly one model receipt")
        goose_receipt = json.loads(goose_receipts[0].read_text(encoding="utf-8"))
        if goose_receipt.get("status") != "succeeded":
            raise RuntimeError("Goose loopback model receipt did not succeed")
        if goose_receipt.get("route_digest") != native.model.route.route_digest:
            raise RuntimeError("Goose and Deep Agents route lineage differ")
        memory_samples.append(sample_model_memory())
        monitor_phase = "post_workload"
        # 5. Non-model dispatch latency (100 iterations)
        non_model_dispatch: list[float] = []
        dispatch_receipt_refs: list[dict[str, Any]] = []
        dispatch_event_refs: list[dict[str, Any]] = []
        dispatch_dir = output_dir / "dispatch-evidence"
        dispatch_dir.mkdir(parents=True, exist_ok=True)
        for index in range(100):
            t0 = clock()
            receipt, receipt_path, event_path = run_service(
                tool_name="git_status",
                arguments={},
                session_id=f"benchmark-{index:03d}",
                builder_root=output_dir,
                target_root=Path.cwd(),
                target_name="builder",
                allow_artifact_root_inside_target=False,
            )
            if (
                not isinstance(receipt, dict)
                or receipt.get("status") != "succeeded"
                or receipt_path is None
                or event_path is None
            ):
                raise RuntimeError("admitted non-model dispatch did not succeed")
            t1 = clock()
            non_model_dispatch.append((t1 - t0) * 1000.0)
            dispatch_receipt_refs.append(evidence_ref(receipt_path, role="dispatch_receipt"))
            dispatch_event_refs.append(evidence_ref(event_path, role="dispatch_event"))
            sample_control_plane()

        mem_info = peak_model_memory(memory_samples)
        workload_observations = [item for item in process_observations if item["phase"] in {"deepagents", "goose"}]
        if not workload_observations or any(
            item["validated_root_pids"] != [model_pid] for item in workload_observations
        ):
            raise RuntimeError("combined workload model-server identity is missing, ambiguous, or changed")
        max_concurrency = max(len(item["validated_root_pids"]) for item in workload_observations)

    finally:
        stop_monitor = True
        monitor_thread.join(timeout=1.0)
        if "gateway" in locals():
            gateway.close()
        if stratum_proc is not None and stratum_proc.poll() is None:
            stratum_proc.terminate()
            stratum_proc.wait(timeout=5)

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
        "ttft_pair_order": ttft_pair_order,
        "non_model_dispatch_ms": non_model_dispatch,
        "model_memory_acceptance_metric": "macos_physical_footprint",
        "model_physical_footprint": mem_info["model_physical_footprint"],
        "model_rss_diagnostic": mem_info["model_rss_diagnostic"],
        "graphics_memory_diagnostics": mem_info.get("graphics_memory_diagnostics", {}),
        "control_plane_rss_bytes": control_plane_rss,
        "idle_stratum_rss_bytes": idle_stratum_rss,
        "idle_stratum_rss_samples": idle_stratum_rss_samples,
        "max_large_model_runtime_count": max_concurrency,
        "process_monitor_coverage": ["deepagents", "goose"],
        "model_process_observations": process_observations,
        "deepagents_evidence_ref": evidence_ref(native_evidence_path, role="deepagents_workload"),
        "goose_receipt_ref": evidence_ref(goose_receipts[0], role="goose_loopback_receipt"),
        "combined_runtime": {
            "deepagents_workload_executed": True,
            "active_workers": 2,
            "validated_obligations": 2,
            "goose_loopback_traversed": True,
            "gateway_instance_count": 1,
            "route_lineage_match": goose_receipt.get("route_digest") == native.model.route.route_digest,
            "route_lineage_root": manifest["route_digest"],
            "goose_route_digest": goose_receipt.get("route_digest"),
            "budget_lineage_match": (goose_receipt.get("budget_ref") or {}).get("pre_debit_sha256")
            == goose_pre_budget_digest,
            "model_server_identity_match": all(
                item["validated_root_pids"] == [model_pid] for item in workload_observations
            ),
        },
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
        "dispatch_receipt_refs": dispatch_receipt_refs,
        "dispatch_event_refs": dispatch_event_refs,
        "model_memory_samples": [
            {
                "phase": "baseline"
                if index == 0
                else ("load" if index == 1 else ("warm" if index == 2 else "inference")),
                "physical_footprint_bytes": sample.physical_footprint_bytes,
                "rss_bytes": sample.rss_bytes,
                "graphics_memory_diagnostics": sample.graphics_memory_diagnostics,
                "measured_pids": list(sample.measured_pids),
                "footprint_evidence_ref": sample.footprint_evidence_ref,
            }
            for index, sample in enumerate(memory_samples)
        ],
        "model_server_pid": model_pid,
        "stratum_pid": stratum_proc.pid if stratum_proc is not None else None,
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
        raise ValueError(
            f"raw samples manifest_digest ({samples_manifest_digest}) does not equal manifest manifest_digest ({manifest.get('manifest_digest')})"
        )

    samples_commit = samples.get("git_commit")
    if not samples_commit or samples_commit != manifest.get("git_commit"):
        raise ValueError(
            f"raw samples git_commit ({samples_commit}) does not equal manifest git_commit ({manifest.get('git_commit')})"
        )

    samples_tree = samples.get("git_tree")
    if not samples_tree or samples_tree != manifest.get("git_tree"):
        raise ValueError(
            f"raw samples git_tree ({samples_tree}) does not equal manifest git_tree ({manifest.get('git_tree')})"
        )

    samples_method = samples.get("method_correction_sha256")
    if not samples_method or samples_method != METHOD_CORRECTION_SHA256:
        raise ValueError(
            f"raw samples method_correction_sha256 ({samples_method}) does not match frozen M1 correction ({METHOD_CORRECTION_SHA256})"
        )

    if samples.get("model") and samples.get("model") != manifest.get("model"):
        raise ValueError(
            f"raw samples model ({samples.get('model')}) does not match manifest model ({manifest.get('model')})"
        )

    if not samples.get("samples_digest"):
        raise ValueError("qualifying raw samples require samples_digest")
    if samples.get("samples_digest") != raw_samples_digest(samples):
        raise ValueError("raw samples digest mismatch")

    def verify_ref(ref: Any, *, label: str) -> Path:
        if not isinstance(ref, dict) or ref.get("required") is not True:
            raise ValueError(f"{label} is required")
        path = Path(str(ref.get("path") or ""))
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"{label} is missing or substituted")
        if hashlib.sha256(path.read_bytes()).hexdigest() != ref.get("sha256"):
            raise ValueError(f"{label} digest mismatch")
        return path

    def load_ref(ref: Any, *, label: str) -> dict[str, Any]:
        path = verify_ref(ref, label=label)
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError(f"{label} must reference an object")
        return value

    def load_required_ref(field: str) -> dict[str, Any]:
        return load_ref(samples.get(field), label=field)

    for field, minimum in (
        ("direct_gateway_receipt_refs", 11),
        ("governed_gateway_receipt_refs", 11),
        ("dispatch_receipt_refs", 100),
        ("dispatch_event_refs", 100),
    ):
        refs = samples.get(field)
        if not isinstance(refs, list) or len(refs) < minimum:
            raise ValueError(f"{field} requires at least {minimum} durable references")
        for index, ref in enumerate(refs):
            evidence = load_ref(ref, label=f"{field}[{index}]")
            if field != "dispatch_event_refs" and evidence.get("status") != "succeeded":
                raise ValueError(f"{field}[{index}] does not prove a successful operation")

    combined = samples.get("combined_runtime")
    required_combined = {
        "deepagents_workload_executed": True,
        "active_workers": 2,
        "validated_obligations": 2,
        "goose_loopback_traversed": True,
        "gateway_instance_count": 1,
        "route_lineage_match": True,
        "budget_lineage_match": True,
        "model_server_identity_match": True,
    }
    if not isinstance(combined, dict) or any(combined.get(key) != value for key, value in required_combined.items()):
        raise ValueError("combined Deep Agents and Goose workload evidence is incomplete")
    from builder_ii.adapters.deepagents.native_artifacts import validate_native_evidence_bundle

    native_evidence = load_required_ref("deepagents_evidence_ref")
    native_errors = validate_native_evidence_bundle(native_evidence)
    if native_errors or native_evidence.get("active_workers") != 2 or native_evidence.get("completed_task_count") != 2:
        raise ValueError("invalid Deep Agents workload evidence: " + "; ".join(native_errors))
    goose_receipt = load_required_ref("goose_receipt_ref")
    if goose_receipt.get("status") != "succeeded":
        raise ValueError("invalid Goose loopback evidence")
    if combined.get("route_lineage_root") != manifest.get("route_digest") or combined.get(
        "goose_route_digest"
    ) != goose_receipt.get("route_digest"):
        raise ValueError("Goose route evidence does not bind the frozen route lineage")
    observations = samples.get("model_process_observations")
    if samples.get("process_monitor_coverage") != ["deepagents", "goose"] or not isinstance(observations, list):
        raise ValueError("process monitor did not span the combined workload")
    workload_observations = [
        item for item in observations if isinstance(item, dict) and item.get("phase") in {"deepagents", "goose"}
    ]
    expected_pid = samples.get("model_server_pid")
    if not workload_observations or any(
        item.get("validated_root_pids") != [expected_pid] for item in workload_observations
    ):
        raise ValueError("combined workload model-server identity is absent or ambiguous")
    memory_samples = samples.get("model_memory_samples")
    phases = [item.get("phase") for item in memory_samples] if isinstance(memory_samples, list) else []
    if not {"baseline", "load", "warm", "inference"}.issubset(phases) or phases.count("inference") < 1:
        raise ValueError("memory sampling must cover baseline, load, warm, and inference")
    for index, sample in enumerate(memory_samples):
        if not isinstance(sample, dict):
            raise ValueError(f"model_memory_samples[{index}] must be an object")
        footprint_path = verify_ref(
            sample.get("footprint_evidence_ref"), label=f"model_memory_samples[{index}].footprint_evidence_ref"
        )
        parsed_bytes, _diagnostics = parse_footprint_bytes(footprint_path.read_text(encoding="utf-8"))
        if parsed_bytes != sample.get("physical_footprint_bytes"):
            raise ValueError(f"model_memory_samples[{index}] does not match its footprint evidence")
    schedule = samples.get("ttft_pair_order")
    if (
        not isinstance(schedule, list)
        or len(schedule) < 11
        or any(
            pair != (["direct", "governed"] if index % 2 == 0 else ["governed", "direct"])
            for index, pair in enumerate(schedule)
        )
    ):
        raise ValueError("TTFT pairs must alternate direct/governed order")

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
        "warm_ttft_direct_ms": direct_median,
        "warm_ttft_governed_ms": governed_median,
        "warm_ttft_overhead_percent": overhead,
        "non_model_dispatch_p50_ms": nearest_rank_percentile(dispatch, 50),
        "non_model_dispatch_p95_ms": nearest_rank_percentile(dispatch, 95),
        "non_model_dispatch_max_ms": max(dispatch),
        "max_large_model_runtime_count": int(samples["max_large_model_runtime_count"]),
        "cold_ttft_ms": samples.get("cold_ttft_ms"),
        "warm_ttft_ms": samples.get("warm_ttft_ms"),
        "throughput_tokens_per_second": samples.get("throughput_tokens_per_second"),
        "memory_peak_bytes": samples.get("memory_peak_bytes"),
        "delegation_overhead_ms": samples.get("delegation_overhead_ms"),
        "interruption_latency_ms": samples.get("interruption_latency_ms"),
        "resume_latency_ms": samples.get("resume_latency_ms"),
        "governed_tool_latency_ms": samples.get("governed_tool_latency_ms"),
    }
    checks = {
        "model_footprint": THRESHOLDS["default_local_model_footprint_min_bytes"]
        <= measured["model_footprint_bytes"]
        <= THRESHOLDS["default_local_model_footprint_max_bytes"],
        "control_plane_rss": measured["control_plane_rss_bytes"] < THRESHOLDS["control_plane_rss_max_bytes_exclusive"],
        "idle_stratum_rss": measured["idle_stratum_rss_bytes"] <= THRESHOLDS["idle_stratum_rss_max_bytes"],
        "warm_ttft_overhead": overhead <= THRESHOLDS["warm_ttft_overhead_max_percent"],
        "non_model_dispatch_p95": measured["non_model_dispatch_p95_ms"]
        < THRESHOLDS["non_model_dispatch_p95_max_ms_exclusive"],
        "large_model_runtime_count": measured["max_large_model_runtime_count"]
        <= THRESHOLDS["max_large_model_runtimes"],
    }
    content = {
        "kind": REPORT_KIND,
        "schema_version": SCHEMA_VERSION,
        "manifest_digest": manifest["manifest_digest"],
        "measurements": measured,
        "hard_threshold_results": checks,
        "overall_state": "PASS" if all(checks.values()) and samples.get("qualification_mode") == "PHYSICAL" else "FAIL",
        "raw_samples": samples,
        "artifact_is_authority": False,
        "grants_authority": False,
        "promotes": False,
    }
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
    if (
        value.get("artifact_is_authority") is not False
        or value.get("grants_authority") is not False
        or value.get("promotes") is not False
    ):
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
    if (
        value.get("artifact_is_authority") is not False
        or value.get("grants_authority") is not False
        or value.get("promotes") is not False
    ):
        errors.append("benchmark evidence cannot grant authority or promote")
    if value.get("report_digest") != report_digest(value):
        errors.append("report digest mismatch")
    checks = value.get("hard_threshold_results")
    if not isinstance(checks, dict) or value.get("overall_state") != (
        "PASS" if checks and all(checks.values()) else "FAIL"
    ):
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
        if not raw.get("samples_digest"):
            errors.append("raw samples digest is required")
        elif raw.get("samples_digest") != raw_samples_digest(raw):
            errors.append("raw samples digest mismatch")
        try:
            recomputed = build_report(manifest=manifest, samples=raw) if manifest is not None else None
        except (ValueError, OSError, json.JSONDecodeError) as exc:
            errors.append(f"raw evidence recomputation failed: {exc}")
        else:
            if recomputed is not None:
                if value.get("measurements") != recomputed.get("measurements"):
                    errors.append("report measurements do not match raw-evidence recomputation")
                if value.get("hard_threshold_results") != recomputed.get("hard_threshold_results"):
                    errors.append("hard thresholds do not match raw-evidence recomputation")
                if value.get("overall_state") != recomputed.get("overall_state"):
                    errors.append("overall state does not match raw-evidence recomputation")
    return errors


def write_json(value: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
