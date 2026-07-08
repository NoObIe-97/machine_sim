# After Silicon — MiMo Milestone 17 Goal Spec: Cross-Configuration Adaptive Comparison

## Repository and branch

Repository: `https://github.com/NoObIe-97/machine_sim.git`

Branch: `feature/milestone-1`

Start from the accepted Milestone 16A remote head:

```text
9ad2112
```

Milestone 16 is accepted. Milestone 17 must build on the M14/M15/M16 long-run adaptive-control, multi-generation trace, and trajectory-compression substrate. Do not regress the accepted M14, M15, or M16 judges.

Before final handoff, invoke and satisfy:

```text
prompts/skills/stage_closing_chores.md
```

---

## Strategic direction

Milestone 16 produced compact compressed trajectory capsules and cross-trajectory similarity metrics. Milestone 17 should now compare multiple parameter configurations systematically.

The goal is to run a bounded configuration sweep, compress each resulting adaptive trajectory, compare the resulting trajectory capsules, and produce a machine-native configuration sensitivity report.

This remains read-only at the analysis layer:

```text
configuration set
→ long-run adaptive simulations
→ trajectory compression per configuration
→ cross-configuration trajectory comparison
→ parameter sensitivity summary
→ ranked configuration report for offline inspection
```

No analysis module may directly control unit action selection during a simulation run.

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
cross-configuration adaptive comparison
configuration sweep
parameter sensitivity
trajectory capsule
trajectory signature
trajectory similarity matrix
configuration response vector
trajectory outcome vector
configuration ranking
parameter perturbation set
adaptive trajectory variance
trajectory cluster
configuration envelope
run family
```

Existing accepted legacy fields should not be renamed unless safe. All new M17 fields, config keys, reports, and artifact schemas must follow the preferred wording.

---

## Milestone 17 goal statement

Implement systematic cross-configuration adaptive trajectory comparison.

The M17 system must run or post-process multiple configuration variants, compress each adaptive trajectory using the M16 compressor, compare the resulting trajectory capsules, and produce a bounded sensitivity/ranking artifact that helps identify which configuration changes materially alter adaptive trajectory structure.

---

## Core implementation requirements

### 1. Configuration sweep definition

Add a M17 configuration file such as:

```text
configs/milestone_17_cross_configuration_adaptive_comparison.toml
```

It should define a small bounded sweep over at least 4 configurations, including a baseline and 3 perturbation variants.

Suggested varied parameters:

```text
power_drain_rate
resource_density
hazard_density
fabrication_power_cost
fabrication_interval
component_degradation_scale
signal_energy_cost
signal_default_radius
```

Requirements:

- Sweep must be deterministic for a fixed seed.
- At least 4 configuration variants must run or be generated.
- Each variant must run long enough to produce nontrivial adaptive traces. Recommended target: >= 10000 ticks per variant.
- At least one primary variant must preserve M15-style long-run depth: >= 30000 ticks, transfer count >= 5, generation span >= 3.
- Shorter variants are acceptable for sweep breadth if documented and judge-visible.

### 2. Per-configuration trajectory capsule generation

For each configuration variant, M17 must generate or load:

```text
compressed trajectory capsule
trajectory compression summary
trajectory signature
run outcome vector
```

Suggested per-variant output path:

```text
output/demo_m17/config_<id>/compressed_trajectory_capsule.json
```

Each variant summary should include:

```text
configuration_id
configuration_parameters
run_ticks
initial_unit_count
final_active_count
transfer_count
generation_index_span
signal_observation_count
compressed_segment_count
trajectory_compression_ratio
trajectory_signature
replay_stability_score
```

### 3. Cross-configuration similarity matrix

Compute pairwise trajectory similarity across all variants.

Required artifact:

```text
output/demo_m17/cross_configuration_similarity_matrix.json
```

Required fields:

```text
configuration_ids
similarity_matrix
trajectory_signature_delta_matrix
adaptive_state_similarity_matrix
transfer_delta_similarity_matrix
action_distribution_similarity_matrix
signal_response_similarity_matrix
```

Requirements:

- Matrix must be square and deterministic.
- Diagonal similarity values must be exactly or approximately 1.0.
- At least one off-diagonal pair must show nontrivial difference.

### 4. Parameter sensitivity summary

Compute a bounded sensitivity summary that relates parameter changes to trajectory differences.

Required artifact:

```text
output/demo_m17/parameter_sensitivity_summary.json
```

Suggested fields:

```text
parameter_names
variant_count
per_parameter_delta_summary
trajectory_response_delta_summary
most_sensitive_parameters
least_sensitive_parameters
sensitivity_score_by_parameter
nontrivial_parameter_effect_detected
```

Requirements:

- Sensitivity scores must be numeric and bounded.
- At least one parameter must show nonzero sensitivity.
- Do not claim causal certainty. Use comparison/sensitivity wording only.

### 5. Configuration ranking report

Generate a machine-native ranking artifact based on explicitly defined metrics.

Required artifact:

```text
output/demo_m17/configuration_ranking.json
```

Ranking metrics may include:

```text
late_active_count
transfer_count
generation_index_span
trajectory_compression_ratio
replay_stability_score
signal_observation_count
adaptive_state_delta_rms
bounded_artifact_score
```

Required fields:

```text
ranking_metric_weights
ranked_configurations
per_configuration_scores
score_components
ranking_limitations
```

This ranking is for offline inspection only. It must not feed back into unit runtime decisions.

### 6. Run-family summary capsule

Write a compact run-family artifact:

```text
output/demo_m17/cross_configuration_summary.json
```

Required sections:

```text
run_family_parameters
configuration_variant_summary
similarity_matrix_summary
parameter_sensitivity_summary
configuration_ranking_summary
artifact_size_summary
judge_status
source_artifact_references
```

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
variant_count_check: at least 4 configuration variants
primary_long_run_check: at least one variant has run_ticks >= 30000, transfer_count >= 5, generation span >= 3
per_variant_capsule_check: each variant has compressed trajectory capsule and summary fields
similarity_matrix_check: matrix is square, deterministic, diagonal approx 1.0
nontrivial_off_diagonal_check: at least one off-diagonal pair shows nontrivial difference
parameter_sensitivity_check: sensitivity artifact exists, numeric scores, at least one nonzero score
configuration_ranking_check: ranking artifact exists with all variants and numeric bounded scores
m16_compression_reuse_check: each variant uses M16 compressor outputs or equivalent schema
m15_m16_regression_check: M15 and M16 judges still pass or are explicitly verified on regenerated/current artifacts
artifact_schema_check: all required M17 artifacts present
bounded_artifact_size_check: artifacts remain bounded
machine_native_wording_check: no forbidden terms in artifacts
```

