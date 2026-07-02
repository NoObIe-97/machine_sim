# After Silicon — MiMo Milestone 10 Signal Pattern Field Dynamics Prompt

## Repository and branch

Repository: `https://github.com/NoObIe-97/machine_sim.git`

Branch: `feature/milestone-1`

Start from the accepted Milestone 9B remote head:

```text
5915ea1
```

Milestone 9 is accepted. Milestone 10 should build on it. Do not rework earlier accepted milestones unless a minimal compatibility fix is required.

Before final handoff, invoke the shared stage-closing skill:

```text
prompts/skills/stage_closing_chores.md
```

Do not skip the stage-closing skill. Its checklist is mandatory for this and all later stages.

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

The latest accepted M9 report identifies the next direction as:

```text
Milestone 10: Signal Pattern Field Dynamics — cross-tick pattern frequency analysis, temporal signal-density clustering, signal-gradient mapping, pattern-observation correlation scoring, and non-semantic field dynamics summaries.
```

Milestone 10 must implement that direction while preserving the project’s machine-native boundary.

---

## Conceptual boundary

Milestone 10 is about **field dynamics**, not meaning. Signal patterns must remain non-semantic numerical field events.

Do not introduce human/social/biological/political/economic/strategic/emotional wording or concepts in runtime code, config keys, event labels, artifact schemas, or committed reports.

Avoid concepts such as:

```text
communication
message
language
meaning
instruction
knowledge
learning
teaching
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
```

Use machine-native alternatives:

```text
signal pattern field
pattern frequency
pattern observation count
temporal density
signal-density cluster
signal-gradient map
pattern-observation correlation
field dynamics summary
cross-tick pattern persistence
local signal intensity
bounded field trace
pattern recurrence score
field occupancy
signal perturbation
```

If wording is ambiguous, choose physical/numeric terminology.

---

## Milestone 10 goal

Add a deterministic analysis layer that summarizes cross-tick dynamics of non-semantic signal patterns, including:

1. pattern frequency across ticks,
2. temporal signal-density clusters,
3. local signal-gradient mapping,
4. pattern-observation correlation scores,
5. bounded field dynamics artifacts and summaries.

The layer should be diagnostic and observational. It should not alter unit decision logic unless a minimal metric hook is required.

---

## Desired implementation areas

### 1. Cross-tick pattern frequency analysis

Track how signal pattern identifiers recur across time.

Useful metrics:

```text
pattern_frequency_total
pattern_tick_span
pattern_recurrence_score
pattern_active_ticks
pattern_density_by_tick
most_frequent_pattern_id
```

Minimum expectation:

- Use real emitted/observed signal data from the existing signal/correlation/field-tracker path.
- Keep storage bounded.
- Demo output must show nonzero pattern frequency when signal mode is enabled.

### 2. Temporal signal-density clustering

Add a numeric summary of signal density over time windows. This is a statistical field summary, not semantic clustering.

Useful metrics:

```text
density_window_count
avg_signal_density
max_signal_density
density_cluster_count
density_cluster_peak
cluster_tick_span
```

Minimum expectation:

- Compute clusters or windows from signal density over time.
- Use deterministic thresholds or windowing.
- Tests must prove repeated seed stability.

### 3. Signal-gradient mapping

Summarize how signal intensity or observation density varies spatially.

Useful metrics:

```text
signal_gradient_cells
avg_signal_gradient
max_signal_gradient
local_signal_density
field_gradient_strength
```

Minimum expectation:

- Derive metrics from signal field/world observations or unit field trackers.
- Avoid placeholder values.
- Write bounded summaries to artifact output.

### 4. Pattern-observation correlation scoring

Extend or wrap existing M4/M5 correlation data into a M10 field-dynamics summary.

Useful metrics:

```text
pattern_observation_correlation
pattern_density_correlation
pattern_persistence_score
lag_window_score
pattern_field_score
```

Minimum expectation:

- Use real signal emission/observation records.
- Do not infer meaning, intent, instruction, or semantic value.
- Report at least one nonzero correlation/score in the M10 demo.

### 5. M10 deterministic demo config

Add:

```text
configs/milestone_10_signal_field_dynamics.toml
```

Recommended demo characteristics:

- signal mode enabled,
- adaptive mode enabled if useful for richer signal traces,
- moderate unit count,
- enough ticks to generate recurring pattern observations,
- pressure analysis may remain enabled if useful,
- runtime should remain small enough for full regression.

Expected CLI output should include something like:

```text
Signal dynamics: patterns=..., active_ticks=..., recurrence=...
Density clusters: windows=..., clusters=..., peak_density=...
Signal gradients: cells=..., avg_gradient=..., max_gradient=...
Pattern correlation: records=..., avg_score=..., max_score=...
```

Exact labels can differ, but they must be machine-native and numeric.

### 6. Artifacts

Write one or more JSON artifacts under the output directory when signal field dynamics is enabled.

Preferred simple artifact:

```text
signal_field_dynamics.json
```

Acceptable split artifacts:

```text
pattern_frequency.json
density_clusters.json
signal_gradient.json
pattern_correlation.json
```

