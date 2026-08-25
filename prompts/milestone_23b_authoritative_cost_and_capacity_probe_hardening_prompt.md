# After Silicon — MiMo Milestone 23B Goal Spec: Authoritative Cost and Capacity-Probe Hardening

## Repository and branch

Repository: `https://github.com/NoObIe-97/machine_sim.git`

Branch: `feature/milestone-1`

Accepted M23A candidate head before this prompt:

```text
33895c682612c55c98ee7f68ef1c94707c4f6287
```

M23 core architecture remains technically accepted in direction but M23 is still on HOLD. Do **not** start M24.

Before final handoff, invoke and satisfy:

```text
prompts/skills/stage_closing_chores.md
```

---

# Scope

This is a narrow M23B verification/cost-semantics correction.

Preserve:

- M23 unit-executed construction mode;
- BEGIN / COPY_RECORD / COMMIT runtime construction section;
- whole-program record-by-record copying;
- copied construction instructions;
- per-record copy errors;
- A→B→C zero-error closure;
- M22A transactional finalization;
- M23A atomic BEGIN reservation ordering;
- reservation cleanup/cancel path;
- in-flight capacity accounting;
- deep-digest/checkpoint/pause-resume behavior;
- M23-disabled legacy compatibility;
- M14–M22 regression PASS.

Do not add new evolutionary mechanisms.

---

# Why M23A is still on HOLD

Independent review of `33895c682612c55c98ee7f68ef1c94707c4f6287` found three remaining verification/semantic defects.

## Defect 1 — developmental decode cost is not authoritative

The M23A COMMIT path currently precomputes:

```text
program_base_cost + program_per_instruction_cost * len(target_instructions)
```

and charges that before/around developmental interpretation.

But the accepted M22 interpreter computes authoritative execution cost as:

```text
program_base_cost
+ program_per_instruction_cost * executed_instruction_count
```

where execution stops at developmental `END`, budget exhaustion, invalid operand, or other terminal condition.

Therefore a program containing a runtime construction section after the first developmental END must **not** pay developmental-decode cost for runtime records that the developmental interpreter never executes.

Required correction:

```text
decode_result = DesignProgramInterpreter(...).execute(...)
charge exactly decode_result.execution_cost
```

Charge it exactly once whenever interpretation is actually attempted, including failed interpretation.

Do not independently reconstruct the interpreter cost formula in the engine when the authoritative interpreter result already exposes `execution_cost`.

The report must describe this exact authoritative debit point.

---

## Defect 2 — the new cost judge probes are not actually exact full-cycle probes

The current `_probe_exact_construction_costs()` is insufficient:

- successful-path check validates only `accumulated_copy_cost` against runtime-instruction + copy-record costs;
- it does not prove the **actual source-unit power delta** equals the sum of BEGIN + runtime + copy + authoritative decode + architecture assembly costs;
- it does not prove exact material delta;
- the alleged `failed_decode_exact` fixture ultimately tests an incomplete COMMIT path instead of a real developmental decode failure;
- it uses `actual_delta >= expected`, which is not exact equality.

Required replacement: create controlled live probes that isolate construction costs from unrelated power drain/degradation and use numerical equality within a very tight floating tolerance.

### Successful-cycle exact-cost probe

Use a controlled canonical program and a runtime environment where unrelated power changes are either disabled at the authoritative source or explicitly included in the expected equation.

Measure from an authoritative pre-BEGIN snapshot through one successful COMMIT.

Required expected power debit:

```text
BEGIN base construction power
+ runtime_instruction_power_cost * actual executed runtime instruction count
+ copy_record_power_cost * actual copied source record count
+ decode_result.execution_cost
+ compute_fabrication_cost(decoded_architecture, configured architecture cost model)
```

Required exact material debit:

```text
fabrication_material_cost
```

Prove:

```text
actual_power_debit == expected_power_debit
actual_material_debit == expected_material_debit
successes += 1 exactly
lineage += 1 exactly
one real successor registered
one target cell occupied
no residual reservation
```

Do not use only the accumulator; measure authoritative unit/world state.

### True failed-decode exact-cost probe

