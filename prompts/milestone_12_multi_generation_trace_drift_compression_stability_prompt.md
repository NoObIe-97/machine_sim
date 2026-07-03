# After Silicon — MiMo Milestone 12 Multi-Generation Trace Drift and Compression Stability Prompt

## Repository and branch

Repository: `https://github.com/NoObIe-97/machine_sim.git`

Branch: `feature/milestone-1`

Start from the accepted Milestone 11B remote head:

```text
a6e7a91
```

Milestone 11 is accepted. Milestone 12 should build on it without reworking accepted runtime behavior unless a minimal compatibility fix is required.

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

The accepted M11 next direction is:

```text
Milestone 12: Multi-Generation Trace Drift and Compression Stability — generation-indexed trace deltas, compressed-summary drift envelopes, replay-error stability, capsule-trace compatibility checks, and bounded long-run diagnostic retention.
```

---

## Conceptual boundary

Milestone 12 is about generation-indexed diagnostic drift, not biological or social evolution.

Do not introduce human/social/biological/political/economic/strategic/emotional wording or concepts in runtime code, config keys, event labels, artifact schemas, or committed reports.

Avoid terms such as:

```text
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
society
cooperation
competition
conflict
strategy
trust
knowledge
learning
teaching
memory
message
language
meaning
communication
```

Use machine-native alternatives:

```text
generation-indexed trace
generation index
trace drift
drift envelope
compressed-summary delta
replay-error stability
capsule-trace compatibility
long-run diagnostic retention
lineage-indexed comparison
bounded diagnostic window
trace retention record
summary drift score
```

If wording is ambiguous, choose physical/numeric terminology.

---

## Milestone 12 goal

Add a deterministic analysis layer that evaluates how compressed operational summaries change across generation-indexed lineage records and long-run diagnostic windows.

The layer should remain observational and numeric. It should not alter unit decision logic, capsule application, fabrication behavior, or trace-compression behavior unless a minimal adapter is needed.

---

## Desired implementation areas

### 1. Generation-indexed trace deltas

Add a module such as:

```text
machine_sim/analysis/trace_drift.py
```

Suggested class name:

```text
TraceDriftAnalyzer
```

Suggested fields:

```text
generation_trace_count
generation_index_span
avg_generation_trace_delta
max_generation_trace_delta
compressed_summary_delta
lineage_trace_delta_count
```

Minimum expectations:

- Use real lineage records, trace-compression summaries, or capsule-compatible summaries.
- Safe zero summary when no generation-indexed records exist.
- Deterministic under the same seed.
- Storage bounded by a configured maximum.

### 2. Compressed-summary drift envelopes

Summarize numeric drift ranges across compressed trace summaries.

Suggested fields:

```text
drift_envelope_count
avg_drift_envelope_width
max_drift_envelope_width
power_ratio_drift_range
sensor_health_drift_range
signal_trace_drift_range
```

Minimum expectations:

- Compute from real M11 trace-compression summaries or trace segments.
- Bound stored envelope records.
- Output must be numeric and stable under same seed.

### 3. Replay-error stability

Analyze stability of replay-error metrics across long-run windows.

Suggested fields:

```text
replay_error_window_count
avg_replay_error_delta
max_replay_error_delta
replay_stability_floor
replay_stability_variance
```

Minimum expectations:

- Use M11 replay metrics, not placeholder constants.
- Safe zero output if replay metrics are absent.
- Nonzero in M12 deterministic demo if trace compression is enabled.

### 4. Capsule-trace compatibility checks

Compare capsule-compatible diagnostic summaries against compressed trace summaries.

Suggested fields:

```text
capsule_trace_check_count
capsule_trace_power_delta
capsule_trace_sensor_delta
capsule_trace_field_delta
capsule_trace_compatibility_score
```

Minimum expectations:

- Use M7 capsule summaries or M11 capsule-compatible fields when available.
- Does not alter capsule generation, capsule storage, or warm-start application.
- Safe zero output when capsule data is absent.

### 5. Bounded long-run diagnostic retention

Retain compact drift/trace summaries over a bounded long-run diagnostic window.

Suggested fields:

```text
retention_record_count
retention_window_span
retention_compression_ratio
retained_summary_count
retention_drop_count
```

Minimum expectations:

- Bounded by `max_records` or equivalent.
- Test must prove old records are trimmed.
- Artifact must include retention metrics.

---

## Config expectations

Add minimal config keys only. Keep names machine-native.

Possible keys:

```text
trace_drift_enabled
trace_drift_window
trace_drift_sample_interval
trace_drift_max_records
trace_drift_retention_window
capsule_trace_check_enabled
```

If config keys are added, update guardrail config allowlists accordingly.

Avoid semantic names such as memory, inheritance, mutation, evolution, population, communication, knowledge, or learning.

---

## CLI expectations

The existing `run` command should print Milestone 12 summaries when trace drift analysis is enabled.

Expected output shape:

```text
Trace drift: generations=..., span=..., avg_delta=..., max_delta=...
Drift envelope: records=..., avg_width=..., max_width=...
Replay stability: windows=..., avg_delta=..., stability_floor=...
Capsule trace check: count=..., compatibility=..., power_delta=...
Retention: records=..., span=..., retained=..., dropped=...
```

