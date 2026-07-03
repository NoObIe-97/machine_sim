# After Silicon — MiMo Milestone 12A Documentation Stage-Closing Sync Prompt

## Repository and branch

Repository: `https://github.com/NoObIe-97/machine_sim.git`

Branch: `feature/milestone-1`

Start from the current Milestone 12 remote head:

```text
a2854bd
```

Milestone 12 runtime, tests, artifact wiring, and report content are technically accepted. Final Milestone 12 acceptance is blocked only by documentation stage-closing details.

Do not modify runtime code. Do not start Milestone 13.

Before final handoff, invoke and satisfy the shared stage-closing skill:

```text
prompts/skills/stage_closing_chores.md
```

---

## Current review decision

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
FULL_M1_M12_REGRESSION_REPORTED: PASS_SUMMARY_PRESENT_BUT_COMMANDS_INCOMPLETE
MILESTONE_12_REPORT_CURRENT: FAIL_COMMAND_LIST_INCOMPLETE
REVIEW_PACKAGE_CURRENT: FAIL_ONE_MISSING_COMMIT_HASH
NEXT_MILESTONE_WORDING_MACHINE_NATIVE: PASS
MILESTONE_12_FINAL_ACCEPTANCE: HOLD
READY_FOR_MILESTONE_13: NO
```

---

## Required changes

Update only documentation:

```text
docs/milestone_12_report.md
docs/review_package.md
```

Do not modify runtime code, tests, configs, or artifacts unless a verification command exposes a real breakage.

---

## Required change 1 — expand M12 report command list

`docs/milestone_12_report.md` currently says only:

```text
Full test suite, coverage, guardrail check, and M1-M12 regression demos.
```

Replace that with the actual full M1–M12 verification command set.

Use this command block, updating exact output values if your rerun differs:

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

Keep the existing current M12 test/coverage values if you do not rerun, or update them if you rerun.

---

## Required change 2 — review package current stage commit

`docs/review_package.md` is otherwise current, but its commit history does not list the final M12 implementation commit.

Add:

```text
a2854bd — Milestone 12 trace drift and compression stability
```

Keep the existing current sections intact:

- title: `# Milestone 12 Final Review Package`
- final tests: `228 passed in 20.34s` or exact current rerun value
- final coverage: `81.85%` or exact current rerun value
- full M1–M12 regression summary
- M12 output summary
- artifact paths including `output/demo_m12/trace_drift.json`
- report paths including `docs/milestone_12_report.md`
- clean working tree status

A one-line commit-history append is acceptable for the review package because all other review-package sections are already current.

---

## Verification

At minimum, run:

```bash
python -m machine_sim.cli.main check
```

If time permits, rerun:

```bash
python -m pytest machine_sim/tests/ -v
python -m pytest machine_sim/tests/ --cov=machine_sim --cov-report=term-missing
```

After committing, reopen or inspect both documentation files and confirm:

```text
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
REPORT_PATHS_CURRENT: yes
NEXT_MILESTONE_WORDING_MACHINE_NATIVE: yes
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

If any value is `no`, report `PARTIAL_PASS` or `HOLD`.

---

## Commit and handoff requirements

Commit and push to `feature/milestone-1`.

Final response must include:

```text
MILESTONE_12A_STATUS: PASS or PARTIAL_PASS
MILESTONE_12_STATUS: ACCEPTED or HOLD
READY_FOR_MILESTONE_13: YES or NO
Branch:
Starting commit hash:
Documentation commit hash:
Final remote commit hash:
Files changed:
Tests/checks:
Guardrail result:
Stage closing chores result:
Documentation updates:
Clean working tree:
```

---

## Acceptance criteria

```text
M12A_MILESTONE_REPORT_FULL_COMMAND_SET_PRESENT: PASS
M12A_REVIEW_PACKAGE_CURRENT_STAGE_COMMIT_LISTED: PASS
MILESTONE_12_REPORT_CURRENT: PASS
REVIEW_PACKAGE_CURRENT: PASS
NEXT_MILESTONE_WORDING_MACHINE_NATIVE: PASS
STAGE_CLOSING_CHORES_SATISFIED: PASS
GUARDRAILS: PASS
CLEAN_WORKTREE_AND_PUSHED_REMOTE: PASS
```
