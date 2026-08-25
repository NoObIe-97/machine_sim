# After Silicon — MiMo Milestone 23A Goal Spec: Reservation, Capacity, Cost, and Judge Hardening

## Repository and branch

Repository: `https://github.com/NoObIe-97/machine_sim.git`

Branch: `feature/milestone-1`

Accepted M22 baseline:

```text
5a86fc0a8e589b92f9af8fbc6ecb898ca243f4e5
```

M23 implementation head under correction:

```text
49f4249cd05a89e3193cade1759874a5a551fbb4
```

Do **not** start M24.

Before final handoff, invoke and satisfy:

```text
prompts/skills/stage_closing_chores.md
```

---

# Stage status

The core M23 architectural transition is accepted in direction but M23 final acceptance is **HOLD** pending this hardening stage.

Preserve these M23 mechanisms:

- opt-in `unit_executed_construction_enabled` mode;
- old periodic Phase-7 fabrication loop bypassed in M23 mode;
- one inherited `DesignProgram` containing developmental and runtime-construction sections;
- runtime construction opcodes 91/92/93;
- bounded per-tick construction stepping;
- record-by-record whole-program copy;
- runtime construction instructions copied with the rest of the program;
- per-record copy-error channel;
- M22 whole-program variation bypass in M23 mode;
- A→B→C zero-error closure;
- M22A transactional success accounting;
- deep-digest/checkpoint integration;
- process-isolated mid-copy pause/resume equivalence;
- legacy M23-disabled regressions.

This task must fix the correctness gaps below without weakening those properties.

---

# Confirmed blockers

## Blocker A — required M23 judge checks are hard-coded PASS

At the current head, `machine_sim/verification/milestone_23_judge.py` contains required checks equivalent to:

```python
checks["exact_success_cost_accounting_check"] = "PASS"
checks["exact_failed_copy_cost_accounting_check"] = "PASS"
```

This violates the project's exact-PASS discipline. A required check must be derived from live evidence or strict artifacts. It may not pass unconditionally.

Also inspect all M23 judge probes for permissive success fallbacks. For example, a probe must not return success merely because it failed to reach the state it intended to test. Missing/precondition-not-reached evidence must fail.

## Blocker B — reservation leak on incomplete commit

`execute_runtime_step()` currently handles an incomplete `CONSTRUCTION_COMMIT` by resetting unit-side state to idle and clearing `reserved_target_position`, but it does not call an engine/world service that releases the existing reservation first.

A program containing BEGIN then COMMIT without a completed COPY path can therefore abandon a world reservation and later reserve more cells.

Every construction cycle must have exactly one reservation lifecycle:

```text
unreserved
→ reserved
→ released on failure/cancel
or
→ converted to real occupancy on success then reservation released
```

No path may lose the reservation handle before release.

## Blocker C — outstanding reservations are not counted against finite capacity

`begin_unit_construction()` checks approximately:

```text
len(engine.units) >= unit_capacity
```

but a construction cycle takes multiple ticks. Two or more units can begin while the same final capacity slot is still uncommitted because outstanding construction reservations are not represented in this capacity check.

Finite capacity is part of world physics and must hold across in-flight construction:

```text
registered units + reserved construction capacity slots <= unit_capacity
```

at every tick.

Do not solve this by restoring the legacy periodic scheduler/cooldown. Use a deterministic atomic reservation model.

## Blocker D — begin-failure material accounting order

The current BEGIN path consumes local material before target placement reservation is successfully acquired.

A placement/reservation failure can therefore consume material even though the construction cycle never entered the active reserved phase.

Required phase ordering:

```text
check source active / actual power availability
check material sufficiency without consuming
check finite capacity availability including in-flight capacity reservations
reserve target cell + capacity slot atomically/deterministically
only then consume BEGIN base power/material exactly once
initialize cycle state
```

If reservation cannot be acquired, no BEGIN base power/material cost should be consumed.

If a failure happens after BEGIN successfully enters the active cycle, already-consumed BEGIN and copy costs remain consumed.

## Blocker E — report/code cost-model mismatch

