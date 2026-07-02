# Stage Closing Chores Skill

Use this skill at the end of every implementation stage, including a fresh milestone, corrective pass, documentation-only patch, or test-hardening pass.

## Purpose

Prevent stale reports, stale review-package entries, incomplete regression records, stale artifact paths, stale next-stage wording, and premature acceptance claims.

This skill is a hard acceptance gate. If any required item cannot be verified after the final commit and push, report `PARTIAL_PASS` or `HOLD`, not `PASS`.

---

## Required closing sequence

### 1. Record the exact stage identity

Capture and report:

- Stage name and scope.
- Starting commit hash.
- Implementation/documentation commit hash.
- Final remote commit hash after push.
- Branch name.
- Files changed.

### 2. Run and capture current verification

Run and record the current outputs for:

- Full test suite.
- Coverage command.
- Guardrail command.
- All milestone demo/regression commands required by the active prompt.
- Any milestone-specific comparison command.

Do not reuse old test counts, old coverage values, old demo summaries, or previous-stage timings.

### 3. Update the milestone report

The current milestone report must include:

- Commands actually run in the current stage.
- Current test result and runtime.
- Current coverage result.
- Current guardrail result.
- Full required regression command set.
- Numeric demo summaries for every milestone up to the current milestone.
- Current milestone-specific output.
- Artifact paths produced by the current milestone.
- Current known limitations.
- Next recommended milestone wording, using only machine-native terms.

For a corrective pass, the report must be updated even if only tests or docs changed.

### 4. Update the review package

The review package must be fully current, not merely appended by one line.

Required updates:

- Title must match the current accepted/target milestone, for example `Milestone 10 Final Review Package`.
- Commit list must include the current stage commit.
- Final test result must match the current run.
- Final coverage must match the current run.
- Regression summary must include every milestone up to the current milestone.
- Artifact paths must include current milestone artifacts.
- Report paths must include current milestone report paths.
- Clean working tree status must reflect the final pushed state.

A one-line commit-hash append is not sufficient unless all other review-package sections were already current.

### 5. Perform documentation freshness checks

After updating docs, reopen or inspect the committed files and verify:

- Milestone report title references the current milestone.
- Review package title references the current milestone.
- Test count in milestone report equals the final test count.
- Test count in review package equals the final test count.
- Coverage in milestone report equals the final coverage value.
- Coverage in review package equals the final coverage value.
- Regression summaries include the current milestone.
- Artifact paths include the current milestone output artifacts.
- Report paths include the current milestone report.
- Next milestone wording does not say the next milestone has already started.
- No `pending`, `TBD`, `old`, `previous`, `stale`, or obsolete placeholder text remains in final report/review sections.

Recommended local checks:

```bash
grep -n "Milestone [0-9].*Final Review Package" docs/review_package.md
grep -n "passed\|coverage\|Total coverage" docs/milestone_*_report.md docs/review_package.md
grep -n "pending\|TBD\|stale\|old result\|previous result" docs/milestone_*_report.md docs/review_package.md || true
grep -n "output/demo_" docs/milestone_*_report.md docs/review_package.md
```

If the active prompt specifies exact expected commands, also verify the milestone report contains those command lines.

### 6. Check project vocabulary boundary

Keep runtime, config, artifact, report, and prompt wording machine-native.

If the active prompt defines disallowed terms, remove matches from files added or modified in this stage.

Prefer physical/numeric phrasing:

```text
pressure
load
density
gradient
telemetry
continuity
drift
perturbation
bounded record
diagnostic summary
field dynamics
trace compression
lineage-indexed comparison
```

Avoid introducing human/social/biological/semantic wording. When in doubt, rewrite using measurable physical state.

### 7. Verify stage-closing evidence before final handoff

Before final response, produce an internal or final evidence block with:

```text
STAGE_CLOSING_SKILL_INVOKED: yes
MILESTONE_REPORT_TITLE_CURRENT: yes/no
MILESTONE_REPORT_TESTS_CURRENT: yes/no
MILESTONE_REPORT_COVERAGE_CURRENT: yes/no
MILESTONE_REPORT_FULL_REGRESSION_CURRENT: yes/no
REVIEW_PACKAGE_TITLE_CURRENT: yes/no
REVIEW_PACKAGE_TESTS_CURRENT: yes/no
REVIEW_PACKAGE_COVERAGE_CURRENT: yes/no
REVIEW_PACKAGE_CURRENT_MILESTONE_SUMMARY: yes/no
CURRENT_ARTIFACT_PATHS_REPORTED: yes/no
NEXT_MILESTONE_WORDING_MACHINE_NATIVE: yes/no
NO_STALE_DOC_VALUES_FOUND: yes/no
CLEAN_WORKTREE_AFTER_PUSH: yes/no
FINAL_REMOTE_HASH_REPORTED: yes/no
```

If any value is `no`, do not report `PASS` or next-milestone readiness.

### 8. Final git hygiene

- Commit all intended changes.
- Push to the active branch.
- Confirm clean working tree.
- Report exact final remote hash.

---

## Final handoff checklist

Do not report `PASS`, `ACCEPTED`, or readiness for the next milestone until all items below are true:

```text
STAGE_CODE_OR_DOC_SCOPE_COMPLETE: yes
TESTS_CURRENT_AND_PASSING: yes
COVERAGE_CURRENT_AND_ABOVE_THRESHOLD: yes
GUARDRAILS_CURRENT_AND_PASSING: yes
FULL_REQUIRED_REGRESSION_REPORTED: yes
MILESTONE_REPORT_CURRENT: yes
MILESTONE_REPORT_TITLE_CURRENT: yes
MILESTONE_REPORT_TESTS_CURRENT: yes
MILESTONE_REPORT_COVERAGE_CURRENT: yes
MILESTONE_REPORT_CURRENT_STAGE_OUTPUT: yes
REVIEW_PACKAGE_CURRENT: yes
REVIEW_PACKAGE_TITLE_CURRENT: yes
REVIEW_PACKAGE_TESTS_CURRENT: yes
REVIEW_PACKAGE_COVERAGE_CURRENT: yes
REVIEW_PACKAGE_CURRENT_STAGE_SUMMARY: yes
ARTIFACT_PATHS_REPORTED: yes
REPORT_PATHS_CURRENT: yes
NEXT_MILESTONE_WORDING_MACHINE_NATIVE: yes
NO_STALE_RESULTS_OR_PENDING_COMMIT_TEXT: yes
CLEAN_WORKTREE_AFTER_PUSH: yes
FINAL_REMOTE_HASH_REPORTED: yes
```

If any item is not true, report `PARTIAL_PASS` or `HOLD` with exact blockers.
