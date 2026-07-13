# After Silicon — MiMo Milestone 17B Judge Strictness and Stage-Closing Prompt

## Repository and branch

Repository: `https://github.com/NoObIe-97/machine_sim.git`

Branch: `feature/milestone-1`

Start from the current Milestone 17A remote head:

```text
14ab341ebb8f9b3aef5f9f2fa1fa1588f59960bc
```

Milestone 17A fixed the major neural-controller determinism issue and preserved the internal neural processing unit. However, final M17 acceptance is still on HOLD because the M17 judge remains too permissive and stage-closing artifacts/docs are pending.

Do not start Milestone 18.

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
M17_TESTS_ASSERT_REAL_NEURAL_BEHAVIOR: PASS
M17_INDEPENDENT_JUDGE_PASS_NO_SKIP: FAIL_STILL_PERMISSIVE
M14_M15_M16_REGRESSION_JUDGES_STILL_PASS: FAIL_JUDGE_STILL_SOFT
MILESTONE_17_REPORT_CURRENT: PENDING_STAGE_CLOSING
REVIEW_PACKAGE_CURRENT: PENDING_STAGE_CLOSING
REVIEW_BUNDLE_CURRENT: PENDING_STAGE_CLOSING
STAGE_CLOSING_CHORES_SATISFIED: FAIL
MILESTONE_17_FINAL_ACCEPTANCE: HOLD
READY_FOR_MILESTONE_18: NO
```

---

## What is accepted and must be preserved

Preserve:

- `stable_seed()` and all replacement of Python `hash()` in neural RNG paths.
- `NeuralController` architecture and pure Python recurrent controller.
- Local sensor input vector.
- Neural action logits and preferences.
- Local plasticity update.
- Successor neural-state transfer.
- Neural-vs-scalar comparison artifact.
- Current test count or updated rerun value.

Do not weaken the neural controller or remove the M17 artifacts.

---

## Blocking issue 1 — M17 judge still allows non-PASS outcomes

Current judge behavior still allows `PARTIAL` to pass because it computes failure only as checks with value `FAIL`.

Required fix:

- Overall `M17_JUDGE_STATUS` must be `PASS` only if **every required check is exactly `PASS`**.
- Any value other than `PASS`, including `PARTIAL`, `SKIP`, `UNKNOWN`, `NOT_FOUND`, or missing, must make the overall status `FAIL`.
- `successor_neural_transfer_check` must fail unless both summary count and transfer-trace file count are nonzero and mutually consistent.
- `failed_checks` should include any check whose value is not exactly `PASS`.

Acceptance target:

```text
successor_neural_transfer_check: PASS only when summary_count > 0, file_count > 0, and counts agree or are explicitly reconciled.
```

---

## Blocking issue 2 — long-run tick check still has trace-count fallback

Current judge still permits:

```text
run_ticks == 0 and state_trace_count >= 5 -> PASS
```

This must be removed.

Required fix:

```text
long_run_ticks_check: PASS only if run_ticks >= 20000
```

The M17 artifact writer already adds `run_ticks` to `neural_processing_summary.json`; the judge must require it.

Add tests proving:

- missing `run_ticks` fails,
- `run_ticks < 20000` fails,
- `run_ticks >= 20000` passes when other artifacts are valid.

---

## Blocking issue 3 — regression judge check still passes by default

Current tests include a test named like:

```text
TestM14M15M16Regression.test_regression_check_passes_by_default
```

This contradicts the M17A goal.

Required fix:

- Delete or rewrite that test.
- `m14_m15_m16_regression_check` must fail if required regression judge status artifacts are missing or non-PASS.
- The M17 judge should check explicit regression detail fields in `neural_processing_summary.json` or dedicated files copied into `output/demo_m17/`.

Preferred artifact schema in `neural_processing_summary.json`:

```json
{
  "regression_judges": {
    "m14": "PASS",
    "m15": "PASS",
    "m16": "PASS"
  }
}
```

Acceptable alternative: include these judge result JSON files in `output/demo_m17/` and verify status from them:

```text
milestone_14_judge_result.json
milestone_15_judge_result.json
milestone_16_judge_result.json
```

Required tests:

- missing regression details fail,
- `m14 != PASS` fails,
- `m15 != PASS` fails,
- `m16 != PASS` fails,
- all three PASS succeeds.

---

## Blocking issue 4 — required artifacts list omits transfer trace and judge result

Current `REQUIRED_ARTIFACTS` does not include:

```text
neural_successor_transfer_trace.jsonl
milestone_17_judge_result.json
```

Add both where appropriate. If including the judge result creates a bootstrapping problem when the judge runs before writing its result, handle it explicitly by checking required input artifacts separately from final output artifact, or document and test the behavior. The final artifact set must include the judge result.

---

## Blocking issue 5 — stage-closing docs/review package/review bundle are pending

Update documentation after judge hardening.

Required:

```text
docs/milestone_17_report.md
docs/review_package.md
```

The M17 report must clearly state:

- stable SHA-256 seed derivation replaced Python `hash()` in neural paths,
- FABRICATE output is an intent-only neural output and is engine-gated/mapped to IDLE in direct action selection,
- M17 judge was hardened so only exact PASS checks can pass,
- run_ticks is strictly checked,
- M14/M15/M16 regression judge evidence is real, not default-pass,
- final tests/coverage,
- full command list actually run,
- final artifact paths.

The review package must list:

```text
69747f6 — Milestone 17 internal neural processing unit
14ab341 — Milestone 17A neural determinism and judge hardening
<new commit> — Milestone 17B judge strictness and stage closing
```

If the project convention requires review bundle files, create/update them and report paths:

```text
review_bundle_dir_repo_path
review_bundle_zip_repo_path
summary_md_repo_path
```

If not used in this repository stage, state explicitly in the handoff that no review bundle path is required for this repo and why.

---

## Verification commands

Run:

```bash
python -m pytest machine_sim/tests/ -v
python -m pytest machine_sim/tests/ --cov=machine_sim --cov-report=term-missing
python -m machine_sim.cli.main check
python -m machine_sim.cli.main run -c configs/milestone_17_internal_neural_processing_unit.toml -t 20000 -s 42 -o output/demo_m17
python -m machine_sim.cli.main inspect output/demo_m17
python -m machine_sim.verification.milestone_14_judge output/demo_m14
python -m machine_sim.verification.milestone_15_judge output/demo_m15
python -m machine_sim.verification.milestone_16_judge output/demo_m16
python -m machine_sim.verification.milestone_17_judge output/demo_m17
```

If regression judge outputs are copied into `output/demo_m17/` or summarized in `neural_processing_summary.json`, document the exact source and commands.

---

## Required stage-closing evidence

Final handoff must include:

```text
M17B_STATUS: PASS or PARTIAL_PASS
MILESTONE_17_STATUS: ACCEPTED or HOLD
READY_FOR_MILESTONE_18: YES or NO
Branch:
Starting commit hash:
Implementation/hardening commit hash:
Final remote commit hash:
Files changed:
Tests:
Coverage:
Guardrail result:
M14/M15/M16 regression judge results:
M17 judge result:
Determinism hardening summary:
Judge strictness summary:
Stage closing docs updated:
Review bundle paths, or explicit reason not applicable:
Clean working tree:
```

Also include these yes/no gates:

```text
M17_GOAL_SPEC_SATISFIED:
M17_STABLE_SEED_ALL_NEURAL_RNG_PATHS:
M17_NO_PYTHON_HASH_IN_NEURAL_PATHS:
M17_JUDGE_EXACT_PASS_ONLY:
M17_RUN_TICKS_STRICTLY_CHECKED:
M17_REGRESSION_JUDGES_REQUIRED_AND_VERIFIED:
M17_SUCCESSOR_TRANSFER_REQUIRED_AND_VERIFIED:
M17_REQUIRED_ARTIFACTS_COMPLETE:
MILESTONE_REPORT_CURRENT:
REVIEW_PACKAGE_CURRENT:
STAGE_CLOSING_CHORES_SATISFIED:
```

---

## Acceptance criteria

```text
M17_STABLE_SEED_ALL_NEURAL_RNG_PATHS: PASS
M17_NO_PYTHON_HASH_IN_NEURAL_PATHS: PASS
M17_FABRICATE_OUTPUT_SEMANTICS_DOCUMENTED: PASS
M17_JUDGE_EXACT_PASS_ONLY: PASS
M17_RUN_TICKS_STRICTLY_CHECKED: PASS
M17_REGRESSION_JUDGES_REQUIRED_AND_VERIFIED: PASS
M17_SUCCESSOR_TRANSFER_REQUIRED_AND_VERIFIED: PASS
M17_REQUIRED_ARTIFACTS_COMPLETE: PASS
M17_TESTS_COVER_JUDGE_FAILURE_CASES: PASS
M17_INDEPENDENT_JUDGE_PASS_NO_SKIP: PASS
TESTS_AND_COVERAGE: PASS
GUARDRAILS: PASS
FULL_M1_M17_REGRESSION_REPORTED: PASS
MILESTONE_17_REPORT_CURRENT: PASS
REVIEW_PACKAGE_CURRENT: PASS
STAGE_CLOSING_CHORES_SATISFIED: PASS
CLEAN_WORKTREE_AND_PUSHED_REMOTE: PASS
```
