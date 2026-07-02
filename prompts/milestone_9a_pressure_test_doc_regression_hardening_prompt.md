# After Silicon — MiMo Milestone 9A Pressure Test, Regression, and Documentation Hardening Prompt

## Repository and branch

Repository: `https://github.com/NoObIe-97/machine_sim.git`

Branch: `feature/milestone-1`

Start from the current Milestone 9 remote head:

```text
cf176e8
```

Milestone 9 core implementation is partially accepted at the code-structure level, but final Milestone 9 acceptance is on hold pending stronger tests and documentation synchronization.

Do not start Milestone 10.

---

## Current review decision

```text
MILESTONE_9_CORE_IMPLEMENTATION: PASS
PRESSURE_ANALYZER_MODULE: PASS
ENGINE_AND_CLI_INTEGRATION: PASS
M9_ARTIFACT_OUTPUT: PASS
M9_TEST_ASSERTION_STRENGTH: FAIL
FULL_M1_M9_REGRESSION_REPORTING: FAIL
MILESTONE_9_FINAL_ACCEPTANCE: HOLD
READY_FOR_MILESTONE_10: NO
```

---

## What already passed

The current implementation includes:

- `machine_sim/analysis/pressure.py`
- `PressureAnalyzer`
- bounded resource samples, extraction records, and pressure history
- engine Phase 10 pressure analysis hook
- CLI pressure summary output
- `pressure_analysis.json` artifact
- deterministic M9 demo config
- nonzero M9 demo output for resource pressure, extraction load, proximity pressure, and field perturbation

Keep these pieces unless a minimal correction is needed.

---

## Blocking issue 1 — tests are too weak

The current tests prove basic generation and determinism, but they do not strongly assert the required Milestone 9 behavior.

Strengthen `machine_sim/tests/test_pressure.py` so the tests prove real numeric behavior, not only existence/non-negative values.

Required test hardening:

1. **Extraction-load coupling must be nonzero in the deterministic M9 demo**

Add or strengthen a test so it asserts:

```python
assert pressure["total_extraction_events"] > 0
assert pressure["peak_cell_load"] > 0.0
assert pressure["avg_load_per_active_unit"] > 0.0
```

Use a deterministic setup that reliably produces extraction load.

2. **Signal-field perturbation must be nonzero when signal mode is enabled**

Add or strengthen a test so it asserts:

```python
assert pressure["signal_density"] > 0.0
assert pressure["field_perturbation_score"] > 0.0
```

The test must run with `signal_enabled=True` and should rely on real unit activity/field tracker state, not fake placeholder values.

3. **Bounded storage must be asserted**

Add a targeted unit test for `PressureAnalyzer(max_records=N)` that records more than `N` samples and asserts all bounded stores stay within `N`:

```python
assert len(analyzer._resource_samples) <= N
assert len(analyzer._extraction_records) <= N
assert len(analyzer._pressure_history) <= N
```

Using private fields is acceptable here because the test is verifying the internal bound contract.

4. **Dense pressure must be strictly higher than sparse pressure**

The existing test uses `>=`. Make it stronger by using a deterministic setup where dense pressure is strictly higher for at least one pressure metric:

```python
assert dense["avg_proximity_pressure"] > sparse["avg_proximity_pressure"]
```

or another clearly pressure-related metric that reliably increases.

5. **Resource pressure should assert meaningful nonzero pressure**

Add or strengthen a test so it asserts:

```python
assert pressure["resource_pressure_cells"] > 0
assert pressure["avg_resource_pressure"] > 0.0
assert pressure["max_resource_pressure"] > 0.0
```

6. Existing tests must continue to pass.

---

## Blocking issue 2 — full regression reporting is missing

`docs/milestone_9_report.md` currently lists only:

```bash
python -m pytest machine_sim/tests/ -v
python -m pytest machine_sim/tests/ --cov=machine_sim --cov-report=term-missing
python -m machine_sim.cli.main check
python -m machine_sim.cli.main run -c configs/milestone_9_resource_pressure.toml -t 200 -s 42 -o output/demo_m9
python -m machine_sim.cli.main inspect output/demo_m9
```

This is not enough for Milestone 9 final acceptance.

Update `docs/milestone_9_report.md` with the full verification command set:

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
```

Also include concise M1–M9 regression summaries in the report, including:

- M1 event count and active count
- M2 event count and movement-block count
- M3 signal emission summary
- M4 correlation summary
- M5 adaptive summary
- M5 comparison summary
- M6 fabrication summary
- M7 capsule summary and capsule comparison summary
- M8 telemetry/reconciliation/lineage-drift summary
- M9 pressure summary

Do not merely list the commands; include the numeric results.

---

## Documentation wording cleanup

The report currently includes a `What Was Deliberately Excluded` section with forbidden/social terms. This is not runtime logic, but the project is easier to review if committed docs avoid those words entirely.

Replace that section with machine-native wording such as:

```markdown
## Scope Boundary

- No semantic interpretation is assigned to signal patterns.
- No human/social/biological framing is used in runtime metrics.
- Pressure analysis is observational and numeric only.
- Unit state is not modified by pressure summaries.
```

Avoid writing the explicit forbidden terms in committed docs.

Also ensure the Next Recommended Milestone remains machine-native. The current wording is acceptable in direction but should avoid phrases like `interpretation layer`. Use wording such as:

```text
Milestone 10: Signal Pattern Field Dynamics — cross-tick pattern frequency analysis, temporal signal-density clustering, gradient mapping, pattern-observation correlation scoring, and non-semantic field dynamics summaries.
```

Do not start M10.

---

## Review package update

Update `docs/review_package.md` with the M9A commit hash and final M9 summary after the implementation is complete.

Ensure it does not claim Milestone 10 has started.

---

## Required verification commands

Run the full command set from the report section above.

Also run:

```bash
grep -R "conflict\|cooperation\|competition\|alliance\|enemy\|friend\|trust\|deception\|negotiation\|strategy\|social" machine_sim configs docs/milestone_9_report.md docs/review_package.md || true
```

For M9 final acceptance, avoid matches in files added or modified for M9/M9A. If a legacy file outside the M9 scope matches, report it but do not expand scope unnecessarily.

---

## Handoff requirements

Commit all changes and push to `feature/milestone-1`.

Final response must include:

```text
MILESTONE_9A_STATUS: PASS or PARTIAL_PASS
MILESTONE_9_STATUS: ACCEPTED or HOLD
READY_FOR_MILESTONE_10: YES or NO
Branch:
Starting commit hash:
Implementation commit hash:
Final remote commit hash:
Files changed:
Tests:
Coverage:
Guardrail result:
Full M1-M9 regression summary:
M9 pressure output:
Artifact paths:
Documentation updates:
Clean working tree:
```

Do not mark PASS unless tests, docs, guardrails, full regression reporting, and clean push are all complete.

---

## Acceptance criteria

```text
M9A_STRONG_NUMERIC_TESTS: PASS
M9_EXTRACTION_LOAD_NONZERO_TEST: PASS
M9_SIGNAL_FIELD_PERTURBATION_NONZERO_TEST: PASS
M9_PRESSURE_STORAGE_BOUND_TEST: PASS
M9_DENSE_GREATER_THAN_SPARSE_TEST: PASS
FULL_M1_M9_REGRESSION_REPORTED: PASS
MILESTONE_9_REPORT_SYNC: PASS
REVIEW_PACKAGE_SYNC: PASS
FORBIDDEN_FRAMING_IN_M9_DOCS: ABSENT
TESTS_AND_COVERAGE: PASS
GUARDRAILS: PASS
CLEAN_WORKTREE_AND_PUSHED_REMOTE: PASS
```
