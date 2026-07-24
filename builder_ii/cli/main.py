from __future__ import annotations

import hashlib
import importlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional

import click
import typer
from rich.console import Console
from rich.table import Table
from typer.core import TyperGroup

from builder_ii.cli.plain_stdout import echo_stdout


class LazyGroup(TyperGroup):
    """Custom Click Group to lazy-load subcommands on-demand, dropping startup latency to near-zero."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._lazy_commands = {}
        self.add_lazy_command("builder_ii.cli.workflow_cli", "workflow_app", "workflow")
        self.add_lazy_command("builder_ii.cli.ledger_cli", "ledger_app", "ledger")
        self.add_lazy_command("builder_ii.cli.tools_cli", "tools_app", "tools")
        self.add_lazy_command("builder_ii.cli.mcp_cli", "mcp_app", "mcp")
        self.add_lazy_command("builder_ii.cli.chain_cli", "chain_app", "chain")
        self.add_lazy_command("builder_ii.cli.tui_inspection_cli", "inspect_app", "inspect")
        self.add_lazy_command("builder_ii.cli.tui_cli", "tui_app", "tui")
        self.add_lazy_command("builder_ii.cli.orchestration_cli", "orchestration_app", "orchestration")

    def add_lazy_command(self, module_path: str, attr_name: str, name: str):
        self._lazy_commands[name] = (module_path, attr_name)

    def list_commands(self, ctx):
        return sorted(list(self.commands.keys()) + list(self._lazy_commands.keys()))

    def get_command(self, ctx, name):
        if name in self.commands:
            return self.commands[name]

        if name in self._lazy_commands:
            module_path, attr_name = self._lazy_commands[name]
            try:
                module = importlib.import_module(module_path)
                sub_app = getattr(module, attr_name)
                click_command = typer.main.get_command(sub_app)
                self.add_command(click_command, name=name)
                return click_command
            except Exception as e:
                click.secho(f"Error loading subcommand '{name}': {e}", fg="red", err=True)
                return None
        return None


app = typer.Typer(
    name="builder",
    cls=LazyGroup,
    help="builder-II — Generic governed platform for local agent-assisted development.",
    no_args_is_help=True,
)
console = Console()


def _as_answer(value: object) -> str | None:
    """Render a resolved config value as the string a wizard answer is.

    Config resolution yields `bool` for `allow_artifact_root_inside_target` and `Path` for
    `artifact_root`; a wizard answer is always a string, and `BOOL_ANSWERS` is `("false", "true")`.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def _as_bool(answer: str) -> bool:
    """The inverse, for the one decision the onboarding pipeline wants typed."""
    return answer.strip().lower() == "true"


def _backend_ready_for_selected_model(settings) -> tuple[bool, str]:
    from builder_ii.routing.backends import check_health, check_serves_active_model

    ok, msg = check_health(settings)
    if not ok:
        return False, msg

    model_ok, model_msg = check_serves_active_model(settings)
    if not model_ok:
        return False, model_msg

    return True, f"{msg}; {model_msg}"


def _ensure_backend(settings, no_backend: bool) -> None:
    if no_backend:
        return

    from builder_ii.routing.backends import check_health, check_serves_active_model, list_start_command

    health_ok, health_msg = check_health(settings)
    if health_ok:
        model_ok, model_msg = check_serves_active_model(settings)
        if model_ok:
            console.print(f"[green]Backend ready[/] {health_msg}; {model_msg}")
            return
        console.print(f"[red]Backend model mismatch[/] {model_msg}")
        raise typer.Exit(1)

    console.print(f"[yellow]Starting backend[/] ({health_msg})")
    cmd = list(list_start_command(settings))
    console.print(f"  {' '.join(cmd)}")
    subprocess.Popen(cmd)
    last_msg = health_msg
    for _ in range(90):
        time.sleep(2)
        ready, msg = _backend_ready_for_selected_model(settings)
        last_msg = msg
        if ready:
            console.print(f"[green]Backend ready[/] {msg}")
            return
    console.print(f"[red]Backend did not become ready in 180s[/] {last_msg}")
    raise typer.Exit(1)


@app.command("setup")
def setup() -> None:
    """Legacy compatibility wrapper for the governed R1 setup path."""
    from builder_ii.adapters.goose.goose_setup import render_legacy_setup_redirect_text
    from builder_ii.core.config import load_settings

    settings = load_settings()
    echo_stdout(render_legacy_setup_redirect_text(settings))
    raise typer.Exit(1)


