# After Silicon — MiMo Milestone 14 Goal Spec: Long-Run Internal Adaptive Control

## Repository and branch

Repository: `https://github.com/NoObIe-97/machine_sim.git`

Branch: `feature/milestone-1`

Start from the current Milestone 13 remote head:

```text
e9c0a87
```

Milestone 13 is technically complete. Before final M14 handoff, ensure the review package history includes the M13 implementation commit `e9c0a87` and that M14 final docs are fully current.

This milestone is intentionally **goal-spec driven**. Treat the spec below as the goal. Implement, test, run, judge, revise, and repeat until an independent judge pass is achieved. Do not stop at a superficial implementation.

Before final handoff, invoke and satisfy:

```text
prompts/skills/stage_closing_chores.md
```

---

## Strategic correction

Previous milestones built substantial diagnostics and external analysis layers. Those layers are useful instrumentation, but the project target now returns to the core simulation question:

```text
Drop a small number of machine units into a large operating field, let them run for a long time, and observe whether internal action-selection parameters adapt from local operational feedback.
```

Milestone 14 must therefore be a **runtime adaptation milestone**, not another passive analytics milestone.

The simulator should define:

- a large operating field,
- a small initial unit set,
- an embodiment/action envelope,
- harvestable resources,
- non-instant hazards,
- long tick counts,
- bounded local feedback,
- descendant transfer of bounded adaptive state,
- long-run traces for later offline study.

The units must decide which allowed actions to perform and how their internal tendencies change. External analyzers may record and judge; they must not decide unit actions.

---

## Conceptual boundary

