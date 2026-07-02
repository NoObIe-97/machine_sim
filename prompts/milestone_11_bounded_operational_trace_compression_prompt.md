# After Silicon — MiMo Milestone 11 Bounded Operational Trace Compression Prompt

## Repository and branch

Repository: `https://github.com/NoObIe-97/machine_sim.git`

Branch: `feature/milestone-1`

Start from the accepted Milestone 10D remote head:

```text
bdf6549
```

Milestone 10 is accepted. Milestone 11 should build on it without reworking accepted runtime behavior unless a minimal compatibility fix is required.

Before final handoff, invoke and satisfy the shared stage-closing skill:

```text
prompts/skills/stage_closing_chores.md
```

Do not skip the stage-closing skill. Its checklist is mandatory.

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
- M10 signal pattern field dynamics, including pattern frequency, density clusters, signal gradients, and pattern-observation correlation

The accepted M10 next direction is:

```text
Milestone 11: Bounded Operational Trace Compression — compressed signal-field histories, telemetry-window reduction, capsule-compatible diagnostic summaries, lineage-indexed trace comparison, and bounded replay metrics.
```

---

## Conceptual boundary

Milestone 11 is about bounded compression of operational traces, not semantic memory.

Do not introduce human/social/biological/political/economic/strategic/emotional wording or concepts in runtime code, config keys, event labels, artifact schemas, or committed reports.

Avoid terms such as:

```text
memory
remember
knowledge
learning
teaching
message
language
meaning
instruction
communication
cooperation
conflict
competition
strategy
trust
alliance
deception
friend
enemy
society
community
parent
child
offspring
inheritance
```

Use machine-native alternatives:

```text
operational trace
trace compression
compressed field history
telemetry-window reduction
diagnostic summary
capsule-compatible summary
lineage-indexed comparison
bounded replay metric
trace reconstruction error
compression ratio
signal-field trace
state trace segment
summary vector
```

If wording is ambiguous, choose physical/numeric terminology.

---

## Milestone 11 goal

Add a deterministic analysis layer that compresses bounded operational traces into compact diagnostic summaries.

The layer should summarize signal-field history, telemetry windows, capsule-compatible diagnostics, and lineage-indexed trace comparisons. It should be observational and should not alter unit decision logic.

---

## Desired implementation areas

### 1. Bounded trace compressor

Add a module such as:

```text
machine_sim/analysis/trace_compression.py
```

Suggested class name:

```text
TraceCompressor
```

Suggested summary fields:

```text
trace_window_count
raw_trace_points
compressed_trace_points
compression_ratio
trace_reconstruction_error
summary_vector_count
max_records
```

Minimum expectations:

- Bounded storage using `max_records` or equivalent.
- Deterministic output under same seed.
- Compression uses real simulation-derived traces, not placeholder constants.
- Compression ratio is numeric and visible in CLI/demo output.

### 2. Signal-field history compression

Compress signal-field dynamics traces from M10.

Suggested fields:

```text
signal_trace_points
compressed_signal_points
signal_trace_ratio
signal_density_summary
pattern_frequency_summary
field_gradient_summary
```

Minimum expectations:

- Use M10 signal dynamics output or signal event traces.
- Preserve compact numeric summaries of pattern count, signal density, and gradient strength.
- Do not infer meaning or assign semantic labels.

### 3. Telemetry-window reduction

Compress M8 telemetry/reconciliation summaries into bounded diagnostic windows.

Suggested fields:

```text
telemetry_window_count
telemetry_input_frames
compressed_telemetry_frames
avg_power_ratio_summary
avg_sensor_health_summary
continuity_summary
```

Minimum expectations:

- Use real telemetry tracker or reconciliation summaries when enabled.
- Safe zero summary when telemetry is disabled.
- Bounded output.

### 4. Capsule-compatible diagnostic summaries

Generate a compact diagnostic summary that can be compared with M7 capsule fields without changing capsule behavior.

Suggested fields:

```text
capsule_summary_count
capsule_compatible_fields
power_ratio_trace_summary
sensor_health_trace_summary
local_field_trace_summary
```

Minimum expectations:

- Does not alter capsule generation or application.
- Uses only numeric operational fields.
- Provides nonzero summary when capsule-enabled demo creates capsules.

### 5. Lineage-indexed trace comparison

Add bounded comparisons across lineage indices or successor records.

Suggested fields:

```text
lineage_trace_count
lineage_index_span
lineage_trace_delta
lineage_compression_drift
lineage_replay_error
```

Minimum expectations:

- Uses real lineage records and/or capsule summaries when available.
- Safe zero output when lineage data is absent.
- Does not use biological framing.

### 6. Bounded replay metrics

Add a compact replay-style diagnostic metric that compares compressed summaries against source trace windows.

Suggested fields:

```text
replay_window_count
avg_replay_error
max_replay_error
replay_stability_score
```

Minimum expectations:

- Numeric, deterministic, bounded.
- Does not re-run or change the simulation state.
- Computed from stored trace windows or summaries.

---

## Config expectations

Add minimal config keys only. Keep names machine-native.

Possible keys:

```text
trace_compression_enabled
trace_compression_window
trace_compression_sample_interval
trace_compression_max_records
trace_compression_ratio_target
trace_replay_enabled
```

