# Governed run lifecycle

Plan Set 1 consolidates the existing manifest, WRP, model-gateway, receipt,
checkpoint, and event-ledger surfaces behind one lifecycle. The lifecycle is an
evidence coordinator; it is not an approval or authority source.

The runtime-adapter interface owns only substrate behavior:

`prepare -> start/resume -> interrupt/cancel -> inspect -> close`

`GovernedRun` owns the run manifest, monotonic event chain, checkpoint binding,
unexecuted-step accounting, and terminal receipt. A checkpoint is accepted only
when its run ID, manifest digest, policy digest, event-chain digest, and own
digest all match. A foreign, corrupted, or policy-incompatible checkpoint is
rejected before the adapter is called.

The deterministic `SyntheticRuntimeAdapter` is the Plan Set 1 exit-gate
evidence lane. It performs no model, shell, tool, target-repository, or provider
work. `WrpSubagentRuntimeAdapter` delegates real WRP steps to the existing
`run_governed_subagent_step` seam, preserving its model gateway, budget, approval,
and receipt controls.

Terminal receipts list both completed and unexecuted steps. An interrupted or
failed run never claims that remaining steps executed. All lifecycle artifacts
remain `RECORDED_ONLY` and carry `grants_authority: false` and
`artifact_is_authority: false`.
