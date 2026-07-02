# After Silicon — MiMo Milestone 10B Tests, Documentation, and Stage Closing Prompt

## Repository and branch

Repository: `https://github.com/NoObIe-97/machine_sim.git`

Branch: `feature/milestone-1`

Start from the current Milestone 10A remote head:

```text
24261e9
```

Milestone 10 gradient exposure is now implemented, but final acceptance remains on hold because tests and stage-closing documentation are still stale.

Do not start Milestone 11.

Before final handoff, invoke and satisfy the updated shared stage-closing skill:

```text
prompts/skills/stage_closing_chores.md
```

---

## Current review decision

```text
M10A_SIGNAL_GRADIENT_EXPOSED_IN_SUMMARY: PASS
M10A_SIGNAL_GRADIENT_EXPOSED_IN_CLI_AND_ARTIFACT: PASS
M10A_STRONG_NUMERIC_TESTS: FAIL
M10A_BOUNDED_STORAGE_TEST: FAIL
FULL_M1_M10_REGRESSION_REPORTED: FAIL
MILESTONE_10_REPORT_CURRENT: FAIL
REVIEW_PACKAGE_CURRENT: FAIL
NEXT_MILESTONE_WORDING_MACHINE_NATIVE: FAIL
STAGE_CLOSING_CHORES_SATISFIED: FAIL
MILESTONE_10_FINAL_ACCEPTANCE: HOLD
READY_FOR_MILESTONE_11: NO
```

---

## What already passed

Keep these items unless a minimal correction is required:

- `SignalFieldDynamics` summary now includes:
  - `signal_gradient_cells`
  - `avg_signal_gradient`
  - `max_signal_gradient`
- Engine computes and records signal-gradient during field-dynamics phase.
- CLI prints `Signal gradient: cells=..., avg_gradient=..., max_gradient=...`.
- The artifact path writes `signal_field_dynamics.json`, and that artifact should now include the gradient fields because it serializes the summary.

---

## Blocking issue 1 — tests are still too weak

Strengthen `machine_sim/tests/test_field_dynamics.py`.

Required test updates:

1. **Summary exposes gradient fields**

Add or update a test to assert:

```python
assert "signal_gradient_cells" in summary
assert "avg_signal_gradient" in summary
assert "max_signal_gradient" in summary
assert summary["signal_gradient_cells"] > 0
assert summary["max_signal_gradient"] > 0.0
```

Use the deterministic M10 demo-style engine run so this comes from real world state.

2. **Density clusters are nonzero in deterministic demo**

Replace weak `>= 0` assertions with strict assertions where the deterministic demo supports it:

```python
assert summary["cluster_count"] > 0
assert summary["peak_cluster_density"] > 0
```

3. **Pattern correlation is nonzero in deterministic demo**

Replace weak `>= 0` assertions with:

```python
assert summary["correlation_count"] > 0
assert summary["avg_correlation_score"] > 0.0
assert summary["max_correlation_score"] > 0.0
```

If the deterministic engine run cannot guarantee nonzero correlation, adjust the deterministic setup within machine-native bounds so it does.

4. **Bounded storage test**

Add a direct unit test:

```python
dynamics = SignalFieldDynamics(enabled=True, max_records=5)
for i in range(20):
    dynamics.record_signal(i, "u0", i % 3, {})
    dynamics.record_observation(i, "u0", "proximity", {})
assert len(dynamics._signal_history) <= 5
assert len(dynamics._observation_history) <= 5
```

5. **Signal-disabled safe-zero remains valid**

Ensure disabled/empty summary remains safe and returns zero counts without crashing, including gradient fields.

6. **Artifact contains gradient fields**

If feasible, add a CLI/output test or direct engine artifact-generation test verifying `signal_field_dynamics.json` includes:

```text
signal_gradient_cells
avg_signal_gradient
max_signal_gradient
```

Existing tests must keep passing.

---

## Blocking issue 2 — M10 report is stale

`docs/milestone_10_report.md` still lists only M10 commands and old output without gradient.

Update it with:

- Current test result and runtime from the latest run.
- Current coverage result from the latest run.
- Full M1–M10 regression command set.
- Numeric summaries for M1 through M10.
- M10 output including the new signal-gradient line.
- Artifact path: `output/demo_m10/signal_field_dynamics.json`.
- Current known limitations.
- Machine-native next milestone wording.

Required next milestone wording:

```text
Milestone 11: Bounded Operational Trace Compression — compressed signal-field histories, telemetry-window reduction, capsule-compatible diagnostic summaries, lineage-indexed trace comparison, and bounded replay metrics.
```

Do not implement Milestone 11.

---

## Blocking issue 3 — review package is stale

`docs/review_package.md` still says `Milestone 9 Final Review Package`, still reports M9 values, and lacks M10 artifact/report paths.

Update it so all of these are true:

```text
REVIEW_PACKAGE_TITLE_CURRENT: yes
REVIEW_PACKAGE_TESTS_CURRENT: yes
REVIEW_PACKAGE_COVERAGE_CURRENT: yes
REVIEW_PACKAGE_CURRENT_MILESTONE_SUMMARY: yes
CURRENT_ARTIFACT_PATHS_REPORTED: yes
REPORT_PATHS_CURRENT: yes
```

Required review-package updates:

- Title: `# Milestone 10 Final Review Package`
- Commit list includes M10, M10A, and M10B commits.
- Final tests match latest run.
- Final coverage matches latest run.
- M1–M10 regression summary is present.
- M10 output includes signal-gradient line.
- Artifact paths include `output/demo_m10/signal_field_dynamics.json`.
- Report paths include `docs/milestone_10_report.md`.
- Clean working tree status is current after push.

A one-line commit append is not sufficient.

---

## Required full verification commands

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
```

Run the documentation freshness checks from:

```text
prompts/skills/stage_closing_chores.md
```

Also run a wording check against files added or modified for M10/M10A/M10B and remove problematic wording introduced by these stages.

---

## Stage-closing evidence required in final handoff

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

If any value is `no`, report `PARTIAL_PASS` or `HOLD`.

---

## Commit and handoff requirements

Commit all changes and push to `feature/milestone-1`.

Final response must include:

```text
MILESTONE_10B_STATUS: PASS or PARTIAL_PASS
MILESTONE_10_STATUS: ACCEPTED or HOLD
READY_FOR_MILESTONE_11: YES or NO
Branch:
Starting commit hash:
Implementation commit hash:
Final remote commit hash:
Files changed:
Tests:
Coverage:
Guardrail result:
Full M1-M10 regression summary:
M10 demo output:
Artifact paths:
Stage closing chores result:
Documentation updates:
Known limitations:
Clean working tree:
```

---

## Acceptance criteria

Do not mark PASS unless all are true:

```text
M10B_STRONG_NUMERIC_TESTS: PASS
M10B_SIGNAL_GRADIENT_TESTED_IN_SUMMARY: PASS
M10B_BOUNDED_STORAGE_TEST: PASS
M10B_ARTIFACT_GRADIENT_FIELDS_VERIFIED: PASS
FULL_M1_M10_REGRESSION_REPORTED: PASS
MILESTONE_10_REPORT_CURRENT: PASS
REVIEW_PACKAGE_CURRENT: PASS
NEXT_MILESTONE_WORDING_MACHINE_NATIVE: PASS
STAGE_CLOSING_CHORES_SATISFIED: PASS
TESTS_AND_COVERAGE: PASS
GUARDRAILS: PASS
CLEAN_WORKTREE_AND_PUSHED_REMOTE: PASS
```
