# After Silicon — MiMo Milestone 18 Goal Spec: Neural Controller Variant Sensitivity

## Repository and branch

Repository: `https://github.com/NoObIe-97/machine_sim.git`

Branch: `feature/milestone-1`

Start from the accepted Milestone 17C remote head:

```text
d89c1a9886dc9e046bc66ba91a8483383d24c6ff
```

Milestone 17 is accepted. Milestone 18 must build on the accepted M17/M17A/M17B/M17C internal neural processing unit, stable deterministic seeding, strict M17 judge, and documentation state. Do not regress the accepted M14, M15, M16, or M17 judges.

Before final handoff, invoke and satisfy:

```text
prompts/skills/stage_closing_chores.md
```

---

## Strategic direction

M17 introduced a compact recurrent neural controller with local sensor inputs, recurrent processing state, neural action preferences, local plasticity, successor neural-state transfer, and strict judge validation.

M18 should now compare neural controller variants scientifically. The objective is to determine how controller size, plasticity setting, and selected controller parameters affect run outcomes and internal neural trajectory traces.

This remains an observation-and-comparison milestone:

```text
controller variant set
→ deterministic long-run simulations
→ per-variant neural trajectory artifacts
→ cross-variant comparison metrics
→ parameter sensitivity summary
→ bounded report for offline inspection
```