This must reach COMMIT with a **complete copied buffer** and then cause `DesignProgramInterpreter.execute()` to return `decoded_architecture is None` after actual interpretation begins.

A controlled live probe may, for example, start from a valid source program, complete the source copy, then deterministically alter a copied developmental operand in the target buffer to a non-finite value before invoking COMMIT, provided this exercises the real M23 COMMIT/decode/failure path and does not bypass cost accounting.

Required expected power debit for this failure:

```text
BEGIN base power
+ runtime instruction costs actually incurred
+ copy record costs actually incurred
+ decode_result.execution_cost
```

No architecture assembly cost may be charged because usable architecture was never produced.

Required material behavior:

```text
BEGIN material cost consumed exactly once and retained on failure
```

Required final state:

```text
successes unchanged
lineage unchanged
units unchanged
occupancy unchanged
reservation released
one deterministic decode-failure event/cause
```

Use equality with a tight float tolerance. No `>=`, no “at least”, no nonzero-only assertion.

### Incomplete-COMMIT probe remains separate

Retain a separate BEGIN→COMMIT-without-COPY probe for reservation cleanup and its own cost semantics, but do not call it a failed-decode probe.

---

## Defect 3 — the capacity contention probe does not test N−1 plus competing BEGINs

The current `_probe_capacity_reservation_bound()` claims to test:

```text
capacity = N
registered = N - 1
multiple units compete for the final capacity slot
```

but actually initializes `capacity == registered units`, proving only that a full population blocks all BEGINs.

Replace it with the real causal fixture.

Example:

```text
unit_capacity = 3
registered construction-capable units = 2
both have abundant power/material and free adjacent cells
both reach CONSTRUCTION_BEGIN on the same tick
```

Because engine stepping is deterministic/sequential, exactly one may acquire the final in-flight slot.

After the competing BEGIN tick, prove:

```text
registered == 2
reserved capacity/cell slots == 1
effective population == 3
second BEGIN did not reserve
second BEGIN did not consume BEGIN base power/material
registered + in_flight <= capacity
```

Then continue through commit/cancellation and prove at every sampled tick:

```text
len(engine.units) + active capacity reservations <= unit_capacity
len(engine.units) <= unit_capacity
```

Do not satisfy this check with a population that starts already at full capacity.

If cell reservations remain the representation of capacity reservations in M23, explicitly document and test the invariant that every in-flight construction owns exactly one cell reservation and therefore `len(world.reserved_cells)` is a valid capacity-slot count. If that invariant is not universal, create an explicit capacity reservation structure instead.

---

# Judge hardening

Keep M23 independent judge exact-PASS-only.

Required judge properties:

1. No unconditional required `PASS` assignments.
2. `exact_success_cost_accounting_check` must call the new full authoritative exact probe.
3. `exact_failed_decode_cost_accounting_check` must call a **true failed developmental decode** probe.
4. Keep incomplete-COMMIT cleanup as a separate check.
5. Capacity contention check must use N−1 registered units and at least two competing BEGIN-capable sources for one final slot.
6. Missing preconditions must FAIL, never PASS.
7. Negative judge tests must prove each new check fails when its evidence/mechanism is deliberately broken.
8. The reported check count in artifacts/docs must equal the actual number of required checks produced by `judge()`.
9. Missing/empty artifacts used by artifact-backed checks must fail.
10. Overall PASS only when every required check is exactly `PASS`.

Search the judge source for patterns such as:

```text
= "PASS"
return True  # precondition missing
>= expected_cost
at least
```

and ensure no required scientific check is weakened by them.

---

# Test requirements

Add or update tests for at least:

- authoritative decode cost equals `decode_result.execution_cost`;
- runtime records after developmental END do not inflate developmental decode cost;
- successful full-cycle exact power debit;
- successful full-cycle exact material debit;
- true failed-decode exact power debit;
- true failed-decode material retained exactly once;
- failed decode has no architecture assembly charge;
- failed decode releases reservation and creates no lineage/unit/occupancy;
- incomplete COMMIT cleanup remains correct;
- N−1 competing-BEGIN capacity fixture allows exactly one final-slot reservation;
- losing competitor pays no BEGIN base power/material;
- registered + in-flight never exceeds capacity across copy/commit;
- deep digest/checkpoint still preserve in-flight reservation state;
- M14–M22 regression judges remain PASS.