`docs/milestone_23_report.md` currently states that copied-program developmental decode cost and neural architecture cost are charged at COMMIT, but the current M23 commit path does not visibly charge those costs.

Resolve this in code and documentation with a physically coherent explicit model.

Recommended model, consistent with M22:

```text
BEGIN:
  base construction power + material consumed once after reservation succeeds

runtime step:
  runtime instruction power consumed per executed runtime instruction

COPY_RECORD:
  copy-record power consumed per source record processed

COMMIT decode attempt:
  developmental interpreter execution cost consumed when decode is actually executed,
  including a decode that later fails (computation was performed)

architecture assembly:
  existing M19 architecture fabrication/complexity cost consumed exactly once
  when that assembly work is actually performed
```

Do not give failed copied-program decode a free computation path.

Do not double-charge the M22 whole-program construction cost or legacy fabrication cost.

If an equivalent accounting model is chosen, document it precisely and prove exact deltas for success and failure. There must be no quality-dependent reward or refund.

---

# Required implementation corrections

## 1. Explicit construction reservation object or equivalent atomic state

Introduce a clear representation for an active M23 construction reservation that can cover both:

- target-cell ownership;
- one finite capacity slot.

This may live in `World`, `SimEngine`, or a focused construction-reservation component, but its semantics must be deterministic and checkpointed.

Recommended conceptual state:

```text
owner_key
source_unit_id
construction_cycle_index
reserved_position
provisional_successor_id
capacity_slot_reserved = true
reservation_tick
```

There must be one authoritative reservation registry, or explicitly reconciled registries with tests proving consistency.

## 2. Atomic BEGIN preparation

BEGIN must either:

```text
FAIL before consumption:
  no cell reservation
  no capacity reservation
  no base power consumption
  no material consumption

or

SUCCEED:
  target + capacity slot reserved
  base power consumed once
  material consumed once
  runtime cycle initialized
```

No half-reserved/half-consumed state.

## 3. Universal release/cancel service

Provide one idempotent engine service, conceptually:

```text
cancel_unit_construction(unit, state, cause)
```

or equivalent.

All post-BEGIN failure/cancel paths must use it, including at minimum:

- incomplete COMMIT;
- copied program length/schema failure;
- copied developmental decode failure;
- source becomes inactive;
- reservation invalidation;
- assembly failure;
- explicit cycle reset/fault;
- any future exception-safe cleanup path that can be represented deterministically.

It must:

- release target reservation exactly once;
- release capacity slot exactly once;
- preserve already-consumed costs;
- record one deterministic failure/cancel cause where appropriate;
- clear unit runtime reservation fields only after release;
- never create success/lineage/occupancy.

Calling cleanup twice must not corrupt capacity or release another cycle's reservation.

## 4. Capacity recheck at COMMIT

Even with reserved slots, COMMIT must assert that the cycle still owns its capacity reservation before registering a successor.

No successful commit may result in:

```text
len(engine.units) > unit_capacity
```

## 5. World occupancy / success finalization order

Preserve M22A's principle that success-only accounting is committed exactly once after the successor is fully valid.

The finalization sequence must be documented and exception-safe enough that there cannot be:

- lineage without a unit;
- occupied cell without a registered unit;
- registered unit without corresponding successful construction accounting;
- success counter without lineage;
- reservation remaining after success.

Use deterministic ordering and rollback/cancel where needed.

---

# Required tests

Add focused tests in a new M23A test module or extend M23 tests. At minimum:

## A. Capacity contention with one slot remaining

Setup:

```text
unit_capacity = 3
2 active source units
both have rich power/material
both have valid copy-capable programs
both can execute BEGIN in the same construction window
```

Required:

- at most one in-flight capacity reservation may be created for the one remaining slot;
- registered + reserved capacity never exceeds 3;
- after commits, registered unit count never exceeds 3;
- losing contender records deterministic begin failure or retry behavior;
- no phantom IDs/lineage.

## B. Reservation leak — BEGIN + incomplete COMMIT

Use a broken program with no COPY_RECORD or otherwise force incomplete commit.

After failure:

```text
world target reservations: none for failed cycle
capacity reservations: none for failed cycle
unit reservation fields: cleared
successes: unchanged
lineage: unchanged
occupancy: unchanged
```

Repeat several cycles/attempts and prove reservation count does not monotonically leak.

## C. Reservation failure consumes no BEGIN base cost

Block every adjacent target cell or exhaust capacity before BEGIN.

Prove exact before/after:

- source power unchanged except ordinary unrelated tick costs explicitly controlled out of the fixture;
- local material unchanged;
- no reservation;
- no success/lineage.

## D. Successful BEGIN consumes exact base cost once

After reservation succeeds, prove exact base power/material deltas once and only once.

## E. Successful full-cycle cost accounting

For a deterministic zero-error canonical program, compute expected:

```text
BEGIN base power
+ runtime instruction costs
+ per-record copy costs
+ copied-program developmental decode execution cost
+ architecture fabrication/assembly cost when applicable
```

and prove source power/material deltas exactly match the documented model.

Do not compare only `>` or nonzero; calculate the expected value.

## F. Failed copied-program decode cost accounting

Force a copied program that reaches COMMIT but fails developmental decode.

Prove:

- BEGIN cost retained;
- runtime/copy costs retained;
- developmental decode execution cost charged according to the documented model;
- architecture cost not charged if architecture assembly never occurs;
- reservation/capacity released;
- no success/lineage/unit/occupancy.

## G. Source-inactive cleanup precondition must actually be reached

The test/judge must fail if it cannot drive the source into an active reserved construction cycle. Do not allow `return True` on missing preconditions.

## H. Process-isolated pause/resume during active reservation

Retain the existing mid-copy pause/resume proof and additionally ensure:

- target reservation owner is identical;
- capacity reservation state is identical;
- after continuation, no capacity leak;
- final accounting and deep digest match uninterrupted execution.

---

# Judge hardening

Keep M23 judge exact-PASS-only, but expand it beyond 37 checks as necessary.

Mandatory changes:

1. Remove all unconditional required PASS assignments.
2. `exact_success_cost_accounting_check` must call a live probe or strict artifact generated from a validated live run.
3. `exact_failed_copy_cost_accounting_check` must do the same.
4. Add a live `capacity_reservation_bound_check`.
5. Add a live `failed_cycle_reservation_release_check`.
6. Add a live `reservation_failure_no_begin_cost_check`.
7. Add a live `capacity_never_exceeded_after_commit_check`.
8. Harden `_probe_source_inactive_cleanup()` or equivalent: inability to reach the required active-cycle precondition is FAIL, not PASS.
9. Search all judge helpers for `return True` fallback paths that represent missing/inconclusive evidence; replace with strict failure.
10. A missing required artifact or malformed required field must fail.
11. Overall PASS only if every required check is exactly `PASS`.

Negative judge tests must prove each new check can fail.

---

# Deep digest / checkpoint

If new capacity-reservation state is added, it is future-causal and must enter:

- M21 deep semantic snapshot;
- checkpoint encoding/decoding;
- process-isolated pause/resume equivalence.

Output-only traces remain excluded.

Changing a capacity-reservation owner/slot/count must flip the deep digest.

---

# Performance

This is correctness hardening, not another M21 optimization milestone.

However:

- reservation accounting should remain O(1) or bounded-local per BEGIN/COMMIT;
- do not add an O(population) scan per unit per tick merely to count outstanding reservations;
- preserve the M23-disabled path and profile if a regression appears.

---

# Documentation corrections

Update `docs/milestone_23_report.md` and `docs/review_package.md` to match final code.

At the current head, `docs/review_package.md` has a stale section heading:

```text
## Full M1-M22 Regression Summary
```

while the table includes M23. Correct it to an M1–M23 heading.

Also:

- document the exact final construction cost equation;
- document cell + capacity reservation semantics;
- document failure cleanup semantics;
- report final test count/coverage/judge check count;
- report M14–M22 regressions;
- keep M24 wording machine-native;
- include the M23A correction commit in stage history;
- no stale current-stage counts or hashes.

---

# `_trash/` cleanup approval

