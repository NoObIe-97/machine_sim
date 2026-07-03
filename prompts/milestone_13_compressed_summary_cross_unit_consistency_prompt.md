# After Silicon — MiMo Milestone 13 Compressed Summary Cross-Unit Consistency Prompt

## Repository and branch

Repository: `https://github.com/NoObIe-97/machine_sim.git`

Branch: `feature/milestone-1`

Start from the accepted Milestone 12A remote head:

```text
0c50e70
```

Milestone 12 is accepted. Milestone 13 should build on it without reworking accepted runtime behavior unless a minimal compatibility fix is required.

Before final handoff, invoke and satisfy the shared stage-closing skill:

```text
prompts/skills/stage_closing_chores.md
```

Do not skip the stage-closing skill.

---

## Current accepted state

The simulator currently supports:

- M1 survival substrate
- M2 physical interaction and movement blocking
- M3 non-semantic signal emission and observation
- M4 signal correlation metrics
- M5 adaptive signal/sensing control
- M6 fabricated descent and lineage records
- M7 calibration capsules and measurable warm-start impact
- M8 operational telemetry, reconciliation, and lineage calibration drift
- M9 resource pressure, extraction load, proximity pressure, and signal-field perturbation
- M10 signal pattern field dynamics
- M11 bounded operational trace compression with signal, telemetry, capsule, lineage, and replay summaries
- M12 generation-indexed trace drift, drift envelopes, replay-error stability, capsule-trace compatibility checks, and bounded long-run diagnostic retention

The accepted M12 next direction is:

```text
Milestone 13: Compressed Summary Cross-Unit Consistency and Windowed Retention Stability — cross-unit diagnostic summary comparison, windowed retention stability, long-run compression ratio convergence, and bounded cross-generation diagnostic envelope.
```

---

## Conceptual boundary

Milestone 13 is about numeric consistency among compressed diagnostic summaries. It is not social alignment, consensus, collaboration, communication, or semantic agreement.

Do not introduce human/social/biological/political/economic/strategic/emotional wording or concepts in runtime code, config keys, event labels, artifact schemas, or committed reports.

Avoid terms such as:

```text
consensus
agreement
disagreement
cooperation
competition
conflict
strategy
trust
alliance
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
population
replication
mutation
inheritance
offspring
parent
child
species
fitness
evolution
```

Use machine-native alternatives:

```text
cross-unit summary consistency
consistency delta
summary comparison
windowed retention stability
compression ratio convergence
bounded diagnostic envelope
cross-generation envelope
unit-pair diagnostic delta
retention-window variance
compressed-summary alignment metric
numeric stability score
```

If wording is ambiguous, choose physical/numeric terminology.

---

## Milestone 13 goal

Add a deterministic analysis layer that compares compressed diagnostic summaries across active units, retention windows, and generation-indexed diagnostic envelopes.

The layer should remain observational and numeric. It must not alter unit decision logic, capsule behavior, fabrication behavior, trace compression, or trace drift analysis unless a minimal read-only adapter is needed.

---

## Desired implementation areas

### 1. Cross-unit diagnostic summary comparison

Add a module such as:

```text
machine_sim/analysis/summary_consistency.py
```

Suggested class name:

```text
SummaryConsistencyAnalyzer
```

Suggested fields:

```text
unit_summary_count
unit_pair_count
avg_unit_summary_delta
max_unit_summary_delta
avg_power_ratio_delta
avg_sensor_health_delta
avg_signal_trace_delta
avg_replay_error_delta
summary_consistency_score
```

Minimum expectations:

- Use real compressed summaries, trace-compression segments, telemetry windows, or per-unit diagnostic trace points.
- Safe zero summary when fewer than two unit summaries exist.
- Deterministic under the same seed.
- Storage bounded by a configured maximum.

### 2. Windowed retention stability

Analyze stability across bounded retention windows from M12 retention data.

Suggested fields:

```text
retention_window_count
retention_window_span
avg_retention_variance
max_retention_variance
retention_stability_score
retention_drop_rate
```

Minimum expectations:

- Use real retention records or M12 retention summaries.
- Safe zero summary when retention data is absent.
- Nonzero in the M13 deterministic demo if trace drift and retention are enabled.

### 3. Long-run compression ratio convergence

Measure whether compressed-summary ratios stabilize across long-run windows.

Suggested fields:

```text
compression_window_count
avg_compression_ratio
compression_ratio_delta
compression_ratio_variance
compression_convergence_score
compression_convergence_window_span
```

Minimum expectations:

- Use M11 compression ratio and/or segment counts over time.
- Numeric and deterministic.
- Safe zero summary when compression summaries are absent.

### 4. Bounded cross-generation diagnostic envelope

Build a compact envelope over generation-indexed diagnostic metrics.