All checks must PASS. No SKIP is allowed.

---

## Required artifacts

Main M17 output directory must contain:

```text
output/demo_m17/cross_configuration_summary.json
output/demo_m17/cross_configuration_similarity_matrix.json
output/demo_m17/parameter_sensitivity_summary.json
output/demo_m17/configuration_ranking.json
output/demo_m17/milestone_17_judge_result.json
```

Each variant subdirectory must contain at least:

```text
compressed_trajectory_capsule.json
trajectory_compression_summary.json
compressed_trajectory_segments.jsonl
trajectory_replay_metrics.json
adaptive_trajectory_summary.json
generation_adaptive_state_trace.jsonl
```

If the implementation uses shared artifacts instead of per-variant subdirectories, the schema must still clearly preserve per-variant records and source references.

---

## Test requirements

Add focused tests for M17. Tests may use small fixtures or synthetic compressed capsules.

Required tests:

1. Configuration sweep parser creates at least 4 deterministic variants.
2. Per-configuration summary schema includes required fields.
3. Similarity matrix is square and diagonal values are approximately 1.0.
4. Nontrivial off-diagonal difference is detected for intentionally different fixtures.
5. Parameter sensitivity scores are numeric and bounded.
6. Sensitivity summary identifies nonzero parameter effect for synthetic differing variants.
7. Configuration ranking includes all variants and bounded numeric scores.
8. M17 judge fails when fewer than 4 variants exist.
9. M17 judge fails when similarity matrix is missing or malformed.
10. M17 judge fails when ranking artifact is missing.
11. M17 judge passes on a valid fixture artifact set.
12. M16 judge still passes on accepted or regenerated M16 artifacts.
13. Existing tests continue to pass.

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
- relation to M14/M15/M16 substrate,
- configuration sweep definition,
- per-variant run parameters,
- per-variant trajectory capsule summary,
- similarity matrix summary,
- parameter sensitivity summary,
- configuration ranking summary,
- M15/M16 regression judge results,
- M17 judge result with all checks PASS and no SKIP,
- artifact paths,
- current tests/coverage,
- full command list actually run,
- full M1-M17 regression summary,
- limitations that are not acceptance violations,
- next recommended milestone using machine-native wording only.

