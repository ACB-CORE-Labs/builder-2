from subprocess import CompletedProcess

from builder_ii.lifecycle.candidate.runtime_control import RuntimeProcess, _candidate_listener_pids


class SettingsStub:
    port = 8080


def test_runtime_process_command_joins_command_parts() -> None:
    item = RuntimeProcess(pid=123, name="python", cmdline=("python", "-m", "module"))

    assert item.command == "python -m module"


def test_runtime_process_command_uses_name_when_command_is_empty() -> None:
    item = RuntimeProcess(pid=123, name="python", cmdline=())

    assert item.command == "python"


def test_candidate_listener_pids_parse_lsof_output(monkeypatch) -> None:
    def fake_run(command, check, capture_output, text):
        return CompletedProcess(command, 0, stdout="p123\np456\n", stderr="")

    monkeypatch.setattr("builder_ii.runtime_control.subprocess.run", fake_run)

    assert _candidate_listener_pids(SettingsStub()) == {123, 456}
