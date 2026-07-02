# Stage Closing Chores Skill

Use this skill at the end of every implementation stage, including a fresh milestone, corrective pass, documentation-only patch, or test-hardening pass.

## Purpose

Prevent stale reports, stale review-package entries, incomplete regression records, and premature acceptance claims.

## Required closing sequence

1. **Record the exact stage identity**
   - Stage name and scope.
   - Starting commit hash.
   - Implementation commit hash or documentation commit hash.
   - Final remote commit hash after push.
   - Branch name.

2. **Run and capture current verification**
   - Full test suite.
   - Coverage command.
   - Guardrail command.
   - All milestone demo/regression commands required by the active prompt.
   - Any milestone-specific comparison command.

3. **Update the milestone report**
   - Commands actually run.
   - Current test result and runtime.
   - Current coverage result.
   - Guardrail result.
   - Demo outputs with numeric summaries.
   - Artifact paths.
   - Current known limitations.
   - Next recommended milestone wording, using only machine-native terms.

4. **Update the review package**
   - Retitle if the package title is stale.
   - Add the latest commit hash and stage label.
   - Update final test and coverage values.
   - Include summaries for every milestone up to the current one.
   - Include all current report paths.
   - Include clean working tree status after final push.

5. **Check documentation freshness**
   - Search for stale milestone labels, stale test counts, stale coverage values, old commit hashes, and old “pending commit” text.
   - Ensure the latest milestone report and review package agree with the final handoff.
   - Ensure the report does not claim a later milestone has started.

6. **Check project vocabulary boundary**
   - Keep runtime, config, artifact, report, and prompt wording machine-native.
   - If the active prompt defines disallowed terms, remove matches from files added or modified in this stage.
   - Prefer physical/numeric phrasing: pressure, load, density, gradient, telemetry, continuity, drift, perturbation, bounded record, diagnostic summary.

7. **Final git hygiene**
   - Commit all intended changes.
   - Push to the active branch.
   - Confirm clean working tree.
   - Report exact final remote hash.

## Final handoff checklist

Do not report `PASS`, `ACCEPTED`, or readiness for the next milestone until all items below are true:

```text
STAGE_CODE_OR_DOC_SCOPE_COMPLETE: yes
TESTS_CURRENT_AND_PASSING: yes
COVERAGE_CURRENT_AND_ABOVE_THRESHOLD: yes
GUARDRAILS_CURRENT_AND_PASSING: yes
FULL_REQUIRED_REGRESSION_REPORTED: yes
MILESTONE_REPORT_CURRENT: yes
REVIEW_PACKAGE_CURRENT: yes
ARTIFACT_PATHS_REPORTED: yes
NEXT_MILESTONE_WORDING_MACHINE_NATIVE: yes
NO_STALE_RESULTS_OR_PENDING_COMMIT_TEXT: yes
CLEAN_WORKTREE_AFTER_PUSH: yes
FINAL_REMOTE_HASH_REPORTED: yes
```

If any item is not true, report `PARTIAL_PASS` or `HOLD` with exact blockers.
