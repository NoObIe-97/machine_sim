# After Silicon — MiMo Milestone 14A Goal-Spec Hardening Prompt

## Repository and branch

Repository: `https://github.com/NoObIe-97/machine_sim.git`

Branch: `feature/milestone-1`

Start from the current Milestone 14 remote head:

```text
760dd11
```

Milestone 14 introduced useful adaptive-control infrastructure, but final acceptance is on HOLD. The current implementation does not yet satisfy the goal-spec intent because the demo is too forgiving, the judge thresholds are too weak, descendant transfer is skipped, signal observation is absent, and action selection still relies on a mostly fixed priority ladder.

Do not start Milestone 15.

This is still a **goal-spec task**. Implement, run, judge, revise, and repeat until the independent judge passes the strengthened goal conditions below.

Before final handoff, invoke and satisfy:

```text
prompts/skills/stage_closing_chores.md
```

---

## Current review decision

```text
M14_ADAPTIVE_STATE_VECTOR: PASS
M14_LOCAL_FEEDBACK_UPDATE_INFRASTRUCTURE: PARTIAL_PASS
M14_ACTION_SELECTION_USES_FULL_ADAPTIVE_STATE: FAIL
M14_SIGNAL_BEHAVIOR_ADAPTS: PARTIAL_PASS
M14_DESCENDANT_ADAPTIVE_STATE_TRANSFER: FAIL_SKIPPED_IN_DEMO
M14_LARGE_SPARSE_LONG_RUN_ENVIRONMENT: FAIL
M14_NO_EARLY_COLLAPSE_LONG_RUN: PASS_BUT_TRIVIAL
M14_STATIC_VS_ADAPTIVE_COMPARISON: PARTIAL_PASS_WEAK_PRESSURE
M14_INDEPENDENT_JUDGE_PASS: FAIL_WEAK_JUDGE_THRESHOLDS
M14_LONG_RUN_ARTIFACTS_WRITTEN: PASS
M14_TESTS_AND_COVERAGE: PASS
M14_FINAL_ACCEPTANCE: HOLD
READY_FOR_MILESTONE_15: NO
```

---

## What already passed and should be preserved

Keep and improve these pieces:

- `machine_sim/agents/adaptive_control.py`
- `AdaptiveStateVector`
- `AdaptiveController`
- bounded adaptive-state update from local feedback
- adaptive signal interval/parameter modulation
- adaptive state snapshots
- long-run artifacts under `output/demo_m14/`
- independent judge script structure
- M14 tests, extending them as required

---

## Blocking issue 1 — demo environment is not large/sparse/pressured enough

Current demo uses roughly:

```text
grid_width = 40
grid_height = 40
resource_density = 0.9
hazard_density = 0.01
power_drain_rate = 0.0
fabrication_enabled = false
capsule_enabled = false
max_ticks reported as 3000
```

This is not the requested long-run sparse operating field. It is a forgiving survival sandbox.

Update `configs/milestone_14_long_run_adaptation.toml` and runtime support so the main M14 demo satisfies:

```text
grid_width >= 120
grid_height >= 120
initial unit_count between 3 and 12
max_ticks >= 20000 in the actual M14 demo command
resource_density substantially below 0.9 unless resources are explicitly pocketed
hazard_density high enough to create measurable but non-instant exposure
power_drain_rate > 0
starting power high enough to avoid early collapse but not so high that survival is trivial
fabrication_enabled = true
capsule_enabled = true if needed for descendant state transfer
signal_default_radius and/or placement tuned so signal observations can occur
```

If 20,000 ticks is too slow, optimize sampling/logging first. Do not lower the acceptance target without a documented judge-visible reason and a separate long-run profile.

---

## Blocking issue 2 — action selection is still mostly fixed

Current unit logic still uses a fixed priority ladder: critical power, low power, maintain, signal, scan, idle. Adaptive state mostly changes signal interval/parameters and scan interval.

M14A must make adaptive state materially affect broader action selection.

Requirements:

- Use `AdaptiveController.compute_action_scores()` or an equivalent internal scoring system in `MachineUnitImpl.decide()` after safety-critical overrides.
- Adaptive state must influence at least MOVE, SCAN, HARVEST, EMIT_SIGNAL, and IDLE/CONSERVE selection.
- Resource/hazard local readings should influence scores through adaptive biases, not global knowledge.
- Critical safety overrides are allowed for very low power or critical component state, but normal operating ticks must be adaptive-score-driven.
- Tests must prove two units with different adaptive states choose materially different action distributions under the same local sensed state.

---

## Blocking issue 3 — local feedback is too approximate

