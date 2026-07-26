"""``builder-govern`` -- inspect ratification points, grant/revoke standing delegations, audit them.

Output is plain stdout, not Rich. That is deliberate: this surface prints digests and file paths,
and Rich wraps to the terminal width, which on the CI runner broke a path across a line *inside*
the filename. A governance surface whose output changes shape with the console width is one whose
output cannot be pinned.

Granting is itself an exercise of authority, so ``grant-auto`` refuses to be quiet about it: it
prints what the point ratifies and what delegating it costs, then requires the operator to type
the point id back. ``--yes`` exists for scripted flows and is recorded in the ledger as the actor's
own choice -- there is no path here that creates a grant without naming who created it.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from builder_ii.cli.plain_stdout import echo_stdout
from builder_ii.governance.ledger.ratification_ledger import (
    EVENT_APPROVAL_MINTED,
    EVENT_GRANT_CREATED,
    EVENT_GRANT_REVOKED,
    EVENT_POLICY_SET,
    append_ratification_event,
    ledger_path,
    read_ratification_events,
    validate_ratification_ledger,
)
from builder_ii.governance.ratification_approvals import (
    APPROVAL_CONFIRMATION_PREFIX_LENGTH,
    DEFAULT_APPROVAL_TTL_SECONDS,
    build_ratification_approval,
    validate_ratification_approval_file,
    write_ratification_approval,
)
from builder_ii.governance.ratification_grants import (
    build_ratification_grant,
    build_ratification_revocation,
    consult_ratification_grant,
    load_grants,
    resolve_ratification_root,
    revoked_grant_digests,
    validate_ratification_grant_artifact,
    validate_ratification_grant_file,
    write_grant,
    write_revocation,
)
from builder_ii.governance.ratification_points import (
    RATIFICATION_POINTS,
    get_ratification_point,
    grant_eligibility,
)
from builder_ii.governance.ratification_policy import (
    build_ratification_policy,
    effective_level,
    load_policy,
    policy_path,
    validate_ratification_policy_artifact,
    validate_ratification_policy_file,
    write_policy,
)

govern_app = typer.Typer(
    name="builder-govern",
    help="Ratification points, standing grants, and the ratification audit ledger.",
    no_args_is_help=True,
)

_ROOT_OPTION = typer.Option(
    None,
    "--root",
    help="Ratification store root. Defaults to BUILDER_RATIFICATION_ROOT, then .builder/artifacts/ratification.",
)


@govern_app.command("list-points")
def list_points(root: Path | None = _ROOT_OPTION) -> None:
    """List every ratification point and whether a standing grant may satisfy it."""
    lines: list[str] = []
    for point in RATIFICATION_POINTS:
        eligibility = grant_eligibility(point)
        consultation = consult_ratification_grant(point.id, root=root)
        status = "GRANTABLE" if eligibility.eligible else "NOT GRANTABLE"
        held = "held" if consultation.satisfied else "none"
        lines.append(f"{point.id}")
        lines.append(f"  command:     {point.command}")
        lines.append(f"  kind:        {point.kind}")
        lines.append(f"  grantable:   {status} -- {eligibility.because}")
        lines.append(f"  grant:       {held}")
        lines.append(f"  ratifies:    {point.what_is_ratified}")
        lines.append(f"  if granted:  {point.consequence_of_auto}")
        lines.append("")
    echo_stdout("\n".join(lines))


@govern_app.command("grant-auto")
def grant_auto(
    point_id: str = typer.Argument(..., help="Ratification point id to delegate (see list-points)."),
    granted_by: str = typer.Option(..., "--granted-by", help="Who is delegating this confirmation."),
    assume_yes: bool = typer.Option(
        False, "--yes", help="Skip the typed confirmation (scripted flows). The grant still records --granted-by."
    ),
    root: Path | None = _ROOT_OPTION,
) -> None:
    """Delegate one named confirmation to a standing, revocable, ledgered grant."""
    point = get_ratification_point(point_id)
    if point is None:
        echo_stdout(
            f"no ratification point is registered as `{point_id}`\n"
            "run `builder-govern list-points` to see the registered points\n"
        )
        raise typer.Exit(1)

    eligibility = grant_eligibility(point)
    if not eligibility.eligible:
        echo_stdout(
            f"`{point_id}` cannot be delegated: {eligibility.because}\n"
            "no grant was written\n"
        )
        raise typer.Exit(1)

    echo_stdout(
        f"point:      {point.id}\n"
        f"command:    {point.command}\n"
        f"ratifies:   {point.what_is_ratified}\n"
        f"if granted: {point.consequence_of_auto}\n"
        "This delegation is recorded, attributed to you, and revocable with `builder-govern revoke`.\n"
    )
    if not assume_yes:
        echo_stdout(f"To delegate this confirmation, type the point id back: {point.id}\n")
        typed = typer.prompt("point id").strip()
        if typed != point.id:
            echo_stdout("Point id did not match. No grant was written.\n")
            raise typer.Exit(1)

    grant = build_ratification_grant(point, granted_by=granted_by)
    path = write_grant(grant, root=root)
    append_ratification_event(
        resolve_ratification_root(root),
        event=EVENT_GRANT_CREATED,
        point_id=point.id,
        command=point.command,
        actor=granted_by,
        because=eligibility.because,
        grant_digest=str(grant["grant_digest"]),
    )
    echo_stdout(f"grant written: {path}\ngrant_digest: {grant['grant_digest']}\n")


@govern_app.command("list-grants")
def list_grants(root: Path | None = _ROOT_OPTION) -> None:
    """List every grant on file, including invalid and revoked ones, and say why each is ignored."""
    revoked = revoked_grant_digests(root=root)
    grants = load_grants(root=root)
    if not grants:
        echo_stdout(f"no grants under {resolve_ratification_root(root)}\n")
        return
    lines: list[str] = []
    for grant, path in grants:
        errors = validate_ratification_grant_artifact(grant)
        digest = str(grant.get("grant_digest", ""))
        if errors:
            status = f"IGNORED (invalid: {errors[0]})"
        elif digest in revoked:
            status = "REVOKED"
        else:
            status = "ACTIVE"
        lines.append(f"{status}  {grant.get('point_id')}  {digest[:12]}")
        lines.append(f"  granted_by: {grant.get('granted_by')}  created_at: {grant.get('created_at')}")
        lines.append(f"  file:       {path}")
    echo_stdout("\n".join(lines) + "\n")


@govern_app.command("revoke")
def revoke(
    grant_digest: str = typer.Argument(..., help="Full grant_digest to revoke (see list-grants)."),
    revoked_by: str = typer.Option(..., "--revoked-by", help="Who is revoking this delegation."),
    reason: str = typer.Option(..., "--reason", help="Why the delegation is being withdrawn."),
    root: Path | None = _ROOT_OPTION,
) -> None:
    """Withdraw a standing grant. The grant file is kept; the revocation is a new artifact."""
    match = None
    for grant, _path in load_grants(root=root):
        if str(grant.get("grant_digest", "")) == grant_digest:
            match = grant
            break
    if match is None:
        echo_stdout(f"no grant on file with grant_digest {grant_digest}\nnothing was written\n")
        raise typer.Exit(1)

    revocation = build_ratification_revocation(match, revoked_by=revoked_by, reason=reason)
    path = write_revocation(revocation, root=root)
    append_ratification_event(
        resolve_ratification_root(root),
        event=EVENT_GRANT_REVOKED,
        point_id=str(match.get("point_id", "")),
        command=str(match.get("command", "")),
        actor=revoked_by,
        because=reason,
        grant_digest=grant_digest,
    )
    echo_stdout(f"revocation written: {path}\nrevocation_digest: {revocation['revocation_digest']}\n")


@govern_app.command("validate-grant")
def validate_grant(path: Path = typer.Argument(..., help="Ratification grant JSON artifact path.")) -> None:
    """Validate a ratification grant artifact (schema, kind, registered point, digest)."""
    errors = validate_ratification_grant_file(path)
    if errors:
        echo_stdout("\n".join(f"error: {error}" for error in errors) + "\n")
        raise typer.Exit(1)
    echo_stdout("ratification grant artifact is valid\n")


@govern_app.command("ledger")
def ledger(root: Path | None = _ROOT_OPTION) -> None:
    """Print the ratification audit ledger, one event per line."""
    store_root = resolve_ratification_root(root)
    events = read_ratification_events(store_root)
    if not events:
        echo_stdout(f"no ratification ledger at {ledger_path(store_root)}\n")
        return
    lines = [
        f"{event.get('seq'):>4}  {event.get('timestamp')}  {event.get('event'):<16} "
        f"{event.get('point_id')}  actor={event.get('actor')}  grant={str(event.get('grant_digest') or '-')[:12]}"
        for event in events
    ]
    echo_stdout("\n".join(lines) + "\n")


@govern_app.command("validate-ledger")
def validate_ledger(root: Path | None = _ROOT_OPTION) -> None:
    """Re-verify the ledger hash chain: recomputed digests, sequence and link continuity."""
    store_root = resolve_ratification_root(root)
    errors = validate_ratification_ledger(store_root)
    if errors:
        echo_stdout("\n".join(f"error: {error}" for error in errors) + "\n")
        raise typer.Exit(1)
    count = len(read_ratification_events(store_root))
    echo_stdout(f"ratification ledger chain intact across {count} event(s)\n")


def _trace_artifact(path: Path, *, root: Path | None) -> None:
    """Walk the authority chain backwards from a consuming artifact.

    Answers the receipt-first question -- "who authorised this, how, and is that authority still in
    force?" -- which the point-id form cannot, because a reader holding a receipt does not
    necessarily know which point produced it. That is why the receipt records `approval_point_id`.
    """
    try:
        artifact = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        echo_stdout(f"unreadable artifact: {exc}\n")
        raise typer.Exit(1) from exc
    if not isinstance(artifact, dict):
        echo_stdout("artifact must be a JSON object\n")
        raise typer.Exit(1)

    store_root = resolve_ratification_root(root)
    mode = artifact.get("approval_mode")
    point_id = artifact.get("approval_point_id")
    grant_digest = artifact.get("approval_grant_digest")
    approval_ref = artifact.get("approval_ref_digest")

    lines = [
        f"artifact:  {path}",
        f"kind:      {artifact.get('kind', '—')}",
        f"approved:  {mode or '—'}",
    ]
    if mode is None:
        lines.append("")
        lines.append("This artifact records no approval_mode, so there is no ratification chain to walk.")
        echo_stdout("\n".join(lines) + "\n")
        return

    if not point_id:
        lines.append("")
        lines.append(
            "This artifact records no approval_point_id. It predates receipt-level point recording, "
            "so the chain cannot be resolved from the receipt alone; trace the point id directly."
        )
        echo_stdout("\n".join(lines) + "\n")
        return

    lines.append(f"point:     {point_id}")
    decision = effective_level(str(point_id), root=store_root)
    lines.append(f"level now: {decision.level} -- {decision.because}")

    if grant_digest:
        revoked = revoked_grant_digests(root=store_root)
        match = next(
            (grant for grant, _p in load_grants(root=store_root) if grant.get("grant_digest") == grant_digest),
            None,
        )
        lines.append(f"grant:     {str(grant_digest)[:12]}")
        if match is None:
            lines.append("           NOT ON FILE -- the grant that satisfied this is no longer in the store")
        else:
            state = "REVOKED" if grant_digest in revoked else "still active"
            lines.append(f"           granted by {match.get('granted_by')} on {match.get('created_at')} ({state})")
    if approval_ref:
        lines.append(f"approval:  {str(approval_ref)[:12]} (digest-bound ratification approval)")
    if not grant_digest and not approval_ref:
        lines.append("satisfied:  by a human typing the digest prefix; no delegating artifact involved")

    events = [event for event in read_ratification_events(store_root) if event.get("point_id") == point_id]
    lines.append(f"history:   {len(events)} recorded event(s) for this point")
    for event in events:
        lines.append(
            f"  {event.get('seq'):>4}  {event.get('timestamp')}  {event.get('event'):<18} "
            f"actor={event.get('actor')}  grant={str(event.get('grant_digest') or '-')[:12]}"
        )
    echo_stdout("\n".join(lines) + "\n")


@govern_app.command("trace")
def trace(
    target: str = typer.Argument(..., help="Ratification point id, or a path to a consuming artifact."),
    root: Path | None = _ROOT_OPTION,
) -> None:
    """Trace a ratification point's history, or walk a consuming artifact's authority chain.

    Accepts either form because forensics starts from whichever one you are holding: an operator
    reviewing policy has a point id, and an auditor reviewing a change has a receipt.
    """
    candidate = Path(target)
    if candidate.is_file():
        _trace_artifact(candidate, root=root)
        return

    point_id = target
    point = get_ratification_point(point_id)
    if point is None:
        echo_stdout(
            f"no ratification point is registered as `{point_id}`, and no file exists at that path\n"
        )
        raise typer.Exit(1)

    store_root = resolve_ratification_root(root)
    eligibility = grant_eligibility(point)
    consultation = consult_ratification_grant(point_id, root=root)
    events = [event for event in read_ratification_events(store_root) if event.get("point_id") == point_id]

    lines = [
        f"point:     {point.id}",
        f"command:   {point.command}",
        f"kind:      {point.kind}",
        f"grantable: {eligibility.eligible} -- {eligibility.because}",
        f"now:       {'satisfied by grant' if consultation.satisfied else 'prompts'} -- {consultation.because}",
        f"history:   {len(events)} recorded event(s)",
    ]
    for event in events:
        lines.append(
            f"  {event.get('seq'):>4}  {event.get('timestamp')}  {event.get('event'):<16} "
            f"actor={event.get('actor')}  grant={str(event.get('grant_digest') or '-')[:12]}"
        )
    echo_stdout("\n".join(lines) + "\n")


@govern_app.command("policy-show")
def policy_show(root: Path | None = _ROOT_OPTION) -> None:
    """Show the ratification level in force for every point, and what put it there."""
    store_root = resolve_ratification_root(root)
    policy = load_policy(root=store_root)
    lines: list[str] = []
    if policy is None:
        lines.append(f"no policy file at {policy_path(store_root)}; registry baselines apply")
    else:
        errors = validate_ratification_policy_artifact(policy)
        lines.append(f"policy set by {policy.get('set_by')} on {policy.get('created_at')}")
        lines.append(f"allow_grants: {policy.get('allow_grants')}")
        for error in errors:
            lines.append(f"  WARNING: {error}")
    lines.append("")
    for point in RATIFICATION_POINTS:
        decision = effective_level(point.id, root=store_root)
        lines.append(f"{point.id}")
        lines.append(f"  level:    {decision.level}")
        lines.append(f"  because:  {decision.because}")
    echo_stdout("\n".join(lines) + "\n")


@govern_app.command("policy-set")
def policy_set(
    level_spec: list[str] = typer.Option(
        [],
        "--level",
        help="POINT_ID=LEVEL, repeatable. Levels: delegable, always_prompt, require_approval_artifact.",
    ),
    set_by: str = typer.Option(..., "--set-by", help="Who is setting this policy."),
    allow_grants: bool = typer.Option(
        True, "--allow-grants/--no-grants", help="Project-wide kill switch: --no-grants raises every point to always_prompt."
    ),
    root: Path | None = _ROOT_OPTION,
) -> None:
    """Replace the ratification policy. A policy may only tighten; weaker levels are refused."""
    levels: dict[str, str] = {}
    for spec in level_spec:
        if "=" not in spec:
            echo_stdout(f"malformed --level {spec!r}; expected POINT_ID=LEVEL\nnothing was written\n")
            raise typer.Exit(1)
        point_id, _, level = spec.partition("=")
        levels[point_id.strip()] = level.strip()

    policy = build_ratification_policy(levels, set_by=set_by, allow_grants=allow_grants)
    errors = validate_ratification_policy_artifact(policy)
    if errors:
        echo_stdout("\n".join(f"error: {error}" for error in errors) + "\nnothing was written\n")
        raise typer.Exit(1)

    store_root = resolve_ratification_root(root)
    path = write_policy(policy, root=store_root)
    append_ratification_event(
        store_root,
        event=EVENT_POLICY_SET,
        point_id="*",
        command="builder-govern policy-set",
        actor=set_by,
        because=f"allow_grants={allow_grants}; levels={sorted(levels.items())}",
        grant_digest=None,
    )
    echo_stdout(f"policy written: {path}\npolicy_digest: {policy['policy_digest']}\n")


@govern_app.command("policy-validate")
def policy_validate(
    path: Path | None = typer.Argument(None, help="Policy JSON path. Defaults to the store's policy file."),
    root: Path | None = _ROOT_OPTION,
) -> None:
    """Validate a ratification policy artifact, including its one-way (tighten-only) rule."""
    target = path if path is not None else policy_path(resolve_ratification_root(root))
    errors = validate_ratification_policy_file(target)
    if errors:
        echo_stdout("\n".join(f"error: {error}" for error in errors) + "\n")
        raise typer.Exit(1)
    echo_stdout("ratification policy artifact is valid\n")


@govern_app.command("approve")
def approve(
    point_id: str = typer.Argument(..., help="Ratification point id this approval is for."),
    subject_digest: str = typer.Option(..., "--digest", help="Exact subject digest being approved."),
    approved_by: str = typer.Option(..., "--approved-by", help="Who is approving."),
    output: Path = typer.Option(..., "--output", "-o", help="Required explicit approval artifact output path."),
    ttl_seconds: int = typer.Option(
        DEFAULT_APPROVAL_TTL_SECONDS, "--ttl-seconds", help="How long this approval stays usable."
    ),
    root: Path | None = _ROOT_OPTION,
) -> None:
    """Mint a digest-bound approval artifact by typing the subject digest prefix back.

    There is deliberately no `--yes`: this artifact is evidence a human decided, so the only way to
    produce one is for a human to transcribe the digest at an interactive prompt.
    """
    point = get_ratification_point(point_id)
    if point is None:
        echo_stdout(f"no ratification point is registered as `{point_id}`\nnothing was written\n")
        raise typer.Exit(1)
    if not subject_digest:
        echo_stdout("--digest must name the exact subject digest being approved\nnothing was written\n")
        raise typer.Exit(1)

    expected = subject_digest[:APPROVAL_CONFIRMATION_PREFIX_LENGTH]
    echo_stdout(
        f"point:   {point.id}\n"
        f"command: {point.command}\n"
        f"subject: {subject_digest}\n"
        f"To approve, type the first {APPROVAL_CONFIRMATION_PREFIX_LENGTH} characters of the subject digest.\n"
    )
    typed = typer.prompt("digest prefix").strip()
    if typed != expected:
        echo_stdout("Prefix did not match. No approval was written.\n")
        raise typer.Exit(1)

    artifact = build_ratification_approval(
        point,
        subject_digest=subject_digest,
        approved_by=approved_by,
        confirmed_digest_prefix=typed,
        ttl_seconds=ttl_seconds,
    )
    write_ratification_approval(artifact, output)
    store_root = resolve_ratification_root(root)
    if store_root.is_dir():
        append_ratification_event(
            store_root,
            event=EVENT_APPROVAL_MINTED,
            point_id=point.id,
            command=point.command,
            actor=approved_by,
            because=f"approved subject {subject_digest[:12]}",
            grant_digest=None,
        )
    echo_stdout(f"approval written: {output}\napproval_digest: {artifact['approval_digest']}\n")


@govern_app.command("validate-approval")
def validate_approval(path: Path = typer.Argument(..., help="Ratification approval JSON artifact path.")) -> None:
    """Validate a ratification approval artifact (schema, point, digest binding)."""
    errors = validate_ratification_approval_file(path)
    if errors:
        echo_stdout("\n".join(f"error: {error}" for error in errors) + "\n")
        raise typer.Exit(1)
    echo_stdout("ratification approval artifact is valid\n")


@govern_app.command("consult")
def consult(
    point_id: str = typer.Argument(..., help="Ratification point id to consult."),
    root: Path | None = _ROOT_OPTION,
) -> None:
    """Ask whether a standing grant satisfies a point right now, as JSON. Reads only."""
    consultation = consult_ratification_grant(point_id, root=root)
    echo_stdout(
        json.dumps(
            {
                "point_id": consultation.point_id,
                "satisfied": consultation.satisfied,
                "because": consultation.because,
                "grant_digest": consultation.grant_digest,
                "granted_by": consultation.granted_by,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def main() -> None:
    govern_app()


if __name__ == "__main__":  # pragma: no cover - console-script entry point
    main()