Review package must be current through M17 and include final test count, coverage, M15/M16/M17 judge results, artifact paths, report paths, and current-stage commit hashes.

---

## Verification commands

Run:

```bash
python -m pytest machine_sim/tests/ -v
python -m pytest machine_sim/tests/ --cov=machine_sim --cov-report=term-missing
python -m machine_sim.cli.main check
python -m machine_sim.cli.main run -c configs/milestone_17_cross_configuration_adaptive_comparison.toml -t 30000 -s 42 -o output/demo_m17
python -m machine_sim.cli.main inspect output/demo_m17
python -m machine_sim.verification.milestone_17_judge output/demo_m17
```

Also run M15/M16 judges to ensure no regression:

```bash
python -m machine_sim.verification.milestone_15_judge output/demo_m15
python -m machine_sim.verification.milestone_16_judge output/demo_m16
```

If M17 generates fresh M15/M16-compatible artifacts, document the exact paths used for regression judge verification.

Run full M1-M17 regression commands for reporting and include the actual command list in the report.

---

## Stage-closing evidence required

Final handoff must include all standard stage-closing evidence plus:

```text
M17_GOAL_SPEC_SATISFIED: yes
M17_INDEPENDENT_JUDGE_STATUS: PASS
M17_NO_SKIPPED_REQUIRED_JUDGE_CHECKS: yes
M17_VARIANT_COUNT_GE_4: yes
M17_PRIMARY_LONG_RUN_VALID: yes
M17_SIMILARITY_MATRIX_VALID: yes
M17_PARAMETER_SENSITIVITY_NONZERO: yes
M17_CONFIGURATION_RANKING_PRESENT: yes
M15_M16_REGRESSION_JUDGES_STILL_PASS: yes
```

Do not claim PASS or ACCEPTED unless all are true.

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
Configuration sweep summary:
Tests:
Coverage:
Guardrail result:
M15 judge result:
M16 judge result:
M17 judge result:
Similarity matrix summary:
Parameter sensitivity summary:
Configuration ranking summary:
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
M17_CONFIGURATION_SWEEP: PASS
M17_PER_CONFIGURATION_TRAJECTORY_CAPSULES: PASS
M17_CROSS_CONFIGURATION_SIMILARITY_MATRIX: PASS
M17_PARAMETER_SENSITIVITY_SUMMARY: PASS
M17_CONFIGURATION_RANKING: PASS
M17_RUN_FAMILY_SUMMARY: PASS
M17_INDEPENDENT_JUDGE_PASS_NO_SKIP: PASS
M17_REQUIRED_ARTIFACTS_WRITTEN: PASS
M17_TESTS_ASSERT_REAL_COMPARISON_BEHAVIOR: PASS
M15_M16_REGRESSION_JUDGES_STILL_PASS: PASS
TESTS_AND_COVERAGE: PASS
GUARDRAILS: PASS
FULL_M1_M17_REGRESSION_REPORTED: PASS
MILESTONE_17_REPORT_CURRENT: PASS
REVIEW_PACKAGE_CURRENT: PASS
STAGE_CLOSING_CHORES_SATISFIED: PASS
CLEAN_WORKTREE_AND_PUSHED_REMOTE: PASS
```
