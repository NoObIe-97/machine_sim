# After Silicon — MiMo Milestone 17A Neural Controller Determinism and Judge Hardening Prompt

## Repository and branch

Repository: `https://github.com/NoObIe-97/machine_sim.git`

Branch: `feature/milestone-1`

Start from the current Milestone 17 remote head:

```text
69747f6
```

Milestone 17 introduced a substantial internal neural processing unit and is directionally correct. However, final acceptance is on HOLD because there are several correctness and stage-closing issues that must be fixed before moving to Milestone 18.

Do not start Milestone 18.

Before final handoff, invoke and satisfy:

```text
prompts/skills/stage_closing_chores.md
```

---

## Current review decision

```text
M17_INTERNAL_NEURAL_PROCESSING_UNIT: PASS
M17_LOCAL_SENSOR_INPUT_VECTOR: PASS_WITH_REVIEW_CAVEAT
M17_NEURAL_ACTION_SELECTION: PARTIAL_PASS
M17_LOCAL_PLASTICITY_UPDATE: PASS
M17_SUCCESSOR_NEURAL_STATE_TRANSFER: PASS
M17_NEURAL_VS_SCALAR_BASELINE_COMPARISON: PASS
M17_REQUIRED_ARTIFACTS_WRITTEN: PASS
M17_INDEPENDENT_JUDGE_PASS_NO_SKIP: FAIL_WEAK_JUDGE
M17_TESTS_ASSERT_REAL_NEURAL_BEHAVIOR: PASS
M14_M15_M16_REGRESSION_JUDGES_STILL_PASS: PASS_REPORTED_BUT_JUDGE_PLACEHOLDER
TESTS_AND_COVERAGE: PASS
GUARDRAILS: PASS
MILESTONE_17_REPORT_CURRENT: PARTIAL_PASS_NEEDS_CLARIFICATION
REVIEW_PACKAGE_CURRENT: FAIL_CURRENT_STAGE_COMMIT_NOT_LISTED
STAGE_CLOSING_CHORES_SATISFIED: FAIL
MILESTONE_17_FINAL_ACCEPTANCE: HOLD
READY_FOR_MILESTONE_18: NO
```

---

## What is accepted and must be preserved

Preserve the main M17 direction and working infrastructure:

- `machine_sim/agents/neural_controller.py`
- compact recurrent neural controller
- 16-input / 16-hidden / action-logit architecture
- softmax action preferences
- local sensor input vector
- local plasticity update on neural parameters
- neural traces and plasticity traces
- successor neural-state transfer
- neural-vs-scalar comparison artifact
- M17 demo configuration and artifacts
- 332 passing tests / current coverage level unless rerun values change

---

## Blocking issue 1 — Python `hash()` breaks cross-process determinism

Current implementation uses Python's built-in `hash()` in places such as:

```text
NeuralController._make_rng(...): hash(("neural_init", unit_id, seed))
MachineUnitImpl.decide(...): Random(tick * 1000 + hash(self.unit_id))
SimEngine neural feedback/update paths: Random(... + hash(unit.unit_id))
SimEngine neural successor transfer path: Random(... + hash(unit.unit_id))
```

Python's built-in `hash()` is process-randomized unless `PYTHONHASHSEED` is fixed. This violates the M17 requirement that neural initialization/action sampling/transfer be deterministic under seed across independent runs.

Required fix:

- Add a stable deterministic seed helper, e.g. in a small utility module or inside `neural_controller.py`:

```python
import hashlib

def stable_u32_seed(*parts: object) -> int:
    payload = "|".join(str(p) for p in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:4], "big")
```

- Replace every neural-path use of built-in `hash()` with stable hashing.
- Do not rely on Python process hash randomization.
- Add tests that would fail if deterministic initialization/action selection uses Python `hash()` or changes across separate controller instances.

Required test coverage:

```text
same unit_id + seed -> identical neural parameters
same tick + unit_id + seed -> identical action sampling path
successor neural transfer with same source/seed -> identical transferred state
```

---

## Blocking issue 2 — FABRICATE neural output is not actually an action

The report says the neural controller has 7 action outputs including `FABRICATE`, but `MachineUnitImpl.decide()` currently maps:

```text
"FABRICATE": ActionType.IDLE
```

This is misleading. It means the neural controller does not actually select fabrication as an action. Fabrication remains an engine phase outside neural action selection.

Choose one of these acceptable fixes:

### Option A — make fabrication a real neural-modulated runtime decision

Preferred if feasible:

- If `FABRICATE` is selected by the neural controller, emit an action or internal intent that influences the existing fabrication phase.
- The engine should only attempt fabrication for a unit when the unit's current internal state/action intent allows it, except for backward-compatible scalar/config modes.
- Neural parameter output may modulate fabrication threshold or fabrication readiness.
- Record neural fabrication intent in `neural_action_trace.jsonl` and successor transfer summaries.

### Option B — remove FABRICATE from the neural action output for M17A

Acceptable if direct fabrication control is too invasive:

- Reduce/rename the neural action output schema so it does not claim FABRICATE is a real action.
- Keep fabrication as a body-level runtime process and clearly document it as not neural-selected in M17.
- The successor neural-state transfer can still occur when fabrication succeeds.
- Update tests, report, and judge so they do not claim neural action output includes effective FABRICATE control.

Do not leave `FABRICATE` as a fake output mapped to `IDLE` while claiming it is a neural action.

---

## Blocking issue 3 — M17 judge is too weak

Strengthen `machine_sim/verification/milestone_17_judge.py`.

Current weaknesses:

- `long_run_ticks_check` infers tick count from neural state trace count instead of checking actual run ticks.
- `successor_neural_transfer_check` can become `PARTIAL`, but overall status still PASS because only `FAIL` counts as failure.
- `m14_m15_m16_regression_check` is effectively a placeholder and always passes.
- `local_input_only_check` only checks `input_size > 0`, not actual schema or forbidden global/oracle fields.

Required fixes:

```text
long_run_ticks_check: read actual run_ticks or max_ticks from neural_processing_summary/resource_hazard_field_summary/config artifact and require >= 20000
successor_neural_transfer_check: require at least one valid neural successor transfer; no PARTIAL for final acceptance
m14_m15_m16_regression_check: verify actual regression judge result files or explicit documented paths/status artifacts; no placeholder pass
local_input_only_check: verify declared input schema has only local fields and no global/oracle/analyzer-score fields
no_partial_or_skip_check: fail if any required check is PARTIAL/SKIP/UNKNOWN
```

The judge output must contain only PASS/FAIL for required checks, and final status must be PASS only if all required checks PASS.

---

## Blocking issue 4 — M17 summary artifacts need stronger schema

Update M17 artifact writers if needed so the judge can verify real values instead of inference.

`neural_processing_summary.json` should include at least:

```text
run_ticks
grid_width
grid_height
initial_unit_count
final_active_count
neural_controller_enabled
neural_controller_mode
neural_plasticity_enabled
neural_state_trace_count
neural_action_trace_count
neural_plasticity_trace_count
neural_successor_transfer_count
signal_emission_count
signal_observation_count
local_input_schema
local_input_only_declared
forbidden_input_fields_detected
```

`neural_controller_config.json` should include:

```text
input_size
hidden_size
output_size
action_names
param_output_size
plasticity_rate
plasticity_enabled
weight_bound
seed_mode = "stable_hash" or equivalent
```

`neural_vs_scalar_compare.json` should distinguish:

```text
neural_signal_emissions
neural_signal_observations
```

Do not use neural action trace `EMIT_SIGNAL` count as a proxy for observations.

---

## Blocking issue 5 — review package does not list current M17 commit

Update:

```text
docs/review_package.md
```

It currently lists through M16 and does not list:

```text
69747f6 — Milestone 17 internal neural processing unit
```

Add the M17 implementation commit and the new M17A hardening commit once available.

---

## Documentation updates required

Update:

```text
docs/milestone_17_report.md
docs/review_package.md
```

M17 report must clearly state:

- whether FABRICATE is a real neural-selected action or not,
- deterministic seed mechanism uses stable hashing, not Python `hash()`,
- actual run_ticks is reported and judge-verified,
- actual M14/M15/M16 regression judge paths/statuses are verified,
- all M17 judge checks are PASS with no PARTIAL/SKIP/UNKNOWN,
- current tests/coverage,
- full command list actually run,
- artifact paths,
- limitations that are not acceptance violations.

---

## Required verification commands

Run:

