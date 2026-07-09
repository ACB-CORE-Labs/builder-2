"""A receipt for one run of the blocking gate battery (``scripts/ci.sh``).

builder-II's Forgejo Actions runner is offline. Merges to ``main`` are currently gated by a
human running ``bash scripts/ci.sh`` locally and writing "it was green" into a pull-request
body. That is testimony, not evidence. This module gives the gate battery the same treatment
every other builder-II subsystem gets: a ``kind``-tagged, digest-bound artifact plus a paired
validator, so a verification run doesn't get to *say* it passed -- it emits a record naming
exactly what ran, against what, under a digest.

THE HONEST LIMIT -- read this before trusting a receipt.

A locally generated receipt does not create independence. The same host that runs the gates
writes the receipt; anyone who can run the battery can hand-edit its JSON afterward. This
artifact's ``governance`` block says so explicitly: ``independent_observer`` and
``artifact_is_authority`` are both hard-pinned ``false``, and ``merge_authority`` is pinned to
``"operator"``. What this receipt eliminates is transcription error (claiming nine gates ran
when eight did), commit mismatch (a green battery cited for the wrong commit), and dirty-tree
ambiguity (a green battery that only proves something about an uncommitted local edit). What it
does **not** eliminate is dishonesty, and it is not a substitute for an independent runner. This
artifact is a *receipt*, never a *proof* and never a *verification* -- do not describe it as
either, here or anywhere else.

Corollary: ``gate_battery_receipt_digest`` binds *this run*, not *this commit*. Two honest runs
of the identical tree produce two different receipts (different timestamps, different
durations), so the digest only answers "has this receipt been tampered with since it was
written?" -- it never answers "what is the gate result for commit X?". Only
``head_sha_before`` / ``head_sha_after`` / ``working_tree_clean`` speak to commit identity, and
even those only within the honest limit above: they say what the recorder observed, not that
the recorder cannot lie.

Record honestly; refuse nothing. A dirty tree or a HEAD that moved mid-run does not make a
receipt invalid -- it makes the receipt truthfully record that it is useless for merge
citation. Refusing to build a receipt over a dirty tree would be strictly worse: it would hide
exactly the fact a reviewer most needs to see. The one thing this module never does is coerce
an absent fact into a fabricated default: a ``SKIPPED`` gate has a ``null`` ``exit_code`` and a
``null`` ``duration_seconds``, never ``0``; a ``SKIPPED`` or absent-for-cause gate has ``null``
``argv``, never ``""`` or ``[]``. Absent is ``null``. A validator that let ``null`` and ``0``
collapse into each other would make a legitimately blocked/skipped record indistinguishable
from a corrupted one -- exactly the defect this module exists to avoid repeating.

This is ``RECORDED_ONLY``: it flips no completion-matrix row, grants no new authority, and does
not change who may merge. The operator still merges.

Scope: this receipt covers the **blocking** gates in ``scripts/ci.sh`` only. Gitleaks runs as a
GitHub/Forgejo Action with ``continue-on-error: true`` -- advisory, never blocking -- and is
deliberately out of scope (``covered_gates: "blocking"``).
"""

from __future__ import annotations

import datetime
import json as json_lib
import platform
import shutil
import sys
from pathlib import Path
from typing import Any

from builder_ii.config_schema import attach_digest, digest_jsonable

GATE_BATTERY_RECEIPT_KIND = "builder_ii.gate_battery_receipt"
GATE_BATTERY_RECEIPT_SCHEMA_VERSION = 1
GATE_BATTERY_RECEIPT_CAPABILITY_STATE = "RECORDED_ONLY"
GATE_BATTERY_RECEIPT_DIGEST_KEY = "gate_battery_receipt_digest"

STATUS_PASSED = "PASSED"
STATUS_FAILED = "FAILED"
STATUS_SKIPPED = "SKIPPED"
GATE_STATUSES: frozenset[str] = frozenset({STATUS_PASSED, STATUS_FAILED, STATUS_SKIPPED})

OVERALL_PASSED = "PASSED"
OVERALL_FAILED = "FAILED"
OVERALL_STATES: frozenset[str] = frozenset({OVERALL_PASSED, OVERALL_FAILED})

COVERED_GATES = "blocking"
MERGE_AUTHORITY = "operator"


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_hex_sha(value: Any) -> bool:
    if not isinstance(value, str) or len(value) not in (40, 64):
        return False
    return all(c in "0123456789abcdefABCDEF" for c in value)


