# After Silicon — MiMo Milestone 9B Documentation and Regression Sync Prompt

## Repository and branch

Repository: `https://github.com/NoObIe-97/machine_sim.git`

Branch: `feature/milestone-1`

Start from the current Milestone 9A remote head:

```text
cc0601d
```

Milestone 9 code and test hardening are substantially complete, but final acceptance is still blocked by stale documentation and regression reporting.

Do not start Milestone 10.

---

## Current review decision

```text
MILESTONE_9A_CODE_FIXES: PASS
MILESTONE_9A_STRONG_NUMERIC_TESTS: PASS
MILESTONE_9_REPORT_SYNC: FAIL
REVIEW_PACKAGE_SYNC: FAIL
MILESTONE_9_FINAL_ACCEPTANCE: HOLD
READY_FOR_MILESTONE_10: NO
```

---

## What passed in 9A

The following 9A items are accepted:

- `signal_density` now counts emitted plus received signal totals.
- Tests assert nonzero extraction load.
- Tests assert nonzero signal-field perturbation.
- Tests assert nonzero resource pressure.
- Tests assert bounded storage for `PressureAnalyzer`.
- Dense-vs-sparse test now uses strict `>` comparison.

Do not rework runtime code unless a minimal documentation-related correction is unavoidable.

---

## Blocking issue 1 — `docs/milestone_9_report.md` is stale

The report still shows only the old M9 command set and old results:

```text
182 passed in 14.31s
Total coverage: 83.75%
```

It also lists only the M9 demo commands instead of full M1–M9 regression.

Update `docs/milestone_9_report.md` to reflect the actual M9A state:

```text
186 passed in 16.09s
Coverage: 83.30%
```

Use the exact coverage table from your local run if it differs slightly, but the reported total must match the actual current run.

---

## Blocking issue 2 — full M1–M9 regression reporting missing

Update `docs/milestone_9_report.md` so the Commands Run section includes the full verification command set:

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

The report must also include numeric summaries for each regression item, not only commands:

- M1 event count and active count
- M2 event count and movement-block count
- M3 signal emission summary
- M4 correlation summary
- M5 adaptive summary
- M5 comparison summary
- M6 fabrication summary
- M7 capsule summary and capsule comparison
- M8 telemetry/reconciliation/lineage-drift summary
- M9 pressure output

Use exact current outputs from your run.

---

## Blocking issue 3 — report wording cleanup

Replace the current `What Was Deliberately Excluded` section in `docs/milestone_9_report.md` with a neutral machine-native section that avoids repeating forbidden/social terms.

Use wording like:

```markdown
## Scope Boundary

- Signal patterns are treated only as numeric field events.
- Pressure analysis is observational and numeric only.
- Unit state is not modified by pressure summaries.
- Runtime metrics remain limited to resource, movement, signal-field, component, and density measurements.
```

Do not explicitly list forbidden terms in the committed report.

Also update the next milestone wording to avoid `interpretation layer`. Suggested wording:

```text
Milestone 10: Signal Pattern Field Dynamics — cross-tick pattern frequency analysis, temporal signal-density clustering, signal-gradient mapping, pattern-observation correlation scoring, and non-semantic field dynamics summaries.
```

Do not implement Milestone 10.

---

## Blocking issue 4 — `docs/review_package.md` is stale

The review package currently still has an old title and old final verification values from Milestone 7:

```text
# Milestone 7 Final Review Package
165 passed in 11.01s
Total coverage: 84.30%
```

Update `docs/review_package.md` to be current through Milestone 9A or 9B:

- Retitle it to something like `# Milestone 9 Final Review Package`.
- Include commit hashes through the M9B documentation commit.
- Update final test result to current value, expected from 9A: `186 passed in 16.09s` unless your rerun differs.
- Update final coverage to current value, expected from 9A: `83.30%` unless your rerun differs.
- Include full M1–M9 command set or concise reference to the M9 report command set.
- Include M8 and M9 report paths.
- Include M8 telemetry/reconciliation summary.
- Include M9 pressure summary.
- Keep clean working tree status current.

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
```

Also run a targeted wording check:

```bash
grep -R "conflict\|cooperation\|competition\|alliance\|enemy\|friend\|trust\|deception\|negotiation\|strategy\|social" machine_sim configs docs/milestone_9_report.md docs/review_package.md || true
```

Remove any matches introduced by M9/M9A/M9B docs or runtime code.

---

## Commit and handoff requirements

Commit all changes and push to `feature/milestone-1`.

Final response must include:

```text
MILESTONE_9B_STATUS: PASS or PARTIAL_PASS
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
Documentation updates:
Clean working tree:
```

Do not mark PASS unless documentation is actually updated and pushed.

Do not start Milestone 10.

---

## Acceptance criteria

```text
M9B_MILESTONE_9_REPORT_SYNC: PASS
M9B_REVIEW_PACKAGE_SYNC: PASS
FULL_M1_M9_REGRESSION_REPORTED: PASS
CURRENT_TEST_RESULTS_REPORTED: PASS
CURRENT_COVERAGE_REPORTED: PASS
M9_DOC_FORBIDDEN_WORDING_REMOVED: PASS
M9_NEXT_MILESTONE_WORDING_MACHINE_NATIVE: PASS
TESTS_AND_COVERAGE: PASS
GUARDRAILS: PASS
CLEAN_WORKTREE_AND_PUSHED_REMOTE: PASS
```
