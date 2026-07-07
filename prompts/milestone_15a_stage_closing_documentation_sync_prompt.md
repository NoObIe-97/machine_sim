# After Silicon — MiMo Milestone 15A Stage-Closing Documentation Sync Prompt

## Repository and branch

Repository: `https://github.com/NoObIe-97/machine_sim.git`

Branch: `feature/milestone-1`

Start from the current Milestone 15 remote head:

```text
da47146
```

Milestone 15 runtime, multi-generation adaptive trace analyzer, 30,000-tick demo, M14 regression judge, M15 judge, artifacts, tests, and coverage are technically accepted. Final Milestone 15 acceptance is blocked only by documentation stage-closing details.

Do not modify runtime code. Do not modify tests. Do not start Milestone 16.

Before final handoff, invoke and satisfy:

```text
prompts/skills/stage_closing_chores.md
```

---

## Current review decision

```text
M15_MULTI_GENERATION_LONG_RUN_ENVIRONMENT: PASS
M15_GENERATION_INDEXED_ADAPTIVE_TRACE: PASS
M15_TRANSFER_COUNT_AND_GENERATION_SPAN: PASS
M15_ADAPTIVE_TRAJECTORY_COMPARISON: PASS
M15_TRAJECTORY_COMPRESSION_SUMMARY: PASS
M15_REFERENCE_COMPARISON: PASS
M15_INDEPENDENT_JUDGE_PASS_NO_SKIP: PASS
M15_REQUIRED_ARTIFACTS_WRITTEN: PASS
M15_TESTS_ASSERT_REAL_RUNTIME_BEHAVIOR: PASS
M14_REGRESSION_JUDGE_STILL_PASS: PASS
TESTS_AND_COVERAGE: PASS
GUARDRAILS: PASS
FULL_M1_M15_REGRESSION_REPORTED: PASS
MILESTONE_15_REPORT_CURRENT: FAIL_FORBIDDEN_DOC_WORDING
REVIEW_PACKAGE_CURRENT: FAIL_CURRENT_STAGE_COMMIT_NOT_LISTED
STAGE_CLOSING_CHORES_SATISFIED: FAIL
MILESTONE_15_FINAL_ACCEPTANCE: HOLD
READY_FOR_MILESTONE_16: NO
```

---

## Required change 1 — review package current stage commit

Update only:

```text
docs/review_package.md
```

The current review package lists milestones through:

```text
bb875d9 — Milestone 14A stage-closing documentation and final remote state
```

but it does not list the M15 implementation/final remote commit:

```text
da47146
```

Add:

```text
da47146 — Milestone 15 multi-generation adaptive trace evolution
```

Keep all current review-package sections intact:

- title: `# Milestone 15 Final Review Package`
- final tests: `284 passed in 27.84s` or exact current rerun value
- final coverage: `85.46%` or exact current rerun value
- M14 judge: `12/12 PASS, 0 SKIP`
- M15 judge: `12/12 PASS, 0 SKIP`
- full M1–M15 regression summary
- M15 demo output
- all 9 M15 artifact paths
- report paths
- clean working tree status

---

## Required change 2 — remove forbidden wording from M15 report

Update only:

```text
docs/milestone_15_report.md
```

The report currently includes this known-limitation wording:

```text
Population capacity (40) is high to enable deep generation chains — constrained environments would show fewer generations
```

This violates the machine-native wording boundary because `population` is forbidden for new M15 documentation.

Replace it with machine-native wording such as:

```text
Unit capacity (40) is high to enable deeper generation-indexed paths — constrained capacity settings would show fewer generation-indexed transfer records
```

Search the modified docs for forbidden wording before final handoff, especially:

```text
population
evolution
mutation
inheritance
offspring
parent
child
society
community
communication
message
language
meaning
knowledge
learning
teaching
strategy
trust
cooperation
competition
conflict
agreement
consensus
species
fitness
```

Do not alter accepted runtime terminology unless a check fails.

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
python -m machine_sim.verification.milestone_15_judge output/demo_m15
```

After committing, reopen or inspect both documentation files and confirm:

```text
MILESTONE_REPORT_TITLE_CURRENT: yes
MILESTONE_REPORT_TESTS_CURRENT: yes
MILESTONE_REPORT_COVERAGE_CURRENT: yes
MILESTONE_REPORT_FULL_REGRESSION_CURRENT: yes
MILESTONE_REPORT_FULL_COMMAND_SET_PRESENT: yes
MILESTONE_REPORT_FORBIDDEN_WORDING_REMOVED: yes
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
MILESTONE_REPORT_FORBIDDEN_WORDING_REMOVED: yes
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
M15_GOAL_SPEC_SATISFIED: yes
M15_INDEPENDENT_JUDGE_STATUS: PASS
M15_NO_SKIPPED_REQUIRED_JUDGE_CHECKS: yes
M15_LONG_RUN_TICKS_GE_30000: yes
M15_TRANSFER_COUNT_GE_5: yes
M15_GENERATION_SPAN_GE_3: yes
M15_SIGNAL_OBSERVATIONS_NONZERO: yes
M15_REFERENCE_COMPARISON_NONTRIVIAL: yes
```

Do not claim PASS or ACCEPTED unless all are true.

---

## Final handoff format

```text
MILESTONE_15A_STATUS: PASS or PARTIAL_PASS
MILESTONE_15_STATUS: ACCEPTED or HOLD
READY_FOR_MILESTONE_16: YES or NO
Branch:
Starting commit hash:
Documentation commit hash:
Final remote commit hash:
Files changed:
Tests/checks:
Guardrail result:
M15 judge result:
Documentation updates:
Stage closing chores result:
Clean working tree:
```

---

## Acceptance criteria

```text
M15A_REVIEW_PACKAGE_CURRENT_STAGE_COMMIT_LISTED: PASS
M15A_MILESTONE_REPORT_FORBIDDEN_WORDING_REMOVED: PASS
MILESTONE_15_REPORT_CURRENT: PASS
REVIEW_PACKAGE_CURRENT: PASS
M15_GOAL_SPEC_SATISFIED: PASS
M15_INDEPENDENT_JUDGE_STATUS: PASS
STAGE_CLOSING_CHORES_SATISFIED: PASS
GUARDRAILS: PASS
CLEAN_WORKTREE_AND_PUSHED_REMOTE: PASS
```