def _is_sha256_hex(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value.lower())


def _is_number_ge_zero(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0


def _dedupe(errors: list[str]) -> list[str]:
    return list(dict.fromkeys(errors))


def _looks_like_absolute_path(value: str) -> bool:
    if value.startswith("/") or value.startswith("\\"):
        return True
    # Windows drive letter, e.g. "C:\Users\..." -- host-identifying either way.
    return len(value) > 1 and value[1] == ":" and value[0].isalpha()


def find_absolute_paths(value: Any, location: str = "$") -> list[str]:
    """Recursively locate string leaves that look like absolute filesystem paths.

    Nothing legitimate in this artifact is an absolute path: gate argv is fixed and
    repo-relative, git SHAs and digests are hex, timestamps are ISO-8601. A hit here means an
    absolute path leaked in (the motivating case is ``PYO3_PYTHON``, an env var ci.sh derives
    from ``sys.executable`` under the developer's home directory) and the receipt must be
    rejected, not merely frowned at.
    """
    found: list[str] = []
    if isinstance(value, str):
        if _looks_like_absolute_path(value):
            found.append(location)
    elif isinstance(value, dict):
        for key, item in value.items():
            found.extend(find_absolute_paths(item, f"{location}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(find_absolute_paths(item, f"{location}[{index}]"))
    return found


def gate_record_for_run(name: str, argv: list[str], exit_code: int, duration_seconds: float | int) -> dict[str, Any]:
    """Build a per-gate record for a gate that actually ran (PASSED or FAILED)."""
    status = STATUS_PASSED if exit_code == 0 else STATUS_FAILED
    return {
        "name": name,
        "argv": list(argv),
        "exit_code": int(exit_code),
        "duration_seconds": max(duration_seconds, 0),
        "status": status,
        "skip_reason": None,
    }


def gate_record_for_skip(name: str, skip_reason: str) -> dict[str, Any]:
    """Build a per-gate record for a gate that never ran. Absent, not fabricated: no argv,
    no exit code, no duration -- only the fixed status and the reason."""
    return {
        "name": name,
        "argv": None,
        "exit_code": None,
        "duration_seconds": None,
        "status": STATUS_SKIPPED,
        "skip_reason": skip_reason,
    }


def build_gate_battery_receipt(
    *,
    gates: list[dict[str, Any]],
    head_sha_before: str | None,
    head_sha_after: str | None,
    working_tree_clean: bool,
    cargo_present: bool | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Assemble, digest, and self-validate a gate battery receipt.

    Records what happened, refuses nothing: a dirty tree, an unstable HEAD, or a FAILED gate
    all produce a valid, well-formed receipt -- they just carry fields that say the receipt is
    unfit for merge citation. Refusal is left to the consumer (a reviewer, or a later
    validator), never done here.
    """
    gates_list = [dict(gate) for gate in gates]
    skipped = [gate.get("name") for gate in gates_list if gate.get("status") == STATUS_SKIPPED]
    overall_state = OVERALL_FAILED if any(gate.get("status") == STATUS_FAILED for gate in gates_list) else OVERALL_PASSED
    head_sha_stable = head_sha_before is not None and head_sha_before == head_sha_after
    resolved_cargo_present = (shutil.which("cargo") is not None) if cargo_present is None else bool(cargo_present)

    receipt: dict[str, Any] = {
        "kind": GATE_BATTERY_RECEIPT_KIND,
        "schema_version": GATE_BATTERY_RECEIPT_SCHEMA_VERSION,
        "generated_at": generated_at or _utc_now(),
        "capability_state": GATE_BATTERY_RECEIPT_CAPABILITY_STATE,
        "head_sha_before": head_sha_before,
        "head_sha_after": head_sha_after,
        "head_sha_stable": head_sha_stable,
        "working_tree_clean": bool(working_tree_clean),
        "gates": gates_list,
        "skipped": skipped,
        "covered_gates": COVERED_GATES,
        "host": {
            "platform": platform.system(),
            "machine": platform.machine(),
            "python_version": platform.python_version(),
            "cargo_present": resolved_cargo_present,
        },
        "overall_state": overall_state,
        "governance": {
            "artifact_is_authority": False,
            "independent_observer": False,
            "merge_authority": MERGE_AUTHORITY,
        },
        "errors": [],
        "valid": True,
    }
    receipt = attach_digest(receipt, digest_key=GATE_BATTERY_RECEIPT_DIGEST_KEY)
    errors = validate_gate_battery_receipt(receipt)
    if errors:
        receipt["errors"] = errors
        receipt["valid"] = False
        receipt = attach_digest(receipt, digest_key=GATE_BATTERY_RECEIPT_DIGEST_KEY)
    return receipt


def dumps_gate_battery_receipt(receipt: dict[str, Any]) -> str:
    return json_lib.dumps(receipt, indent=2, sort_keys=True) + "\n"


def write_gate_battery_receipt(receipt: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_gate_battery_receipt(receipt), encoding="utf-8")


def _validate_gates(value: Any) -> tuple[list[str], dict[str, list[str]]]:
    by_status: dict[str, list[str]] = {STATUS_PASSED: [], STATUS_FAILED: [], STATUS_SKIPPED: []}
    if not isinstance(value, list) or not value:
        return (["gates must be a non-empty list"], by_status)
    errors: list[str] = []
    seen_names: set[str] = set()
    for index, item in enumerate(value):
        prefix = f"gates[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        name = item.get("name")
        if not _is_non_empty_string(name):
            errors.append(f"{prefix}.name must be a non-empty string")
        else:
            assert isinstance(name, str)
            if name in seen_names:
                errors.append(f"{prefix}.name must be unique within gates[] (duplicate: {name!r})")
            else:
                seen_names.add(name)

        status = item.get("status")
        if status not in GATE_STATUSES:
            errors.append(f"{prefix}.status must be one of: {', '.join(sorted(GATE_STATUSES))}")
            continue
        if isinstance(name, str):
            by_status[status].append(name)

        argv = item.get("argv")
        exit_code = item.get("exit_code")
        duration = item.get("duration_seconds")
        skip_reason = item.get("skip_reason")

        if status == STATUS_SKIPPED:
            if argv is not None:
                errors.append(f"{prefix}.argv must be null when status is SKIPPED")
            if exit_code is not None:
                errors.append(f"{prefix}.exit_code must be null when status is SKIPPED")
            if duration is not None:
                errors.append(f"{prefix}.duration_seconds must be null when status is SKIPPED")
            if not _is_non_empty_string(skip_reason):
                errors.append(f"{prefix}.skip_reason must be a non-empty string when status is SKIPPED")
            continue

        # PASSED or FAILED: a command actually ran.
        if skip_reason is not None:
            errors.append(f"{prefix}.skip_reason must be null when status is {status}")
        if not isinstance(argv, list) or not argv or not all(_is_non_empty_string(word) for word in argv):
            errors.append(f"{prefix}.argv must be a non-empty list of non-empty strings when status is {status}")
        if not _is_number_ge_zero(duration):
            errors.append(f"{prefix}.duration_seconds must be a non-negative number when status is {status}")
        is_valid_exit_code = isinstance(exit_code, int) and not isinstance(exit_code, bool)
        if status == STATUS_PASSED:
            if not is_valid_exit_code or exit_code != 0:
                errors.append(f"{prefix}.exit_code must be 0 when status is PASSED")
        else:  # STATUS_FAILED
            if not is_valid_exit_code or exit_code == 0:
                errors.append(f"{prefix}.exit_code must be a non-zero integer when status is FAILED")

    return (_dedupe(errors), by_status)


def _validate_host(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["host must be an object"]
    errors: list[str] = []
    for field in ("platform", "machine", "python_version"):
        if not _is_non_empty_string(value.get(field)):
            errors.append(f"host.{field} must be a non-empty string")
    if not isinstance(value.get("cargo_present"), bool):
        errors.append("host.cargo_present must be a boolean")
    return errors


def _validate_governance(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["governance must be an object"]
    errors: list[str] = []
    if value.get("artifact_is_authority") is not False:
        errors.append("governance.artifact_is_authority must be false")
    if value.get("independent_observer") is not False:
        errors.append("governance.independent_observer must be false")
    if value.get("merge_authority") != MERGE_AUTHORITY:
        errors.append(f"governance.merge_authority must be {MERGE_AUTHORITY!r}")
    return errors


def validate_gate_battery_receipt(data: Any) -> list[str]:
    """Structural + cross-field validation. Returns an empty list iff ``data`` is well-formed.

    Every cross-field rule is enforced in both directions: a hand-edited receipt that claims
    ``overall_state: PASSED`` while a gate carries ``status: FAILED`` is rejected here just as
    surely as one that gets the SKIPPED/exit_code coupling backwards. Forging a claim should
    require lying in two places, never omitting one field.
    """
    if not isinstance(data, dict):
        return ["gate battery receipt artifact must be a JSON object"]

    errors: list[str] = []
    if data.get("kind") != GATE_BATTERY_RECEIPT_KIND:
        errors.append(f"kind must be {GATE_BATTERY_RECEIPT_KIND}")
    if data.get("schema_version") != GATE_BATTERY_RECEIPT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {GATE_BATTERY_RECEIPT_SCHEMA_VERSION}")
    if not _is_non_empty_string(data.get("generated_at")):
        errors.append("generated_at must be a non-empty string")
    if data.get("capability_state") != GATE_BATTERY_RECEIPT_CAPABILITY_STATE:
        errors.append(f"capability_state must be {GATE_BATTERY_RECEIPT_CAPABILITY_STATE}")

    head_sha_before = data.get("head_sha_before")
    head_sha_after = data.get("head_sha_after")
    if head_sha_before is not None and not _is_hex_sha(head_sha_before):
        errors.append("head_sha_before must be null or a hex git SHA")
    if head_sha_after is not None and not _is_hex_sha(head_sha_after):
        errors.append("head_sha_after must be null or a hex git SHA")
    expected_stable = head_sha_before is not None and head_sha_before == head_sha_after
    if data.get("head_sha_stable") is not expected_stable:
        errors.append("head_sha_stable must equal (head_sha_before is not null and head_sha_before == head_sha_after)")

    if not isinstance(data.get("working_tree_clean"), bool):
        errors.append("working_tree_clean must be a boolean")

    gate_errors, gate_names_by_status = _validate_gates(data.get("gates"))
    errors.extend(gate_errors)

    if data.get("covered_gates") != COVERED_GATES:
        errors.append(f"covered_gates must be {COVERED_GATES!r}")

    skipped = data.get("skipped")
    if not isinstance(skipped, list) or not all(isinstance(item, str) for item in skipped):
        errors.append("skipped must be a list of strings")
    else:
        expected_skipped = gate_names_by_status.get(STATUS_SKIPPED, [])
        if len(skipped) != len(set(skipped)):
            errors.append("skipped must not contain duplicates")
        elif sorted(skipped) != sorted(expected_skipped):
            errors.append("skipped must contain exactly the names of gates with status SKIPPED")

    errors.extend(_validate_host(data.get("host")))

    overall_state = data.get("overall_state")
    if overall_state not in OVERALL_STATES:
        errors.append(f"overall_state must be one of: {', '.join(sorted(OVERALL_STATES))}")
    else:
        expected_overall = OVERALL_FAILED if gate_names_by_status.get(STATUS_FAILED) else OVERALL_PASSED
        if overall_state != expected_overall:
            errors.append("overall_state must be FAILED if and only if some gate has status FAILED")

    errors.extend(_validate_governance(data.get("governance")))

    artifact_errors = data.get("errors")
    if not isinstance(artifact_errors, list) or not all(isinstance(item, str) for item in artifact_errors):
        errors.append("errors must be a list of strings")
    valid = data.get("valid")
    if not isinstance(valid, bool):
        errors.append("valid must be a boolean")
    elif valid is True and artifact_errors:
        errors.append("errors must be empty when valid is true")
    elif valid is False and not artifact_errors:
        errors.append("errors must be non-empty when valid is false")

    digest = data.get(GATE_BATTERY_RECEIPT_DIGEST_KEY)
    if not _is_sha256_hex(digest):
        errors.append(f"{GATE_BATTERY_RECEIPT_DIGEST_KEY} must be a SHA-256 hex string")
    elif digest != digest_jsonable(data, digest_key=GATE_BATTERY_RECEIPT_DIGEST_KEY):
        errors.append(f"{GATE_BATTERY_RECEIPT_DIGEST_KEY} drift detected")

    leaked = find_absolute_paths(data)
    if leaked:
        errors.append(f"absolute path(s) leaked into receipt at: {', '.join(leaked)}")

    return _dedupe(errors)


def validate_gate_battery_receipt_file(path: Path) -> list[str]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"gate battery receipt file could not be read: {exc}"]
    try:
        data = json_lib.loads(raw)
    except json_lib.JSONDecodeError as exc:
        return [f"gate battery receipt file is not valid JSON: {exc}"]
    return validate_gate_battery_receipt(data)


# --- python -m builder_ii.gate_battery_receipt CLI -------------------------------------------
#
# Deliberately not a `[project.scripts]` console entry (see module docstring's sibling doc,
# tests/test_operator_status.py:19): a console script would force a command_authority.py
# registration. `python -m` needs none.
#
#   record-gate --log PATH --name NAME --exit-code N --duration D -- ARGV...   (an executed gate)
#   record-gate --log PATH --name NAME --skip-reason TEXT                     (a skipped gate)
#   build --gate-log PATH --output PATH --head-sha-before SHA --head-sha-after SHA
#         --working-tree-clean {true,false}
#   --validate PATH


def _pop_flag(args: list[str], flag: str) -> str | None:
    if flag not in args:
        return None
    index = args.index(flag)
    if index + 1 >= len(args):
        raise SystemExit(f"{flag} requires a value")
    value = args[index + 1]
    del args[index : index + 2]
    return value


def _cmd_record_gate(argv: list[str]) -> int:
    args = list(argv)
    log_path = _pop_flag(args, "--log")
    name = _pop_flag(args, "--name")
    exit_code_raw = _pop_flag(args, "--exit-code")
    duration_raw = _pop_flag(args, "--duration")
    skip_reason = _pop_flag(args, "--skip-reason")
    trailing_argv: list[str] = []
    if "--" in args:
        sep = args.index("--")
        trailing_argv = args[sep + 1 :]
        del args[sep:]

    if log_path is None or name is None:
        print("record-gate requires --log and --name", file=sys.stderr)
        return 2

    if skip_reason is not None:
        if exit_code_raw is not None or duration_raw is not None or trailing_argv:
            print(
                "record-gate: --skip-reason is mutually exclusive with --exit-code/--duration/argv",
                file=sys.stderr,
            )
            return 2
        record = gate_record_for_skip(name, skip_reason)
    else:
        if exit_code_raw is None or duration_raw is None or not trailing_argv:
            print("record-gate: an executed gate requires --exit-code, --duration, and -- ARGV...", file=sys.stderr)
            return 2
        record = gate_record_for_run(name, trailing_argv, int(exit_code_raw), float(duration_raw))

    with open(log_path, "a", encoding="utf-8") as handle:
        handle.write(json_lib.dumps(record) + "\n")
    return 0


def _read_gate_log(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(json_lib.loads(line))
    return records


def _cmd_build(argv: list[str]) -> int:
    args = list(argv)
    gate_log = _pop_flag(args, "--gate-log")
    output = _pop_flag(args, "--output")
    head_sha_before = _pop_flag(args, "--head-sha-before") or None
    head_sha_after = _pop_flag(args, "--head-sha-after") or None
    working_tree_clean_raw = _pop_flag(args, "--working-tree-clean")

    if gate_log is None or output is None or working_tree_clean_raw is None:
        print("build requires --gate-log, --output, and --working-tree-clean", file=sys.stderr)
        return 2

    receipt = build_gate_battery_receipt(
        gates=_read_gate_log(Path(gate_log)),
        head_sha_before=head_sha_before,
        head_sha_after=head_sha_after,
        working_tree_clean=working_tree_clean_raw.strip().lower() == "true",
    )
    write_gate_battery_receipt(receipt, Path(output))
    print(f"gate battery receipt written: {output} (overall_state={receipt['overall_state']})")
    if receipt["errors"]:
        for error in receipt["errors"]:
            print(f"gate battery receipt validation error: {error}", file=sys.stderr)
        return 1
    return 0


def _cmd_validate(path_str: str) -> int:
    errors = validate_gate_battery_receipt_file(Path(path_str))
    if errors:
        for error in errors:
            print(f"gate battery receipt validation error: {error}", file=sys.stderr)
        return 1
    print(f"gate battery receipt valid: {path_str}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print(
            "usage: python -m builder_ii.gate_battery_receipt {record-gate|build|--validate <path>}",
            file=sys.stderr,
        )
        return 2
    if args[0] == "--validate":
        if len(args) != 2:
            print("--validate requires exactly one path argument", file=sys.stderr)
            return 2
        return _cmd_validate(args[1])
    if args[0] == "record-gate":
        return _cmd_record_gate(args[1:])
    if args[0] == "build":
        return _cmd_build(args[1:])
    print(f"unsupported gate_battery_receipt entrypoint: {args[0]}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