No external analysis module may command, override, or force unit actions during a simulation run.

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
neural controller variant
variant sweep
controller sensitivity
processing-state trajectory
plasticity-rate variant
hidden-size variant
input-schema variant
action-preference distribution
neural transfer summary
trajectory signature
cross-variant similarity
run-family summary
bounded comparison artifact
```

Existing accepted legacy fields should not be renamed unless safe. All new M18 fields, configs, reports, and artifact schemas must follow machine-native wording.

---

## Milestone 18 goal statement

Implement deterministic cross-variant comparison for internal neural processing units.

M18 must run or post-process multiple neural controller variants under controlled field conditions, collect bounded artifacts for each variant, compare the resulting neural trajectories and runtime outcomes, and produce a sensitivity report identifying which controller parameters most strongly change observable machine-native metrics.

M18 must not replace the M17 controller architecture. It may expose additional configuration fields required to vary controller parameters, provided the M17 baseline still works and the M17 judge remains PASS.

---

## Core implementation requirements

### 1. Configurable neural controller parameters

Expose controller parameters through simulation configuration if not already configurable:

```text
neural_input_size
neural_hidden_size
neural_output_size
neural_param_output_size
neural_plasticity_rate
neural_weight_bound
neural_plasticity_enabled
```

Minimum acceptable implementation:

- `hidden_size` configurable.
- `plasticity_rate` configurable.
- `plasticity_enabled` already supported and must remain configurable.
- Existing default M17 behavior must remain unchanged when no M18-specific fields are provided.

All deterministic seed behavior from M17A must be preserved.

### 2. Variant sweep configuration

Add:

```text
configs/milestone_18_neural_controller_variant_sensitivity.toml
```

Define at least 5 variants:

```text
scalar_baseline
neural_h16_rate001
neural_h8_rate001
neural_h32_rate001
neural_h16_rate000
neural_h16_rate005
```

Equivalent variant names are acceptable if they are machine-native and clearly documented.

Requirements:

- All variants must use deterministic seeds.
- All neural variants must use the same field seed family unless a variant explicitly changes field seed for a documented reason.
- At least one neural variant must match the accepted M17 controller settings.
- At least one variant must disable plasticity.
- At least one variant must change hidden state size.
- At least one variant must change plasticity rate.

### 3. Variant run execution or post-processing

Implement a M18 run path that produces per-variant outputs. This may be a CLI command, a mode in the existing CLI, or a deterministic helper module invoked by the CLI.

Preferred output layout:

```text
output/demo_m18/variants/<variant_id>/
```

Each variant directory should contain:

```text
neural_processing_summary.json
neural_state_trace.jsonl
neural_action_trace.jsonl
neural_plasticity_trace.jsonl
neural_successor_transfer_trace.jsonl
neural_vs_scalar_compare.json or variant_runtime_summary.json
resource_hazard_field_summary.json
neural_controller_config.json
```

The scalar baseline may omit neural traces only if represented by a clearly documented scalar runtime summary. Neural variants must include neural traces.

Recommended run length:

```text
primary baseline-compatible neural variant: >= 20000 ticks
all other variants: >= 10000 ticks
```

Longer runs are acceptable if runtime remains practical.

### 4. Cross-variant comparison metrics

Create a comparison module such as:

```text
machine_sim/analysis/neural_variant_comparison.py
```

or integrate equivalent logic into a clearly named analysis component.

Required metrics:

```text
variant_count
per_variant_active_count
per_variant_transfer_count
per_variant_signal_observation_count
per_variant_plasticity_event_count
per_variant_action_distribution
per_variant_neural_state_delta
per_variant_successor_transfer_count
cross_variant_action_distribution_delta
cross_variant_neural_state_delta
cross_variant_runtime_metric_delta
```

### 5. Similarity matrix and sensitivity summary

Required artifact:

```text
output/demo_m18/neural_variant_similarity_matrix.json
```

Required fields:

```text
variant_ids
similarity_matrix
action_distribution_similarity_matrix
neural_state_similarity_matrix
runtime_metric_similarity_matrix
nontrivial_off_diagonal_difference_detected
```

Required artifact:

```text
output/demo_m18/neural_controller_sensitivity_summary.json
```

Required fields:

```text
variant_count
varied_parameters
sensitivity_score_by_parameter
most_sensitive_parameters
least_sensitive_parameters
plasticity_effect_summary
hidden_size_effect_summary
nontrivial_controller_parameter_effect_detected
```

Sensitivity scores must be numeric and bounded.

Do not claim causal certainty. Use sensitivity/comparison wording only.

### 6. Run-family summary artifact

Required artifact:

```text
output/demo_m18/neural_variant_sweep_summary.json
```

Required sections:

```text
run_family_parameters
variant_definitions
per_variant_runtime_summary
per_variant_neural_summary
similarity_matrix_summary
controller_sensitivity_summary
strict_regression_summary
artifact_size_summary
judge_status
source_artifact_references
```

### 7. M17 regression preservation

M18 must preserve M17’s accepted behavior and judge strictness.

Required:

```text
python -m machine_sim.verification.milestone_17_judge output/demo_m17
```

must PASS using current accepted or regenerated M17 artifacts.

M14/M15/M16 regression judges must also remain PASS or be explicitly verified with current artifacts.

---

## Independent M18 judge

Add:

```text
machine_sim/verification/milestone_18_judge.py
```

Input:

```text
output/demo_m18/
```

Output:

```text
output/demo_m18/milestone_18_judge_result.json
```

Required judge checks:

```text
variant_count_check: at least 5 variants, including scalar baseline and at least 4 neural variants
accepted_m17_variant_check: one variant matches accepted M17 neural settings
hidden_size_variant_check: at least one hidden-size variant differs from M17 baseline
plasticity_rate_variant_check: at least one plasticity-rate variant differs from M17 baseline
plasticity_disabled_variant_check: at least one neural variant has plasticity disabled
per_variant_artifact_check: required per-variant artifacts exist
per_variant_runtime_check: primary variant run_ticks >= 20000 and other variants run_ticks >= 10000
similarity_matrix_check: matrix exists, square, numeric, diagonal approx 1.0
nontrivial_difference_check: at least one off-diagonal difference is nontrivial
sensitivity_summary_check: sensitivity artifact exists with numeric bounded scores
m17_regression_check: strict M17 judge PASS verified
m14_m15_m16_regression_check: M14/M15/M16 judges PASS verified
bounded_artifact_size_check: JSON/JSONL artifacts remain bounded
machine_native_wording_check: no forbidden terms in artifacts
```

All required checks must be exactly PASS. No PARTIAL, SKIP, UNKNOWN, NOT_FOUND, or missing check may pass overall.

---

## Required artifacts

M18 output directory must contain:

```text
output/demo_m18/neural_variant_sweep_summary.json
output/demo_m18/neural_variant_similarity_matrix.json
output/demo_m18/neural_controller_sensitivity_summary.json
output/demo_m18/per_variant_runtime_summary.jsonl
output/demo_m18/per_variant_neural_summary.jsonl
output/demo_m18/milestone_18_judge_result.json
```

Each neural variant must have bounded trace artifacts. The scalar baseline must have a runtime summary.

---

## Test requirements

Add focused M18 tests. Short fixtures are acceptable.

Required tests:

1. Variant sweep config expands to at least 5 deterministic variants.
2. M17 baseline neural variant is present.
3. Hidden-size variant changes controller dimensions without breaking defaults.
4. Plasticity-rate variant changes configured rate.
5. Plasticity-disabled variant records zero or disabled plasticity behavior as expected.
6. Per-variant summary schema includes required fields.
7. Similarity matrix is square, numeric, and diagonal approx 1.0.
8. Nontrivial off-diagonal difference is detected for fixture variants.
9. Sensitivity scores are numeric and bounded.
10. M18 judge fails when variant count is too small.
11. M18 judge fails when required per-variant artifacts are missing.
12. M18 judge fails when M17 regression evidence is missing or non-PASS.
13. M18 judge fails on non-PASS/PARTIAL/SKIP/UNKNOWN check values.
14. M18 judge passes on a valid fixture artifact set.
15. Existing tests continue to pass.

---

## Documentation requirements

Add:

```text
docs/milestone_18_report.md
```

Update:

```text
docs/review_package.md
```

M18 report must include:

- design summary,
- relation to accepted M17 neural processing unit,
- variant definitions,
- controller parameters varied,
- per-variant runtime summary,
- per-variant neural summary,
- similarity matrix summary,
- controller sensitivity summary,
- M14/M15/M16/M17 regression judge results,
- M18 judge result with all checks exactly PASS and no SKIP/PARTIAL,
- artifact paths,
- current tests/coverage,
- full command list actually run,
- full M1-M18 regression summary,
- limitations that are not acceptance violations,
- next recommended milestone using machine-native wording only.

Review package must be current through M18 and include final test count, coverage, M14/M15/M16/M17/M18 judge results, artifact paths, report paths, and current-stage commit hashes.

---

## Verification commands

Run:

```bash
python -m pytest machine_sim/tests/ -v
python -m pytest machine_sim/tests/ --cov=machine_sim --cov-report=term-missing
python -m machine_sim.cli.main check
python -m machine_sim.cli.main run -c configs/milestone_18_neural_controller_variant_sensitivity.toml -t 20000 -s 42 -o output/demo_m18
python -m machine_sim.cli.main inspect output/demo_m18
python -m machine_sim.verification.milestone_18_judge output/demo_m18
```

Also verify accepted regression judges:

```bash
python -m machine_sim.verification.milestone_14_judge output/demo_m14
python -m machine_sim.verification.milestone_15_judge output/demo_m15
python -m machine_sim.verification.milestone_16_judge output/demo_m16
python -m machine_sim.verification.milestone_17_judge output/demo_m17
```

If fresh regenerated outputs are used, document the exact paths.

Run full M1-M18 regression commands for reporting and include the actual command list in the report.

---

## Stage-closing evidence required

Final handoff must include all standard stage-closing evidence plus:

```text
M18_GOAL_SPEC_SATISFIED: yes
M18_VARIANT_COUNT_GE_5: yes
M18_ACCEPTED_M17_VARIANT_PRESENT: yes
M18_HIDDEN_SIZE_VARIANT_PRESENT: yes
M18_PLASTICITY_RATE_VARIANT_PRESENT: yes
M18_PLASTICITY_DISABLED_VARIANT_PRESENT: yes
M18_SIMILARITY_MATRIX_VALID: yes
M18_CONTROLLER_SENSITIVITY_NONTRIVIAL: yes
M18_INDEPENDENT_JUDGE_STATUS: PASS
M18_NO_SKIPPED_OR_PARTIAL_REQUIRED_CHECKS: yes
M14_M15_M16_M17_REGRESSION_JUDGES_STILL_PASS: yes
```

Do not claim PASS or ACCEPTED unless all required checks are true.

---

## Final handoff format

```text
TASK_STATUS: PASS or PARTIAL_PASS
MILESTONE_18_STATUS: ACCEPTED or HOLD
READY_FOR_MILESTONE_19: YES or NO
Branch:
Starting commit hash:
Implementation commit hash:
Final remote commit hash:
Design summary:
Files changed:
Variant sweep summary:
Tests:
Coverage:
Guardrail result:
M14/M15/M16/M17 judge results:
M18 judge result:
Similarity matrix summary:
Controller sensitivity summary:
M18 demo output:
Artifact paths:
Full M1-M18 regression summary:
Stage closing chores result:
Known limitations:
Clean working tree:
```

---

## Acceptance criteria

```text
M18_CONFIGURABLE_NEURAL_CONTROLLER_PARAMETERS: PASS
M18_VARIANT_SWEEP_CONFIG: PASS
M18_PER_VARIANT_ARTIFACTS: PASS
M18_CROSS_VARIANT_SIMILARITY_MATRIX: PASS
M18_CONTROLLER_SENSITIVITY_SUMMARY: PASS
M18_RUN_FAMILY_SUMMARY: PASS
M18_INDEPENDENT_JUDGE_PASS_EXACT_ONLY: PASS
M18_REQUIRED_ARTIFACTS_WRITTEN: PASS
M18_TESTS_ASSERT_REAL_VARIANT_BEHAVIOR: PASS
M14_M15_M16_M17_REGRESSION_JUDGES_STILL_PASS: PASS
TESTS_AND_COVERAGE: PASS
GUARDRAILS: PASS
FULL_M1_M18_REGRESSION_REPORTED: PASS
MILESTONE_18_REPORT_CURRENT: PASS
REVIEW_PACKAGE_CURRENT: PASS
STAGE_CLOSING_CHORES_SATISFIED: PASS
CLEAN_WORKTREE_AND_PUSHED_REMOTE: PASS
```