The prior handoff reported an untracked local `_trash/` directory containing session diagnostic scripts.

You are approved to delete `_trash/` **only if it contains no tracked project artifact and only disposable session diagnostics**.

Before deletion:

```bash
git status --short
find _trash -maxdepth 2 -type f -print
```

Confirm none are tracked or required by reports/tests. Then remove it and finish with a clean worktree.

Do not delete tracked files merely to satisfy cleanliness.

---

# Required regression verification

Run at minimum:

```bash
python -m pytest machine_sim/tests/ -q
python -m pytest machine_sim/tests/ -q --cov=machine_sim --cov-report=term
python -m machine_sim.cli.main check
python -m machine_sim.verification.milestone_23_judge output/demo_m23
```

Regenerate M23 demo artifacts affected by cost/reservation semantics.

Run/capture M14–M22 regression judges on the corrected runtime according to established project practice.

Retain zero-mismatch M21/M22/M23 deterministic/checkpoint guarantees.

---

# Acceptance criteria

All must be true:

```text
M23A_NO_UNCONDITIONAL_REQUIRED_JUDGE_PASS: yes
M23A_SUCCESS_COST_CHECK_LIVE_AND_EXACT: yes
M23A_FAILED_COST_CHECK_LIVE_AND_EXACT: yes
M23A_BEGIN_RESERVATION_ATOMIC_BEFORE_COST_CONSUMPTION: yes
M23A_FAILED_BEGIN_CONSUMES_NO_BEGIN_BASE_COST: yes
M23A_FAILED_CYCLE_RELEASES_CELL_RESERVATION: yes
M23A_FAILED_CYCLE_RELEASES_CAPACITY_RESERVATION: yes
M23A_INCOMPLETE_COMMIT_DOES_NOT_LEAK_RESERVATION: yes
M23A_CAPACITY_COUNTS_INFLIGHT_RESERVATIONS: yes
M23A_REGISTERED_PLUS_RESERVED_NEVER_EXCEEDS_CAP: yes
M23A_COMMIT_NEVER_EXCEEDS_UNIT_CAPACITY: yes
M23A_SUCCESS_FINALIZATION_EXACTLY_ONCE: yes
M23A_NO_PHANTOM_LINEAGE_OR_OCCUPANCY: yes
M23A_DECODE_AND_ARCHITECTURE_COST_MODEL_IMPLEMENTED_AND_DOCUMENTED: yes
M23A_DECODE_FAILURE_COST_ACCOUNTING_EXACT: yes
M23A_SOURCE_INACTIVE_PROBE_STRICT_PRECONDITION: yes
M23A_DEEP_DIGEST_COVERS_CAPACITY_RESERVATION_STATE: yes
M23A_MIDCOPY_PAUSE_RESUME_RESERVATION_EQUIVALENCE: yes
M23_CORE_UNIT_EXECUTED_CONSTRUCTION_PRESERVED: yes
M23_A_TO_B_TO_C_ZERO_ERROR_CLOSURE_PRESERVED: yes
M14_M15_M16_M17_M18_M19_M20_M21_M22_REGRESSIONS_PASS: yes
M23_INDEPENDENT_JUDGE_EXACT_PASS_ONLY: yes
M23_REPORT_CURRENT: yes
REVIEW_PACKAGE_CURRENT: yes
STAGE_CLOSING_CHORES_SATISFIED: yes
CLEAN_WORKTREE_AFTER_APPROVED_TRASH_CLEANUP: yes
MILESTONE_23_FINAL_ACCEPTANCE: ACCEPTED
READY_FOR_MILESTONE_24: YES
```

---

# Final handoff

Return:

- repository;
- branch;
- starting commit;
- correction implementation commit(s);
- final remote commit;
- exact files changed;
- final tests/coverage;
- guardrails;
- M14–M22 regression status;
- M23 judge exact count;
- live exact cost equations and measured fixture deltas;
- capacity contention evidence;
- failed-cycle reservation-release evidence;
- pause/resume reservation equivalence;
- docs/stage-closing status;
- `_trash/` cleanup result;
- clean-worktree status.

Do not start M24.