@app.command("stratum")
def stratum(
    sandbox: bool = typer.Option(
        False,
        "--sandbox",
        help="Launch STRATUM with strict execution confinement (read-only composition).",
    ),
    no_guide: bool = typer.Option(
        False,
        "--no-guide",
        help="Skip first-session walkthrough auto-open (also: STRATUM_SKIP_GUIDE=1).",
    ),
    guide: bool = typer.Option(
        False,
        "--guide",
        help="Force first-session walkthrough open even if previously dismissed.",
    ),
) -> None:
    """Launch STRATUM: The Builder-II Operator Console."""
    from builder_ii.governance.authority import enforce_command_authority

    enforce_command_authority("builder stratum")

    try:
        from builder_ii.tui.app import StratumApp, run_tui

        has_tui = True
    except ImportError:
        has_tui = False

    if not has_tui:
        console.print("[red]TUI dependencies not found.[/] Run [bold]uv sync[/] to install textual.")
        raise typer.Exit(1)

    console.print(
        "[bold cyan]STRATUM[/] — builder-II operator console\n"
        "[yellow]GOVERNANCE NOTICE: planned ≠ executed ≠ verified ≠ promoted[/]\n"
        "[dim]Tip: [bold]uv run builder-stratum[/] is the short form (same gate).[/]\n"
        "[dim]observe + compose only · docs/STRATUM.md · H help · 0 walkthrough[/]"
    )
    if guide and no_guide:
        console.print("[red]--guide and --no-guide are mutually exclusive.[/]")
        raise typer.Exit(1)
    tui_app = StratumApp(show_guide=guide or None, skip_guide=no_guide)
    raise typer.Exit(run_tui(tui_app))


@app.command("onboarding")
def onboarding(
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", help="Output directory for onboarding artifacts."),
    root: Path = typer.Option(Path.cwd(), "--root", help="Project root for configuration resolution."),
    target_profile: Optional[str] = typer.Option(None, "--target-profile", help="Target profile override."),
    model_backend: Optional[str] = typer.Option(None, "--model-backend", help="Model backend override."),
    model_alias: Optional[str] = typer.Option(None, "--model-alias", help="Model alias override."),
) -> None:
    """Interactive guided onboarding wizard flow (delegates to builder-setup wizard)."""
    from builder_ii.cli.setup_cli import setup_wizard

    setup_wizard(
        output_dir=output_dir,
        root=root,
        target_profile=target_profile,
        model_backend=model_backend,
        model_alias=model_alias,
    )