```bash
python -m pytest machine_sim/tests/ -v
python -m pytest machine_sim/tests/ --cov=machine_sim --cov-report=term-missing
python -m machine_sim.cli.main check
python -m machine_sim.cli.main run -c configs/milestone_17_internal_neural_processing_unit.toml -t 20000 -s 42 -o output/demo_m17
python -m machine_sim.cli.main inspect output/demo_m17
python -m machine_sim.verification.milestone_17_judge output/demo_m17
python -m machine_sim.verification.milestone_14_judge output/demo_m14
python -m machine_sim.verification.milestone_15_judge output/demo_m15
python -m machine_sim.verification.milestone_16_judge output/demo_m16
```

If regression artifacts are regenerated, document exact paths.

Also add or run a deterministic repeat check. Example:

```bash
python -m pytest machine_sim/tests/test_neural_controller.py -v
```

Tests should prove deterministic neural initialization and action sampling under the same seed across separate instances.

---

## Stage-closing evidence required

Final handoff must include all standard stage-closing evidence plus:

```text
M17A_STABLE_DETERMINISTIC_SEEDING: yes
M17A_NO_PYTHON_HASH_IN_NEURAL_PATH: yes
M17A_FABRICATE_OUTPUT_RESOLVED: yes
M17A_STRONG_JUDGE_NO_PARTIAL_OR_SKIP: yes
M17A_REGRESSION_JUDGE_CHECK_REAL: yes
M17A_LOCAL_INPUT_SCHEMA_VERIFIED: yes
M17_GOAL_SPEC_SATISFIED: yes
M17_INTERNAL_NEURAL_PROCESSING_UNIT_PRESENT: yes
M17_NEURAL_CONTROLLER_DRIVES_NORMAL_ACTION_SELECTION: yes
M17_PLASTICITY_UPDATE_NONZERO: yes
M17_LOCAL_INPUT_ONLY: yes
M17_NEURAL_VS_SCALAR_NONTRIVIAL_DIFFERENCE: yes
M17_SUCCESSOR_NEURAL_TRANSFER_RECORDED: yes
M17_INDEPENDENT_JUDGE_STATUS: PASS
M17_NO_SKIPPED_REQUIRED_JUDGE_CHECKS: yes
M14_M15_M16_REGRESSION_JUDGES_STILL_PASS: yes
```

Do not claim ACCEPTED unless all are true.

---

## Final handoff format

```text
MILESTONE_17A_STATUS: PASS or PARTIAL_PASS
MILESTONE_17_STATUS: ACCEPTED or HOLD
READY_FOR_MILESTONE_18: YES or NO
Branch:
Starting commit hash:
Implementation commit hash:
Final remote commit hash:
Design summary:
Files changed:
Deterministic seeding summary:
FABRICATE output resolution:
Judge hardening summary:
Long-run demo parameters:
Tests:
Coverage:
Guardrail result:
M14/M15/M16 judge results:
M17 judge result:
Neural-vs-scalar comparison:
Plasticity update summary:
Successor neural transfer summary:
Artifact paths:
Full M1-M17 regression summary:
Stage closing chores result:
Known limitations:
Clean working tree:
```

---

## Acceptance criteria

```text
M17A_STABLE_DETERMINISTIC_SEEDING: PASS
M17A_NO_PYTHON_HASH_IN_NEURAL_PATH: PASS
M17A_FABRICATE_OUTPUT_RESOLVED: PASS
M17A_STRONG_INDEPENDENT_JUDGE: PASS
M17A_NO_PARTIAL_SKIP_UNKNOWN_REQUIRED_CHECKS: PASS
M17A_REAL_M14_M15_M16_REGRESSION_CHECK: PASS
M17A_LOCAL_INPUT_SCHEMA_VERIFIED: PASS
M17_INTERNAL_NEURAL_PROCESSING_UNIT: PASS
M17_NEURAL_ACTION_SELECTION: PASS
M17_LOCAL_PLASTICITY_UPDATE: PASS
M17_SUCCESSOR_NEURAL_STATE_TRANSFER: PASS
M17_NEURAL_VS_SCALAR_BASELINE_COMPARISON: PASS
M17_REQUIRED_ARTIFACTS_WRITTEN: PASS
M17_TESTS_ASSERT_REAL_NEURAL_BEHAVIOR: PASS
TESTS_AND_COVERAGE: PASS
GUARDRAILS: PASS
FULL_M1_M17_REGRESSION_REPORTED: PASS
MILESTONE_17_REPORT_CURRENT: PASS
REVIEW_PACKAGE_CURRENT: PASS
STAGE_CLOSING_CHORES_SATISFIED: PASS
CLEAN_WORKTREE_AND_PUSHED_REMOTE: PASS
```