Current feedback uses event labels and a fixed `+5` harvest reward. Strengthen local feedback evidence.

Requirements:

- Compute feedback from actual before/after local state where practical: power delta, component-health delta, action result success, signal cost, resource extraction result, hazard encounter, movement block, scan observations.
- Store sampled feedback trace entries in a bounded JSONL artifact:

```text
local_feedback_trace.jsonl
```

- Judge must verify that adaptive-state changes correlate with nonzero local feedback entries, not only first-vs-last drift.

---

## Blocking issue 4 — signal observation/adaptation is not actually demonstrated

Current report admits units are too far apart for signal observation. Fix this.

Requirements:

- Main demo must produce nonzero signal emissions and nonzero signal observations.
- Signal-related local feedback must update signal tendency or signal parameters.
- Artifact summary must report:

```text
total_signal_emissions
total_signal_observations
signal_emission_rate_delta
signal_pattern_bias_delta or equivalent
```

- Judge must fail if signal observations are zero.

---

## Blocking issue 5 — descendant transfer is skipped

Current judge treats missing descendant trace as `SKIP`; this violates the goal spec.

Requirements:

- Main M14 demo must enable fabrication/descendant initialization.
- At least one descendant adaptive-state transfer must occur, or the judge must fail.
- Generate:

```text
descendant_adaptive_state_trace.jsonl
```

- Each entry should include source unit id, successor unit id, tick, source adaptive summary, successor adaptive summary, and bounded delta summary.
- Judge must require PASS for descendant transfer, not SKIP.

---

## Blocking issue 6 — independent judge thresholds are too weak

Strengthen `machine_sim/verification/milestone_14_judge.py`.

Required judge checks:

```text
long_run_ticks_check: run_ticks >= 20000
large_sparse_environment_check: grid_width >= 120, grid_height >= 120, initial_unit_count <= 12, and resource/hazard pressure nontrivial
no_early_collapse_check: at least one late-run active source or descendant path, but not because power_drain_rate == 0
adaptive_state_changed_check: early-vs-late adaptive state delta exceeds documented threshold
action_distribution_changed_check: early-vs-late action distribution delta exceeds documented threshold
local_feedback_update_evidence_check: local_feedback_trace exists and has nonzero feedback events correlated with state deltas
signal_adaptation_check: signal emissions > 0, signal observations > 0, and signal-related adaptive parameter delta > threshold
descendant_transfer_check: descendant transfer artifact exists and has >= 1 valid transfer
static_vs_adaptive_difference_check: adaptive/static comparison has nonzero action-distribution difference and at least one nontrivial runtime metric delta
artifact_schema_check: all required artifacts present
bounded_trace_size_check: JSONL traces are sampled/bounded
machine_native_wording_check: no forbidden terms in artifacts
```

No SKIP is allowed for required goal checks.

The judge should write:

```text
output/demo_m14/milestone_14_judge_result.json
```

and must exit nonzero on failure.

---

## Blocking issue 7 — static-vs-adaptive comparison is weak

Current static and adaptive runs both finish with all units active and nearly identical emissions/scans.

Requirements:

- Keep same-seed static vs adaptive comparison.
- Environment must be pressured enough that adaptive vs static produces meaningful differences.
- The adaptive run does not need to win every metric, but comparison must show:

```text
action_distribution_delta > threshold
adaptive_state_delta > threshold
at least one runtime metric delta > threshold
```

Runtime metric may be active count, median lifetime, resource extraction, hazard exposure, movement block rate, signal observation, or descendant transfer count.

---

## Required artifacts

Main M14 demo must write:

```text
output/demo_m14/long_run_adaptation_summary.json
output/demo_m14/unit_adaptive_state_trace.jsonl
output/demo_m14/action_distribution_trace.jsonl
output/demo_m14/unit_lifetime_trace.jsonl
output/demo_m14/local_feedback_trace.jsonl
output/demo_m14/descendant_adaptive_state_trace.jsonl
output/demo_m14/resource_hazard_field_summary.json
output/demo_m14/adaptive_vs_static_compare.json
output/demo_m14/milestone_14_judge_result.json
```

Summary must include:

```text
run_ticks
grid_width
grid_height
initial_unit_count
final_active_unit_count
descendant_active_count
power_drain_rate
resource_density_or_pocket_summary
hazard_density_or_region_summary
unit_lifetime_summary
action_distribution_early
action_distribution_late
action_distribution_delta
adaptive_state_delta_summary
local_feedback_summary
resource_extraction_summary
hazard_exposure_summary
movement_block_summary
signal_behavior_summary
descendant_transfer_summary
adaptive_vs_static_summary
judge_status
```

