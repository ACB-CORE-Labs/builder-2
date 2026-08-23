# Self-Hosting Bootstrap Boundary

builder-II is not currently admitted to govern development of builder-II itself.

The product's planning, approval, execution, receipt, and rollback surfaces may be run
against this repository to test their behavior. Their outputs are test artifacts only:
they do not authorize source changes, certify correctness, or replace code review and
local CI. This avoids assuming the correctness of the unfinished system in order to
establish that same correctness.

Ordinary builder-II development therefore follows the operator-supervised repository
workflow:

1. inspect the live repository and define the intended change;
2. edit directly on an isolated branch or durable project-local worktree;
3. run focused tests for the affected invariants;
4. run `bash scripts/ci.sh --receipt <path>` on the settled commit before publication;
5. review the exact diff and publish through normal Git and GitHub pull-request custody.

The CI receipt remains useful test evidence from the product. It is not self-issued
authority. The actual development evidence is the exact command, exit status, source
commit and tree, test output, human review, and hosted Git custody.

## Admission requirement

Self-hosting may begin only after the complete system is independently qualified and a
separate explicit decision admits builder-II to govern its own development. That
decision must define the admitted surfaces, trust basis, failure recovery, and rollback
path. Passing one subsystem test, minting one valid approval, or producing one receipt
cannot imply platform-wide admission.

Until then, repeated HITL approval artifacts are neither required nor authoritative for
ordinary changes to this repository.
