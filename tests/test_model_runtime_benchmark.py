import hashlib
import json
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from builder_ii.benchmark.model_runtime import (
    METHOD_CORRECTION_SHA256,
    THRESHOLDS,
    ModelMemorySample,
    build_manifest,
    build_report,
    collect_model_memory,
    nearest_rank_percentile,
    parse_footprint_bytes,
    peak_model_memory,
    percentile,
    validate_manifest,
    validate_report,
)


def _manifest():
    return build_manifest(git_commit="a" * 40, git_tree="b" * 40, backend="mlx-lm", provider="local",
                          client="mlx", model="m", route_digest="c" * 64,
                          policy_digest="d" * 64, budget_digest="e" * 64)


def _samples(manifest, **overrides):
    base = {
        "git_commit": manifest["git_commit"],
        "git_tree": manifest["git_tree"],
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
    }
    base.update(overrides)
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
    manifest["manifest_digest"] = hashlib.sha256(json.dumps(
        {k: v for k, v in manifest.items() if k != "manifest_digest"},
        sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()
    assert "methodology differs" in ";".join(validate_manifest(manifest))


def test_report_derives_all_hard_thresholds() -> None:
    manifest = _manifest()
    samples = _samples(manifest)
    report = build_report(manifest=manifest, samples=samples)
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


@pytest.mark.parametrize("value,passes", [
    (2 * 1024**3, True), (7 * 1024**3, True),
    (2 * 1024**3 - 1, False), (7 * 1024**3 + 1, False),
])
def test_physical_footprint_boundaries(value: int, passes: bool) -> None:
    manifest = _manifest()
    samples = _samples(manifest, model_physical_footprint={"acceptance_bytes": value},
                       warm_ttft_governed_ms=[100] * 10)
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
        "baseline_bytes": 900, "steady_warm_bytes": 800, "peak_bytes": 900,
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
        collect_model_memory(123, identity_check=lambda _pid: False,
                             footprint_binary=Path("/usr/bin/footprint"), runner=runner)
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
        collect_model_memory(123, identity_check=lambda _pid: True,
                             footprint_binary=Path("/usr/bin/footprint"), runner=runner)


def test_collector_refuses_missing_footprint_binary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("builder_ii.benchmark.model_runtime.platform.system", lambda: "Darwin")
    monkeypatch.setattr("builder_ii.benchmark.model_runtime.platform.machine", lambda: "arm64")
    with pytest.raises(FileNotFoundError, match="footprint binary"):
        collect_model_memory(123, identity_check=lambda _pid: True,
                             footprint_binary=tmp_path / "missing")


def test_collector_passes_root_and_children_in_one_deduplicated_process_set(
    monkeypatch: pytest.MonkeyPatch,
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
    sample = collect_model_memory(123, identity_check=lambda _pid: True,
                                  footprint_binary=Path("/usr/bin/footprint"), runner=runner)
    argv = runner.call_args.args[0]
    assert argv.count("--pid") == 2
    assert argv[-4:] == ["--pid", "123", "--pid", "124"]
    assert sample.measured_pids == (123, 124)
    assert sample.physical_footprint_bytes == 4_000


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
        collect_model_memory(123, identity_check=identity,
                             footprint_binary=Path("/usr/bin/footprint"), runner=runner)


def test_report_digest_cryptographically_binds_manifest_digest() -> None:
    manifest_a = _manifest()
    manifest_b = build_manifest(
        git_commit="f" * 40, git_tree="e" * 40, backend="mlx-lm", provider="local",
        client="mlx", model="m", route_digest="c" * 64,
        policy_digest="d" * 64, budget_digest="e" * 64,
    )
    samples_a = {
        "git_commit": manifest_a["git_commit"],
        "git_tree": manifest_a["git_tree"],
        "method_correction_sha256": METHOD_CORRECTION_SHA256,
        "warm_ttft_direct_ms": [100] * 10, "warm_ttft_governed_ms": [110] * 10,
        "non_model_dispatch_ms": [10] * 100,
        "model_memory_acceptance_metric": "macos_physical_footprint",
        "model_physical_footprint": {"acceptance_bytes": 3 * 1024**3},
        "control_plane_rss_bytes": 500 * 1024**2, "idle_stratum_rss_bytes": 200 * 1024**2,
        "max_large_model_runtime_count": 1,
    }
    samples_b = dict(samples_a, git_commit=manifest_b["git_commit"], git_tree=manifest_b["git_tree"])

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
    samples = {
        "git_commit": "0" * 40,  # Mismatched commit
        "git_tree": manifest["git_tree"],
        "method_correction_sha256": METHOD_CORRECTION_SHA256,
        "warm_ttft_direct_ms": [100] * 10, "warm_ttft_governed_ms": [110] * 10,
        "non_model_dispatch_ms": [10] * 100,
        "model_memory_acceptance_metric": "macos_physical_footprint",
        "model_physical_footprint": {"acceptance_bytes": 3 * 1024**3},
        "control_plane_rss_bytes": 500 * 1024**2, "idle_stratum_rss_bytes": 200 * 1024**2,
        "max_large_model_runtime_count": 1,
    }
    with pytest.raises(ValueError, match="git_commit"):
        build_report(manifest=manifest, samples=samples)

    # Mismatched tree
    samples_bad_tree = dict(samples, git_commit=manifest["git_commit"], git_tree="0" * 40)
    with pytest.raises(ValueError, match="git_tree"):
        build_report(manifest=manifest, samples=samples_bad_tree)

    # Mismatched method correction
    samples_bad_method = dict(samples, git_commit=manifest["git_commit"], method_correction_sha256="wrong")
    with pytest.raises(ValueError, match="method_correction_sha256"):
        build_report(manifest=manifest, samples=samples_bad_method)