If config keys are added, update guardrail config allowlists accordingly.

Avoid semantic names such as memory, knowledge, learning, teaching, message, language, meaning, inheritance, or communication.

---

## CLI expectations

The existing `run` command should print Milestone 11 summaries when trace compression is enabled.

Expected output shape:

```text
Trace compression: raw=..., compressed=..., ratio=..., error=...
Signal trace: points=..., compressed=..., ratio=...
Telemetry trace: windows=..., frames=..., compressed=...
Lineage trace: count=..., delta=..., replay_error=...
```

Exact labels can differ, but they must be machine-native and numeric.

When `-o` is provided, write an artifact such as:

```text
trace_compression.json
```

Artifact contents should be compact and bounded.

---

## Demo config

Add:

```text
configs/milestone_11_trace_compression.toml
```

Recommended characteristics:

- signal mode enabled,
- signal dynamics enabled,
- telemetry enabled,
- reconciliation enabled,
- fabrication/capsule enabled if needed for lineage/capsule summaries,
- pressure analysis can remain enabled if useful,
- enough ticks for nonzero trace windows,
- deterministic seed 42.

Runtime should remain small enough for full regression.

---

## Testing requirements

Add focused tests for M11. Tests must assert real numeric behavior.

Required tests:

1. **Trace compression produces nonzero compression summary**
   - Assert raw trace points > 0.
   - Assert compressed trace points > 0.
   - Assert compression ratio > 0.

2. **Bounded storage**
   - Use `max_records=N`.
   - Record more than `N` trace points.
   - Assert internal stores stay within `N`.

3. **Deterministic same-seed summary**
   - Same seed produces identical compression summary.

4. **Signal trace compression uses real signal data**
   - With signal dynamics enabled, assert signal trace points > 0.

5. **Telemetry-window reduction safe behavior**
   - Enabled telemetry produces nonzero telemetry summary in demo.
   - Disabled telemetry produces clean zero summary without crash.

6. **Capsule-compatible diagnostic summary safe behavior**
   - Capsule-enabled demo produces numeric capsule-compatible summary when capsules exist.
   - Capsule-disabled mode returns clean zero summary.

7. **Lineage-indexed comparison safe behavior**
   - Fabrication/lineage-enabled demo produces numeric lineage trace summary when records exist.
   - No-lineage mode returns clean zero summary.

8. **Artifact generation**
   - Demo output writes `trace_compression.json`.
   - Artifact contains compression ratio, signal trace summary, telemetry trace summary, and replay metrics.

Existing tests must keep passing.

---

## Documentation requirements

Add:

```text
docs/milestone_11_report.md
```

The report must include:

- M11 design summary,
- what was implemented,
- scope boundary in machine-native wording,
- config keys,
- artifact path and high-level schema,
- commands run,
- current test/coverage results,
- guardrail result,
- full M1–M11 regression summary with numeric results,
- M5 comparison summary,
- M7 capsule comparison summary,
- M8 telemetry/reconciliation summary,
- M9 pressure summary,
- M10 signal-dynamics summary,
- M11 trace-compression summary,
- known limitations,
- next recommended milestone using machine-native wording only.

Update:

```text
docs/review_package.md
```

The review package must be current through M11 and must not retain stale milestone titles, stale test counts, stale coverage values, or stale report paths.

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

Do not claim `PASS`, `ACCEPTED`, or `READY_FOR_MILESTONE_12` unless every line is `yes`.

---

## Commit and handoff requirements

Commit all changes and push to `feature/milestone-1`.

Final response must include:

```text
TASK_STATUS: PASS or PARTIAL_PASS
MILESTONE_11_STATUS: ACCEPTED or HOLD
READY_FOR_MILESTONE_12: YES or NO
Branch:
Starting commit hash:
Implementation commit hash:
Final remote commit hash:
Design summary:
Files changed:
Tests:
Coverage:
Guardrail result:
Full M1-M11 regression summary:
M11 demo output:
Artifact paths:
Stage closing chores result:
Known limitations:
Clean working tree:
```

---

## Acceptance criteria

Do not mark PASS unless all are true:

```text
M11_TRACE_COMPRESSION_CORE: PASS
M11_SIGNAL_TRACE_COMPRESSION: PASS
M11_TELEMETRY_WINDOW_REDUCTION: PASS
M11_CAPSULE_COMPATIBLE_DIAGNOSTIC_SUMMARY: PASS
M11_LINEAGE_INDEXED_TRACE_COMPARISON: PASS
M11_BOUNDED_REPLAY_METRICS: PASS
M11_DETERMINISTIC_DEMO: PASS
M11_ARTIFACTS_WRITTEN: PASS
M11_TESTS_ASSERT_REAL_NUMERIC_BEHAVIOR: PASS
TESTS_AND_COVERAGE: PASS
GUARDRAILS: PASS
FULL_M1_M11_REGRESSION_REPORTED: PASS
MILESTONE_11_REPORT_CURRENT: PASS
REVIEW_PACKAGE_CURRENT: PASS
STAGE_CLOSING_CHORES_SATISFIED: PASS
CLEAN_WORKTREE_AND_PUSHED_REMOTE: PASS
```

If any item fails, return `PARTIAL_PASS` with exact blockers and do not claim Milestone 11 is accepted.
