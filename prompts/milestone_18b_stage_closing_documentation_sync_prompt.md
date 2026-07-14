# After Silicon — MiMo Milestone 18B Stage-Closing Documentation Sync Prompt

## Repository and branch

Repository: `https://github.com/NoObIe-97/machine_sim.git`

Branch: `feature/milestone-1`

Start from the current Milestone 18A remote head:

```text
2f3464d2d0bf444c93d775d63384864e65e4c08b
```

Milestone 18 runtime implementation and M18A judge hardening are technically accepted. Final M18 acceptance is blocked only by documentation/stage-closing inconsistencies.

Do not modify runtime code. Do not modify tests. Do not modify configs. Do not start Milestone 19.

Before final handoff, invoke and satisfy:

```text
prompts/skills/stage_closing_chores.md
```

---

## Current review decision

```text
M18_NEURAL_VARIANT_SWEEP: PASS
M18_CONFIGURABLE_HIDDEN_SIZE_AND_PLASTICITY_RATE: PASS
M18_PER_VARIANT_ARTIFACTS: PASS
M18_SIMILARITY_MATRIX: PASS
M18_PARAMETER_SENSITIVITY_SUMMARY: PASS
M18_RUNTIME_SUMMARY_STRICTNESS: PASS
M18_REGRESSION_JUDGES_REPORTED: PASS
M18_INDEPENDENT_JUDGE: PASS
M18_TESTS_ASSERT_RUNTIME_SUMMARY_FAILURES: PASS
MILESTONE_18_REPORT_CURRENT: FAIL_STALE_TEST_COUNT
REVIEW_PACKAGE_CURRENT: FAIL_STALE_TEST_COUNT_AND_WRONG_M18A_COMMIT
STAGE_CLOSING_CHORES_SATISFIED: FAIL
MILESTONE_18_FINAL_ACCEPTANCE: HOLD
READY_FOR_MILESTONE_19: NO
```

---

## Blocking issue 1 — review package lists the wrong M18A final commit

Current final remote head is:

```text
2f3464d2d0bf444c93d775d63384864e65e4c08b
```

But `docs/review_package.md` currently lists:

```text
`7df6e23` — Milestone 18A variant runtime judge and stage-closing
```

Required fix:

- Replace the `7df6e23` M18A entry with the actual final commit hash:

```text
`2f3464d` — Milestone 18A variant runtime judge and stage-closing
```

or, preferably, the full hash:

```text
`2f3464d2d0bf444c93d775d63384864e65e4c08b` — Milestone 18A variant runtime judge and stage-closing
```

If there was an intermediate local commit named `7df6e23`, do not list it as the final stage commit unless it exists on the remote branch and is part of the final accepted lineage. The current final remote hash must be listed.

---

## Blocking issue 2 — test count is stale in report and review package

The handoff reports:

```text
390/390 tests pass
```

But both `docs/milestone_18_report.md` and `docs/review_package.md` still say:

```text
385 passed
```

Required fix:

- Update `docs/milestone_18_report.md` Tests and Coverage block to the actual final values.
- Update `docs/review_package.md` Test Results and demo summary to the actual final values.
- If coverage was not rerun after the 5 new M18A tests, rerun coverage and use the fresh coverage value.
- If coverage was rerun and remains `80.02%`, keep `80.02%`; otherwise use the fresh value.
- Do not leave mismatched values between report and review package.

Expected if the handoff values are still current:

```text
390 passed
Coverage: 80.02%
```

But use the actual command output if rerun values differ.

---

## Required documentation updates

Update only:

```text
docs/milestone_18_report.md
docs/review_package.md
```

Required final state:

```text
M18A_FINAL_REMOTE_HASH_LISTED: yes, 2f3464d... or full hash
M18_REPORT_TEST_COUNT_CURRENT: yes
M18_REPORT_COVERAGE_CURRENT: yes
REVIEW_PACKAGE_TEST_COUNT_CURRENT: yes
REVIEW_PACKAGE_COVERAGE_CURRENT: yes
NO_PENDING_OR_STALE_STAGE_VALUES: yes
```

Do not edit runtime code, tests, configs, artifacts, or judges unless a verification command exposes a real breakage.

---

## Verification commands

At minimum run:

```bash
python -m machine_sim.cli.main check
```

If possible, also rerun:

```bash
python -m pytest machine_sim/tests/ -v
python -m pytest machine_sim/tests/ --cov=machine_sim --cov-report=term-missing
python -m machine_sim.verification.milestone_18_judge output/demo_m18
python -m machine_sim.verification.milestone_17_judge output/demo_m17
python -m machine_sim.verification.milestone_14_judge output/demo_m14
python -m machine_sim.verification.milestone_15_judge output/demo_m15
python -m machine_sim.verification.milestone_16_judge output/demo_m16
```

The final report/review package must list the commands actually run.

---

## Stage-closing evidence required

Final handoff must include:

```text
STAGE_CLOSING_SKILL_INVOKED: yes
MILESTONE_18_REPORT_CURRENT: yes
REVIEW_PACKAGE_CURRENT: yes
M18_IMPLEMENTATION_COMMIT_LISTED: yes
M18A_FINAL_COMMIT_LISTED: yes (2f3464d...)
M18_REPORT_TEST_COUNT_CURRENT: yes
M18_REPORT_COVERAGE_CURRENT: yes
REVIEW_PACKAGE_TEST_COUNT_CURRENT: yes
REVIEW_PACKAGE_COVERAGE_CURRENT: yes
M18_JUDGE_STATUS: PASS
M18_RUNTIME_SUMMARY_STRICT: yes
M14_M15_M16_M17_REGRESSION_JUDGES_STILL_PASS: yes
NO_STALE_DOC_VALUES_FOUND: yes
CLEAN_WORKTREE_AFTER_PUSH: yes
FINAL_REMOTE_HASH_REPORTED: yes
MILESTONE_18_STATUS: ACCEPTED or HOLD
READY_FOR_MILESTONE_19: YES or NO
```

Do not claim ACCEPTED unless all documentation and stage-closing values are current and consistent.

---

## Acceptance criteria

```text
M18_REPORT_CURRENT: PASS
REVIEW_PACKAGE_CURRENT: PASS
M18A_FINAL_REMOTE_HASH_LISTED: PASS
TEST_COUNT_AND_COVERAGE_SYNCHRONIZED: PASS
NO_STALE_DOC_VALUES: PASS
STAGE_CLOSING_CHORES_SATISFIED: PASS
CLEAN_WORKTREE_AND_PUSHED_REMOTE: PASS
```
