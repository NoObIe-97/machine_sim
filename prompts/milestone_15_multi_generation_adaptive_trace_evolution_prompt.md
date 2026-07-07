# After Silicon — MiMo Milestone 15 Goal Spec: Multi-Generation Adaptive Trace Evolution

## Repository and branch

Repository: `https://github.com/NoObIe-97/machine_sim.git`

Branch: `feature/milestone-1`

Start from the accepted Milestone 14B remote head:

```text
347d544
```

Milestone 14 is accepted. Milestone 15 must build on the M14A long-run internal adaptive-control substrate and should not regress the accepted 20,000-tick large-field demo, strengthened judge, adaptive action scoring, local feedback traces, signal observation, or descendant adaptive-state transfer.

Before final handoff, invoke and satisfy:

```text
prompts/skills/stage_closing_chores.md
```

---

## Strategic direction

Milestone 14 proved that adaptive state can change during long-run operation and that descendant adaptive-state transfer can occur. Milestone 15 should now test whether those adaptive states form measurable generation-indexed trajectories across multiple descendant steps.

The goal is not another passive diagnostic layer. The goal is to create a long-run simulation condition where adaptive-state transfer can occur repeatedly enough to study multi-generation adaptive trajectories.

---

## Conceptual boundary

Use machine-native terminology only. Do not introduce human/social/biological/political/economic/strategic/emotional framing in runtime code, config keys, event labels, artifact schemas, or reports.

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
multi-generation adaptive trace
adaptive-state trajectory
generation-indexed adaptive state
source unit
successor unit
descendant initialization state
adaptive-state transfer
bounded transfer variation
lineage-indexed adaptive delta
adaptive trajectory compression
cross-generation adaptive comparison
transfer continuity score
adaptive drift envelope
```

If existing accepted fields use older terms, do not rename them unless safe. All new M15 names should follow the preferred machine-native vocabulary.

---

## Milestone 15 goal statement

Implement and demonstrate multi-generation adaptive-state trajectory tracking.

The simulator must run long enough and with suitable fabrication/transfer parameters to produce multiple generation-indexed adaptive-state transfer records. It must then output bounded artifacts that allow later offline study of how adaptive action-selection state changes across source-to-successor transitions and across generation indices.

---

## Core runtime requirements

### 1. Multi-generation long-run demo

Add a main M15 demo config:

```text
configs/milestone_15_multi_generation_adaptive_trace.toml
```

Recommended minimums:

```text
grid_width >= 120
grid_height >= 120
initial unit_count between 4 and 12
max_ticks >= 30000 for the main M15 demo
seed = 42
adaptive_enabled = true
signal_enabled = true
fabrication_enabled = true
capsule_enabled = true
long_run_adaptation_enabled = true
```

Tune resources, hazards, power drain, fabrication costs, and placement so that:

```text
successful fabrication count >= 5
descendant adaptive-state transfer count >= 5
at least 3 distinct generation_index values are observed
at least one active source or successor path exists near the late-run checkpoint
signal observations remain nonzero
```

If runtime becomes heavy, optimize sampling/logging. Do not simply lower the generation/transfer requirements.

### 2. Generation-indexed adaptive-state records

Extend the M14 transfer artifact or add a new artifact:

```text
output/demo_m15/generation_adaptive_state_trace.jsonl
```

Each record should include:

```text
tick
source_unit_id
successor_unit_id
source_generation_index
successor_generation_index
source_adaptive_state_summary
successor_adaptive_state_summary
adaptive_state_delta
transfer_variation_summary
source_lifetime_ticks_at_transfer
successor_initial_power_ratio
local_feedback_context_summary
```

The artifact must be sampled/bounded if needed but must preserve all transfer records for the main M15 run if the count is moderate.

### 3. Adaptive trajectory comparison

Add runtime or analysis support to compare adaptive state across generation-indexed transfers.

Suggested output fields:

```text
transfer_count
generation_index_span
avg_transfer_delta
max_transfer_delta
avg_source_successor_similarity
adaptive_weight_drift_summary
signal_parameter_drift_summary
resource_response_drift_summary
hazard_response_drift_summary
trajectory_continuity_score
```

The comparison must use actual adaptive-state values, not placeholder constants.

### 4. Adaptive trajectory compression

Long runs should write a compact summary artifact:

```text
output/demo_m15/adaptive_trajectory_summary.json
```

Required sections:

```text
run_parameters
transfer_summary
generation_summary
adaptive_state_delta_summary
trajectory_continuity_summary
signal_adaptation_summary
resource_hazard_response_summary
late_run_survival_summary
artifact_size_summary
judge_status
```

### 5. Static or reduced-transfer reference

Provide a comparison run or reference mode to show that transfer-enabled adaptive runs produce different generation-indexed trace structure than a reduced-transfer baseline.

Possible baseline:

```text
same seed, same field, fabrication disabled
```

or:

```text
same seed, same field, adaptive-state transfer disabled while fabrication remains enabled
```

Required comparison artifact:

```text
output/demo_m15/adaptive_transfer_compare.json
```

Required fields:

```text
transfer_enabled_count
reference_transfer_count
adaptive_state_delta_enabled
adaptive_state_delta_reference
signal_adaptation_delta
late_active_delta
generation_index_span_delta
```

### 6. No external decision control

M15 may analyze and judge, but it must not let the analysis module decide unit actions.

Unit action selection must remain internally driven by the M14 adaptive state and local feedback. Any new trajectory modules must be read-only observers.

---

## Independent M15 judge

Add or extend an independent judge:

```text
machine_sim/verification/milestone_15_judge.py
```

Input:

```text
output/demo_m15/
```

Output:

```text
output/demo_m15/milestone_15_judge_result.json
```

Required judge checks:

```text
long_run_ticks_check: run_ticks >= 30000
large_field_check: grid_width >= 120 and grid_height >= 120
transfer_count_check: descendant adaptive-state transfer count >= 5
generation_span_check: at least 3 distinct generation_index values
trajectory_artifact_schema_check: required M15 artifacts present and schema-valid
adaptive_state_delta_check: transfer deltas are numeric and nonzero
trajectory_continuity_check: continuity score is numeric and bounded
signal_observation_check: signal observations > 0
late_run_activity_check: active source or successor path exists near late-run checkpoint
reference_comparison_check: transfer-enabled vs reference comparison has nonzero structural difference
bounded_artifact_size_check: JSONL artifacts remain bounded/sampled
machine_native_wording_check: no forbidden terms in artifacts
```

All checks must PASS. No SKIP is allowed for required checks.

---

## Required artifacts

Main M15 run must write:

```text
output/demo_m15/adaptive_trajectory_summary.json
output/demo_m15/generation_adaptive_state_trace.jsonl
output/demo_m15/adaptive_transfer_compare.json
output/demo_m15/unit_adaptive_state_trace.jsonl
output/demo_m15/action_distribution_trace.jsonl
output/demo_m15/local_feedback_trace.jsonl
output/demo_m15/descendant_adaptive_state_trace.jsonl
output/demo_m15/resource_hazard_field_summary.json
output/demo_m15/milestone_15_judge_result.json
```

If reusing M14 artifact writers, ensure M15-specific artifacts are clearly present and documented.

---

## Test requirements

Add focused tests for M15. Tests can use shorter runs than the main demo.

Required tests:

1. Generation-indexed transfer record schema is complete.
2. Transfer delta computation is numeric, bounded, and nonzero when states differ.
3. Transfer continuity score is bounded and deterministic.
4. Multi-generation trace builder records at least two generation indices in a controlled short run or synthetic fixture.
5. Reference comparison detects transfer-enabled vs transfer-disabled structural difference.
6. M15 judge fails when transfer count is below threshold.
7. M15 judge fails when generation span is too small.
8. M15 judge fails when required artifacts are missing.
9. M15 judge passes on a valid generated or fixture artifact set.
10. Existing M14 judge and M14 tests still pass.

Existing tests must continue to pass.

---

## Documentation requirements

Add:

```text
docs/milestone_15_report.md
```

Update:

```text
docs/review_package.md
```

M15 report must include:

- design summary,
- relation to M14 adaptive-control substrate,
- long-run parameters,
- transfer count and generation span,
- adaptive trajectory comparison metrics,
- transfer-enabled vs reference comparison,
- signal observation summary,
- late-run activity summary,
- judge result with all checks PASS and no SKIP,
- artifact paths,
- current tests/coverage,
- full command list actually run,
- full M1-M15 regression summary,
- limitations that are not acceptance violations,
- next recommended milestone using machine-native wording only.

Review package must be current through M15 and include final test count, coverage, judge result, artifact paths, report paths, and current-stage commit hashes.

---

## Verification commands

Run:

```bash
python -m pytest machine_sim/tests/ -v
python -m pytest machine_sim/tests/ --cov=machine_sim --cov-report=term-missing
python -m machine_sim.cli.main check
python -m machine_sim.cli.main run -c configs/milestone_15_multi_generation_adaptive_trace.toml -t 30000 -s 42 -o output/demo_m15
python -m machine_sim.cli.main inspect output/demo_m15
python -m machine_sim.verification.milestone_15_judge output/demo_m15
```

Also run the accepted M14 judge to ensure no regression:

```bash
python -m machine_sim.cli.main run -c configs/milestone_14_long_run_adaptation.toml -t 20000 -s 42 -o output/demo_m14
python -m machine_sim.verification.milestone_14_judge output/demo_m14
```

Run full M1-M15 regression commands for reporting and include the actual command list in the report.

---

## Stage-closing evidence required

Final handoff must include all standard stage-closing evidence plus:

```text
M15_GOAL_SPEC_SATISFIED: yes
M15_INDEPENDENT_JUDGE_STATUS: PASS
M15_NO_SKIPPED_REQUIRED_JUDGE_CHECKS: yes
M15_LONG_RUN_TICKS_GE_30000: yes
M15_TRANSFER_COUNT_GE_5: yes
M15_GENERATION_SPAN_GE_3: yes
M15_SIGNAL_OBSERVATIONS_NONZERO: yes
M15_REFERENCE_COMPARISON_NONTRIVIAL: yes
```

Do not claim PASS or ACCEPTED unless all are true.

---

## Final handoff format

```text
TASK_STATUS: PASS or PARTIAL_PASS
MILESTONE_15_STATUS: ACCEPTED or HOLD
READY_FOR_MILESTONE_16: YES or NO
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
M15 judge result:
Transfer/generation summary:
Reference comparison summary:
Signal observation summary:
M15 demo output:
Artifact paths:
Full M1-M15 regression summary:
Stage closing chores result:
Known limitations:
Clean working tree:
```

---

## Acceptance criteria

```text
M15_MULTI_GENERATION_LONG_RUN_ENVIRONMENT: PASS
M15_GENERATION_INDEXED_ADAPTIVE_TRACE: PASS
M15_TRANSFER_COUNT_AND_GENERATION_SPAN: PASS
M15_ADAPTIVE_TRAJECTORY_COMPARISON: PASS
M15_TRAJECTORY_COMPRESSION_SUMMARY: PASS
M15_REFERENCE_COMPARISON: PASS
M15_INDEPENDENT_JUDGE_PASS_NO_SKIP: PASS
M15_REQUIRED_ARTIFACTS_WRITTEN: PASS
M15_TESTS_ASSERT_REAL_RUNTIME_BEHAVIOR: PASS
M14_REGRESSION_JUDGE_STILL_PASS: PASS
TESTS_AND_COVERAGE: PASS
GUARDRAILS: PASS
FULL_M1_M15_REGRESSION_REPORTED: PASS
MILESTONE_15_REPORT_CURRENT: PASS
REVIEW_PACKAGE_CURRENT: PASS
STAGE_CLOSING_CHORES_SATISFIED: PASS
CLEAN_WORKTREE_AND_PUSHED_REMOTE: PASS
```
