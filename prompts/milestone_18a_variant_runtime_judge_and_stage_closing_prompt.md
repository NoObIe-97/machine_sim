# After Silicon — MiMo Milestone 18A Variant Runtime Judge and Stage-Closing Prompt

## Repository and branch

Repository: `https://github.com/NoObIe-97/machine_sim.git`

Branch: `feature/milestone-1`

Start from the current Milestone 18 remote head:

```text
6fe25140f61d7362517415003de0fac267b2f5f7
```

Milestone 18 implemented the neural controller variant-sensitivity sweep and is directionally correct. Final M18 acceptance is on HOLD because the M18 judge needs one strict runtime-summary hardening patch and the review package still has stage-closing documentation issues.

Do not start Milestone 19.

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
M18_REGRESSION_JUDGES_REPORTED: PASS
M18_TESTS_AND_COVERAGE: PASS
M18_INDEPENDENT_JUDGE: PARTIAL_PASS_NEEDS_RUNTIME_SUMMARY_STRICTNESS
MILESTONE_18_REPORT_CURRENT: PASS
REVIEW_PACKAGE_CURRENT: FAIL_PENDING_M18_COMMIT_AND_HEADING
STAGE_CLOSING_CHORES_SATISFIED: FAIL
MILESTONE_18_FINAL_ACCEPTANCE: HOLD
READY_FOR_MILESTONE_19: NO
```

---

## Preserve what is accepted

Preserve:

- `configs/milestone_18_neural_controller_variant_sensitivity.toml`
- configurable `neural_hidden_size`
- configurable `neural_plasticity_rate`
- `machine_sim/analysis/neural_variant_comparison.py`
- variant-sweep CLI command
- per-variant output directory design
- M18 similarity matrix artifacts
- M18 parameter sensitivity artifacts
- M18 report content unless explicitly corrected below
- 385 passing tests / 80.02% coverage unless rerun values change

Do not alter M17 accepted runtime behavior except if required to fix a real regression.

---

## Blocking issue 1 — M18 judge runtime summary check is too permissive

Current M18 judge has a `per_variant_runtime_check`, but if `per_variant_runtime_summary.jsonl` is missing or empty, the loop over runtime rows does not fail. This means a malformed output directory could still pass the runtime-duration check as long as other artifacts exist.

Required fix in:

```text
machine_sim/verification/milestone_18_judge.py
```

Strengthen `per_variant_runtime_check` so it passes only when all of the following are true:

```text
per_variant_runtime_summary.jsonl exists
it contains at least one valid JSON record for every variant_id in the similarity matrix
runtime variant_ids exactly cover the expected variant_ids, or any extra rows are documented and ignored safely
all required fields exist for each variant: variant_id, run_ticks, neural_controller_enabled, neural_hidden_size, neural_plasticity_rate
accepted M17 neural baseline variant has run_ticks >= 10000
all other variants have run_ticks >= 5000
scalar baseline is explicitly allowed but must still have run_ticks >= 5000
```

The judge must fail on:

```text
missing runtime summary file
empty runtime summary file
missing variant runtime row
duplicate variant runtime row without deterministic reconciliation
missing run_ticks
run_ticks below threshold
```

Also update tests in:

```text
machine_sim/tests/test_neural_variant_comparison.py
```

Required tests:

1. M18 judge fails when `per_variant_runtime_summary.jsonl` is missing.
2. M18 judge fails when `per_variant_runtime_summary.jsonl` is empty.
3. M18 judge fails when one variant runtime row is missing.
4. M18 judge fails when a variant has `run_ticks` below threshold.
5. M18 judge passes when every variant has a valid runtime row and all thresholds are met.

---

## Blocking issue 2 — review package still has pending M18 commit

Update only documentation after the judge/test hardening patch is complete.

In:

```text
docs/review_package.md
```

Current commit history contains:

```text
(pending) — Milestone 18 neural controller variant sensitivity
```

Replace with the actual M18 implementation commit:

```text
6fe2514 — Milestone 18 neural controller variant sensitivity
```

After M18A is committed, also add:

```text
<NEW_M18A_COMMIT> — Milestone 18A variant runtime judge and stage-closing
```

Do not leave any `(pending)` entries.

---

## Blocking issue 3 — review package heading says M1-M17 while including M18

In:

```text
docs/review_package.md
```

The heading currently says:

```text
## Full M1-M17 Regression Summary
```

but the table includes M18. Replace with:

```text
## Full M1-M18 Regression Summary
```

Ensure the M18 row remains present.

---

## Documentation finalization

Ensure:

```text
docs/milestone_18_report.md
```

remains current with:

- 385 tests or fresh rerun value,
- 80.02% coverage or fresh rerun value,
- exact commands actually run,
- M14/M15/M16/M17 regression PASS,
- M18 judge PASS after the stricter runtime-summary check,
- artifact paths,
- limitations,
- machine-native next milestone wording.

Update the report only if rerun values or judge details change.

---

## Verification commands

Run:

```bash
python -m pytest machine_sim/tests/ -v
python -m pytest machine_sim/tests/ --cov=machine_sim --cov-report=term-missing
python -m machine_sim.cli.main check
python -m machine_sim.cli.main variant-sweep -c configs/milestone_18_neural_controller_variant_sensitivity.toml -o output/demo_m18
python -m machine_sim.verification.milestone_18_judge output/demo_m18
python -m machine_sim.verification.milestone_17_judge output/demo_m17
python -m machine_sim.verification.milestone_14_judge output/demo_m14
python -m machine_sim.verification.milestone_15_judge output/demo_m15
python -m machine_sim.verification.milestone_16_judge output/demo_m16
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
MILESTONE_REPORT_COMMAND_SET_PRESENT: yes
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
M18_GOAL_SPEC_SATISFIED: yes
M18_JUDGE_STATUS: PASS
M18_JUDGE_EXACT_PASS_ONLY: yes
M18_RUNTIME_SUMMARY_STRICT: yes
M14_M15_M16_M17_REGRESSION_JUDGES_STILL_PASS: yes
```

Do not claim ACCEPTED unless all are true.

---

## Final handoff format

```text
MILESTONE_18A_STATUS: PASS or PARTIAL_PASS
MILESTONE_18_STATUS: ACCEPTED or HOLD
READY_FOR_MILESTONE_19: YES or NO
Branch:
Starting commit hash:
Implementation/documentation commit hash:
Final remote commit hash:
Files changed:
Tests:
Coverage:
Guardrail result:
M14/M15/M16/M17 judge results:
M18 judge result:
Runtime summary strictness:
Documentation updates:
Stage closing chores result:
Clean working tree:
```

---

## Acceptance criteria

```text
M18A_RUNTIME_SUMMARY_FILE_REQUIRED: PASS
M18A_RUNTIME_ROWS_MATCH_VARIANTS: PASS
M18A_RUNTIME_THRESHOLDS_STRICT: PASS
M18A_JUDGE_EXACT_PASS_ONLY_PRESERVED: PASS
M18A_TESTS_COVER_MISSING_EMPTY_AND_INCOMPLETE_RUNTIME_SUMMARY: PASS
MILESTONE_18_REPORT_CURRENT: PASS
REVIEW_PACKAGE_CURRENT: PASS
M18_IMPLEMENTATION_COMMIT_LISTED: PASS
M18A_FINAL_COMMIT_LISTED: PASS
STAGE_CLOSING_CHORES_SATISFIED: PASS
M18_FINAL_ACCEPTANCE: PASS
```