@app.command("init")
def init(
    output_dir: Optional[Path] = typer.Option(
        None, "--output-dir", help="Output directory for onboarding artifacts (prompted when omitted)."
    ),
    root: Path = typer.Option(Path.cwd(), "--root", help="Project root for configuration resolution."),
    config_file: Optional[Path] = typer.Option(None, "--config-file", help="Optional builder config file path."),
    target_repo: Optional[Path] = typer.Option(None, "--target-repo", help="Target repository override."),
    target_profile: Optional[str] = typer.Option(
        None, "--target-profile", help="Target profile (prompted when omitted; registry-validated)."
    ),
    model_backend: Optional[str] = typer.Option(
        None, "--model-backend", help="Model backend (prompted when omitted; registry-validated)."
    ),
    model_alias: Optional[str] = typer.Option(
        None, "--model-alias", help="Model alias (prompted when omitted; registry-validated)."
    ),
    agent_profile: Optional[str] = typer.Option(
        None, "--agent-profile", help="Agent profile (prompted when omitted; registry-validated)."
    ),
    verification_profile: Optional[str] = typer.Option(
        None, "--verification-profile", help="Verification profile (prompted when omitted; registry-validated)."
    ),
    artifact_root: Optional[Path] = typer.Option(
        None, "--artifact-root", help="Platform artifact root (prompted when omitted)."
    ),
    runtime_mode: Optional[str] = typer.Option(
        None, "--runtime-mode", help="Runtime mode (prompted when omitted; registry-validated)."
    ),
    allow_artifact_root_inside_target: Optional[bool] = typer.Option(
        None,
        "--allow-artifact-root-inside-target/--no-allow-artifact-root-inside-target",
        help="Allow artifact root inside target source paths (prompted when omitted).",
    ),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        help="Never prompt; missing decisions take their resolved documented defaults.",
    ),
) -> None:
    """Unified governed onboarding orchestrator: emits plan/overlay/snapshot/intent artifacts, never applies.

    Wizard v2 (Ladder 5) prompts all nine onboarding decisions, each registry-validated, with the
    precedence the original four always had: flag > prompt > resolved default. Five of the nine
    used to be resolved silently and echoed afterwards — including where artifacts land and
    whether a runtime may start. The apply step is a separately invoked, digest-confirmed command
    (builder-setup apply) — init renders digests but never harvests the confirmation.
    """
    from builder_ii.core.config_sources import resolve_config_sources
    from builder_ii.lifecycle.setup.init_decisions import (
        DEFAULT_INIT_OUTPUT_DIR,
        TARGET_PROFILE_DECISION,
        decisions,
        init_wizard_step_definitions,
        validate_decision_value,
    )
    from builder_ii.lifecycle.setup.setup_onboarding import run_onboarding_pipeline
    from builder_ii.lifecycle.setup.wizard_framework import WizardAborted, WizardEngine, run_typer_prompt_loop

    resolution = resolve_config_sources(project_root=root, builder_config_file=config_file)
    if resolution.errors:
        for error in resolution.errors:
            console.print(f"[red]config resolution error:[/] {error}")
        raise typer.Exit(1)

    # Every decision's flag answer, keyed by decision name. One entry per decision, no exceptions:
    # a decision whose flag is missing from this map would silently ignore the flag.
    flag_answers: dict[str, str | None] = {
        "output_dir": str(output_dir) if output_dir is not None else None,
        "target_profile": target_profile,
        "model_backend": model_backend,
        "model_alias": model_alias,
        "agent_profile": agent_profile,
        "verification_profile": verification_profile,
        "artifact_root": str(artifact_root) if artifact_root is not None else None,
        "runtime_mode": runtime_mode,
        "allow_artifact_root_inside_target": (
            None if allow_artifact_root_inside_target is None else str(allow_artifact_root_inside_target).lower()
        ),
    }
    missing_flags = {d.name for d in decisions()} - set(flag_answers)
    if missing_flags:  # pragma: no cover - pinned by tests/test_wizard_v2.py
        raise RuntimeError(f"decisions with no flag wired into `builder init`: {sorted(missing_flags)}")

    # Registry-validate every flag-provided answer up front — fail closed, never free text.
    for decision_name, provided in flag_answers.items():
        if provided is None:
            continue
        errors = validate_decision_value(decision_name, provided)
        if errors:
            for error in errors:
                console.print(f"[red]invalid decision:[/] {error}")
            raise typer.Exit(2)

    # All nine decisions: flag > interactive registry-validated prompt > resolved default.
    # Prompt text renders from the live registries at prompt time, answers are registry-validated
    # with the same three-attempt boundary, and the observable behavior is pinned by
    # tests/test_wizard_characterization.py (run against unmodified main before PR-1).
    #
    # `output_dir` alone has no config-resolution field: its default is a constant.
    defaults: dict[str, str | None] = {
        decision.name: (
            DEFAULT_INIT_OUTPUT_DIR
            if decision.resolution_field is None
            else _as_answer(resolution.value(decision.resolution_field))
        )
        for decision in decisions()
    }

    # `agent_profile` and `verification_profile` are resolved *from* the target profile, and the
    # resolution above ran before the operator picked one. Re-resolve them against the target
    # actually chosen, or `--target-profile generic` shows -- and on Enter records -- `builder`'s
    # `patch_planner` / `builder_full`, in a plan whose own verification profile then declares
    # itself incompatible with the target beside it.
    _field_by_decision = {d.name: d.resolution_field for d in decisions()}
    # The override key is the target decision's own resolution field, never the decision's name.
    # `resolve_config_sources` ignores an unrecognised key in silence, so a transcribed one is a
    # re-resolution that quietly changes nothing and hands back the same stale default.
    _target_field = _field_by_decision[TARGET_PROFILE_DECISION]

    def _default_for_target(decision_name: str, chosen_target: str) -> str | None:
        field = _field_by_decision[decision_name]
        if field is None:  # pragma: no cover - only `output_dir` lacks a field, and it is not dependent
            return defaults[decision_name]
        retargeted = resolve_config_sources(
            project_root=root,
            builder_config_file=config_file,
            cli_overrides={_target_field: chosen_target},
        )
        return _as_answer(retargeted.value(field))

    engine = WizardEngine(steps=init_wizard_step_definitions(defaults, _default_for_target))
    for decision_name, provided in flag_answers.items():
        if provided is not None:
            engine.preanswer(decision_name, provided)

    if non_interactive:
        # In step order, so a later step's `default_from` sees the earlier answers it depends on.
        # Membership, not truthiness: an answer of "" is an answer, and must not fall to a default.
        chosen = {}
        for step in engine.steps:
            chosen[step.id] = engine.answers[step.id] if step.id in engine.answers else step.resolved_default(chosen)
        prompted_any = False
    else:
        try:
            chosen, prompted_any = run_typer_prompt_loop(
                engine,
                prompt_fn=typer.prompt,
                invalid_echo=lambda error: console.print(f"[red]invalid answer:[/] {error}"),
                max_attempts=3,
            )
        except WizardAborted:
            console.print("[red]no valid answer after 3 attempts; aborting without writing artifacts[/]")
            raise typer.Exit(2) from None

    chosen_artifact_root = chosen.get("artifact_root")
    result = run_onboarding_pipeline(
        output_dir=Path(chosen["output_dir"]),
        onboarding_mode="wizard" if prompted_any else "init",
        root=root,
        config_file=config_file,
        target_repo=target_repo,
        artifact_root=Path(chosen_artifact_root) if chosen_artifact_root else None,
        target_profile=chosen["target_profile"],
        agent_profile=chosen["agent_profile"],
        verification_profile=chosen["verification_profile"],
        model_backend=chosen["model_backend"],
        model_alias=chosen["model_alias"],
        runtime_mode=chosen["runtime_mode"],
        allow_artifact_root_inside_target=_as_bool(chosen["allow_artifact_root_inside_target"]),
    )
    if not result.valid:
        console.out(json.dumps(result.summary_dict(), indent=2, sort_keys=True) + "\n", end="")
        raise typer.Exit(1)

    console.out("Onboarding plan generated (no setup was applied).\n\n", end="")
    console.out("Selected decisions:\n", end="")
    for decision in decisions():
        console.out(f"  {decision.name}: {chosen[decision.name]}  (override: {decision.override_flag})\n", end="")
    console.out("\nArtifacts:\n", end="")
    console.out(f"  setup plan:        {result.setup_plan_path}\n", end="")
    console.out(f"  overlay plan:      {result.setup_overlay_path}\n", end="")
    console.out(f"  rollback snapshot: {result.rollback_snapshot_path}\n", end="")
    console.out(f"  intent report:     {result.onboarding_intent_path}\n", end="")
    console.out("\nDigests:\n", end="")
    console.out(f"  setup plan digest:   {result.setup_plan['plan_digest']}\n", end="")
    console.out(f"  overlay plan digest: {result.overlay_plan['overlay_plan_digest']}\n", end="")
    console.out(f"  rollback snapshot:   {result.rollback_snapshot['snapshot_id']}\n", end="")
    console.out("\nNext (separately invoked apply step; init never applies):\n", end="")
    console.out(f"  1. Review the overlay plan: {result.setup_overlay_path}\n", end="")
    console.out(
        f"  2. builder-setup apply {result.setup_overlay_path} "
        f"--rollback-snapshot {result.rollback_snapshot_path} "
        f"--output {result.output_dir / 'setup-receipt.json'}\n",
        end="",
    )
    console.out(
        "     apply prints the overlay digest and asks you to type its 4-character prefix —\n"
        "     the same digest-prefix confirmation grammar as builder-hitl approvals.\n"
        "     (Scripted flows may instead pass --approve-digest with the full overlay digest.)\n",
        end="",
    )


