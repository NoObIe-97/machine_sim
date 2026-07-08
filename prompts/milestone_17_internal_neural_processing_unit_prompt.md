# After Silicon — MiMo Milestone 17 Goal Spec: Internal Neural Processing Unit

## Repository and branch

Repository: `https://github.com/NoObIe-97/machine_sim.git`

Branch: `feature/milestone-1`

Start from the latest remote head:

```text
39caca41876e8cb963298b403b8e801019f32571
```

Important: a previous Milestone 17 prompt exists for cross-configuration adaptive comparison. Do **not** execute that prompt yet. This prompt supersedes it for the next milestone. Cross-configuration comparison can resume after the internal neural processing unit is implemented and accepted.

Milestone 16 is accepted. Milestone 17 must build on the M14/M15/M16 adaptive-control, multi-generation trace, and trajectory-compression substrate without regressing the accepted M14, M15, or M16 judges.

Before final handoff, invoke and satisfy:

```text
prompts/skills/stage_closing_chores.md
```

---

## Strategic direction

Current unit adaptation is based on a bounded scalar adaptive-state vector and hand-coded local update rules. This is useful, but it is not yet a true internal processing unit.

Milestone 17 must introduce a small internal neural processing unit inside each adaptive unit. The neural unit should convert local sensed inputs plus internal recurrent state into action preferences and selected action parameters. Its internal state and selected plastic parameters must update from local operational feedback during runtime.

This milestone must preserve the core philosophy:

```text
units receive local signals
→ units process those signals internally
→ units choose actions from their own internal state
→ local feedback updates the internal processing unit
→ external analysis only observes
```

No external analyzer may decide, recommend, override, optimize, or force unit actions during a simulation run.

---

## Conceptual boundary

Use machine-native terminology only. Avoid human/social/biological/political/economic/emotional framing in runtime code, config keys, event labels, artifact schemas, or reports.

Avoid terms such as:

```text
human
social
society
community
communication
message
language
meaning
knowledge
learning
teaching
memory
strategy
trust
cooperation
competition
conflict
agreement
consensus
population
evolution
mutation
inheritance
offspring
parent
child
species
fitness
brain
```

Preferred machine-native terms:

```text
internal neural processing unit
neural controller
recurrent processing state
local plasticity update
plastic connection parameter
neural action logits
sensor input vector
feedback-modulated update
successor neural initialization state
bounded neural-state transfer
neural trajectory trace
scalar adaptive controller baseline
neural controller variant
```

The implementation may use the word `neural` and `controller`. Do not use `brain` in committed code/docs/artifacts.

---

## Explicit architecture decision

Do **not** implement a transformer, token model, or tiny LLM for M17.

Rationale:

- The current simulator uses low-dimensional sensorimotor inputs, not token streams.
- An untrained token-sequence model would be computationally expensive and scientifically noisy at this stage.
- The immediate need is a compact internal processing unit with inspectable local plasticity.

M17 should implement a tiny recurrent neural controller using only existing lightweight dependencies. Prefer pure Python and standard math/random tools unless NumPy is already a project dependency. Do not introduce heavyweight ML frameworks unless absolutely necessary and justified in the report.

---

## Milestone 17 goal statement

Implement a compact internal neural processing unit that can replace or augment the current scalar adaptive controller for normal action selection.

The neural processing unit must:

```text
consume local sensor/feedback features
maintain recurrent processing state
emit action logits or normalized action preferences
emit selected action-parameter suggestions
update internal state and selected plastic parameters from local feedback
transfer bounded neural initialization state to successor units
write traces that allow offline inspection of neural-state changes
```

This must be a runtime behavior milestone, not merely a new analysis module.

---

## Core implementation requirements

### 1. Neural controller module

Add a module such as:

```text
machine_sim/agents/neural_controller.py
```

Suggested classes:

```text
NeuralProcessingConfig
NeuralProcessingState
NeuralController
```

