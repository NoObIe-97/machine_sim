# After Silicon — MiMo Milestone 16 Goal Spec: Adaptive Trajectory Compression and Offline Analysis

## Repository and branch

Repository: `https://github.com/NoObIe-97/machine_sim.git`

Branch: `feature/milestone-1`

Start from the accepted Milestone 15A remote head:

```text
c1664ee
```

Milestone 15 is accepted. Milestone 16 must build on the M14/M15 long-run adaptive-control and multi-generation adaptive-state trajectory substrate. Do not regress the accepted M14 and M15 judges.

Before final handoff, invoke and satisfy:

```text
prompts/skills/stage_closing_chores.md
```

---

## Strategic direction

Milestone 15 generated generation-indexed adaptive-state transfer traces across multiple successor steps. Milestone 16 should convert those long-run traces into compact, bounded offline-analysis artifacts.

The goal is to make long-run adaptive trajectories easier to compare across runs/configurations without letting the analysis layer influence unit actions.

Milestone 16 should remain a read-only offline-analysis/compression milestone:

```text
long-run adaptive trace artifacts
→ bounded trajectory compression
→ offline trajectory replay metrics
→ cross-trajectory similarity comparison
→ compact run-level diagnostic outputs
```

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
adaptive trajectory compression
bounded trajectory summary
offline trajectory replay
trajectory reconstruction error
cross-trajectory similarity
run-configuration comparison
adaptive-state segment
generation-indexed segment
transfer-delta segment
trajectory envelope
compressed trajectory capsule
trajectory compression ratio
trajectory replay error
trajectory signature
```

Existing accepted legacy fields should not be renamed unless safe. All new M16 fields, config keys, reports, and artifact schemas must follow machine-native wording.

---

## Milestone 16 goal statement

Implement bounded compression and offline analysis for multi-generation adaptive trajectories.

The M16 system must read trajectory data produced by a long M15-style run and generate compact summaries that preserve enough information to compare adaptive-state trajectory structure across configurations.

M16 must not alter unit action selection, adaptive update rules, fabrication behavior, signal behavior, or descendant adaptive-state transfer behavior unless a minimal read-only export adapter is required.

---

## Core implementation requirements

### 1. Trajectory compression analyzer

Add a read-only analyzer such as:

```text
machine_sim/analysis/adaptive_trajectory_compression.py
```

Suggested class:

```text
AdaptiveTrajectoryCompressor
```

It should consume transfer records, adaptive-state traces, action-distribution traces, and local-feedback traces, then produce bounded compressed segments.

Suggested compressed segment fields:

```text
segment_index
start_tick
end_tick
generation_index_min
generation_index_max
transfer_count
avg_adaptive_state
adaptive_state_range
avg_transfer_delta
max_transfer_delta
action_distribution_summary
signal_parameter_summary
resource_response_summary
hazard_response_summary
feedback_event_summary
segment_signature
```

Requirements:

- Output segment count must be bounded by config.
- Compression must be deterministic for the same input artifacts/seed.
- Compression must use actual trace values, not placeholder constants.
- Compression must include generation-indexed and transfer-delta information.

### 2. Offline trajectory replay metrics

Add read-only replay metrics that estimate how well compressed segments reconstruct or approximate the source trajectory statistics.

Suggested fields:

```text
replay_window_count
avg_trajectory_replay_error
max_trajectory_replay_error
adaptive_state_replay_error
action_distribution_replay_error
transfer_delta_replay_error
replay_stability_score
```

Requirements:

- Replay here means diagnostic approximation from compressed summaries, not unit action replay.
- Metrics must be numeric and bounded.
- Judge must fail if replay metrics are missing or nonnumeric.

### 3. Cross-trajectory similarity comparison

Generate at least two run/configuration trajectory summaries and compare them.

Suggested approach:

- main M16 adaptive-transfer run using M15-style config,
- alternate run with changed adaptive/fabrication/field parameter, or transfer reference run,
- compare compressed trajectory signatures.

Required artifact:

```text
output/demo_m16/cross_trajectory_compare.json
```

Required fields:

```text
primary_segment_count
comparison_segment_count
trajectory_signature_delta
adaptive_state_similarity
transfer_delta_similarity
action_distribution_similarity
signal_response_similarity
overall_trajectory_similarity
nontrivial_difference_detected
```

The comparison must show a nontrivial difference between the selected configurations.

### 4. Compact trajectory capsule artifact

Write a compact artifact:

```text
output/demo_m16/compressed_trajectory_capsule.json
```

Required sections:

```text
run_parameters
compression_parameters
segment_summaries
trajectory_signature
replay_metrics
cross_trajectory_similarity
artifact_size_summary
source_artifact_references
judge_status
```

### 5. Bounded artifact and size reporting

M16 must report source-vs-compressed sizes and compression ratios.

Required fields:

```text
source_trace_record_count
compressed_segment_count
source_artifact_size_bytes
compressed_artifact_size_bytes
trajectory_compression_ratio
bounded_segment_limit
```

The compressed artifact should be meaningfully smaller than the source traces it summarizes.

---

## Demo configuration

Add:

```text
configs/milestone_16_adaptive_trajectory_compression.toml
```

Recommended minimums:

```text
grid_width >= 120
grid_height >= 120
initial unit_count between 4 and 12
max_ticks >= 30000
seed = 42
adaptive_enabled = true
signal_enabled = true
fabrication_enabled = true
capsule_enabled = true
long_run_adaptation_enabled = true
multi_generation_trace_enabled = true
trajectory_compression_enabled = true
trajectory_compression_max_segments <= 64
```

The main M16 run should produce enough source trace content to make compression meaningful:

```text
transfer_count >= 5
generation_index_span >= 3
adaptive_state_trace_count > compressed_segment_count
signal observations > 0
```

---

## Independent M16 judge

Add:

```text
machine_sim/verification/milestone_16_judge.py
```

Input:

```text
output/demo_m16/
```

Output:

```text
output/demo_m16/milestone_16_judge_result.json
```

Required judge checks:

```text
long_run_ticks_check: run_ticks >= 30000
source_trace_available_check: source trace/artifact references exist and record counts are nonzero
compression_segment_check: compressed_segment_count > 0 and <= configured bound
compression_ratio_check: compressed artifact is smaller than source traces or reported ratio is < 1.0
replay_metrics_check: replay metrics exist, numeric, and bounded
cross_trajectory_similarity_check: comparison exists and overall similarity is numeric/bounded
nontrivial_difference_check: nontrivial difference detected between compared trajectories
transfer_generation_check: transfer_count >= 5 and generation_index_span >= 3
signal_observation_check: signal observations > 0
artifact_schema_check: all required M16 artifacts present
bounded_artifact_size_check: JSON/JSONL artifacts remain bounded
machine_native_wording_check: no forbidden terms in artifacts
```

All checks must PASS. No SKIP is allowed.

---

## Required artifacts

Main M16 run must write:

```text
output/demo_m16/compressed_trajectory_capsule.json
output/demo_m16/trajectory_compression_summary.json
output/demo_m16/compressed_trajectory_segments.jsonl
output/demo_m16/trajectory_replay_metrics.json
output/demo_m16/cross_trajectory_compare.json
output/demo_m16/adaptive_trajectory_summary.json
output/demo_m16/generation_adaptive_state_trace.jsonl
output/demo_m16/milestone_16_judge_result.json
```

Reusing M15 artifacts is acceptable if they are copied or generated into `output/demo_m16/` and documented as M16 source artifacts.

---

## Test requirements

Add focused tests for M16. Tests may use small synthetic traces or shorter runs.

Required tests:

1. Trajectory compressor creates bounded segments from synthetic transfer/adaptive traces.
2. Segment summaries include generation range, transfer count, adaptive-state summary, action summary, and signature.
3. Compression ratio calculation is numeric and bounded.
4. Replay metrics are numeric and bounded.
5. Cross-trajectory comparison detects difference between two synthetic trajectory signatures.
6. Compressor output is deterministic for identical inputs.
7. M16 judge fails when compressed segments are missing.
8. M16 judge fails when replay metrics are missing or nonnumeric.
9. M16 judge fails when cross-trajectory comparison is missing or trivial.
10. M16 judge passes on a valid fixture artifact set.
11. M15 judge still passes on accepted M15 artifacts or regenerated M15 run.
12. Existing tests continue to pass.

---

## Documentation requirements

Add:

```text
docs/milestone_16_report.md
```

Update:

```text
docs/review_package.md
```

M16 report must include:

- design summary,
- relation to M14/M15 adaptive-control and multi-generation trace substrate,
- compression method,
- replay metric definitions,
- cross-trajectory comparison setup,
- long-run parameters,
- source trace count and compressed segment count,
- compression ratio,
- replay error metrics,
- cross-trajectory similarity metrics,
- M15 regression judge result,
- M16 judge result with all checks PASS and no SKIP,
- artifact paths,
- current tests/coverage,
- full command list actually run,
- full M1-M16 regression summary,
- limitations that are not acceptance violations,
- next recommended milestone using machine-native wording only.

Review package must be current through M16 and include final test count, coverage, M15/M16 judge results, artifact paths, report paths, and current-stage commit hashes.

---

## Verification commands

Run:

```bash
python -m pytest machine_sim/tests/ -v
python -m pytest machine_sim/tests/ --cov=machine_sim --cov-report=term-missing
python -m machine_sim.cli.main check
python -m machine_sim.cli.main run -c configs/milestone_16_adaptive_trajectory_compression.toml -t 30000 -s 42 -o output/demo_m16
python -m machine_sim.cli.main inspect output/demo_m16
python -m machine_sim.verification.milestone_16_judge output/demo_m16
```

Also run M15 judge to ensure no regression:

```bash
python -m machine_sim.cli.main run -c configs/milestone_15_multi_generation_adaptive_trace.toml -t 30000 -s 42 -o output/demo_m15
python -m machine_sim.verification.milestone_15_judge output/demo_m15
```

Run full M1-M16 regression commands for reporting and include the actual command list in the report.

---

## Stage-closing evidence required

Final handoff must include all standard stage-closing evidence plus:

```text
M16_GOAL_SPEC_SATISFIED: yes
M16_INDEPENDENT_JUDGE_STATUS: PASS
M16_NO_SKIPPED_REQUIRED_JUDGE_CHECKS: yes
M16_LONG_RUN_TICKS_GE_30000: yes
M16_COMPRESSION_SEGMENTS_BOUNDED: yes
M16_REPLAY_METRICS_PRESENT: yes
M16_CROSS_TRAJECTORY_COMPARISON_NONTRIVIAL: yes
M15_REGRESSION_JUDGE_STILL_PASS: yes
```

Do not claim PASS or ACCEPTED unless all are true.

---

## Final handoff format

```text
TASK_STATUS: PASS or PARTIAL_PASS
MILESTONE_16_STATUS: ACCEPTED or HOLD
READY_FOR_MILESTONE_17: YES or NO
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
M16 judge result:
Compression summary:
Replay metric summary:
Cross-trajectory comparison summary:
M16 demo output:
Artifact paths:
Full M1-M16 regression summary:
Stage closing chores result:
Known limitations:
Clean working tree:
```

---

## Acceptance criteria

```text
M16_TRAJECTORY_COMPRESSION_ANALYZER: PASS
M16_BOUNDED_COMPRESSED_SEGMENTS: PASS
M16_REPLAY_METRICS: PASS
M16_CROSS_TRAJECTORY_SIMILARITY: PASS
M16_COMPACT_TRAJECTORY_CAPSULE: PASS
M16_COMPRESSION_RATIO_REPORTED: PASS
M16_INDEPENDENT_JUDGE_PASS_NO_SKIP: PASS
M16_REQUIRED_ARTIFACTS_WRITTEN: PASS
M16_TESTS_ASSERT_REAL_ANALYSIS_BEHAVIOR: PASS
M15_REGRESSION_JUDGE_STILL_PASS: PASS
TESTS_AND_COVERAGE: PASS
GUARDRAILS: PASS
FULL_M1_M16_REGRESSION_REPORTED: PASS
MILESTONE_16_REPORT_CURRENT: PASS
REVIEW_PACKAGE_CURRENT: PASS
STAGE_CLOSING_CHORES_SATISFIED: PASS
CLEAN_WORKTREE_AND_PUSHED_REMOTE: PASS
```
