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
    EVENT_GRANT_CREATED,
    EVENT_GRANT_REVOKED,
    append_ratification_event,
    ledger_path,
    read_ratification_events,
    validate_ratification_ledger,
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


@govern_app.command("trace")
def trace(
    point_id: str = typer.Argument(..., help="Ratification point id to trace."),
    root: Path | None = _ROOT_OPTION,
) -> None:
    """Show every recorded decision for one ratification point, and its state right now."""
    point = get_ratification_point(point_id)
    if point is None:
        echo_stdout(f"no ratification point is registered as `{point_id}`\n")
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