Suggested fields:

```text
cross_generation_envelope_count
generation_index_span
generation_envelope_width
generation_delta_floor
generation_delta_ceiling
generation_envelope_stability
```

Minimum expectations:

- Use real generation-indexed M12 trace-drift records or lineage records.
- Safe zero summary when generation-indexed records are absent.
- Bounded by `max_records` or equivalent.

### 5. Combined stability summary

Produce one compact top-level combined summary for CLI/report use.

Suggested fields:

```text
combined_window_count
combined_consistency_score
combined_stability_score
combined_delta_score
combined_record_count
```

Minimum expectations:

- Deterministic.
- Uses actual section summaries, not placeholder constants.
- Visible in CLI output and artifact.

---

## Config expectations

Add minimal config keys only. Keep names machine-native.

Possible keys:

```text
summary_consistency_enabled
summary_consistency_window
summary_consistency_sample_interval
summary_consistency_max_records
summary_consistency_retention_window
cross_generation_envelope_enabled
```

If config keys are added, update guardrail config allowlists accordingly.

Avoid semantic names such as consensus, agreement, communication, knowledge, learning, memory, population, inheritance, mutation, or evolution.

---

## CLI expectations

The existing `run` command should print Milestone 13 summaries when summary consistency analysis is enabled.

Expected output shape:

```text
Summary consistency: units=..., pairs=..., avg_delta=..., score=...
Retention stability: windows=..., variance=..., stability=..., drop_rate=...
Compression convergence: windows=..., ratio=..., delta=..., score=...
Generation envelope: records=..., span=..., width=..., stability=...
Combined stability: windows=..., consistency=..., stability=..., delta=...
```

Exact labels can differ, but they must be machine-native and numeric.

When `-o` is provided, write an artifact such as:

```text
summary_consistency.json
```

Artifact contents should be compact and bounded.

---

## Demo config

Add:

```text
configs/milestone_13_summary_consistency.toml
```

Recommended characteristics:

- trace compression enabled,
- trace drift enabled,
- telemetry enabled,
- reconciliation enabled,
- fabrication enabled,
- capsule enabled,
- signal dynamics enabled,
- enough ticks for multiple units, multiple compressed windows, and generation-indexed records,
- deterministic seed 42.

Runtime should remain small enough for full regression.

---

## Testing requirements

Add focused tests for M13. Tests must assert real numeric behavior.

Required tests:

1. **Cross-unit diagnostic summary comparison**
   - Two or more unit summaries produce nonzero pair count and numeric deltas.
   - Fewer than two summaries returns clean zero pair metrics.

2. **Windowed retention stability**
   - Retention records produce numeric variance and stability fields.
   - No retention records returns clean zero summary.

3. **Compression ratio convergence**
   - Multiple compression-ratio windows produce numeric convergence fields.
   - Same seed produces identical convergence summary.

4. **Cross-generation diagnostic envelope**
   - Generation-indexed records produce envelope count/span/width fields.
   - No generation-indexed records returns clean zero summary.

5. **Combined stability summary**
   - Combined summary uses section summaries and reports bounded numeric scores.
   - Scores remain within documented ranges.

6. **Bounded storage**
   - `max_records=N`; record more than `N`; assert internal stores stay within `N`.

7. **Deterministic demo**
   - Same seed produces identical M13 summary.

8. **Artifact schema test**
   - `summary_consistency.json` contains cross-unit, retention, compression, generation-envelope, and combined sections.

Existing tests must keep passing.

---

## Documentation requirements

Add:

```text
docs/milestone_13_report.md
```

The report must include:

- M13 design summary,
- what was implemented,
- scope boundary in machine-native wording,
- config keys,
- artifact path and high-level schema,
- full command list actually run,
- current test/coverage results,
- guardrail result,
- full M1–M13 regression summary with numeric results,
- M5 comparison summary,
- M7 capsule comparison summary,
- M8 telemetry/reconciliation summary,
- M9 pressure summary,
- M10 signal-dynamics summary,
- M11 trace-compression summary,
- M12 trace-drift summary,
- M13 summary-consistency summary,
- known limitations,
- next recommended milestone using machine-native wording only.

Update:

```text
docs/review_package.md
```

The review package must be current through M13 and must not retain stale milestone titles, stale test counts, stale coverage values, stale report paths, or missing current-stage commit hashes.

---

## Required verification commands

Run the full verification set before final handoff:

```bash
python -m pytest machine_sim/tests/ -v
python -m pytest machine_sim/tests/ --cov=machine_sim --cov-report=term-missing
python -m machine_sim.cli.main check

python -m machine_sim.cli.main run -c configs/milestone_1.toml -t 500 -s 42 -o output/demo_m1
python -m machine_sim.cli.main inspect output/demo_m1

python -m machine_sim.cli.main run -c configs/milestone_2_crowded.toml -t 100 -s 42 -o output/demo_m2
python -m machine_sim.cli.main inspect output/demo_m2

python -m machine_sim.cli.main run -c configs/milestone_3_signals.toml -t 100 -s 42 -o output/demo_m3
python -m machine_sim.cli.main inspect output/demo_m3

python -m machine_sim.cli.main run -c configs/milestone_4_correlation.toml -t 100 -s 42 -o output/demo_m4
python -m machine_sim.cli.main inspect output/demo_m4

python -m machine_sim.cli.main run -c configs/milestone_5_adaptive.toml -t 150 -s 42 -o output/demo_m5
python -m machine_sim.cli.main inspect output/demo_m5
python -m machine_sim.cli.main compare -c configs/milestone_5_adaptive.toml -t 150 -s 42

python -m machine_sim.cli.main run -c configs/milestone_6_fabrication.toml -t 200 -s 42 -o output/demo_m6
python -m machine_sim.cli.main inspect output/demo_m6

python -m machine_sim.cli.main run -c configs/milestone_7_calibration_capsules.toml -t 200 -s 42 -o output/demo_m7
python -m machine_sim.cli.main inspect output/demo_m7
python -m machine_sim.cli.main capsule-compare -c configs/milestone_7_calibration_capsules.toml -t 200 -s 42

python -m machine_sim.cli.main run -c configs/milestone_8_telemetry_reconciliation.toml -t 200 -s 42 -o output/demo_m8
python -m machine_sim.cli.main inspect output/demo_m8

python -m machine_sim.cli.main run -c configs/milestone_9_resource_pressure.toml -t 200 -s 42 -o output/demo_m9
python -m machine_sim.cli.main inspect output/demo_m9

python -m machine_sim.cli.main run -c configs/milestone_10_signal_field_dynamics.toml -t 200 -s 42 -o output/demo_m10
python -m machine_sim.cli.main inspect output/demo_m10

python -m machine_sim.cli.main run -c configs/milestone_11_trace_compression.toml -t 200 -s 42 -o output/demo_m11
python -m machine_sim.cli.main inspect output/demo_m11

python -m machine_sim.cli.main run -c configs/milestone_12_trace_drift.toml -t 220 -s 42 -o output/demo_m12
python -m machine_sim.cli.main inspect output/demo_m12

python -m machine_sim.cli.main run -c configs/milestone_13_summary_consistency.toml -t 240 -s 42 -o output/demo_m13
python -m machine_sim.cli.main inspect output/demo_m13
```

Run wording/freshness checks from:

```text
prompts/skills/stage_closing_chores.md
```

---

## Stage closing chores

Before final handoff, invoke and satisfy:

```text
prompts/skills/stage_closing_chores.md
```

Your final handoff must include this block with all values set to `yes`:

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

Do not claim `PASS`, `ACCEPTED`, or `READY_FOR_MILESTONE_14` unless every line is `yes`.

---

## Commit and handoff requirements

Commit all changes and push to `feature/milestone-1`.

Final response must include:

```text
TASK_STATUS: PASS or PARTIAL_PASS
MILESTONE_13_STATUS: ACCEPTED or HOLD
READY_FOR_MILESTONE_14: YES or NO
Branch:
Starting commit hash:
Implementation commit hash:
Final remote commit hash:
Design summary:
Files changed:
Tests:
Coverage:
Guardrail result:
Full M1-M13 regression summary:
M13 demo output:
Artifact paths:
Stage closing chores result:
Known limitations:
Clean working tree:
```

---

## Acceptance criteria

Do not mark PASS unless all are true:

```text
M13_CROSS_UNIT_SUMMARY_CONSISTENCY: PASS
M13_WINDOWED_RETENTION_STABILITY: PASS
M13_COMPRESSION_RATIO_CONVERGENCE: PASS
M13_CROSS_GENERATION_DIAGNOSTIC_ENVELOPE: PASS
M13_COMBINED_STABILITY_SUMMARY: PASS
M13_DETERMINISTIC_DEMO: PASS
M13_ARTIFACTS_WRITTEN: PASS
M13_TESTS_ASSERT_REAL_NUMERIC_BEHAVIOR: PASS
TESTS_AND_COVERAGE: PASS
GUARDRAILS: PASS
FULL_M1_M13_REGRESSION_REPORTED: PASS
MILESTONE_13_REPORT_CURRENT: PASS
REVIEW_PACKAGE_CURRENT: PASS
STAGE_CLOSING_CHORES_SATISFIED: PASS
CLEAN_WORKTREE_AND_PUSHED_REMOTE: PASS
```

If any item fails, return `PARTIAL_PASS` with exact blockers and do not claim Milestone 13 is accepted.
