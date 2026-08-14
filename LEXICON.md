# builder-II Lexicon

| builder-II Term | Industry Equivalent | One-Line Definition |
|---|---|---|
| Builder's Signet | Governance doctrine / integrity seal | Engineering pillars every authority-bearing change must satisfy |
| STRATUM | Permission tier + operator TUI | Authority layer and governed Textual UI for lanes, digests, and gates |
| WRP | Write-Restricted Path / exchange protocol | Protected namespace and WRP artifact exchange track |
| Passive Lanes | Read-only execution context | Observe and artifact; no target source mutation |
| Honesty Pins | Immutable audit anchors | Checksum-locked tests/matrix rows that reject false claims |
| B1.3A Verification | Phase-gated commit verification | Digest checks before promotion to executed state |
| HITL | Human-in-the-Loop | Human approval checkpoint before authority-bearing execution |
| WAL | Write-Ahead Log | Append-only ledger of proposed and executed mutations |
| Command Authority | Capability registry / RBAC table | Maps every CLI surface to tier, promotion state, allowed effects |
| Assurance State | Risk classification label | Derived lattice from capability flags and promotion state |
| Artifact | Durable governance record | Digest-bound JSON with a `kind` field; never itself authority |
| Artifact Kind | Schema / message type ID | Stable `builder_ii.*` string naming an artifact family |
| Promotion State | Lifecycle / feature-flag stage | How far a command is allowed (spec_only → enabled / forbidden) |
| Execution Candidate | Change proposal | Manifest of work that may later be approved; not execution |
| Chain Binding | Provenance / hash chain | Digest refs tying proposal → approval → receipt → evidence |
| Gate Battery | CI gate suite | Blocking local/CI checks (`scripts/ci.sh`) |
| CodeVault | Proprietary upgrade | Separately licensed commercial plugin |
| Fail-Closed Seam | Graceful degradation boundary | Open core refuses CodeVault with upgrade message |
| Third Door | Governed middle path | Artifact → validate → approve → execute → receipt |
| RECORDED_ONLY | Self-attested log | Receipt written by the same host that ran the action |
| Target Profile | Project configuration profile | generic / builder / core describing the governed repo |
| Digest | Content hash (SHA-256) | Canonical hash of an artifact body for binding and validation |
