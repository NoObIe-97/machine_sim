# After Silicon — MiMo Milestone 11A Trace Compression Hardening and Stage Closing Prompt

## Repository and branch

Repository: `https://github.com/NoObIe-97/machine_sim.git`

Branch: `feature/milestone-1`

Start from the current Milestone 11 remote head:

```text
1f2fe76
```

Milestone 11 has a real core trace compressor, but final acceptance is on hold pending missing M11 feature areas, stronger tests, and stage-closing documentation.

Do not start Milestone 12.

Before final handoff, invoke and satisfy the shared stage-closing skill:

```text
prompts/skills/stage_closing_chores.md
```

---

## Current review decision

```text
M11_TRACE_COMPRESSION_CORE: PASS
M11_BASIC_DEMO_OUTPUT: PASS
M11_SIGNAL_TRACE_COMPRESSION: PARTIAL
M11_TELEMETRY_WINDOW_REDUCTION: FAIL
M11_CAPSULE_COMPATIBLE_DIAGNOSTIC_SUMMARY: FAIL
M11_LINEAGE_INDEXED_TRACE_COMPARISON: FAIL
M11_BOUNDED_REPLAY_METRICS: FAIL
M11_ARTIFACT_SCHEMA_TESTING: FAIL
FULL_M1_M11_REGRESSION_REPORTED: FAIL
MILESTONE_11_REPORT_CURRENT: FAIL
REVIEW_PACKAGE_CURRENT: FAIL
NEXT_MILESTONE_WORDING_MACHINE_NATIVE: FAIL
STAGE_CLOSING_CHORES_SATISFIED: FAIL
MILESTONE_11_FINAL_ACCEPTANCE: HOLD
READY_FOR_MILESTONE_12: NO
```

---

## What already passed

Keep these pieces unless a minimal correction is needed:

- `machine_sim/analysis/trace_compression.py` exists.
- `TraceCompressor` stores bounded raw trace points.
- Basic compression produces nonzero raw/compressed counts and a compression ratio.
- Engine integration records per-unit trace points.
- CLI prints a basic trace compression line.
- `trace_compression.json` is written when trace compression is enabled.
- M11 tests currently cover basic compression, determinism, bounded raw-trace storage, and nonzero demo metrics.

---

## Blocking issue 1 — required M11 summary fields are missing

The current summary only includes basic trace counts and ratio. Extend the M11 summary/artifact with explicit fields for the M11 accepted scope.

Required top-level summary fields or nested sections:

```text
signal_trace_points
compressed_signal_points
signal_trace_ratio
telemetry_window_count
telemetry_input_frames
compressed_telemetry_frames
capsule_summary_count
capsule_compatible_fields
lineage_trace_count
lineage_index_span
lineage_trace_delta
replay_window_count
avg_replay_error
max_replay_error
replay_stability_score
```

These may be grouped under nested objects if preferred, but the artifact must expose equivalent machine-native fields.

Safe zero summaries are acceptable when the relevant upstream subsystem is disabled or has no records. In the deterministic M11 demo, enable enough upstream subsystems to make signal, telemetry, and at least one lineage/capsule summary nonzero if practical.

---

## Blocking issue 2 — telemetry-window reduction missing

Implement a compact telemetry-window reduction path.

Minimum behavior:

- When telemetry is enabled and frames exist, produce nonzero telemetry-window metrics.
- When telemetry is disabled, return clean zero metrics without crash.
- Keep output bounded.

Suggested fields:

```text
telemetry_window_count
telemetry_input_frames
compressed_telemetry_frames
avg_power_ratio_summary
avg_sensor_health_summary
continuity_summary
```

Use existing telemetry tracker or reconciliation summaries. Do not duplicate unbounded telemetry logs.

---

## Blocking issue 3 — capsule-compatible diagnostic summary missing

Implement a compact capsule-compatible diagnostic summary without changing capsule generation or application.

Minimum behavior:

- Capsule-enabled demo should produce numeric capsule-compatible fields when capsules exist.
- Capsule-disabled mode should return clean zero metrics.
- Keep names numeric and machine-native.

Suggested fields:

```text
capsule_summary_count
capsule_compatible_fields
power_ratio_trace_summary
sensor_health_trace_summary
local_field_trace_summary
```

---

## Blocking issue 4 — lineage-indexed trace comparison missing

Implement bounded lineage-indexed trace comparison.

Minimum behavior:

- Fabrication/lineage-enabled demo should produce numeric lineage trace metrics when records exist.
- No-lineage mode should return clean zero metrics.
- Do not use biological framing.

Suggested fields:

```text
lineage_trace_count
lineage_index_span
lineage_trace_delta
lineage_compression_drift
lineage_replay_error
```

