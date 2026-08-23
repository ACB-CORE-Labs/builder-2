from types import SimpleNamespace
from unittest.mock import patch

import pytest

from builder_ii.lifecycle.candidate.runtime_control import RuntimeProcess
from builder_ii.routing.backends import ensure_warm_backend


@pytest.fixture
def mock_settings():
    return SimpleNamespace(active_model_id="model-a")


def test_reuses_one_healthy_exact_model(mock_settings) -> None:
    process = RuntimeProcess(123, "python", ("python", "-m", "mlx_lm.server"))
    with (
        patch("builder_ii.lifecycle.candidate.runtime_control.find_runtime_processes", return_value=[process]),
        patch("builder_ii.routing.backends.check_health", return_value=(True, "ok")),
        patch("builder_ii.routing.backends.check_serves_active_model", return_value=(True, "exact")),
        patch("builder_ii.routing.backends.start_backend_process") as start,
    ):
        result = ensure_warm_backend(mock_settings)
    assert result.state == "reused"
    assert result.pid == 123
    start.assert_not_called()


def test_refuses_second_large_runtime(mock_settings) -> None:
    processes = [RuntimeProcess(1, "p", ()), RuntimeProcess(2, "p", ())]
    with patch("builder_ii.lifecycle.candidate.runtime_control.find_runtime_processes", return_value=processes):
        with pytest.raises(RuntimeError, match="more than one"):
            ensure_warm_backend(mock_settings)


def test_unhealthy_resident_requires_governed_reset(mock_settings) -> None:
    process = RuntimeProcess(123, "python", ("python", "-m", "mlx_lm.server"))
    with (
        patch("builder_ii.lifecycle.candidate.runtime_control.find_runtime_processes", return_value=[process]),
        patch("builder_ii.routing.backends.check_health", return_value=(False, "down")),
        patch("builder_ii.routing.backends.start_backend_process") as start,
    ):
        with pytest.raises(RuntimeError, match="governed reset"):
            ensure_warm_backend(mock_settings)
    start.assert_not_called()