Exact labels can differ, but they must be machine-native and numeric.

When `-o` is provided, write an artifact such as:

```text
trace_drift.json
```

Artifact contents should be compact and bounded.

---

## Demo config

Add:

```text
configs/milestone_12_trace_drift.toml
```

Recommended characteristics:

- trace compression enabled,
- telemetry enabled,
- reconciliation enabled,
- fabrication enabled,
- capsule enabled,
- lineage drift enabled if useful,
- enough ticks for multiple generation-indexed records,
- deterministic seed 42.

Runtime should remain small enough for full regression.

---

## Testing requirements

Add focused tests for M12. Tests must assert real numeric behavior.

Required tests:

1. **Generation-indexed trace deltas**
   - Enabled setup produces numeric generation trace counts and deltas when records exist.
   - No-generation setup returns clean zero summary.

2. **Compressed-summary drift envelopes**
   - Drift envelope fields are present, numeric, bounded, and non-negative.
   - Deterministic same seed produces identical envelope summary.

3. **Replay-error stability**
   - Uses replay metrics from trace compression.
   - Produces numeric stability fields.
   - Safe zero output when replay metrics are absent.

4. **Capsule-trace compatibility checks**
   - Capsule-enabled setup produces numeric compatibility fields when capsule-compatible data exists.
   - Capsule-disabled setup returns clean zero summary.

5. **Long-run diagnostic retention**
   - `max_records=N`; record more than `N`; assert internal stores stay within `N`.
   - Retention metrics report retained/dropped counts or equivalent.

6. **Deterministic demo**
   - Same seed produces identical M12 summary.

7. **Artifact schema test**
   - `trace_drift.json` contains generation, drift envelope, replay stability, capsule-trace, and retention fields or sections.

Existing tests must keep passing.

---

## Documentation requirements

Add:

```text
docs/milestone_12_report.md
```

The report must include:

- M12 design summary,
- what was implemented,
- scope boundary in machine-native wording,
- config keys,
- artifact path and high-level schema,
- commands run,
- current test/coverage results,
- guardrail result,
- full M1–M12 regression summary with numeric results,
- M5 comparison summary,
- M7 capsule comparison summary,
- M8 telemetry/reconciliation summary,
- M9 pressure summary,
- M10 signal-dynamics summary,
- M11 trace-compression summary,
- M12 trace-drift summary,
- known limitations,
- next recommended milestone using machine-native wording only.

Update:

```text
docs/review_package.md
```

The review package must be current through M12 and must not retain stale milestone titles, stale test counts, stale coverage values, or stale report paths.

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
REVIEW_PACKAGE_TITLE_CURRENT: yes
REVIEW_PACKAGE_TESTS_CURRENT: yes
REVIEW_PACKAGE_COVERAGE_CURRENT: yes
REVIEW_PACKAGE_CURRENT_MILESTONE_SUMMARY: yes
CURRENT_ARTIFACT_PATHS_REPORTED: yes
NEXT_MILESTONE_WORDING_MACHINE_NATIVE: yes
NO_STALE_DOC_VALUES_FOUND: yes
CLEAN_WORKTREE_AFTER_PUSH: yes
FINAL_REMOTE_HASH_REPORTED: yes
```

Do not claim `PASS`, `ACCEPTED`, or `READY_FOR_MILESTONE_13` unless every line is `yes`.

---

## Commit and handoff requirements

Commit all changes and push to `feature/milestone-1`.

Final response must include:

```text
TASK_STATUS: PASS or PARTIAL_PASS
MILESTONE_12_STATUS: ACCEPTED or HOLD
READY_FOR_MILESTONE_13: YES or NO
Branch:
Starting commit hash:
Implementation commit hash:
Final remote commit hash:
Design summary:
Files changed:
Tests:
Coverage:
Guardrail result:
Full M1-M12 regression summary:
M12 demo output:
Artifact paths:
Stage closing chores result:
Known limitations:
Clean working tree:
```

---

## Acceptance criteria

Do not mark PASS unless all are true:

```text
M12_GENERATION_INDEXED_TRACE_DELTAS: PASS
M12_COMPRESSED_SUMMARY_DRIFT_ENVELOPES: PASS
M12_REPLAY_ERROR_STABILITY: PASS
M12_CAPSULE_TRACE_COMPATIBILITY: PASS
M12_LONG_RUN_DIAGNOSTIC_RETENTION: PASS
M12_DETERMINISTIC_DEMO: PASS
M12_ARTIFACTS_WRITTEN: PASS
M12_TESTS_ASSERT_REAL_NUMERIC_BEHAVIOR: PASS
TESTS_AND_COVERAGE: PASS
GUARDRAILS: PASS
FULL_M1_M12_REGRESSION_REPORTED: PASS
MILESTONE_12_REPORT_CURRENT: PASS
REVIEW_PACKAGE_CURRENT: PASS
STAGE_CLOSING_CHORES_SATISFIED: PASS
CLEAN_WORKTREE_AND_PUSHED_REMOTE: PASS
```

If any item fails, return `PARTIAL_PASS` with exact blockers and do not claim Milestone 12 is accepted.