@app.command("pull")
def pull(
    tier: str = typer.Option("recommended", "--tier", "-t", help="recommended|fast|primary|all-safe|status|legacy"),
) -> None:
    """Download/cache local models. Prefer scripts/pull-roster.sh for MLX-LM."""
    from builder_ii.adapters.goose.goose_launcher import pull_models
    from builder_ii.core.config import load_settings
    from builder_ii.governance.authority import enforce_command_authority

    enforce_command_authority("builder pull", requested_effects=("external_tool", "state_write"))
    settings = load_settings()
    script = settings.project_root / "scripts" / "pull-roster.sh"
    if script.exists() and tier != "legacy":
        proc = subprocess.run(["bash", str(script), tier])
        raise typer.Exit(proc.returncode)
    for line in pull_models(settings):
        console.print(line)


@app.command("start")
def start(
    mode: str = typer.Option("orchestrator", "--mode", "-m", help="orchestrator|quick|deep|coding"),
    task_hint: Optional[str] = typer.Option(
        None, "--task", "--task-hint", help="Free-text task used to choose the M1-safe model alias for this session"
    ),
    model_alias: Optional[str] = typer.Option(
        None, "--model", help="Explicit model alias override; see `builder models`"
    ),
    resume: bool = typer.Option(False, "--resume", "-r"),
    no_backend: bool = typer.Option(False, "--no-backend"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Goose session name"),
    wrapper_plan: Optional[Path] = typer.Option(None, "--wrapper-plan", help="Path to governed Goose wrapper plan artifact"),
    from_last: bool = typer.Option(False, "--from-last", help="Auto-resolve wrapper-plan from the last generated artifact"),
) -> None:
    """Start MLX backend + Goose session with governed CORE recipes."""
    from builder_ii.adapters.goose.goose_launcher import goose_status, launch_goose_session
    from builder_ii.core.config import load_settings, normalize_model_alias
    from builder_ii.routing.model_router import SESSION_MODES, explain_plan, plan_session

    if mode not in SESSION_MODES:
        console.print(f"mode must be one of {SESSION_MODES}")
        raise typer.Exit(1)

    session = plan_session(mode, task_hint or "")
    selected_alias = normalize_model_alias(model_alias or session.model_alias, tier_fallback=session.model_tier)

    os.environ["CORE_AGENT_MODEL_TIER"] = session.model_tier
    os.environ["CORE_AGENT_MODEL_ALIAS"] = selected_alias
    settings = load_settings()

    console.print("[bold]Builder routing[/]")
    console.print(explain_plan(session))
    if selected_alias != session.model_alias:
        console.print(f"Model override : {selected_alias}")
    console.print(
        f"[bold]Builder[/] mode={session.mode} alias={settings.model_alias} tier={session.model_tier} backend={settings.backend} model={settings.active_model_id}"
    )
    console.print(goose_status())

    _ensure_backend(settings, no_backend)

    console.print(f"CORE repo: {settings.target_repo}")
    console.print("Slash commands: /explore /implement /review /verify /handoff /plan /coding /platform")
    console.print("Skills: core-governed-coding, core-verify-loop, core-pre-edit-sweep")
    session_name = name or f"builder_{int(time.time())}"

    approval_artifact = None
    if wrapper_plan or from_last:
        from builder_ii.cli._chain_resolve import resolve_path_or_last
        resolved = resolve_path_or_last(wrapper_plan, from_last, "builder_ii.goose_wrapper_plan", "wrapper-plan")
        approval_artifact = str(resolved)

    proc = launch_goose_session(
        settings,
        resume=resume,
        session=session,
        name=session_name,
        wrapper_plan_path=approval_artifact
    )
    proc.wait()

    try:
        transcript_path_obj = settings.target_repo / ".builder" / "artifacts" / f"{session_name}.jsonl"
        transcript_path_obj.parent.mkdir(parents=True, exist_ok=True)
        transcript_path = str(transcript_path_obj)
        import subprocess
        subprocess.run(["goose", "session", "export", "--name", session_name, "--format", "json", "--output", transcript_path], check=False)

        hasher = hashlib.sha256()
        with open(transcript_path_obj, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(chunk)
        transcript_digest = hasher.hexdigest()

        from builder_ii.governance.ledger.event_ledger import write_event_record, create_event_record
        event = create_event_record(
            event_id=session_name + "_close",
            session_id=session_name,
            sequence=0,
            event_type="goose_session_closed",
            stage="orchestration",
            subject_refs=[{"kind": "builder_ii.goose_transcript", "path": transcript_path, "sha256": transcript_digest, "role": "transcript"}],
            command_surface="builder_ii",
            policy_snapshot_ref={"kind": "null"},
        )
        ledger_path = settings.target_repo / ".builder" / "artifacts" / "event_ledger.jsonl"
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        write_event_record(event, ledger_path / f"{event['event_id']}.json")
    except Exception as exc:
        console.print(f"[yellow]Could not export session transcript or record ledger event:[/] {exc}")


@app.command("ask")
def ask(
    prompt: str = typer.Option(..., "--prompt", "-p", help="Prompt for the selected local model"),
    model_alias: Optional[str] = typer.Option(None, "--model", help="Explicit model alias; see `builder models`"),
    system_prompt: str = typer.Option(
        "You are a local builder-II review assistant. Answer from the prompt only and state uncertainty clearly.",
        "--system",
    ),
    max_tokens: int = typer.Option(512, "--max-tokens", min=1, max=4096),
    timeout: float = typer.Option(120.0, "--timeout", min=1.0),
    no_backend: bool = typer.Option(False, "--no-backend"),
) -> None:
    """Ask the selected local model directly through /v1/chat/completions."""
    from builder_ii.core.config import load_settings, normalize_model_alias
    from builder_ii.governance.authority import enforce_command_authority
    from builder_ii.routing.model_client_registry import create_model_client_registry
    from builder_ii.routing.model_execution_gateway import ModelExecutionGateway
    from builder_ii.routing.model_router import tier_for_alias
    from builder_ii.routing.model_routing_policy import create_model_execution_policy

    enforce_command_authority("builder ask", requested_effects=("model_execution", "artifact_write"))
    if model_alias:
        selected_alias = normalize_model_alias(model_alias)
        os.environ["CORE_AGENT_MODEL_ALIAS"] = selected_alias
        os.environ["CORE_AGENT_MODEL_TIER"] = tier_for_alias(selected_alias)

    settings = load_settings()
    console.print(
        f"[bold]Builder ask[/] alias={settings.model_alias} backend={settings.backend} model={settings.active_model_id}"
    )
    _ensure_backend(settings, no_backend)

    registry = create_model_client_registry()
    active_model = settings.active_model_id
    active_client = None
    for client in registry["clients"]:
        if client.get("model_id") == active_model:
            client["enabled"] = True
            active_client = client
            break
    if active_client is None:
        console.print(f"[red]Active model is not registered[/] {active_model}")
        raise typer.Exit(1)

    recommendation = {
        "kind": "builder_ii.model_routing_recommendation",
        "recommended_candidates": [
            {
                "model_id": active_model,
                "provider_id": active_client.get("provider_id"),
                "client_id": active_client.get("client_id"),
                "risk_classification": active_client.get("risk_classification"),
            }
        ],
    }
    execution_policy = create_model_execution_policy(recommendation, max_tokens=max_tokens)
    ask_root = settings.project_root / ".builder" / "ask"
    session_id = hashlib.sha256(f"{time.time_ns()}:{prompt}".encode("utf-8")).hexdigest()[:16]
    envelope_path = ask_root / f"{session_id}.envelope.json"
    receipt_path = ask_root / f"{session_id}.receipt.json"

    try:
        _envelope, receipt, _debited = ModelExecutionGateway(settings, registry, execution_policy).run_model_call(
            model_id=active_model,
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=None,
            envelope_path=envelope_path,
            receipt_path=receipt_path,
        )
    except Exception as exc:
        console.print(f"[red]Governed ask failed[/] {exc}")
        raise typer.Exit(1)
    console.print(receipt.get("response_text", ""))


@app.command("verify")
def verify(
    module: Optional[str] = typer.Argument(None),
    suite: Optional[str] = typer.Option(None, "--suite", "-s"),
    fail_fast: bool = typer.Option(False, "--fail-fast", "-x"),
) -> None:
    """Run CORE verification harness."""
    from builder_ii.core.config import load_settings
    from builder_ii.core.harness import format_verify_report, run_verification
    from builder_ii.governance.authority import enforce_command_authority

    enforce_command_authority("builder verify", requested_effects=("readonly_subprocess", "external_tool"))
    settings = load_settings()
    result = run_verification(settings, module=module, suite=suite, fail_fast=fail_fast)
    console.print(format_verify_report(result))
    raise typer.Exit(0 if result.passed else 1)


@app.command("benchmark")
def benchmark(output: Optional[Path] = typer.Option(None, "--output", "-o")) -> None:
    """Benchmark TTFT, tool-calling, compliance, memory."""
    from builder_ii.core.config import load_settings
    from builder_ii.governance.authority import enforce_command_authority
    from builder_ii.validation.benchmark import format_benchmark_report, run_benchmark, write_benchmark_report

    effects = ("model_execution", "external_tool") + (("artifact_write",) if output else ())
    enforce_command_authority("builder benchmark", requested_effects=effects)
    settings = load_settings()
    report = run_benchmark(settings)
    console.print(format_benchmark_report(report))
    if output:
        write_benchmark_report(report, output)
    raise typer.Exit(0)


@app.command("capabilities")
def capabilities(chat: bool = typer.Option(False, "--chat", help="Run a live /v1/chat/completions smoke")) -> None:
    """Check local model capability gates without modifying CORE."""
    from builder_ii.core.config import load_settings
    from builder_ii.governance.authority import enforce_command_authority
    from builder_ii.governance.authority.capabilities import capability_gates

    effects = ("external_tool",) + (("model_execution",) if chat else ())
    enforce_command_authority("builder capabilities", requested_effects=effects)
    settings = load_settings()
    table = Table("Gate", "Result", "Details")
    gates = capability_gates(settings, run_chat_smoke=chat)
    for gate in gates:
        table.add_row(gate.name, gate.result, gate.details)
    console.print(table)
    raise typer.Exit(1 if any(gate.result == "FAIL" for gate in gates) else 0)


@app.command("switch-model")
def switch_model(
    alias: str = typer.Argument(..., help="Model alias or legacy tier; run `builder models`"),
    backend: Optional[str] = typer.Option(None, "--backend", "-b"),
) -> None:
    """Print .env lines to switch model alias/tier. Restart backend after."""
    from builder_ii.core.config import BACKENDS, MODEL_TIERS, normalize_model_alias
    from builder_ii.governance.authority import enforce_command_authority

    enforce_command_authority("builder switch-model")
    if alias in MODEL_TIERS:
        normalized = normalize_model_alias(None, tier_fallback=alias)
        tier = alias
    else:
        normalized = normalize_model_alias(alias)
        tier = "fast" if normalized in {"phi-reasoning", "gemma-fast"} else "primary"
    if backend and backend not in BACKENDS:
        console.print(f"backend must be one of {BACKENDS}")
        raise typer.Exit(1)
    lines = [f"CORE_AGENT_MODEL_ALIAS={normalized}", f"CORE_AGENT_MODEL_TIER={tier}"]
    if backend:
        lines.append(f"CORE_AGENT_BACKEND={backend}")
    lines.append("# Then: builder start --task 'describe the work'  (or restart backend/session)")
    console.print("\n".join(lines))


@app.command("models")
def models() -> None:
    """Show the configured model roster and cache status."""
    from builder_ii.core.config import load_settings
    from builder_ii.core.models import model_definitions, model_status_report
    from builder_ii.governance.authority import enforce_command_authority

    enforce_command_authority("builder models", requested_effects=("readonly_subprocess",))
    settings = load_settings()
    status_by_alias = {m.alias: m for m in model_status_report(settings)}
    table = Table("Alias", "Tier", "Policy", "Repo", "Cache", "Expected", "Note")
    for definition in model_definitions(settings):
        status = status_by_alias[definition.alias]
        cache = "COMPLETE" if status.likely_complete else ("PARTIAL" if status.cache_dir else "MISSING")
        if status.has_incomplete:
            cache += "/RESUMABLE"
        table.add_row(
            definition.alias,
            definition.tier,
            definition.policy,
            definition.hf_repo,
            f"{cache} {status.size_gb}GB",
            f"~{definition.expected_gb}GB",
            definition.note,
        )
    console.print(table)
    console.print("\nDownload: bash scripts/pull-roster.sh recommended | alias <name> | all-safe | candidates")


@app.command("doctor")
def doctor() -> None:
    """Run a local platform readiness check without editing CORE."""
    from builder_ii.adapters.goose.goose_launcher import find_goose_binary, goose_status
    from builder_ii.adapters.goose.goose_recipe_validation import validate_recipes
    from builder_ii.core.config import load_settings
    from builder_ii.core.models import model_status_report
    from builder_ii.governance.authority import enforce_command_authority
    from builder_ii.governance.authority.compliance import run_compliance_checks
    from builder_ii.routing.backends import check_health, check_serves_active_model

    enforce_command_authority("builder doctor", requested_effects=("readonly_subprocess", "external_tool"))
    settings = load_settings()
    failures: list[str] = []
    table = Table("Check", "Result", "Details")

    core_ok = settings.target_repo.exists() and (settings.target_repo / ".git").exists()
    table.add_row("CORE repo", "PASS" if core_ok else "FAIL", str(settings.target_repo))
    if not core_ok:
        failures.append("CORE repo path is missing or not a git repository")

    goose_ok = find_goose_binary() is not None
    table.add_row("Goose", "PASS" if goose_ok else "WARN", goose_status())

    backend_ok, backend_msg = check_health(settings)
    table.add_row("Backend", "PASS" if backend_ok else "WARN", backend_msg)

    if backend_ok:
        served_ok, served_msg = check_serves_active_model(settings)
        table.add_row("Served model", "PASS" if served_ok else "WARN", served_msg)
    else:
        table.add_row("Served model", "WARN", "backend not running; run builder start to serve selected model")

    compliance = run_compliance_checks()
    compliance_ok = compliance.init_literals_ok and compliance.refusal_probe_ok
    table.add_row(
        "Compliance",
        "PASS" if compliance_ok else "FAIL",
        f"literals={compliance.init_literals_ok} refusal={compliance.refusal_probe_ok}",
    )
    if not compliance_ok:
        failures.append("governed prompt/refusal compliance check failed")

    recipe_results = validate_recipes(settings)
    if recipe_results:
        recipe_ok = all(ok for _path, ok, _msg in recipe_results)
        table.add_row(
            "Recipes",
            "PASS" if recipe_ok else "FAIL",
            f"{sum(ok for _p, ok, _m in recipe_results)}/{len(recipe_results)} valid",
        )
        if not recipe_ok:
            failures.append("one or more Goose recipes failed validation")
    else:
        table.add_row("Recipes", "WARN", "goose unavailable; validation skipped")

    active_status = next((m for m in model_status_report(settings) if m.alias == settings.model_alias), None)
    if active_status:
        model_ok = active_status.likely_complete
        table.add_row(
            "Active model",
            "PASS" if model_ok else "WARN",
            f"{settings.model_alias}: {active_status.size_gb}GB; {active_status.resume_hint}",
        )

    hf_bin = shutil.which("hf") or str(settings.project_root / ".venv" / "bin" / "hf")
    table.add_row("HF CLI", "PASS" if Path(hf_bin).exists() or shutil.which("hf") else "WARN", hf_bin)

    console.print(table)
    if failures:
        for failure in failures:
            console.print(f"[red]FAIL[/] {failure}")
        raise typer.Exit(1)
    raise typer.Exit(0)


@app.command("status")
def status() -> None:
    """Backend, Goose, compliance, recipe, and model status."""
    from builder_ii.adapters.goose.goose_launcher import goose_status
    from builder_ii.adapters.goose.goose_recipe_validation import validate_recipes
    from builder_ii.core.config import load_settings
    from builder_ii.core.models import model_status_report
    from builder_ii.governance.authority import enforce_command_authority
    from builder_ii.governance.authority.compliance import run_compliance_checks
    from builder_ii.routing.backends import check_health, check_serves_active_model

    enforce_command_authority("builder status", requested_effects=("readonly_subprocess", "external_tool"))
    settings = load_settings()
    ok, msg = check_health(settings)
    served_ok, served_msg = check_serves_active_model(settings) if ok else (False, "backend down")
    compliance = run_compliance_checks()
    console.print(
        f"backend={settings.backend} alias={settings.model_alias} tier={settings.model_tier} model={settings.active_model_id} url={settings.base_url}"
    )
    console.print(f"health: {'OK' if ok else 'DOWN'} — {msg}")
    console.print(f"served-model: {'OK' if served_ok else 'WARN'} — {served_msg}")
    console.print(goose_status())
    console.print(
        f"compliance: literals={'PASS' if compliance.init_literals_ok else 'FAIL'} refusal={'PASS' if compliance.refusal_probe_ok else 'FAIL'}"
    )
    validations = validate_recipes(settings)
    ok_count = sum(1 for _p, ok, _m in validations if ok)
    console.print(f"recipes: {ok_count}/{len(validations)} valid")
    for m in model_status_report(settings):
        flag = "COMPLETE" if m.likely_complete else ("PARTIAL" if m.cache_dir else "MISSING")
        inc = " (resumable)" if m.has_incomplete else ""
        active = " *active*" if m.alias == settings.model_alias else ""
        console.print(f"model {m.alias}: {flag} {m.size_gb}GB / ~{m.expected_gb}GB{inc}{active}")
        if not m.likely_complete:
            console.print(f"  → {m.resume_hint}")


@app.command("config")
def config_dump() -> None:
    """Print passive config and legacy setup reconciliation metadata as JSON."""
    from builder_ii.adapters.goose.goose_setup import legacy_setup_redirect_payload
    from builder_ii.core.config import load_settings
    from builder_ii.governance.authority import enforce_command_authority

    enforce_command_authority("builder config")
    settings = load_settings()
    payload = legacy_setup_redirect_payload(settings)
    payload["settings"] = {
        "project_root": str(settings.project_root),
        "target_repo": str(settings.target_repo),
        "backend": settings.backend,
        "model_alias": settings.model_alias,
        "model_tier": settings.model_tier,
        "active_model_id": settings.active_model_id,
    }
    echo_stdout(json.dumps(payload, indent=2) + "\n")


@app.command("init-prompt")
def init_prompt() -> None:
    """Print governed system prompt."""
    from builder_ii.governance.authority import enforce_command_authority
    from builder_ii.lifecycle.setup.init_content import CORE_INIT_SYSTEM_PROMPT, estimate_tokens

    enforce_command_authority("builder init-prompt")
    console.print(CORE_INIT_SYSTEM_PROMPT)
    console.print(f"\n# ~{estimate_tokens(CORE_INIT_SYSTEM_PROMPT)} tokens")


if __name__ == "__main__":
    app()