Do not reduce test coverage below project threshold.

---

# Documentation correction

Update `docs/milestone_23_report.md` and `docs/review_package.md` so they match the final implementation.

Specifically:

- describe developmental decode cost as **the interpreter-returned `decode_result.execution_cost`**, not copied-program length;
- distinguish true failed-decode cost evidence from incomplete-COMMIT evidence;
- document the N−1 capacity-contention fixture;
- report the actual final M23 judge check count (the current report still says 37 even though the M23A handoff claims 42);
- report final tests, coverage, guardrails, regression status, correction commit, and final remote head appropriately;
- keep `Full M1-M23 Regression Summary` current;
- preserve the next milestone wording for M24, but do not start M24.

Also correct the final handoff `files_changed` list from actual GitHub state rather than a stale planned file list.

---

# Acceptance criteria

All must be true:

```text
M23B_DECODE_COST_USES_AUTHORITATIVE_INTERPRETER_EXECUTION_COST: yes
M23B_RUNTIME_SECTION_NOT_CHARGED_AS_DEVELOPMENTAL_DECODE_WORK: yes
M23B_SUCCESS_POWER_COST_FULL_CYCLE_EXACT: yes
M23B_SUCCESS_MATERIAL_COST_EXACT: yes
M23B_TRUE_FAILED_DECODE_FIXTURE_PRESENT: yes
M23B_FAILED_DECODE_POWER_COST_EXACT: yes
M23B_FAILED_DECODE_MATERIAL_COST_EXACT: yes
M23B_FAILED_DECODE_NO_ARCHITECTURE_ASSEMBLY_COST: yes
M23B_FAILED_DECODE_NO_SUCCESS_LINEAGE_UNIT_OR_OCCUPANCY: yes
M23B_INCOMPLETE_COMMIT_CHECK_SEPARATE_AND_PASS: yes
M23B_CAPACITY_CONTENTION_FIXTURE_STARTS_AT_N_MINUS_1: yes
M23B_ONLY_ONE_FINAL_SLOT_RESERVATION_GRANTED: yes
M23B_LOSING_BEGIN_PAYS_NO_BEGIN_BASE_COST: yes
M23B_REGISTERED_PLUS_INFLIGHT_NEVER_EXCEEDS_CAPACITY: yes
M23B_NO_UNCONDITIONAL_REQUIRED_JUDGE_PASS: yes
M23B_NO_PERMISSIVE_COST_INEQUALITY: yes
M23B_JUDGE_CHECK_COUNT_DOCS_ARTIFACTS_MATCH: yes
M23_CORE_UNIT_EXECUTED_CONSTRUCTION_PRESERVED: yes
M23_A_TO_B_TO_C_ZERO_ERROR_CLOSURE_PRESERVED: yes
M14_M15_M16_M17_M18_M19_M20_M21_M22_REGRESSIONS_PASS: yes
M23_INDEPENDENT_JUDGE_EXACT_PASS_ONLY: yes
M23_REPORT_CURRENT: yes
REVIEW_PACKAGE_CURRENT: yes
STAGE_CLOSING_CHORES_SATISFIED: yes
MILESTONE_23_FINAL_ACCEPTANCE: ACCEPTED
READY_FOR_MILESTONE_24: YES
```

---

# Final handoff

Return:

- repository;
- branch;
- starting commit;
- correction commit(s);
- final remote commit;
- exact files changed from GitHub/git diff;
- tests and failures;
- coverage;
- guardrails;
- M14–M22 regression statuses;
- M23 judge exact status and actual check count;
- successful exact cost equation with expected/actual numerical evidence;
- true failed-decode exact cost equation with expected/actual numerical evidence;
- capacity contention evidence showing N−1 start and exactly one granted final slot;
- explicit confirmation no runtime construction architecture was redesigned beyond this narrow correction;
- stage-closing evidence;
- clean working tree.

Do not start M24.
