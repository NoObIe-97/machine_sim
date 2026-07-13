# After Silicon — MiMo Milestone 17C Stage-Closing Documentation Sync Prompt

## Repository and branch

Repository: `https://github.com/NoObIe-97/machine_sim.git`

Branch: `feature/milestone-1`

Start from the current Milestone 17B remote head:

```text
d6845a46845d33de815737e479bd64d0e0f48f7c
```

Milestone 17 runtime, M17A deterministic neural seeding, and M17B strict judge hardening are technically accepted. Final M17 acceptance is blocked only by documentation/stage-closing issues.

Do not modify runtime code. Do not modify tests. Do not start Milestone 18.

Before final handoff, invoke and satisfy:

```text
prompts/skills/stage_closing_chores.md
```

---

## Current review decision

```text
M17_INTERNAL_NEURAL_PROCESSING_UNIT: PASS
M17_STABLE_SEED_HELPER: PASS
M17_HASHLESS_NEURAL_INITIALIZATION_AND_SELECTION: PASS
M17_HASHLESS_NEURAL_FEEDBACK_AND_TRANSFER: PASS
M17_FABRICATE_OUTPUT_SEMANTICS_CLARIFIED: PASS_WITH_LIMITATION
M17_LOCAL_PLASTICITY_UPDATE: PASS
M17_SUCCESSOR_NEURAL_STATE_TRANSFER: PASS
M17_NEURAL_VS_SCALAR_BASELINE_COMPARISON: PASS
M17_STRICT_JUDGE_EXACT_PASS_ONLY: PASS
M17_STRICT_RUN_TICKS_CHECK: PASS
M17_STRICT_REGRESSION_EVIDENCE_CHECK: PASS
M17_REQUIRED_ARTIFACTS_WRITTEN: PASS
M17_TESTS_ASSERT_REAL_NEURAL_BEHAVIOR: PASS
M17_INDEPENDENT_JUDGE_PASS_NO_SKIP: PASS
M14_M15_M16_REGRESSION_JUDGES_STILL_PASS: PASS
TESTS_AND_COVERAGE: PASS_REPORTED_BUT_DOCS_NOT_SYNCED
GUARDRAILS: PASS
MILESTONE_17_REPORT_CURRENT: PARTIAL_PASS_NEEDS_DOC_SYNC
REVIEW_PACKAGE_CURRENT: FAIL_PENDING_M17B_AND_COVERAGE
STAGE_CLOSING_CHORES_SATISFIED: FAIL
MILESTONE_17_FINAL_ACCEPTANCE: HOLD
READY_FOR_MILESTONE_18: NO
```

---

## Required change 1 — review package must list current M17B commit

Update only:

```text
docs/review_package.md
```

Current review package contains:

```text
(pending) — Milestone 17B judge strictness and stage closing
```

Replace it with:

```text
d6845a4 — Milestone 17B judge strictness and stage closing
```

If using the full hash is preferred, use:

```text
d6845a46845d33de815737e479bd64d0e0f48f7c — Milestone 17B judge strictness and stage closing
```

---

## Required change 2 — review package coverage must be current

The review package currently says:

```text
Coverage (Final)
To be updated after coverage run.
```

and later:

```text
Coverage: pending rerun, 359 tests
```

Replace with the current verified coverage from the handoff or rerun value:

```text
82.83%
```

If rerun produces a different value, use the rerun value and update all mentions consistently.

---

## Required change 3 — M17 report coverage must be current

Update:

```text
docs/milestone_17_report.md
```

The report currently lists tests but not final coverage in the `Tests and Coverage` block. Add the current coverage:

```text
359 passed in 58.36s
Coverage: 82.83%
```

If rerun produces different values, use the rerun values consistently.

---

## Required change 4 — clean malformed strictness sentence

In `docs/milestone_17_report.md`, the M17B strictness sentence currently reads awkwardly:

```text
Overall `M17_JUDGE_STATUS` is `PASS` only when **every required check is exactly the string `PARTIAL` is never produced; the zero-transfer case now fails outright**
```

Replace with clear wording such as:

```text
Overall `M17_JUDGE_STATUS` is `PASS` only when every required check is exactly `PASS`; any non-PASS value fails the judge. `PARTIAL` is never produced, and the zero-transfer case now fails outright.
```

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
python -m machine_sim.verification.milestone_17_judge output/demo_m17
```

After committing, reopen or inspect both documentation files and confirm:

```text
MILESTONE_REPORT_TITLE_CURRENT: yes
MILESTONE_REPORT_TESTS_CURRENT: yes
MILESTONE_REPORT_COVERAGE_CURRENT: yes
MILESTONE_REPORT_FULL_REGRESSION_CURRENT: yes
MILESTONE_REPORT_FULL_COMMAND_SET_PRESENT: yes
MILESTONE_REPORT_STRICTNESS_WORDING_CLEAN: yes
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
MILESTONE_REPORT_STRICTNESS_WORDING_CLEAN: yes
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
M17_GOAL_SPEC_SATISFIED: yes
M17_INTERNAL_NEURAL_PROCESSING_UNIT_PRESENT: yes
M17_NEURAL_CONTROLLER_DRIVES_NORMAL_ACTION_SELECTION: yes
M17_PLASTICITY_UPDATE_NONZERO: yes
M17_LOCAL_INPUT_ONLY: yes
M17_NEURAL_VS_SCALAR_NONTRIVIAL_DIFFERENCE: yes
M17_SUCCESSOR_NEURAL_TRANSFER_RECORDED: yes
M17_INDEPENDENT_JUDGE_STATUS: PASS
M17_NO_SKIPPED_REQUIRED_JUDGE_CHECKS: yes
M14_M15_M16_REGRESSION_JUDGES_STILL_PASS: yes
```

Do not claim PASS or ACCEPTED unless all are true.

---

## Final handoff format

```text
MILESTONE_17C_STATUS: PASS or PARTIAL_PASS
MILESTONE_17_STATUS: ACCEPTED or HOLD
READY_FOR_MILESTONE_18: YES or NO
Branch:
Starting commit hash:
Documentation commit hash:
Final remote commit hash:
Files changed:
Tests/checks:
Coverage:
Guardrail result:
M14/M15/M16 judge results:
M17 judge result:
Documentation updates:
Stage closing chores result:
Clean working tree:
```

---

## Acceptance criteria

```text
M17C_REVIEW_PACKAGE_CURRENT_STAGE_COMMIT_LISTED: PASS
M17C_REVIEW_PACKAGE_COVERAGE_CURRENT: PASS
M17C_MILESTONE_REPORT_COVERAGE_CURRENT: PASS
M17C_MILESTONE_REPORT_STRICTNESS_WORDING_CLEAN: PASS
MILESTONE_17_REPORT_CURRENT: PASS
REVIEW_PACKAGE_CURRENT: PASS
M17_GOAL_SPEC_SATISFIED: PASS
M17_INDEPENDENT_JUDGE_STATUS: PASS
M14_M15_M16_REGRESSION_JUDGES_STILL_PASS: PASS
STAGE_CLOSING_CHORES_SATISFIED: PASS
GUARDRAILS: PASS
CLEAN_WORKTREE_AND_PUSHED_REMOTE: PASS
```