---

## Test hardening requirements

Add or strengthen tests for:

1. Adaptive action scoring affects MOVE/SCAN/HARVEST/SIGNAL/IDLE probabilities.
2. `MachineUnitImpl.decide()` uses adaptive scoring in normal operating conditions.
3. Local feedback trace records nonzero power/resource/hazard/signal/block feedback when those events occur.
4. Signal observation changes signal-related adaptive parameters.
5. Descendant adaptive-state transfer occurs when fabrication succeeds.
6. Descendant transfer is bounded, related to source state, and not an exact unbounded copy.
7. Judge fails when run ticks are below 20,000.
8. Judge fails when descendant transfer artifact is missing.
9. Judge fails when signal observations are zero.
10. Judge passes only for the strengthened demo artifacts.

Existing tests must continue to pass.

---

## Documentation requirements

Update:

```text
docs/milestone_14_goal_spec.md
docs/milestone_14_report.md
docs/review_package.md
```

M14 report must include:

- exact long-run command with `-t 20000` or greater,
- actual large-field parameters,
- actual signal observation count,
- actual descendant transfer count,
- actual adaptive/static comparison with nontrivial deltas,
- judge result with all required checks PASS and no SKIP,
- artifact paths including `local_feedback_trace.jsonl` and `descendant_adaptive_state_trace.jsonl`,
- current tests/coverage,
- full M1-M14 regression summary,
- limitations that are not acceptance violations.

Review package must list:

```text
e9c0a87 — Milestone 13 compressed summary cross-unit consistency
760dd11 — Milestone 14 initial long-run adaptive control
<new M14A commit> — Milestone 14A goal-spec hardening
```

---

## Verification commands

Run:

```bash
python -m pytest machine_sim/tests/ -v
python -m pytest machine_sim/tests/ --cov=machine_sim --cov-report=term-missing
python -m machine_sim.cli.main check
python -m machine_sim.cli.main run -c configs/milestone_14_long_run_adaptation.toml -t 20000 -s 42 -o output/demo_m14
python -m machine_sim.cli.main inspect output/demo_m14
python -m machine_sim.verification.milestone_14_judge output/demo_m14
```

Run full M1-M14 regression commands for reporting and include the actual command list in the report.

---

## Stage-closing evidence required

Final handoff must include all standard stage-closing evidence plus:

```text
M14_GOAL_SPEC_SATISFIED: yes
M14_INDEPENDENT_JUDGE_STATUS: PASS
M14_NO_SKIPPED_REQUIRED_JUDGE_CHECKS: yes
M14_LONG_RUN_TICKS_GE_20000: yes
M14_LARGE_SPARSE_FIELD: yes
M14_SIGNAL_OBSERVATIONS_NONZERO: yes
M14_DESCENDANT_TRANSFER_NONZERO: yes
M14_STATIC_VS_ADAPTIVE_NONTRIVIAL_DELTA: yes
```

Do not claim PASS or ACCEPTED unless all are true.

---

## Final handoff format

```text
MILESTONE_14A_STATUS: PASS or PARTIAL_PASS
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
Signal observation summary:
Descendant transfer summary:
M14 demo output:
Artifact paths:
Full M1-M14 regression summary:
Stage closing chores result:
Known limitations:
Clean working tree:
```

---

## Acceptance criteria

```text
M14A_LARGE_SPARSE_LONG_RUN_ENVIRONMENT: PASS
M14A_ACTION_SELECTION_FULLY_USES_ADAPTIVE_STATE: PASS
M14A_LOCAL_FEEDBACK_TRACE_AND_UPDATE: PASS
M14A_SIGNAL_OBSERVATION_AND_ADAPTATION: PASS
M14A_DESCENDANT_ADAPTIVE_STATE_TRANSFER: PASS
M14A_STATIC_VS_ADAPTIVE_NONTRIVIAL_COMPARISON: PASS
M14A_STRONG_INDEPENDENT_JUDGE: PASS
M14A_JUDGE_PASS_NO_SKIP: PASS
M14A_LONG_RUN_ARTIFACTS_COMPLETE: PASS
M14A_TESTS_ASSERT_REAL_RUNTIME_BEHAVIOR: PASS
TESTS_AND_COVERAGE: PASS
GUARDRAILS: PASS
FULL_M1_M14_REGRESSION_REPORTED: PASS
MILESTONE_14_REPORT_CURRENT: PASS
REVIEW_PACKAGE_CURRENT: PASS
STAGE_CLOSING_CHORES_SATISFIED: PASS
CLEAN_WORKTREE_AND_PUSHED_REMOTE: PASS
```
