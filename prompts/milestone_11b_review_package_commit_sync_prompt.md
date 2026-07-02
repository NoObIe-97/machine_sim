# After Silicon — MiMo Milestone 11B Review-Package Commit Sync Prompt

## Repository and branch

Repository: `https://github.com/NoObIe-97/machine_sim.git`

Branch: `feature/milestone-1`

Start from the current Milestone 11A remote head:

```text
0be8000
```

Milestone 11 runtime, tests, M11 report, and review package contents are otherwise accepted. Final Milestone 11 acceptance is blocked only by one stage-closing detail: `docs/review_package.md` does not list the final M11A hardening commit hash.

Do not modify runtime code. Do not start Milestone 12.

Before final handoff, invoke and satisfy the shared stage-closing skill:

```text
prompts/skills/stage_closing_chores.md
```

---

## Current review decision

```text
M11_TRACE_COMPRESSION_CORE: PASS
M11_SIGNAL_TRACE_COMPRESSION: PASS
M11_TELEMETRY_WINDOW_REDUCTION: PASS
M11_CAPSULE_COMPATIBLE_DIAGNOSTIC_SUMMARY: PASS
M11_LINEAGE_INDEXED_TRACE_COMPARISON: PASS
M11_BOUNDED_REPLAY_METRICS: PASS
M11_ARTIFACT_SCHEMA_TESTING: PASS
M11_STRONG_NUMERIC_TESTS: PASS
FULL_M1_M11_REGRESSION_REPORTED: PASS
MILESTONE_11_REPORT_CURRENT: PASS
REVIEW_PACKAGE_CURRENT: FAIL_ONE_MISSING_COMMIT_HASH
NEXT_MILESTONE_WORDING_MACHINE_NATIVE: PASS
MILESTONE_11_FINAL_ACCEPTANCE: HOLD
READY_FOR_MILESTONE_12: NO
```

---

## Required change

Update only:

```text
docs/review_package.md
```

Add the final M11A hardening commit hash to the commit history:

```text
0be8000 — Milestone 11A trace compression hardening and stage closing
```

Keep all existing current sections intact:

- title: `# Milestone 11 Final Review Package`
- final tests: `213 passed in 18.07s` or exact current rerun value
- final coverage: `81.91%` or exact current rerun value
- full M1–M11 regression summary
- M11 output summary
- artifact paths including `output/demo_m11/trace_compression.json`
- report paths including `docs/milestone_11_report.md`
- clean working tree status

A one-line append is acceptable for this patch because all other review-package sections are already current.

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

Reopen or inspect `docs/review_package.md` after committing to confirm:

```text
REVIEW_PACKAGE_TITLE_CURRENT: yes
REVIEW_PACKAGE_TESTS_CURRENT: yes
REVIEW_PACKAGE_COVERAGE_CURRENT: yes
REVIEW_PACKAGE_CURRENT_MILESTONE_SUMMARY: yes
CURRENT_STAGE_COMMIT_LISTED: yes
CURRENT_ARTIFACT_PATHS_REPORTED: yes
REPORT_PATHS_CURRENT: yes
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
MILESTONE_11B_STATUS: PASS or PARTIAL_PASS
MILESTONE_11_STATUS: ACCEPTED or HOLD
READY_FOR_MILESTONE_12: YES or NO
Branch:
Starting commit hash:
Implementation/documentation commit hash:
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
M11B_REVIEW_PACKAGE_CURRENT_STAGE_COMMIT_LISTED: PASS
MILESTONE_11_REPORT_CURRENT: PASS
REVIEW_PACKAGE_CURRENT: PASS
NEXT_MILESTONE_WORDING_MACHINE_NATIVE: PASS
STAGE_CLOSING_CHORES_SATISFIED: PASS
GUARDRAILS: PASS
CLEAN_WORKTREE_AND_PUSHED_REMOTE: PASS
```
