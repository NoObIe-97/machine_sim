# After Silicon — MiMo Milestone 10D Next-Milestone Wording Patch Prompt

## Repository and branch

Repository: `https://github.com/NoObIe-97/machine_sim.git`

Branch: `feature/milestone-1`

Start from the current Milestone 10C remote head:

```text
f0f2b2e
```

Milestone 10 runtime, tests, report synchronization, and review-package synchronization are otherwise accepted. Final Milestone 10 acceptance is blocked only by the next-milestone wording in `docs/milestone_10_report.md`.

Do not modify runtime code. Do not start Milestone 11.

Before final handoff, invoke and satisfy the updated shared stage-closing skill:

```text
prompts/skills/stage_closing_chores.md
```

---

## Current review decision

```text
M10_CORE_IMPLEMENTATION: PASS
M10A_SIGNAL_GRADIENT_EXPOSED_IN_SUMMARY: PASS
M10A_SIGNAL_GRADIENT_EXPOSED_IN_CLI_AND_ARTIFACT: PASS
M10B_STRONG_NUMERIC_TESTS: PASS
M10B_BOUNDED_STORAGE_TEST: PASS
M10C_MILESTONE_10_REPORT_CURRENT: PASS_WITH_ONE_WORDING_BLOCKER
M10C_REVIEW_PACKAGE_CURRENT: PASS
FULL_M1_M10_REGRESSION_REPORTED: PASS
CURRENT_TESTS_AND_COVERAGE_REPORTED: PASS
M10_DEMO_OUTPUT_WITH_GRADIENT_REPORTED: PASS
M10_ARTIFACT_PATH_REPORTED: PASS
NEXT_MILESTONE_WORDING_MACHINE_NATIVE: FAIL
MILESTONE_10_FINAL_ACCEPTANCE: HOLD
READY_FOR_MILESTONE_11: NO
```

---

## Required change

In `docs/milestone_10_report.md`, replace the current Next Recommended Milestone text:

```text
Milestone 11: Operational Memory Compression — bounded signal history compression, pattern摘要, cross-unit memory sharing, lineage memory inheritance.
```

with this exact machine-native wording:

```text
Milestone 11: Bounded Operational Trace Compression — compressed signal-field histories, telemetry-window reduction, capsule-compatible diagnostic summaries, lineage-indexed trace comparison, and bounded replay metrics.
```

Remove the old wording entirely, including `pattern摘要`, `memory sharing`, and `inheritance`.

---

## Review package update

Update `docs/review_package.md` only if needed to keep the commit list and final status current after the M10D documentation commit.

If you update the review package, do not weaken or remove the existing M1–M10 summary, current test/coverage values, artifacts, or report paths.

---

## Verification

At minimum, run:

```bash
python -m machine_sim.cli.main check
```

If time permits, rerun the current test and coverage commands as well:

```bash
python -m pytest machine_sim/tests/ -v
python -m pytest machine_sim/tests/ --cov=machine_sim --cov-report=term-missing
```

Run a targeted documentation freshness check confirming the old wording is gone:

```bash
grep -n "pattern摘要\|memory sharing\|inheritance" docs/milestone_10_report.md docs/review_package.md || true
grep -n "Bounded Operational Trace Compression" docs/milestone_10_report.md
```

---

## Stage-closing evidence required

Your final handoff must include:

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
MILESTONE_10D_STATUS: PASS or PARTIAL_PASS
MILESTONE_10_STATUS: ACCEPTED or HOLD
READY_FOR_MILESTONE_11: YES or NO
Branch:
Starting commit hash:
Implementation commit hash:
Final remote commit hash:
Files changed:
Tests/checks:
Guardrail result:
M10 demo output:
Artifact paths:
Stage closing chores result:
Documentation updates:
Clean working tree:
```

---

## Acceptance criteria

```text
M10D_NEXT_MILESTONE_WORDING_MACHINE_NATIVE: PASS
OLD_M11_WORDING_REMOVED: PASS
MILESTONE_10_REPORT_CURRENT: PASS
REVIEW_PACKAGE_CURRENT_IF_TOUCHED: PASS
STAGE_CLOSING_CHORES_SATISFIED: PASS
GUARDRAILS: PASS
CLEAN_WORKTREE_AND_PUSHED_REMOTE: PASS
```
