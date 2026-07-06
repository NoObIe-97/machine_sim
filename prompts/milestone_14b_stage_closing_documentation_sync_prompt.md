# After Silicon — MiMo Milestone 14B Stage-Closing Documentation Sync Prompt

## Repository and branch

Repository: `https://github.com/NoObIe-97/machine_sim.git`

Branch: `feature/milestone-1`

Start from the current Milestone 14A remote head:

```text
bb875d9
```

Milestone 14A runtime, strengthened judge, large-field demo, signal observation, descendant transfer, and artifacts are accepted. Final Milestone 14 acceptance is blocked only by documentation stage-closing details.

Do not modify runtime code. Do not modify tests. Do not start Milestone 15.

Before final handoff, invoke and satisfy:

```text
prompts/skills/stage_closing_chores.md
```

---

## Current review decision

```text
M14A_LARGE_SPARSE_LONG_RUN_ENVIRONMENT: PASS
M14A_ACTION_SELECTION_FULLY_USES_ADAPTIVE_STATE: PASS
M14A_LOCAL_FEEDBACK_TRACE_AND_UPDATE: PASS
M14A_SIGNAL_OBSERVATION_AND_ADAPTATION: PASS
M14A_DESCENDANT_ADAPTIVE_STATE_TRANSFER: PASS
M14A_STATIC_VS_ADAPTIVE_NONTRIVIAL_COMPARISON: PASS
M14A_STRONG_INDEPENDENT_JUDGE: PASS
M14A_JUDGE_PASS_NO_SKIP: PASS
M14A_LONG_RUN_ARTIFACTS_COMPLETE: PASS
M14A_TESTS_ASSERT_REAL_RUNTIME_BEHAVIOR: PASS
TESTS_AND_COVERAGE: PASS
GUARDRAILS: PASS
FULL_M1_M14_REGRESSION_REPORTED: PASS_SUMMARY_PRESENT_BUT_COMMAND_LIST_INCOMPLETE
MILESTONE_14_REPORT_CURRENT: FAIL_COMMAND_LIST_INCOMPLETE
REVIEW_PACKAGE_CURRENT: FAIL_FINAL_REMOTE_HASH_NOT_LISTED
STAGE_CLOSING_CHORES_SATISFIED: FAIL
MILESTONE_14_FINAL_ACCEPTANCE: HOLD
READY_FOR_MILESTONE_15: NO
```

---

## Required change 1 — add full command list to M14 report

Update only:

```text
docs/milestone_14_report.md
```

The report must include the actual verification command list, not only `python -m pytest`.

Add a `## Commands Run` section or equivalent containing at least:

```bash
python -m pytest machine_sim/tests/ -v
python -m pytest machine_sim/tests/ --cov=machine_sim --cov-report=term-missing
python -m machine_sim.cli.main check
python -m machine_sim.cli.main run -c configs/milestone_14_long_run_adaptation.toml -t 20000 -s 42 -o output/demo_m14
python -m machine_sim.cli.main inspect output/demo_m14
python -m machine_sim.verification.milestone_14_judge output/demo_m14
```

Also include the full M1-M14 regression command set used for the report. If using a compact block, ensure it contains actual commands for M1 through M14, not only a prose statement.

Keep current M14A values unless rerun results differ:

```text
267 passed in 32.81s
Total coverage: 87.06%
M14 judge: 12/12 PASS, 0 SKIP
```

---

## Required change 2 — add final remote hash to review package

Update only:

```text
docs/review_package.md
```

The current review package lists:

```text
fa8fbb8 — Milestone 14A goal-spec hardening
```

but the final remote hash reported by the handoff is:

```text
bb875d9
```

Add an entry such as:

```text
bb875d9 — Milestone 14A stage-closing documentation and final remote state
```

If `bb875d9` is only a docs/stage-closing commit, describe it accordingly. If it contains other changes, describe accurately after checking the commit.

Keep the existing current sections intact:

- title: `# Milestone 14A Final Review Package`
- final tests: `267 passed in 32.81s` or exact current rerun value
- final coverage: `87.06%` or exact current rerun value
- M14 judge: `12/12 PASS, 0 SKIP`
- M1-M14 summary
- M14A output summary
- all 9 artifact paths
- report paths
- clean working tree status

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
python -m machine_sim.verification.milestone_14_judge output/demo_m14
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
CURRENT_FINAL_REMOTE_HASH_LISTED: yes
CURRENT_ARTIFACT_PATHS_REPORTED: yes
NEXT_MILESTONE_WORDING_MACHINE_NATIVE: yes
NO_STALE_DOC_VALUES_FOUND: yes
CLEAN_WORKTREE_AFTER_PUSH: yes
FINAL_REMOTE_HASH_REPORTED: yes
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
CURRENT_FINAL_REMOTE_HASH_LISTED: yes
CURRENT_ARTIFACT_PATHS_REPORTED: yes
NEXT_MILESTONE_WORDING_MACHINE_NATIVE: yes
NO_STALE_DOC_VALUES_FOUND: yes
CLEAN_WORKTREE_AFTER_PUSH: yes
FINAL_REMOTE_HASH_REPORTED: yes
M14_GOAL_SPEC_SATISFIED: yes
M14_INDEPENDENT_JUDGE_STATUS: PASS
M14_NO_SKIPPED_REQUIRED_JUDGE_CHECKS: yes
M14_LONG_RUN_TICKS_GE_20000: yes
M14_LARGE_SPARSE_FIELD: yes
M14_SIGNAL_OBSERVATIONS_NONZERO: yes
M14_DESCENDANT_TRANSFER_NONZERO: yes
M14_STATIC_VS_ADAPTIVE_NONTRIVIAL_DELTA: yes
```

Do not claim PASS or ACCEPTED unless all are true.

---

## Final handoff format

```text
MILESTONE_14B_STATUS: PASS or PARTIAL_PASS
MILESTONE_14_STATUS: ACCEPTED or HOLD
READY_FOR_MILESTONE_15: YES or NO
Branch:
Starting commit hash:
Documentation commit hash:
Final remote commit hash:
Files changed:
Tests/checks:
Guardrail result:
M14 judge result:
Documentation updates:
Stage closing chores result:
Clean working tree:
```

---

## Acceptance criteria

```text
M14B_MILESTONE_REPORT_FULL_COMMAND_SET_PRESENT: PASS
M14B_REVIEW_PACKAGE_FINAL_REMOTE_HASH_LISTED: PASS
MILESTONE_14_REPORT_CURRENT: PASS
REVIEW_PACKAGE_CURRENT: PASS
M14_GOAL_SPEC_SATISFIED: PASS
M14_INDEPENDENT_JUDGE_STATUS: PASS
STAGE_CLOSING_CHORES_SATISFIED: PASS
GUARDRAILS: PASS
CLEAN_WORKTREE_AND_PUSHED_REMOTE: PASS
```
