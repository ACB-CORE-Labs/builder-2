import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from builder_ii.benchmark.model_runtime import (
    METHOD_CORRECTION_SHA256,
    RAW_SAMPLES_KIND,
    THRESHOLDS,
    ModelMemorySample,
    build_manifest,
    build_report,
    collect_canonical_m1_samples,
    collect_model_memory,
    nearest_rank_percentile,
    parse_footprint_bytes,
    peak_model_memory,
    percentile,
    raw_samples_digest,
    report_digest,
    validate_manifest,
    validate_report,
)
from builder_ii.core.config_schema import digest_jsonable


def _manifest():
    return build_manifest(
        git_commit="a" * 40,
        git_tree="b" * 40,
        backend="mlx-lm",
        provider="local",
        client="mlx",
        model="m",
        route_digest="c" * 64,
        policy_digest="d" * 64,
        budget_digest="e" * 64,
    )


def _samples(manifest, **overrides):
    evidence_dir = Path(tempfile.mkdtemp(prefix="builder-ps5-test-evidence-"))
    native = {
        "kind": "builder_ii.deepagents_native_evidence_bundle",
        "schema_version": 1,
        "status": "INTERRUPTED",
        "official_factory": "deepagents.create_deep_agent",
        "model_adapter": "builder_ii.ModelExecutionGateway",
        "single_model_instance": True,
        "active_workers": 2,
        "obligations": [{"obligation_id": "1"}, {"obligation_id": "2"}],
        "delegated_subagents": ["alpha", "beta"],
        "completed_task_count": 2,
        "parent_child_chain": [
            {"parent_ref": {"seal_digest": "a" * 64}, "delegated": True, "completed": True},
            {"parent_ref": {"seal_digest": "b" * 64}, "delegated": True, "completed": True},
        ],
        "model_receipt_refs": [{}],
        "tool_receipt_refs": [{}],
        "event_refs": [],
        "event_count": 0,
        "target_repo_mutation": False,
        "shell_execution": False,
        "git_mutation": False,
        "direct_provider_bypass": False,
        "artifact_is_authority": False,
        "grants_authority": False,
    }
    native["evidence_digest"] = digest_jsonable(native, digest_key="evidence_digest")
    native_path = evidence_dir / "native.json"
    native_path.write_text(json.dumps(native), encoding="utf-8")
    goose_path = evidence_dir / "goose.json"
    goose_path.write_text(
        json.dumps({"status": "succeeded", "route_digest": manifest["route_digest"]}), encoding="utf-8"
    )

    def ref(path: Path) -> dict[str, object]:
        return {
            "path": str(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "required": True,
        }

    footprint_path = evidence_dir / "footprint.txt"
    footprint_path.write_text(f"{3 * 1024**3} B 0 B 0 B 1 TOTAL\n", encoding="utf-8")

    base = {
        "kind": RAW_SAMPLES_KIND,
        "manifest_digest": manifest["manifest_digest"],
        "git_commit": manifest["git_commit"],
        "git_tree": manifest["git_tree"],
        "qualification_mode": "PHYSICAL",
        "method_correction_sha256": METHOD_CORRECTION_SHA256,
        "warm_ttft_direct_ms": [100] * 10,
        "warm_ttft_governed_ms": [119] * 10,
        "non_model_dispatch_ms": [10] * 100,
        "model_memory_acceptance_metric": "macos_physical_footprint",
        "model_physical_footprint": {
            "baseline_bytes": 2 * 1024**3,
            "steady_warm_bytes": 3 * 1024**3,
            "peak_bytes": 3 * 1024**3,
            "acceptance_bytes": 3 * 1024**3,
        },
        "model_rss_diagnostic": {"peak_bytes": 700_000_000, "acceptance": False},
        "graphics_memory_diagnostics": {"ioaccelerator_graphics_bytes": 2 * 1024**3},
        "control_plane_rss_bytes": 500 * 1024**2,
        "idle_stratum_rss_bytes": 200 * 1024**2,
        "max_large_model_runtime_count": 1,
        "model_server_pid": 123,
        "ttft_pair_order": [
            ["direct", "governed"] if index % 2 == 0 else ["governed", "direct"] for index in range(11)
        ],
        "model_memory_samples": [
            {
                "phase": phase,
                "physical_footprint_bytes": 3 * 1024**3,
                "footprint_evidence_ref": ref(footprint_path),
            }
            for phase in ("baseline", "load", "warm", "inference")
        ],
        "process_monitor_coverage": ["deepagents", "goose"],
        "model_process_observations": [
            {"phase": "deepagents", "validated_root_pids": [123]},
            {"phase": "goose", "validated_root_pids": [123]},
        ],
        "deepagents_evidence_ref": ref(native_path),
        "goose_receipt_ref": ref(goose_path),
        "direct_gateway_receipt_refs": [ref(goose_path) for _ in range(11)],
        "governed_gateway_receipt_refs": [ref(goose_path) for _ in range(11)],
        "dispatch_receipt_refs": [ref(goose_path) for _ in range(100)],
        "dispatch_event_refs": [ref(goose_path) for _ in range(100)],
        "combined_runtime": {
            "deepagents_workload_executed": True,
            "active_workers": 2,
            "validated_obligations": 2,
            "goose_loopback_traversed": True,
            "gateway_instance_count": 1,
            "route_lineage_match": True,
            "route_lineage_root": manifest["route_digest"],
            "goose_route_digest": manifest["route_digest"],
            "budget_lineage_match": True,
            "model_server_identity_match": True,
        },
    }
    base.update(overrides)
    base["samples_digest"] = raw_samples_digest(base)
    return base


def test_percentile_linear_interpolation() -> None:
    assert percentile([1, 2, 3, 4], 50) == 2.5
    assert percentile(range(1, 101), 95) == 95.05
    assert nearest_rank_percentile(range(1, 101), 95) == 95


def test_manifest_freezes_methodology_and_thresholds() -> None:
    manifest = _manifest()
    assert manifest["thresholds"] == THRESHOLDS
    assert manifest["methodology"]["local_model_memory"]["method_correction_sha256"] == METHOD_CORRECTION_SHA256
    assert manifest["methodology"]["local_model_memory"]["rss"] == "diagnostic only"
    assert validate_manifest(manifest) == []
    manifest["thresholds"]["warm_ttft_overhead_max_percent"] = 21
    assert "thresholds differ" in ";".join(validate_manifest(manifest))
    manifest = _manifest()
    manifest["methodology"]["warm_ttft"]["paired_samples_min"] = 9
    manifest["manifest_digest"] = hashlib.sha256(
        json.dumps(
            {k: v for k, v in manifest.items() if k != "manifest_digest"},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    assert "methodology differs" in ";".join(validate_manifest(manifest))


def test_report_derives_all_hard_thresholds() -> None:
    manifest = _manifest()
    samples = _samples(manifest)
    report = build_report(manifest=manifest, samples=samples)
    print(report)
    assert report["overall_state"] == "PASS"
    assert report["measurements"]["warm_ttft_overhead_percent"] == 19
    assert report["measurements"]["model_footprint_bytes"] == 3 * 1024**3
    assert report["measurements"]["model_rss_diagnostic"]["acceptance"] is False
    assert validate_report(report, manifest=manifest) == []


def test_report_fails_without_changing_threshold() -> None:
    manifest = _manifest()
    samples = _samples(manifest, warm_ttft_governed_ms=[121] * 10)
    report = build_report(manifest=manifest, samples=samples)
    assert report["overall_state"] == "FAIL"
    assert report["hard_threshold_results"]["warm_ttft_overhead"] is False


def test_footprint_parser_keeps_graphics_diagnostic_without_double_counting() -> None:
    output = """Physical footprint: 4,608,172,032 bytes
IOAccelerator 4,400,000,000
IOAccelerator (graphics) 4,352,000,000
Owned physical footprint (unmapped) (graphics) 4,300,000,000
"""
    total, diagnostics = parse_footprint_bytes(output)
    assert total == 4_608_172_032
    assert diagnostics["ioaccelerator_graphics_bytes"] == 4_352_000_000
    assert total != total + diagnostics["ioaccelerator_graphics_bytes"]


def test_footprint_parser_accepts_current_macos_bytes_table() -> None:
    output = """   163840 B           0 B           0 B          4    IOAccelerator
    16384 B           0 B           0 B          1    Owned physical footprint (unmapped) (graphics)
4513107808 B    14286848 B           0 B       3692    TOTAL

Auxiliary data:
    phys_footprint: 4513140576 B
"""
    total, diagnostics = parse_footprint_bytes(output)
    assert total == 4_513_107_808
    assert diagnostics["ioaccelerator_bytes"] == 163_840
    assert diagnostics["owned_unmapped_graphics_bytes"] == 16_384


@pytest.mark.parametrize(
    "value,passes",
    [
        (2 * 1024**3, True),
        (7 * 1024**3, True),
        (2 * 1024**3 - 1, False),
        (7 * 1024**3 + 1, False),
    ],
)
def test_physical_footprint_boundaries(value: int, passes: bool) -> None:
    manifest = _manifest()
    samples = _samples(manifest, model_physical_footprint={"acceptance_bytes": value}, warm_ttft_governed_ms=[100] * 10)
    assert build_report(manifest=manifest, samples=samples)["hard_threshold_results"]["model_footprint"] is passes


def test_peak_model_memory_uses_physical_max_and_rss_only_as_diagnostic() -> None:
    values = [
        ModelMemorySample(3_000, 900, {}, (10,)),
        ModelMemorySample(5_000, 700, {"ioaccelerator_bytes": 4_000}, (10, 11)),
        ModelMemorySample(4_000, 800, {}, (10,)),
    ]
    result = peak_model_memory(values)
    assert result["model_physical_footprint"]["acceptance_bytes"] == 5_000
    assert result["model_rss_diagnostic"] == {
        "baseline_bytes": 900,
        "steady_warm_bytes": 800,
        "peak_bytes": 900,
        "acceptance": False,
    }
    assert result["graphics_memory_diagnostics"] == {"ioaccelerator_bytes": 4_000}


def test_footprint_parser_rejects_malformed_output() -> None:
    with pytest.raises(ValueError, match="byte-valued total"):
        parse_footprint_bytes("IOAccelerator: unknown")


def test_collector_refuses_foreign_pid_before_invoking_footprint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("builder_ii.benchmark.model_runtime.platform.system", lambda: "Darwin")
    monkeypatch.setattr("builder_ii.benchmark.model_runtime.platform.machine", lambda: "arm64")
    runner = Mock()
    with pytest.raises(ValueError, match="identity gate"):
        collect_model_memory(
            123, identity_check=lambda _pid: False, footprint_binary=Path("/usr/bin/footprint"), runner=runner
        )
    runner.assert_not_called()


def test_collector_fails_closed_on_footprint_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("builder_ii.benchmark.model_runtime.platform.system", lambda: "Darwin")
    monkeypatch.setattr("builder_ii.benchmark.model_runtime.platform.machine", lambda: "arm64")
    process = Mock()
    process.create_time.return_value = 1.0
    process.children.return_value = []
    process.is_running.return_value = True
    monkeypatch.setattr("builder_ii.benchmark.model_runtime.psutil.Process", lambda _pid: process)
    runner = Mock(return_value=subprocess.CompletedProcess([], 1, "", "not permitted"))
    with pytest.raises(RuntimeError, match="not permitted"):
        collect_model_memory(
            123, identity_check=lambda _pid: True, footprint_binary=Path("/usr/bin/footprint"), runner=runner
        )


def test_collector_refuses_missing_footprint_binary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("builder_ii.benchmark.model_runtime.platform.system", lambda: "Darwin")
    monkeypatch.setattr("builder_ii.benchmark.model_runtime.platform.machine", lambda: "arm64")
    with pytest.raises(ValueError, match="only /usr/bin/footprint"):
        collect_model_memory(123, identity_check=lambda _pid: True, footprint_binary=tmp_path / "missing")


def test_collector_passes_root_and_children_in_one_deduplicated_process_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("builder_ii.benchmark.model_runtime.platform.system", lambda: "Darwin")
    monkeypatch.setattr("builder_ii.benchmark.model_runtime.platform.machine", lambda: "arm64")
    child = Mock(pid=124)
    child.is_running.return_value = True
    process = Mock()
    process.create_time.return_value = 1.0
    process.children.return_value = [child]
    process.is_running.return_value = True
    monkeypatch.setattr("builder_ii.benchmark.model_runtime.psutil.Process", lambda _pid: process)
    monkeypatch.setattr("builder_ii.benchmark.model_runtime.rss_tree", lambda _pid: 700)
    runner = Mock(return_value=subprocess.CompletedProcess([], 0, "Physical footprint: 4,000 bytes\n", ""))
    sample = collect_model_memory(
        123,
        identity_check=lambda _pid: True,
        footprint_binary=Path("/usr/bin/footprint"),
        runner=runner,
        evidence_path=tmp_path / "footprint.txt",
    )
    argv = runner.call_args.args[0]
    assert argv.count("--pid") == 2
    assert argv[-4:] == ["--pid", "123", "--pid", "124"]
    assert sample.measured_pids == (123, 124)
    assert sample.physical_footprint_bytes == 4_000
    assert sample.footprint_evidence_ref == {
        "path": str(tmp_path / "footprint.txt"),
        "sha256": hashlib.sha256(b"Physical footprint: 4,000 bytes\n").hexdigest(),
        "role": "macos_footprint_stdout",
        "required": True,
    }


def test_collector_refuses_identity_drift_after_measurement(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("builder_ii.benchmark.model_runtime.platform.system", lambda: "Darwin")
    monkeypatch.setattr("builder_ii.benchmark.model_runtime.platform.machine", lambda: "arm64")
    process = Mock()
    process.create_time.return_value = 1.0
    process.children.return_value = []
    process.is_running.return_value = True
    monkeypatch.setattr("builder_ii.benchmark.model_runtime.psutil.Process", lambda _pid: process)
    identity = Mock(side_effect=[True, True, False])
    runner = Mock(return_value=subprocess.CompletedProcess([], 0, "Physical footprint: 4,000 bytes\n", ""))
    with pytest.raises(ValueError, match="drifted"):
        collect_model_memory(123, identity_check=identity, footprint_binary=Path("/usr/bin/footprint"), runner=runner)


def test_report_digest_cryptographically_binds_manifest_digest() -> None:
    manifest_a = _manifest()
    manifest_b = build_manifest(
        git_commit="f" * 40,
        git_tree="e" * 40,
        backend="mlx-lm",
        provider="local",
        client="mlx",
        model="m",
        route_digest="c" * 64,
        policy_digest="d" * 64,
        budget_digest="e" * 64,
    )
    samples_a = _samples(manifest_a)
    samples_b = _samples(manifest_b)

    report_a = build_report(manifest=manifest_a, samples=samples_a)
    report_b = build_report(manifest=manifest_b, samples=samples_b)

    assert report_a["manifest_digest"] != report_b["manifest_digest"]
    assert report_a["report_digest"] != report_b["report_digest"]

    # Tampering manifest_digest invalidates report_digest
    tampered = dict(report_a, manifest_digest=manifest_b["manifest_digest"])
    errors = validate_report(tampered, manifest=manifest_a)
    assert any("report digest mismatch" in e for e in errors)
    assert any("report does not bind manifest" in e for e in errors)


def test_build_report_refuses_samples_with_mismatched_provenance() -> None:
    manifest = _manifest()
    samples = _samples(manifest)

    # Mismatched commit
    samples_bad_commit = dict(samples, git_commit="0" * 40)
    samples_bad_commit["samples_digest"] = raw_samples_digest(samples_bad_commit)
    with pytest.raises(ValueError, match="git_commit"):
        build_report(manifest=manifest, samples=samples_bad_commit)

    # Mismatched tree
    samples_bad_tree = dict(samples, git_tree="0" * 40)
    samples_bad_tree["samples_digest"] = raw_samples_digest(samples_bad_tree)
    with pytest.raises(ValueError, match="git_tree"):
        build_report(manifest=manifest, samples=samples_bad_tree)

    # Mismatched method correction
    samples_bad_method = dict(samples, method_correction_sha256="wrong")
    samples_bad_method["samples_digest"] = raw_samples_digest(samples_bad_method)
    with pytest.raises(ValueError, match="method_correction_sha256"):
        build_report(manifest=manifest, samples=samples_bad_method)

    # Mismatched manifest digest
    samples_bad_manifest_digest = dict(samples, manifest_digest="0" * 64)
    samples_bad_manifest_digest["samples_digest"] = raw_samples_digest(samples_bad_manifest_digest)
    with pytest.raises(ValueError, match="manifest_digest"):
        build_report(manifest=manifest, samples=samples_bad_manifest_digest)


def test_old_sample_restamp_lesion_refuses_qualification() -> None:
    """Lesion: taking valid samples from commit A, re-stamping commit B into git_commit/tree,

    and recomputing samples_digest MUST still be refused by canonical qualification.
    """
    manifest_a = _manifest()
    manifest_b = build_manifest(
        git_commit="b" * 40,
        git_tree="c" * 40,
        backend="mlx-lm",
        provider="local",
        client="mlx",
        model="m",
        route_digest="c" * 64,
        policy_digest="d" * 64,
        budget_digest="e" * 64,
    )
    # Valid physical sample collected under manifest A
    samples_from_commit_a = _samples(manifest_a)
    assert build_report(manifest=manifest_a, samples=samples_from_commit_a)["overall_state"] == "PASS"

    # Attempt to restamp samples with commit B's git_commit and git_tree
    restamped_samples = dict(
        samples_from_commit_a,
        git_commit=manifest_b["git_commit"],
        git_tree=manifest_b["git_tree"],
    )
    restamped_samples["samples_digest"] = raw_samples_digest(restamped_samples)

    # Candidate qualification under manifest B must fail closed because manifest_digest remains bound to A
    with pytest.raises(ValueError, match="manifest_digest"):
        build_report(manifest=manifest_b, samples=restamped_samples)


def test_qualification_mode_replay_cannot_close():
    manifest = _manifest()
    samples = _samples(manifest)
    samples["qualification_mode"] = "REPLAY"
    samples["samples_digest"] = raw_samples_digest(samples)

    report = build_report(manifest=manifest, samples=samples)
    assert report["overall_state"] == "FAIL"


def test_canonical_collector_fails_no_real_model_pid(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("builder_ii.benchmark.model_runtime.time.sleep", lambda x: None)
    monkeypatch.setattr("builder_ii.benchmark.model_runtime.platform.system", lambda: "Darwin")
    monkeypatch.setattr("builder_ii.benchmark.model_runtime.platform.machine", lambda: "arm64")
    monkeypatch.setattr("builder_ii.lifecycle.candidate.runtime_control.find_runtime_processes", lambda x: [])

    manifest = _manifest()
    with pytest.raises(ValueError, match="Exact single model server not found"):
        collect_canonical_m1_samples(manifest=manifest)


def test_canonical_collector_fails_no_stratum_process(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("builder_ii.benchmark.model_runtime.time.sleep", lambda x: None)
    monkeypatch.setattr("builder_ii.benchmark.model_runtime.platform.system", lambda: "Darwin")
    monkeypatch.setattr("builder_ii.benchmark.model_runtime.platform.machine", lambda: "arm64")

    # Need to simulate find_runtime_processes returning 1 process
    class MockProcess:
        pid = 123
        cmdline = ["mlx_lm.server"]

    monkeypatch.setattr(
        "builder_ii.lifecycle.candidate.runtime_control.find_runtime_processes", lambda x: [MockProcess()]
    )
    monkeypatch.setattr("builder_ii.core.orchestration_obligation.validate_orchestration_obligation", lambda _item: [])

    # Simulate Stratum missing by making Popen fail
    def mock_popen(*args, **kwargs):
        raise FileNotFoundError("stratum not found")

    monkeypatch.setattr("builder_ii.benchmark.model_runtime.subprocess.Popen", mock_popen)

    manifest = _manifest()
    with pytest.raises(FileNotFoundError, match="stratum not found"):
        collect_canonical_m1_samples(
            manifest=manifest,
            route=Mock(),
            route_sources={},
            obligations=[{"lane": "deepagents", "obligation_id": "a"}, {"lane": "deepagents", "obligation_id": "b"}],
        )


def test_canonical_collector_fails_hardcoded_memory_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("builder_ii.benchmark.model_runtime.platform.system", lambda: "Darwin")
    monkeypatch.setattr("builder_ii.benchmark.model_runtime.platform.machine", lambda: "arm64")
    process = Mock()
    process.create_time.return_value = 1.0
    process.children.return_value = []
    process.is_running.return_value = True
    monkeypatch.setattr("builder_ii.benchmark.model_runtime.psutil.Process", lambda _pid: process)
    runner = Mock(return_value=subprocess.CompletedProcess([], 0, "Physical footprint: 4,000 bytes\n", ""))
    with pytest.raises(ValueError, match="only /usr/bin/footprint"):
        collect_model_memory(
            123, identity_check=lambda _pid: True, footprint_binary=Path("/tmp/fallback-footprint"), runner=runner
        )
    runner.assert_not_called()


def test_canonical_collector_fails_synthetic_ttft() -> None:
    source = Path("builder_ii/benchmark/model_runtime.py").read_text(encoding="utf-8")
    collector = source[source.index("def collect_canonical_m1_samples") : source.index("def build_report")]
    assert ".invoke(" not in collector
    assert "run_model_call(" not in collector
    assert "run_routed_model_call(" in collector
    assert "_invoke_local_model_gateway(" in collector
    assert 'receipt.get("attempt_history")' in collector
    assert 'receipt.get("invocation"' not in collector
    assert "except Exception:\n                pass" not in collector


def test_footprint_uses_only_native_sudo_prompt_and_exact_fixed_argv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("builder_ii.benchmark.model_runtime.platform.system", lambda: "Darwin")
    monkeypatch.setattr("builder_ii.benchmark.model_runtime.platform.machine", lambda: "arm64")
    child = Mock(pid=124)
    child.is_running.return_value = True
    process = Mock()
    process.create_time.return_value = 1.0
    process.children.return_value = [child]
    process.is_running.return_value = True
    monkeypatch.setattr("builder_ii.benchmark.model_runtime.psutil.Process", lambda _pid: process)
    monkeypatch.setattr("builder_ii.benchmark.model_runtime.rss_tree", lambda _pid: 700)
    runner = Mock(return_value=subprocess.CompletedProcess([], 0, "Physical footprint: 4,000 bytes\n", ""))
    collect_model_memory(123, identity_check=lambda _pid: True, runner=runner)
    assert runner.call_args.args[0] == [
        "sudo",
        "/usr/bin/footprint",
        "--format",
        "bytes",
        "--unmapped",
        "--pid",
        "123",
        "--pid",
        "124",
    ]
    assert runner.call_args.kwargs["shell"] is False
    assert "input" not in runner.call_args.kwargs
    assert "stdin" not in runner.call_args.kwargs


def test_collector_source_pins_successful_dispatch_and_durable_refs() -> None:
    source = Path("builder_ii/benchmark/model_runtime.py").read_text(encoding="utf-8")
    collector = source[source.index("def collect_canonical_m1_samples") : source.index("def build_report")]
    assert 'target_name="builder"' in collector
    assert 'receipt.get("status") != "succeeded"' in collector
    assert "hashlib.sha256(path.read_bytes()).hexdigest()" in collector
    assert "direct_ttft_iteration_" not in collector
    assert "governed_ttft_iteration_" not in collector
    assert "len(idle_stratum_rss_samples) != 30" in collector


@pytest.mark.parametrize(
    "field,value",
    [
        ("deepagents_workload_executed", False),
        ("active_workers", 1),
        ("validated_obligations", 1),
        ("goose_loopback_traversed", False),
        ("gateway_instance_count", 2),
        ("route_lineage_match", False),
        ("budget_lineage_match", False),
        ("model_server_identity_match", False),
    ],
)
def test_combined_runtime_invariant_lesions_fail(field: str, value) -> None:
    manifest = _manifest()
    samples = _samples(manifest)
    samples["combined_runtime"] = {**samples["combined_runtime"], field: value}
    samples["samples_digest"] = raw_samples_digest(samples)
    with pytest.raises(ValueError, match="combined Deep Agents and Goose"):
        build_report(manifest=manifest, samples=samples)


def test_process_monitor_span_and_identity_lesions_fail() -> None:
    manifest = _manifest()
    samples = _samples(manifest, process_monitor_coverage=["deepagents"])
    samples["samples_digest"] = raw_samples_digest(samples)
    with pytest.raises(ValueError, match="process monitor"):
        build_report(manifest=manifest, samples=samples)
    samples = _samples(
        manifest,
        model_process_observations=[
            {"phase": "deepagents", "validated_root_pids": [123, 456]},
            {"phase": "goose", "validated_root_pids": [123]},
        ],
    )
    samples["samples_digest"] = raw_samples_digest(samples)
    with pytest.raises(ValueError, match="identity"):
        build_report(manifest=manifest, samples=samples)


def test_memory_schedule_ttft_and_digest_lesions_fail() -> None:
    manifest = _manifest()
    samples = _samples(manifest, model_memory_samples=[{"phase": "inference"}])
    samples["samples_digest"] = raw_samples_digest(samples)
    with pytest.raises(ValueError, match="memory sampling"):
        build_report(manifest=manifest, samples=samples)
    samples = _samples(manifest, ttft_pair_order=[["direct", "governed"]] * 11)
    samples["samples_digest"] = raw_samples_digest(samples)
    with pytest.raises(ValueError, match="alternate"):
        build_report(manifest=manifest, samples=samples)
    samples = _samples(manifest)
    samples.pop("samples_digest")
    with pytest.raises(ValueError, match="require samples_digest"):
        build_report(manifest=manifest, samples=samples)


def test_footprint_evidence_substitution_fails() -> None:
    manifest = _manifest()
    samples = _samples(manifest)
    evidence_path = Path(samples["model_memory_samples"][0]["footprint_evidence_ref"]["path"])
    evidence_path.write_text("4000 B 0 B 0 B 1 TOTAL\n", encoding="utf-8")
    with pytest.raises(ValueError, match="footprint_evidence_ref digest mismatch"):
        build_report(manifest=manifest, samples=samples)


def test_validator_recomputes_and_rejects_claimed_threshold_booleans() -> None:
    manifest = _manifest()
    report = build_report(manifest=manifest, samples=_samples(manifest))
    report["hard_threshold_results"] = {**report["hard_threshold_results"], "warm_ttft_overhead": False}
    report["overall_state"] = "FAIL"
    report["report_digest"] = report_digest(report)
    errors = validate_report(report, manifest=manifest)
    assert any("recomputation" in error for error in errors)


def test_collector_uses_one_gateway_for_direct_wrp_deepagents_and_goose() -> None:
    source = Path("builder_ii/benchmark/model_runtime.py").read_text(encoding="utf-8")
    collector = source[source.index("def collect_canonical_m1_samples") : source.index("def build_report")]
    assert collector.count("ModelExecutionGateway(") == 1
    assert "prevalidated_gateway=gateway" in collector
    assert "gateway=gateway" in collector
    assert "close_gateway_on_close=False" in collector


def test_canonical_collector_fails_no_physical_footprint(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("builder_ii.benchmark.model_runtime.platform.system", lambda: "Darwin")
    monkeypatch.setattr("builder_ii.benchmark.model_runtime.platform.machine", lambda: "arm64")

    class MockProcess:
        pid = 123
        cmdline = ["mlx_lm.server"]

    monkeypatch.setattr(
        "builder_ii.lifecycle.candidate.runtime_control.find_runtime_processes", lambda x: [MockProcess()]
    )

    class MockStratum:
        pid = 456

        def poll(self):
            return None

        def terminate(self):
            pass

        def wait(self, timeout=None):
            pass

    orig_popen = subprocess.Popen

    def mock_popen(*args, **kwargs):
        if "stratum_cli" in str(args):
            return MockStratum()
        return orig_popen(*args, **kwargs)

    monkeypatch.setattr("builder_ii.benchmark.model_runtime.subprocess.Popen", mock_popen)

    monkeypatch.setattr("builder_ii.benchmark.model_runtime.time.sleep", lambda x: None)

    # Mocking gateway and engine
    class MockRes:
        status = "succeeded"

        class Att:
            first_public_chunk_ns = 2000000
            started_ns = 1000000

        attempts = [Att()]

    monkeypatch.setattr(
        "builder_ii.routing.gateway_invocation.governed_invocation_engine",
        lambda x: type("Engine", (), {"invoke": lambda *a, **k: MockRes()})(),
    )

    class MockGateway:
        def __init__(self, *args, **kwargs):
            pass

        def run_model_call(self, *args, **kwargs):
            return {}, {"invocation": {"attempts": [{"first_public_chunk_ns": 2000000, "started_ns": 1000000}]}}, {}

    monkeypatch.setattr(
        "builder_ii.routing.model_client_registry.create_model_client_registry",
        lambda *args, **kwargs: {"clients": [{"model_id": "m"}]},
    )
    monkeypatch.setattr("builder_ii.routing.model_execution_gateway.ModelExecutionGateway", MockGateway)
    monkeypatch.setattr("builder_ii.adapters.mcp.governed_services.run_service", lambda *args, **kwargs: None)

    # Mock rss_tree
    monkeypatch.setattr("builder_ii.benchmark.model_runtime.rss_tree", lambda *a, **kw: 1000)
    monkeypatch.setattr(
        "builder_ii.benchmark.model_runtime.psutil.Process",
        lambda *a, **kw: type("P", (), {"children": lambda self, recursive: [], "pid": 123})(),
    )
    monkeypatch.setattr("builder_ii.core.orchestration_obligation.validate_orchestration_obligation", lambda _item: [])

    # The footprint binary check will fail
    manifest = _manifest()
    with pytest.raises(ValueError, match="only /usr/bin/footprint"):
        collect_canonical_m1_samples(
            manifest=manifest,
            footprint_binary=Path("/does/not/exist"),
            route=Mock(),
            route_sources={"registry": {}, "execution_policy": {}, "budget": {}},
            obligations=[{"lane": "deepagents", "obligation_id": "a"}, {"lane": "deepagents", "obligation_id": "b"}],
        )