Suggested controller form:

```text
input vector size: 8 to 32
hidden/recurrent state size: 8 to 32
action output size: at least MOVE, SCAN, HARVEST, EMIT_SIGNAL, IDLE, MAINTAIN, FABRICATE if supported
parameter output size: signal intensity/radius bias, scan interval bias, extraction/fabrication threshold bias if practical
```

Recommended simple equations:

```text
h_t = tanh(W_in*x_t + W_rec*h_{t-1} + b)
action_logits = W_out*h_t + c
action_preferences = softmax(action_logits)
```

Use deterministic initialization from unit id and run seed.

### 2. Local sensory input vector

Build a fixed sensor input vector from local runtime values only.

Suggested inputs:

```text
power_ratio
average_component_health
local_resource_detected
local_resource_strength
local_hazard_detected
local_hazard_strength
signal_observed_recent
signal_emitted_recent
movement_blocked_recent
resource_extracted_recent
scan_result_count_recent
previous_action_one_hot or compact encoding
time_since_last_signal_normalized
fabrication_ready_flag if locally available
```

Requirements:

- No global map input.
- No future state input.
- No external analysis score input.
- No hidden state from other units except locally sensed signals/events.

### 3. Neural action selection integration

Add a config switch such as:

```text
neural_controller_enabled = true
neural_controller_mode = "replace" or "hybrid"
```

Modes:

- `replace`: normal operating ticks use neural action preferences instead of scalar adaptive action scores.
- `hybrid`: neural action preferences combine with current scalar adaptive scores.

Critical safety overrides may remain for extremely low power or critically degraded components. These overrides should be documented as body-level/homeostatic constraints, not external optimization.

Normal operating ticks must be neural-controller-driven when enabled.

### 4. Local plasticity update

Implement a bounded local plasticity update. Keep it small and inspectable.

Possible update rule:

```text
reward_like_delta = normalized local feedback score
eligibility = outer(hidden_state, selected_action_vector)
W_out += plasticity_rate * reward_like_delta * eligibility
```

or an equivalent local rule. Also allow recurrent/hidden-state adaptation if safe.

Requirements:

- Plastic parameters must be bounded.
- Update must be deterministic under seed.
- Update must use only local feedback.
- It must be possible to disable plasticity for baseline comparison.
- At least one neural parameter or plasticity trace must change over a run.

Use machine-native terms such as `feedback_delta`, `plasticity_update`, and `neural_state_delta`. Avoid using forbidden vocabulary in code/docs/artifacts.

### 5. Successor neural-state transfer

When fabrication/descendant initialization occurs, successor units should receive a bounded neural initialization state from the source unit.

Required transfer components:

```text
recurrent processing state summary
selected plastic connection parameters or compact projection
controller configuration id
bounded transfer variation summary
source/successor neural-state delta
```

This should be written to an artifact:

```text
output/demo_m17/neural_successor_transfer_trace.jsonl
```

Transfer must be bounded and deterministic under seed.

### 6. Neural-vs-scalar baseline comparison

M17 must compare at least two modes under the same field and seed family:

```text
scalar adaptive controller baseline
neural controller variant
```

Required comparison artifact:

```text
output/demo_m17/neural_vs_scalar_compare.json
```

Required fields:

```text
scalar_active_count
neural_active_count
scalar_transfer_count
neural_transfer_count
scalar_signal_observations
neural_signal_observations
action_distribution_delta
adaptive_state_delta_scalar
neural_state_delta
neural_parameter_delta
runtime_metric_delta_summary
nontrivial_neural_difference_detected
```

The neural variant does not need to outperform the scalar baseline. It must show nontrivial internal neural-state/plastic-parameter change and nontrivial action-distribution or runtime metric difference.

### 7. Long-run demo configuration

Add:

```text
configs/milestone_17_internal_neural_processing_unit.toml
```

Recommended minimums:

```text
grid_width >= 120
grid_height >= 120
initial unit_count between 4 and 12
max_ticks >= 20000
seed = 42
adaptive_enabled = true
neural_controller_enabled = true
neural_plasticity_enabled = true
signal_enabled = true
fabrication_enabled = true
capsule_enabled = true
long_run_adaptation_enabled = true
multi_generation_trace_enabled = true if compatible
trajectory_compression_enabled = false unless needed
```

The main M17 demo should produce:

```text
neural_state_trace_count > 0
neural_parameter_delta > threshold
signal observations > 0
at least one neural successor transfer if fabrication succeeds
nontrivial neural-vs-scalar difference
```

If transfer does not occur naturally, tune fabrication parameters while preserving a nontrivial field.

---

## Required artifacts

Main M17 output directory must contain:

```text
output/demo_m17/neural_processing_summary.json
output/demo_m17/neural_state_trace.jsonl
output/demo_m17/neural_action_trace.jsonl
output/demo_m17/neural_plasticity_trace.jsonl
output/demo_m17/neural_successor_transfer_trace.jsonl
output/demo_m17/neural_vs_scalar_compare.json
output/demo_m17/resource_hazard_field_summary.json
output/demo_m17/milestone_17_judge_result.json
```

Optional but useful:

```text
output/demo_m17/neural_controller_config.json
output/demo_m17/neural_parameter_snapshot_initial.json
output/demo_m17/neural_parameter_snapshot_final.json
```

Artifact sizes must be bounded through sampling or compact summaries.

---

## Independent M17 judge

Add:

```text
machine_sim/verification/milestone_17_judge.py
```

Input:

```text
output/demo_m17/
```

Output:

```text
output/demo_m17/milestone_17_judge_result.json
```

Required judge checks:

```text
long_run_ticks_check: run_ticks >= 20000
neural_controller_enabled_check: neural_controller_enabled true in summary/config
neural_state_trace_check: neural_state_trace exists and has nonzero records
neural_action_trace_check: action preferences/logits are recorded and action outputs are nontrivial
plasticity_update_check: plasticity trace exists and at least one bounded neural parameter changes
local_input_only_check: summary declares local input vector; no forbidden global/oracle fields in artifacts
neural_vs_scalar_difference_check: neural-vs-scalar comparison has nontrivial neural-state and behavior/runtime delta
successor_neural_transfer_check: transfer artifact exists; PASS if at least one transfer occurs, or PARTIAL condition only if report proves fabrication did not occur despite enabled fabrication
signal_observation_check: signal observations > 0
bounded_artifact_size_check: JSONL traces remain bounded
m14_m15_m16_regression_check: accepted regression judges still pass or are explicitly verified
machine_native_wording_check: no forbidden terms in artifacts
```

All required checks should PASS with no SKIP. The only allowed non-blocking caveat is successor transfer if zero fabrication occurs despite enabled fabrication; however, preferred acceptance requires at least one neural successor transfer.

---

## Tests required

Add focused tests for M17. Tests may use short synthetic fixtures.

Required tests:

1. Neural controller deterministic initialization for same seed/unit id.
2. Sensor input vector has fixed schema and uses local fields only.
3. Neural action logits/preferences are numeric, bounded, and normalized.
4. Recurrent state changes after input processing.
5. Plasticity update changes selected parameters under nonzero feedback.
6. Plastic parameters remain bounded after repeated updates.
7. Neural controller can be disabled and scalar baseline behavior remains available.
8. Neural-vs-scalar comparison detects nontrivial difference on fixture data.
9. Successor neural-state transfer is bounded and related to source state.
10. M17 judge fails when neural state trace is missing.
11. M17 judge fails when plasticity trace shows no parameter change.
12. M17 judge passes on a valid fixture artifact set.
13. M14/M15/M16 regression judges still pass or accepted artifacts remain judge-compatible.
14. Existing tests continue to pass.

---

## Documentation requirements

