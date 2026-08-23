# After Silicon — MiMo Milestone 22B Goal Spec: Stage-Closing Documentation Sync

## Repository and branch

Repository: `https://github.com/NoObIe-97/machine_sim.git`

Branch: `feature/milestone-1`

Accepted M22A runtime/judge head before this prompt:

```text
0d83c5f09e69fa329a17ddffb63c503e2eb8ca56
```

M22A transactional fabrication finalization is technically accepted. Do **not** change runtime code, tests, configs, judges, artifacts, or simulation semantics unless a verification command exposes a genuine breakage.

This task exists only because the final review package still contains stale stage-closing values after the M22A correction.

Before final handoff, invoke and satisfy:

```text
prompts/skills/stage_closing_chores.md
```

Do not start M23.

---

# Confirmed technical state to preserve

The following M22/M22A implementation state is accepted and must remain unchanged:

- executable per-unit design-program substrate;
- deterministic bounded straight-line interpreter;
- canonical compatibility with the accepted M19/M21 neural architecture;
- per-unit program ownership and successor program transfer;
- bounded insertion/deletion/substitution/operand variation;
- variable program length 1..128;
- program execution cost accounting;
- M21 deep-digest and checkpoint integration;
- process-isolated pause/resume equivalence;
- no self-replication semantics yet;
- M22A two-phase fabrication finalization (`prepare_fabricate()` / `commit_fabrication()`);
- invalid successor program increments attempt/failure only and creates no success, lineage edge, unit, occupancy, or successful-fabrication marker;
- valid successor finalizes success/lineage exactly once;
- failed-then-valid sequence contains no phantom lineage;
- M14–M21 regression judges PASS;
- M22 judge PASS with 31/31 exact-PASS-only checks.

Current verified final test/coverage state from M22A:

```text
614 passed
0 failed
79.78% coverage
M22 judge: 31/31 PASS
```

M22A implementation commit:

```text
8191b187f99a7b7e0aed9db4f2ca768be840bd84
```

Current remote head before this prompt:

```text
0d83c5f09e69fa329a17ddffb63c503e2eb8ca56
```

---

# Documentation defects that must be corrected

At `0d83c5f09e69fa329a17ddffb63c503e2eb8ca56`, `docs/milestone_22_report.md` is substantively current, but `docs/review_package.md` still contains stale M21-era values and duplicate entries.

Correct all of the following:

1. The top-level `## Test Results (Final)` still says `569 passed ...`; update it to the actual final M22A value (`614 passed`, 0 failed). If a fresh verification run changes timing only, record the fresh timing but keep the real count.
2. The top-level `## Coverage (Final)` still says `78.31%`; update it to the actual final M22A coverage (`79.78%`) or the freshly rerun exact value if it differs.
3. In `## Full M1-M22 Regression Summary`, the M22 row still says `judge 25/25 PASS`; update it to `31/31 PASS` and make clear the count includes the six M22A transactional-finalization probes.
4. Remove the duplicate second M21 row from the regression table. There must be one coherent row per milestone/stage entry.
5. Search the entire `docs/review_package.md` for stale current-stage values such as `569`, `78.31`, `25/25`, duplicate M21 summary rows, `pending`, `TBD`, `TODO`, or obsolete M22/M22A wording. Historical values may remain only where they are explicitly labeled as historical M21 evidence, e.g. inside an M21 demo section; do not rewrite truthful historical benchmark/test evidence merely because the same number is old.
6. Ensure the M22/M22A commit history is coherent and includes the accepted M22 implementation commit and M22A correction commit. It is acceptable for the final docs-only remote hash to be reported in the handoff rather than creating an infinite self-referential commit-history loop, but no incorrect implementation hash may remain.
7. Ensure `docs/milestone_22_report.md` and `docs/review_package.md` agree on current-stage test count, coverage, M22 judge count, M14–M21 regression status, M22A correction status, and next milestone wording.
8. Preserve the next milestone wording:

```text
Milestone 23 — Unit-Executed Program Copying and Successor Construction
```

---

# Verification required

Run at minimum:

```bash
python -m pytest machine_sim/tests/ -q
python -m pytest machine_sim/tests/ -q --cov=machine_sim --cov-report=term
python -m machine_sim.cli.main check
python -m machine_sim.verification.milestone_22_judge output/demo_m22
```

Also confirm the M14–M21 regression evidence referenced by the current M22 artifacts remains PASS. If already-current subprocess capture is valid for the exact current runtime commit, do not rerun expensive work merely to modify documentation; if runtime has changed unexpectedly, rerun as required.

Use searches/greps to prove there are no stale current-stage values in the two M22 stage-closing documents.

---

# Acceptance criteria

All must be true:

```text
M22_RUNTIME_CODE_UNCHANGED: yes
M22A_TRANSACTIONAL_FINALIZATION_UNCHANGED: yes
M22_FINAL_TEST_COUNT_CURRENT: yes
M22_FINAL_COVERAGE_CURRENT: yes
M22_JUDGE_COUNT_CURRENT_31_OF_31: yes
M22_REGRESSION_TABLE_NO_DUPLICATE_M21: yes
M22_REPORT_AND_REVIEW_PACKAGE_SYNCHRONIZED: yes
M14_M15_M16_M17_M18_M19_M20_M21_REGRESSION_STATUS_CURRENT: yes
NO_STALE_CURRENT_STAGE_DOC_VALUES: yes
STAGE_CLOSING_CHORES_SATISFIED: yes
MILESTONE_22_FINAL_ACCEPTANCE: ACCEPTED
READY_FOR_MILESTONE_23: YES
```

---

# Final handoff

Return:

- repository;
- branch;
- starting commit;
- docs-sync commit;
- final remote commit;
- exact files changed;
- final tests;
- final coverage;
- guardrail result;
- M14–M21 regression status;
- M22 judge result and exact check count;
- explicit confirmation that runtime/test/judge code was not modified;
- explicit confirmation that duplicate/stale review-package values were removed;
- clean-worktree status.

Do not start M23.