Artifact contents should include bounded summaries, not unbounded logs.

---

## Config expectations

Add minimal config keys only. Keep names machine-native.

Possible keys:

```text
signal_dynamics_enabled
signal_dynamics_window
signal_dynamics_sample_interval
signal_dynamics_max_records
signal_gradient_radius
signal_density_threshold
```

If you add config keys, update guardrail config allowlists accordingly.

Avoid semantic names such as message, language, intent, meaning, knowledge, learning, or communication.

---

## CLI expectations

The existing `run` command should print M10 summaries when signal dynamics is enabled.

When `-o` is provided, write the signal-dynamics artifact(s).

The existing `inspect` command may remain event-based, but the M10 report must include CLI-visible M10 summary output from the `run` command.

---

## Testing requirements

Add focused tests for Milestone 10. Tests must assert behavior, not only object existence.

Required tests:

1. **Pattern frequency is nonzero with signal mode enabled**
   - Run a deterministic signal-enabled setup.
   - Assert total pattern frequency or active pattern count is greater than zero.

2. **Temporal signal-density summaries are deterministic**
   - Same seed produces identical density summary.

3. **Density cluster/window metrics are bounded and numeric**
   - Assert window/record counts stay within configured maximum.
   - Assert averages and maxima are numeric and non-negative.

4. **Signal-gradient metrics are generated from real signal data**
   - Assert gradient cell count and/or gradient strength are present and numeric.
   - Prefer nonzero values in the deterministic demo.

5. **Pattern-observation correlation score is present**
   - Assert correlation record count or average score is present and numeric.
   - Prefer nonzero values in the deterministic demo.

6. **Signal-disabled mode remains safe**
   - Run with signal mode disabled and signal dynamics enabled or disabled.
   - Assert clean zero summaries, no crash.

7. **M10 demo generates visible output**
   - The deterministic M10 config should produce nonzero signal-dynamics metrics.

Existing tests must keep passing.

---

## Documentation requirements

Add:

```text
docs/milestone_10_report.md
```

The report must include:

- summary of signal pattern field dynamics design,
- what was implemented,
- scope boundary in machine-native wording,
- new config keys,
- artifact names and high-level schemas,
- commands run,
- current test/coverage results,
- guardrail result,
- full M1–M10 regression summary with numeric results,
- M5 comparison summary,
- M7 capsule comparison summary,
- M8 telemetry/reconciliation summary,
- M9 pressure summary,
- M10 signal-dynamics summary,
- known limitations,
- next recommended milestone using machine-native wording only.

Update:

```text
docs/review_package.md
```

The review package must be current through M10 and must not retain stale milestone titles, stale test counts, stale coverage values, or stale report paths.

---

## Required verification commands

Run the full verification set before final handoff.

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
```

Also run a targeted wording check against files added or modified for M10. Remove problematic matches introduced by this stage.

---

## Stage closing chores

Before final handoff, invoke and satisfy:

```text
prompts/skills/stage_closing_chores.md
```

This means:

- update `docs/milestone_10_report.md`,
- update `docs/review_package.md`,
- report full regression results,
- report current tests and coverage,
- report artifact paths,
- check machine-native wording,
- confirm clean working tree,
- report final remote hash.

Do not claim `PASS`, `ACCEPTED`, or `READY_FOR_MILESTONE_11` until the stage-closing checklist is satisfied.

---

## Commit and handoff requirements

Commit all changes and push to `feature/milestone-1`.

Final response must include:

```text
TASK_STATUS: PASS or PARTIAL_PASS
MILESTONE_10_STATUS: ACCEPTED or HOLD
READY_FOR_MILESTONE_11: YES or NO
Branch:
Starting commit hash:
Implementation commit hash:
Final remote commit hash:
Design summary:
Files changed:
Tests:
Coverage:
Guardrail result:
Full M1-M10 regression summary:
M10 demo output:
Artifact paths:
Stage closing chores result:
Known limitations:
Clean working tree:
```

---

## Acceptance criteria

Do not mark PASS unless all are true:

```text
M10_PATTERN_FREQUENCY_ANALYSIS: PASS
M10_TEMPORAL_DENSITY_SUMMARY: PASS
M10_SIGNAL_GRADIENT_MAPPING: PASS
M10_PATTERN_OBSERVATION_CORRELATION: PASS
M10_SIGNAL_DISABLED_SAFE_ZERO: PASS
M10_DETERMINISTIC_DEMO: PASS
M10_ARTIFACTS_WRITTEN: PASS
M10_TESTS_ASSERT_REAL_NUMERIC_BEHAVIOR: PASS
TESTS_AND_COVERAGE: PASS
GUARDRAILS: PASS
FULL_M1_M10_REGRESSION_REPORTED: PASS
MILESTONE_10_REPORT_CURRENT: PASS
REVIEW_PACKAGE_CURRENT: PASS
STAGE_CLOSING_CHORES_SATISFIED: PASS
CLEAN_WORKTREE_AND_PUSHED_REMOTE: PASS
```

If any item fails, return `PARTIAL_PASS` with exact blockers and do not claim Milestone 10 is accepted.