Add:

```text
docs/milestone_17_report.md
```

Update:

```text
docs/review_package.md
```

M17 report must include:

- design summary,
- why token/transformer model was deferred,
- neural controller architecture,
- sensor input vector schema,
- action output schema,
- plasticity update rule,
- successor neural-state transfer rule,
- neural-vs-scalar comparison results,
- long-run parameters,
- signal observation summary,
- M14/M15/M16 regression judge results,
- M17 judge result with all checks PASS and no SKIP, or explicit HOLD if not achieved,
- artifact paths,
- current tests/coverage,
- full command list actually run,
- full M1-M17 regression summary,
- limitations that are not acceptance violations,
- next recommended milestone using machine-native wording only.

Review package must be current through M17 and include final test count, coverage, M14/M15/M16/M17 judge results, artifact paths, report paths, and current-stage commit hashes.

---

## Verification commands

Run:

```bash
python -m pytest machine_sim/tests/ -v
python -m pytest machine_sim/tests/ --cov=machine_sim --cov-report=term-missing
python -m machine_sim.cli.main check
python -m machine_sim.cli.main run -c configs/milestone_17_internal_neural_processing_unit.toml -t 20000 -s 42 -o output/demo_m17
python -m machine_sim.cli.main inspect output/demo_m17
python -m machine_sim.verification.milestone_17_judge output/demo_m17
```

Also verify accepted regression judges:

```bash
python -m machine_sim.verification.milestone_14_judge output/demo_m14
python -m machine_sim.verification.milestone_15_judge output/demo_m15
python -m machine_sim.verification.milestone_16_judge output/demo_m16
```

If fresh regenerated outputs are used, document exact paths.

Run full M1-M17 regression commands for reporting and include the actual command list in the report.

---

## Stage-closing evidence required

Final handoff must include all standard stage-closing evidence plus:

```text
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

Do not claim PASS or ACCEPTED unless all required checks are true.

---

## Final handoff format

```text
TASK_STATUS: PASS or PARTIAL_PASS
MILESTONE_17_STATUS: ACCEPTED or HOLD
READY_FOR_MILESTONE_18: YES or NO
Branch:
Starting commit hash:
Implementation commit hash:
Final remote commit hash:
Design summary:
Files changed:
Neural controller architecture:
Long-run demo parameters:
Tests:
Coverage:
Guardrail result:
M14/M15/M16 judge results:
M17 judge result:
Neural-vs-scalar comparison:
Plasticity update summary:
Successor neural transfer summary:
M17 demo output:
Artifact paths:
Full M1-M17 regression summary:
Stage closing chores result:
Known limitations:
Clean working tree:
```

---

## Acceptance criteria

```text
M17_INTERNAL_NEURAL_PROCESSING_UNIT: PASS
M17_LOCAL_SENSOR_INPUT_VECTOR: PASS
M17_NEURAL_ACTION_SELECTION: PASS
M17_LOCAL_PLASTICITY_UPDATE: PASS
M17_SUCCESSOR_NEURAL_STATE_TRANSFER: PASS
M17_NEURAL_VS_SCALAR_BASELINE_COMPARISON: PASS
M17_REQUIRED_ARTIFACTS_WRITTEN: PASS
M17_INDEPENDENT_JUDGE_PASS_NO_SKIP: PASS
M17_TESTS_ASSERT_REAL_NEURAL_BEHAVIOR: PASS
M14_M15_M16_REGRESSION_JUDGES_STILL_PASS: PASS
TESTS_AND_COVERAGE: PASS
GUARDRAILS: PASS
FULL_M1_M17_REGRESSION_REPORTED: PASS
MILESTONE_17_REPORT_CURRENT: PASS
REVIEW_PACKAGE_CURRENT: PASS
STAGE_CLOSING_CHORES_SATISFIED: PASS
CLEAN_WORKTREE_AND_PUSHED_REMOTE: PASS
```