---

## Blocking issue 5 — bounded replay metrics missing

Implement compact replay-style diagnostic metrics from stored trace windows or summaries.

Minimum behavior:

- Numeric, deterministic, bounded.
- Does not re-run or alter simulation state.
- Visible in CLI or artifact.

Suggested fields:

```text
replay_window_count
avg_replay_error
max_replay_error
replay_stability_score
```

---

## Blocking issue 6 — tests need to cover the full M11 scope

Strengthen `machine_sim/tests/test_trace_compression.py`.

Required tests:

1. **Basic compression remains nonzero**
   - raw trace points > 0
   - compressed trace points > 0
   - compression ratio > 0

2. **Bounded raw storage remains tested**
   - max_records bound asserted.

3. **Signal trace compression uses real signal-enabled data**
   - deterministic demo summary has `signal_trace_points > 0` or equivalent.

4. **Telemetry-window reduction**
   - telemetry-enabled setup produces nonzero telemetry summary.
   - telemetry-disabled setup returns clean zero summary.

5. **Capsule-compatible diagnostic summary**
   - capsule-enabled setup produces numeric capsule-compatible summary when capsules exist.
   - capsule-disabled setup returns clean zero summary.

6. **Lineage-indexed trace comparison**
   - lineage/fabrication-enabled setup produces numeric lineage trace fields when lineage records exist.
   - no-lineage setup returns clean zero summary.

7. **Bounded replay metrics**
   - replay fields are present, numeric, deterministic, and non-negative.

8. **Artifact schema test**
   - `trace_compression.json` contains basic compression fields plus signal, telemetry, capsule, lineage, and replay fields or sections.

Existing tests must keep passing.

---

## Blocking issue 7 — M11 report is incomplete/stale

Update `docs/milestone_11_report.md` so it includes:

- Full M1–M11 verification command set.
- Current test and coverage values from the latest run.
- Full M1–M11 numeric regression summary.
- M5 comparison summary.
- M7 capsule comparison summary.
- M8 telemetry/reconciliation summary.
- M9 pressure summary.
- M10 signal-dynamics summary.
- M11 trace-compression summary with signal, telemetry, capsule, lineage, and replay metrics.
- Artifact path: `output/demo_m11/trace_compression.json`.
- Known limitations.
- Machine-native next milestone wording.

Replace current M12 wording. Avoid population/replication/mutation/divergence framing. Suggested next milestone:

```text
Milestone 12: Multi-Generation Trace Drift and Compression Stability — generation-indexed trace deltas, compressed-summary drift envelopes, replay-error stability, capsule-trace compatibility checks, and bounded long-run diagnostic retention.
```

Do not implement Milestone 12.

---

## Blocking issue 8 — review package is stale

Update `docs/review_package.md` so it is current through M11A:

- Title: `# Milestone 11 Final Review Package`
- Commit list includes M11 and M11A commits.
- Final tests match the latest run.
- Final coverage matches the latest run.
- M1–M11 regression summary is present.
- M11 output summary is present.
- Artifact paths include `output/demo_m11/trace_compression.json`.
- Report paths include `docs/milestone_11_report.md`.
- Clean working tree status is current after push.

A one-line commit append is not sufficient.

---

## Required verification commands

Run:

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

Run freshness and wording checks from:

```text
prompts/skills/stage_closing_chores.md
```

---

## Stage-closing evidence required

Final handoff must include:

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

If any value is `no`, report `PARTIAL_PASS` or `HOLD`.

---

## Commit and handoff requirements

Commit all changes and push to `feature/milestone-1`.

Final response must include:

```text
MILESTONE_11A_STATUS: PASS or PARTIAL_PASS
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

```text
M11A_SIGNAL_TRACE_COMPRESSION: PASS
M11A_TELEMETRY_WINDOW_REDUCTION: PASS
M11A_CAPSULE_COMPATIBLE_DIAGNOSTIC_SUMMARY: PASS
M11A_LINEAGE_INDEXED_TRACE_COMPARISON: PASS
M11A_BOUNDED_REPLAY_METRICS: PASS
M11A_ARTIFACT_SCHEMA_TESTING: PASS
M11A_STRONG_NUMERIC_TESTS: PASS
FULL_M1_M11_REGRESSION_REPORTED: PASS
MILESTONE_11_REPORT_CURRENT: PASS
REVIEW_PACKAGE_CURRENT: PASS
NEXT_MILESTONE_WORDING_MACHINE_NATIVE: PASS
STAGE_CLOSING_CHORES_SATISFIED: PASS
TESTS_AND_COVERAGE: PASS
GUARDRAILS: PASS
CLEAN_WORKTREE_AND_PUSHED_REMOTE: PASS
```
