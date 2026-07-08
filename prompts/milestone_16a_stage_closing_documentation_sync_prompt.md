# After Silicon — MiMo Milestone 16A Stage-Closing Documentation Sync Prompt

## Repository and branch

Repository: `https://github.com/NoObIe-97/machine_sim.git`

Branch: `feature/milestone-1`

Start from the current Milestone 16 remote head:

```text
5edc31e
```

Milestone 16 runtime, trajectory compression analyzer, compression CLI, M15 regression judge, M16 judge, artifacts, tests, and coverage are technically accepted. Final Milestone 16 acceptance is blocked only by documentation stage-closing details.

Do not modify runtime code. Do not modify tests. Do not start Milestone 17.

Before final handoff, invoke and satisfy:

```text
prompts/skills/stage_closing_chores.md
```

---

## Current review decision

```text
M16_TRAJECTORY_COMPRESSION_ANALYZER: PASS
M16_BOUNDED_COMPRESSED_SEGMENTS: PASS
M16_REPLAY_METRICS: PASS
M16_CROSS_TRAJECTORY_SIMILARITY: PASS
M16_COMPACT_TRAJECTORY_CAPSULE: PASS
M16_COMPRESSION_RATIO_REPORTED: PASS
M16_INDEPENDENT_JUDGE_PASS_NO_SKIP: PASS
M16_REQUIRED_ARTIFACTS_WRITTEN: PASS
M16_TESTS_ASSERT_REAL_ANALYSIS_BEHAVIOR: PASS
M15_REGRESSION_JUDGE_STILL_PASS: PASS
TESTS_AND_COVERAGE: PASS
GUARDRAILS: PASS
FULL_M1_M16_REGRESSION_REPORTED: PASS_SUMMARY_PRESENT_BUT_COMMAND_LIST_NEEDS_REPRODUCIBILITY_PATCH
MILESTONE_16_REPORT_CURRENT: FAIL_COMMAND_LIST_USES_UNTRACKED_HELPER
REVIEW_PACKAGE_CURRENT: FAIL_CURRENT_STAGE_COMMIT_PENDING
STAGE_CLOSING_CHORES_SATISFIED: FAIL
MILESTONE_16_FINAL_ACCEPTANCE: HOLD
READY_FOR_MILESTONE_17: NO
```

---

## Required change 1 — replace `<pending>` commit entry in review package

Update only:

```text
docs/review_package.md
```

The current review package contains:

```text
<pending> — Milestone 16 adaptive trajectory compression and offline analysis
```

Replace it with:

```text
5edc31e — Milestone 16 adaptive trajectory compression and offline analysis
```

Keep all current review-package sections intact:

- title: `# Milestone 16 Final Review Package`
- final tests: `301 passed in 38.16s` or exact current rerun value
- final coverage: `82.77%` or exact current rerun value
- M14/M15/M16 judge results
- full M1–M16 regression summary
- M16 demo output
- all 8 M16 artifact paths
- report paths
- clean working tree status

---

## Required change 2 — make M16 report command list reproducible

Update only:

```text
docs/milestone_16_report.md
```

The current command list includes:

```bash
python _run_m16.py
```

but the handoff says `_run_m16.py` is untracked. A stage-closing report should not depend on an untracked helper unless the helper is committed or the command is replaced with reproducible committed CLI commands.

Preferred fix: replace `python _run_m16.py` with the actual committed CLI commands used to generate the long-run demo and source artifacts. At minimum the command block should include:

```bash
python -m pytest machine_sim/tests/ -v
python -m pytest machine_sim/tests/ --cov=machine_sim --cov-report=term-missing
python -m machine_sim.cli.main check
python -m machine_sim.cli.main run -c configs/milestone_16_adaptive_trajectory_compression.toml -t 30000 -s 42 -o output/demo_m16
python -m machine_sim.cli.main inspect output/demo_m16
python -m machine_sim.cli.main compress output/demo_m16 --max-segments 32
python -m machine_sim.verification.milestone_16_judge output/demo_m16
python -m machine_sim.cli.main run -c configs/milestone_15_multi_generation_adaptive_trace.toml -t 30000 -s 42 -o output/demo_m15
python -m machine_sim.verification.milestone_15_judge output/demo_m15
```

If the current CLI cannot generate `output/demo_m16` without the untracked helper, report `PARTIAL_PASS` and explain the exact blocker instead of claiming final acceptance. Do not commit `_run_m16.py` unless it is made production-quality and documented; this prompt is intended as documentation-only unless a verification command exposes a real breakage.

Also replace this known limitation wording if present:

```text
not semantic
```

with machine-native wording such as:

```text
not structural-metric equivalent
```

This avoids reintroducing terminology outside the project boundary.

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
python -m machine_sim.verification.milestone_16_judge output/demo_m16
```

After committing, reopen or inspect both documentation files and confirm:

```text
MILESTONE_REPORT_TITLE_CURRENT: yes
MILESTONE_REPORT_TESTS_CURRENT: yes
MILESTONE_REPORT_COVERAGE_CURRENT: yes
MILESTONE_REPORT_FULL_REGRESSION_CURRENT: yes
MILESTONE_REPORT_FULL_COMMAND_SET_PRESENT: yes
MILESTONE_REPORT_COMMANDS_REPRODUCIBLE_FROM_COMMITTED_FILES: yes
MILESTONE_REPORT_BOUNDARY_WORDING_CLEAN: yes
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
MILESTONE_REPORT_COMMANDS_REPRODUCIBLE_FROM_COMMITTED_FILES: yes
MILESTONE_REPORT_BOUNDARY_WORDING_CLEAN: yes
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
M16_GOAL_SPEC_SATISFIED: yes
M16_INDEPENDENT_JUDGE_STATUS: PASS
M16_NO_SKIPPED_REQUIRED_JUDGE_CHECKS: yes
M16_LONG_RUN_TICKS_GE_30000: yes
M16_COMPRESSION_SEGMENTS_BOUNDED: yes
M16_REPLAY_METRICS_PRESENT: yes
M16_CROSS_TRAJECTORY_COMPARISON_NONTRIVIAL: yes
M15_REGRESSION_JUDGE_STILL_PASS: yes
```

Do not claim PASS or ACCEPTED unless all are true.

---

## Final handoff format

```text
MILESTONE_16A_STATUS: PASS or PARTIAL_PASS
MILESTONE_16_STATUS: ACCEPTED or HOLD
READY_FOR_MILESTONE_17: YES or NO
Branch:
Starting commit hash:
Documentation commit hash:
Final remote commit hash:
Files changed:
Tests/checks:
Guardrail result:
M15 judge result:
M16 judge result:
Documentation updates:
Stage closing chores result:
Clean working tree:
```

---

## Acceptance criteria

```text
M16A_REVIEW_PACKAGE_CURRENT_STAGE_COMMIT_LISTED: PASS
M16A_MILESTONE_REPORT_REPRODUCIBLE_COMMANDS: PASS
M16A_MILESTONE_REPORT_BOUNDARY_WORDING_CLEAN: PASS
MILESTONE_16_REPORT_CURRENT: PASS
REVIEW_PACKAGE_CURRENT: PASS
M16_GOAL_SPEC_SATISFIED: PASS
M16_INDEPENDENT_JUDGE_STATUS: PASS
M15_REGRESSION_JUDGE_STILL_PASS: PASS
STAGE_CLOSING_CHORES_SATISFIED: PASS
GUARDRAILS: PASS
CLEAN_WORKTREE_AND_PUSHED_REMOTE: PASS
```