Use machine-native terminology. Do not introduce human/social/biological/political/economic/strategic/emotional framing in runtime code, config keys, event labels, artifact schemas, or committed reports.

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
```

Preferred machine-native terms:

```text
internal adaptive control
adaptive state vector
action-selection weights
local operational feedback
bounded feedback update
operational trace transfer
descendant initialization state
generation-indexed adaptive state
embodiment envelope
action envelope
resource-hazard field
harvestable resource pocket
hazard exposure
power recovery
component recovery
long-run diagnostic trace
adaptation trajectory
static baseline
adaptive variant
```

If existing accepted config fields contain older terms, do not rename them unless safe; however, all new M14 names should follow this boundary.

---

## Milestone 14 goal statement

Implement long-run internal adaptive control in machine units.

A unit must possess an internal bounded adaptive state that modulates its action selection and action parameters over time. This adaptive state must be updated only from local operational feedback observed by that unit.

The unit must not receive global-map knowledge, oracle outputs, or external analyzer decisions. The environment provides local conditions and action results; the unit updates its own tendencies.

---

## Core simulation requirements

### 1. Large sparse operating field

Add a long-run demo configuration such as:

```text
configs/milestone_14_long_run_adaptation.toml
```

Recommended long-run characteristics:

```text
grid_width >= 120
grid_height >= 120
initial unit_count between 3 and 12
max_ticks >= 20000 for the main M14 demo
seed = 42
resource pockets rather than uniform-only resources
hazard regions that damage gradually, not instantly
slow baseline component/power decay
initial reserves high enough to avoid early collapse
resource recovery or renewable resource pockets if supported
trace/output sampling enabled to control artifact size
```

If runtime is too slow at 20,000 ticks, optimize or add sampling. Do not simply lower the main demo to a short run. Tests may use shorter runs, but the M14 demo must be meaningfully long.

Also add a shorter test config if useful:

```text
configs/milestone_14_adaptation_test.toml
```

### 2. Unit embodiment/action envelope

Each adaptive unit should have a clear action envelope. It can only choose from actions its body/runtime supports.

Allowed action families may include existing actions such as:

```text
move
scan
extract
emit_signal
conserve or idle
fabricate if enabled and conditions permit
```

Do not add magical new abilities. If a new action is needed, it must be machine-native and physically plausible within the simulator.

Document the embodiment envelope in:

```text
docs/milestone_14_report.md
```

### 3. Internal adaptive state vector

Add an internal adaptive state to each adaptive unit, for example in a new module or in the unit implementation:

```text
machine_sim/agents/adaptive_control.py
```

Suggested fields:

```text
move_weight
scan_weight
extract_weight
signal_weight
conserve_weight
fabricate_weight
exploration_bias
resource_following_bias
hazard_avoidance_bias
signal_emission_rate
signal_pattern_bias
signal_radius_bias
scan_interval_bias
extract_threshold
fabrication_threshold
power_conservation_threshold
```

Requirements:

- Values must be bounded.
- Initial values must be configurable or deterministic.
- Values must influence actual action selection or action parameters.
- Values must change over time in adaptive units.
- Values must remain unchanged or minimally changed in static baseline units.
- Updates must be local-feedback-driven.

### 4. Local operational feedback update

After actions, units must derive feedback from local action results and local state deltas.

Examples of local feedback signals:

```text
power_delta
component_health_delta
resource_detected
resource_extracted
hazard_exposure
movement_blocked
signal_observed
signal_emitted
signal_cost
scan_result_count
fabrication_attempt_result
local_density_or_proximity_if sensed locally
```

The adaptive update must not use:

```text
global resource map
global hazard map
future state
other units' hidden state
external analyzer outputs
post-run metrics
```

Suggested update behavior:

- Increase tendencies associated with recent positive local operational deltas.
- Decrease tendencies associated with recent negative local operational deltas.
- Preserve exploration pressure so the unit does not collapse to one action forever.
- Keep all values bounded.
- Add small deterministic bounded variation if needed.

### 5. Action selection must be internally controlled

The adaptive state must materially affect runtime behavior.

Required action-selection behavior:

- Action probabilities or scores are computed from the internal adaptive state plus local sensed state.
- Different adaptive states should produce different action distributions under the same local conditions.
- Action distributions should measurably change between early and late long-run windows.

### 6. Signal behavior must be adaptive

The existing signal system should be connected to internal adaptation.

At minimum:

- signal emission rate or signal action weight is adaptive,
- signal pattern selection is adaptive or biased by internal state,
- signal cost affects future signal tendency,
- local signal observations can affect scan/move/signal tendencies.

Do not assign semantic meaning to signal patterns.

### 7. Descendant adaptive-state transfer

When fabrication/descendant initialization occurs, the successor should receive a bounded transfer of the source unit's adaptive state.

Use machine-native wording such as:

```text
adaptive state transfer
descendant initialization state
bounded operational trace transfer
```

Requirements:

- Transfer should include action weights and key adaptive biases.
- Transfer should be bounded and compact.
- Transfer should include deterministic bounded variation so successors are not exact copies.
- Successor adaptive state should be measurably related to source state.
- Transfer should integrate with existing capsule/trace mechanisms if possible, without breaking accepted capsule behavior.

### 8. Long-run trace outputs

M14 must produce data for later offline study.

Add artifacts under:

```text
output/demo_m14/
```

Required or equivalent artifacts:

```text
long_run_adaptation_summary.json
unit_adaptive_state_trace.jsonl
action_distribution_trace.jsonl
unit_lifetime_trace.jsonl
descendant_adaptive_state_trace.jsonl
resource_hazard_field_summary.json
adaptive_vs_static_compare.json
```

Artifact size must be controlled. Use sampling intervals or bounded trace windows for long runs.

The summary artifact must include:

```text
run_ticks
initial_unit_count
final_active_unit_count
unit_lifetime_summary
action_distribution_early
action_distribution_late
action_distribution_delta
adaptive_state_delta_summary
resource_extraction_summary
hazard_exposure_summary
movement_block_summary
signal_behavior_summary
descendant_transfer_summary
adaptive_vs_static_summary
```

### 9. Static baseline comparison

Add a static baseline mode/config where units use fixed action selection without internal adaptive updates.

Required comparison:

```text
same seed
same environment
same initial unit count
static baseline vs adaptive variant
```

The comparison must report at least these metrics:

```text
active_unit_count_delta
median_lifetime_delta
resource_extraction_delta
hazard_exposure_delta
movement_block_delta
signal_action_delta
fabrication_success_delta if fabrication enabled
action_distribution_delta
```

The adaptive run does not need to win every metric. It must, however, show measurable internal adaptation and at least one meaningful runtime behavior difference versus the static baseline.

### 10. No early-collapse requirement

The long-run demo must not be trivial extinction.

Acceptance target:

```text
At least one unit remains active at a meaningful late-run checkpoint, or at least one descendant path remains active if source units deactivate.
```

If the first attempt collapses too early, tune the environment/body parameters, not the analysis report.

---

## Independent judge requirement

This milestone is a test of goal-driven implementation. Add an independent M14 judge script or verifier that evaluates the goal spec from generated artifacts.

Suggested path:

```text
machine_sim/verification/milestone_14_judge.py
```

Alternative path acceptable:

```text
scripts/judge_milestone_14.py
```

Judge input:

```text
output/demo_m14/
```

Judge output:

```text
output/demo_m14/milestone_14_judge_result.json
```

The judge must produce:

```text
M14_JUDGE_STATUS: PASS or FAIL
```

and a JSON object with individual checks.

Required judge checks:

```text
long_run_ticks_check
large_sparse_environment_check
no_early_collapse_check
adaptive_state_changed_check
action_distribution_changed_check
local_feedback_update_evidence_check
signal_adaptation_check
descendant_transfer_check
static_vs_adaptive_difference_check
artifact_schema_check
bounded_trace_size_check
machine_native_wording_check
```

The final MiMo handoff must include the judge result. Do not claim M14 accepted if the judge fails.

The judge must be independent of the implementation path: it should evaluate artifacts and documented schemas rather than simply checking that functions exist.

---

## Tests required

Add focused unit/integration tests. Tests can use shorter runs than the full M14 demo, but must verify behavior.

Required tests:

1. **Adaptive state bounds**
   - Repeated updates keep all adaptive state values within documented bounds.

2. **Local feedback update direction**
   - Positive resource/power feedback changes relevant tendencies.
   - Hazard/damage feedback changes hazard avoidance or movement tendencies.
   - Blocked movement feedback changes movement/exploration tendencies.

3. **Action selection uses adaptive state**
   - Two units with different adaptive states produce different action score/probability distributions under the same sensed state.

4. **Adaptive state changes over a run**
   - Adaptive units show nonzero early-vs-late adaptive state delta.

5. **Static baseline remains static**
   - Static baseline action-selection parameters do not adapt, or adapt far less than adaptive units.

6. **Signal adaptation**
   - Signal emission tendency, signal pattern bias, or equivalent signal parameter changes after local signal-related feedback.

7. **Descendant transfer**
   - Successor adaptive state is bounded, related to source state, and not an exact unbounded copy.

8. **Long-run artifact schema**
   - Required M14 artifacts are written and contain required fields.

9. **Adaptive vs static comparison**
   - Same-seed adaptive/static runs produce a measurable difference in at least one runtime metric and nonzero action distribution delta.

10. **Judge pass test**
   - The judge can read `output/demo_m14/` and returns PASS for the generated demo.

Existing tests must keep passing.

---

## Runtime and performance guidance

Long runs must be possible without exhausting memory.

Requirements:

- event/trace output should support sampling or bounded JSONL streaming,
- avoid storing every tick of every field in memory for long runs,
- summary metrics should be computed incrementally or from sampled traces,
- tests should remain fast enough for full regression,
- the long demo may be heavier than tests but should still be practical.

Do not reduce the main M14 long-run demo to a short toy run unless you document why and provide an alternate long-run profile.

---

## Documentation requirements

Add:

```text
docs/milestone_14_goal_spec.md
docs/milestone_14_report.md
```

The goal spec document must contain the acceptance specification in stable wording. The report must describe what was implemented and provide actual results.

M14 report must include:

- design summary,
- embodiment/action envelope,
- internal adaptive state fields,
- local feedback update rules,
- signal adaptation behavior,
- descendant adaptive-state transfer behavior,
- long-run environment parameters,
- static-vs-adaptive comparison results,
- judge checks and judge result,
- artifact paths,
- current tests/coverage,
- guardrail result,
- full M1-M14 regression summary,
- known limitations,
- next recommended milestone using machine-native wording only.

Update:

```text
docs/review_package.md
```

Review package must be current through M14 and include:

- M13 implementation commit `e9c0a87`, if not already listed,
- M14 implementation commit,
- final tests/coverage,
- full M1-M14 summary,
- M14 demo output,
- M14 judge status,
- M14 artifact/report paths,
- clean working tree.

---

## Required verification commands

Run full tests and guardrails:

```bash
python -m pytest machine_sim/tests/ -v
python -m pytest machine_sim/tests/ --cov=machine_sim --cov-report=term-missing
python -m machine_sim.cli.main check
```

Run M14 demo and judge:

```bash
python -m machine_sim.cli.main run -c configs/milestone_14_long_run_adaptation.toml -t 20000 -s 42 -o output/demo_m14
python -m machine_sim.cli.main inspect output/demo_m14
python -m machine_sim.verification.milestone_14_judge output/demo_m14
```

If the judge script path differs, use the implemented equivalent and document the exact command.

Run adaptive/static comparison command if implemented as separate CLI command; otherwise ensure the M14 run writes `adaptive_vs_static_compare.json`.

Run full M1-M14 regression commands for reports. Include the actual command list in the M14 report.

---

## Stage closing chores

Before final handoff, invoke and satisfy:

```text
prompts/skills/stage_closing_chores.md
```

Final handoff must include:

```text
STAGE_CLOSING_SKILL_INVOKED: yes
MILESTONE_REPORT_TITLE_CURRENT: yes
MILESTONE_REPORT_TESTS_CURRENT: yes
MILESTONE_REPORT_COVERAGE_CURRENT: yes
MILESTONE_REPORT_FULL_REGRESSION_CURRENT: yes
MILESTONE_REPORT_FULL_COMMAND_SET_PRESENT: yes
REVIEW_PACKAGE_TITLE_CURRENT: yes
REVIEW_PACKAGE_TESTS_CURRENT: yes
REVIEW_PACKAGE_COVERAGE_CURRENT: yes
REVIEW_PACKAGE_CURRENT_MILESTONE_SUMMARY: yes
CURRENT_STAGE_COMMIT_LISTED: yes
CURRENT_ARTIFACT_PATHS_REPORTED: yes
NEXT_MILESTONE_WORDING_MACHINE_NATIVE: yes
NO_STALE_DOC_VALUES_FOUND: yes
CLEAN_WORKTREE_AFTER_PUSH: yes
FINAL_REMOTE_HASH_REPORTED: yes
```

Also include:

```text
M14_GOAL_SPEC_SATISFIED: yes
M14_INDEPENDENT_JUDGE_STATUS: PASS
```

Do not claim `PASS`, `ACCEPTED`, or `READY_FOR_MILESTONE_15` unless every line is satisfied.

---

## Final handoff format

Final response must include:

```text
TASK_STATUS: PASS or PARTIAL_PASS
MILESTONE_14_STATUS: ACCEPTED or HOLD
READY_FOR_MILESTONE_15: YES or NO
Branch:
Starting commit hash:
Implementation commit hash:
Final remote commit hash:
Design summary:
Files changed:
Long-run demo parameters:
Tests:
Coverage:
Guardrail result:
M14 judge result:
Adaptive-vs-static comparison:
M14 demo output:
Artifact paths:
Full M1-M14 regression summary:
Stage closing chores result:
Known limitations:
Clean working tree:
```

---

## Acceptance criteria

Do not mark PASS unless all are true:

```text
M14_LARGE_SPARSE_LONG_RUN_ENVIRONMENT: PASS
M14_INTERNAL_ADAPTIVE_STATE_VECTOR: PASS
M14_LOCAL_FEEDBACK_UPDATE: PASS
M14_ACTION_SELECTION_USES_ADAPTIVE_STATE: PASS
M14_SIGNAL_BEHAVIOR_ADAPTS: PASS
M14_DESCENDANT_ADAPTIVE_STATE_TRANSFER: PASS
M14_STATIC_VS_ADAPTIVE_COMPARISON: PASS
M14_NO_EARLY_COLLAPSE_LONG_RUN: PASS
M14_LONG_RUN_ARTIFACTS_WRITTEN: PASS
M14_INDEPENDENT_JUDGE_PASS: PASS
M14_TESTS_ASSERT_REAL_RUNTIME_BEHAVIOR: PASS
TESTS_AND_COVERAGE: PASS
GUARDRAILS: PASS
FULL_M1_M14_REGRESSION_REPORTED: PASS
MILESTONE_14_REPORT_CURRENT: PASS
REVIEW_PACKAGE_CURRENT: PASS
STAGE_CLOSING_CHORES_SATISFIED: PASS
CLEAN_WORKTREE_AND_PUSHED_REMOTE: PASS
```

If any item fails, return `PARTIAL_PASS` with exact blockers and do not claim Milestone 14 is accepted.
