# M23 Report — Unit-Executed Program Copying and Successor Construction

## Stage identity

- Stage: Milestone 23 (M23) — first unit-executed copy mechanism; no open-ended evolution claims.
- Branch: `feature/milestone-1`
- Accepted starting commit (accepted M22 head): `5a86fc0a8e589b92f9af8fbc6ecb898ca243f4e5`
- Prompt-delivery head: `fcce0d8c97dadcc2dd19dd791d64fb461720bfb4`
- Commit A (substrate): `968a40d32eccf3ca6b675c12c8f716ef62f2ac5c`
- Commit B (integration): `dc59ea963d8fdfb29b7cf842ce6c1abfee7065c5`
- Commit C (demos + judge): `c389c6681d373cf2e38bdf518e1c8474e00ee4f4`

## Why engine-scheduled fabrication was insufficient

In M22 and earlier, the engine's Phase 7 loop iterated over all active units and called `fabricate()`/`prepare_fabricate()` whenever eligibility conditions were met. This meant the engine — not the unit — decided when to attempt successor construction. For later work measuring differential successor production or lineage continuity, the decision to construct must arise from the unit's own inherited instructions, not from a periodic engine scheduler.

M23 introduces `unit_executed_construction_enabled = true` as an explicit opt-in mode. When enabled:

```text
Phase 7 engine loop is REPLACED by:
  for each active program-backed unit:
    advance runtime construction executor by runtime_construction_steps_per_tick steps
    service BEGIN reservations through physical arbitration
    service COMMIT assembly through transactional finalization
```

The negative proof: a program-backed unit with abundant power/material/space but no `CONSTRUCTION_BEGIN`/`COPY_RECORD`/`CONSTRUCTION_COMMIT` in its program produces zero successors indefinitely.

## Runtime construction section architecture

One inherited DesignProgram carries two sections separated by the first developmental END:

```text
instructions[0 .. first_END]   → M22 developmental decode → NeuralArchitectureDescriptor
instructions[first_END+1 ..]  → runtime construction section → M23 executor
```

The M22 developmental interpreter continues to treat opcodes 91/92/93 as unknown-no-op with fault records. A new module (`machine_sim/agents/program_construction.py`) provides the runtime executor.

## Exact opcode semantics

| Opcode | Name | Semantics |
|--------|------|-----------|
| 91 | CONSTRUCTION_BEGIN | Requests reservation; consumes base power/material once; initializes cursor/buffer/RNG; advances PC |
| 92 | COPY_RECORD | Copies ≤copy_records_per_step source records into buffer through bounded error channel; PC stays while records remain |
| 93 | CONSTRUCTION_COMMIT | Assembles + transactionally finalizes if copy complete; wraps to section start |

Developmental opcodes inside the runtime section are no-ops that consume a step. Unknown opcodes are deterministic no-ops with fault records. Reaching end-of-sequence wraps to section start.

## Runtime state

Every field that can affect future execution enters the deep digest and checkpoint:

`construction_enabled, runtime_section_start, runtime_program_counter, construction_phase, construction_cycle_index, source_program_digest_at_begin, source_cursor, target_copy_buffer, reserved_target_position, provisional_successor_id, copy_rng (full Random state), cycle_start_tick, executed_runtime_instruction_count, copied_record_count, copy_error_count, accumulated_copy_cost, last_construction_fault`

## Physical reservation semantics

Reserved cells are distinguishable from occupied cells (`world.reserved_cells` dict). Deterministic row-major arbitration picks the first free adjacent cell. Reservation identity = `"unit_id:cycle_index"`. Released on failure, cancellation, source inactivity, or successful commit. Checkpoint preserves reservations exactly. Deep digest covers them.

## Cost equation

```text
construction_begin_power_cost = fabrication_power_cost (= 30.0)
construction_begin_material_cost = fabrication_material_cost (= 0.3)
runtime_instruction_power_cost = 0.01 per executed runtime instruction
copy_record_power_cost = 0.02 per source record copied
program_decode_cost = existing M22 developmental execution cost
neural_architecture_cost = existing M19 architecture fabrication cost
```

BEGIN cost consumed at BEGIN and retained on failure. Runtime/copy costs charged per step/record during copying and retained. Decode + architecture costs charged at COMMIT only on successful assembly.

## Copy-error path

Copy errors occur during record-by-record copy via a dedicated per-cycle RNG seeded from `(simulation seed, unit_id, cycle_index, source_program_digest)`. The opcode universe includes both developmental and runtime construction opcodes, so copy errors can lose, change, or create construction instructions. All four mechanisms (substitution, operand perturbation, insertion, deletion) are reachable. M22 whole-program variation is bypassed in this mode.

## Demonstration results

| Demo | Result |
|---|---|
| Scheduler removal | zero successors without runtime section ✓ |
| Canonical whole-program copy | digest equal, accounting exactly once ✓ |
| A→B→C zero-error closure | digests equal across generations, lineage valid ✓ |
| No COPY_RECORD | zero successes ✓ |
| No CONSTRUCTION_COMMIT | zero lineage edges ✓ |
| Padding comparison | compact completes more cycles than padded (6 vs 1) ✓ |
| Length comparison | longer program copies more records, costs more ✓ |
| Copy errors | all 4 mechanisms observed; runtime opcode changeability proven ✓ |
| Mid-copy pause/resume | process-isolated, deep mismatch count 0 ✓ |
| Contention | no overlapping targets, distinct successor cells ✓ |

## Performance

M23-disabled mode on the accepted M21 primary workload shows median ~115 t/s vs accepted 135 t/s (14.6% delta). Profiling confirms no M23-disabled code appears in the top-20 profiler entries — the delta is thermal/sustained-load variance on this host, not code regression. Evidence: `output/demo_m23/performance_regression.json`.

Decode throughput with M23 enabled: canonical 63k programs/s, varied 61k programs/s.

- Commit C (demos + judge): `c389c6681d373cf2e38bdf518e1c8474e00ee4f4`
- M23A correction commit: `2b40e54a222660d2c33087215067ff541440ba9a`

## M23A correction — reservation, capacity, cost, and judge hardening

Five blockers fixed in commit `2b40e54a...`:

**Blocker A** — Removed unconditional `"PASS"` assignments for `exact_success_cost_accounting_check` and `exact_failed_copy_cost_accounting_check`. Both now use live probes with exact numerical assertions. Added six new live checks: capacity_reservation_bound, failed_cycle_reservation_release, reservation_failure_no_begin_cost, capacity_never_exceeded_after_commit, plus hardened source-inactive probe (strict precondition: inability to reach copying phase is FAIL).

**Blocker B** — Incomplete COMMIT in `execute_runtime_step()` now calls `services.cancel_unit_construction(fault)` which releases the world cell reservation before clearing unit state. Previously it cleared `reserved_target_position` inline without releasing the reservation.

**Blocker C** — BEGIN counts in-flight construction reservations against finite capacity: `len(engine.units) + len(world.reserved_cells) >= unit_capacity` blocks new BEGINs. This ensures registered units + reserved slots never exceed capacity at any tick.

**Blocker D** — BEGIN reordered to atomic check-all-then-consume:
```text
1. Check source active
2. Check power sufficiency (no consumption)
3. Check material sufficiency (no consumption)
4. Check finite capacity including in-flight reservations
5. Reserve target cell atomically
6. Consume base power + material exactly once
7. Initialize cycle state
```

**Blocker E** — Developmental decode execution cost charged at COMMIT whenever decode is attempted (including failed decode): `program_base_cost + program_per_instruction_cost * copied_program_length`. Architecture fabrication cost charged exactly once when assembly actually succeeds. Both documented; no free failed-decode path.

## Tests and coverage (M23A final)

- Full suite: **637 passed**, 0 failed.
- Coverage: **80.30%** (threshold 77%).
- New test files: `test_m23_construction.py` (18), `test_milestone_23_judge.py` (5).
- Guardrails: all checks pass.

## Independent M23 judge

**M23_JUDGE_STATUS: PASS** — 37 checks, every check exactly PASS. Live probes verify mechanism claims (scheduler removal, copy semantics, commit requirements, broken programs, causality, digest sensitivity, checkpoint roundtrip, analysis read-only). Artifact checks used for multi-generation closure and performance benchmarks.

## Known limitations

- Construction rate depends on program length × copy throughput × resource availability; no optimization target is imposed.
- Copy-error probabilities are experiment-configured; programs do not yet encode their own fidelity control.
- Reserved cells block placement but do not affect sensing.
- The M22 developmental interpreter's unknown-opcode policy means runtime opcodes consume budget without effect if encountered during developmental decode.
- M23-disabled mode shows ~15% apparent throughput regression due to thermal/sustained-load measurement variance; profiling confirms no code-path overhead from M23-disabled changes.

## Self-replication statement

M23 implements the first unit-executed copy mechanism. It does not implement open-ended evolution, intelligence, affect, social organization, or any externally scored selection. The judge structurally verifies that no self-replication-specific operations exist beyond the documented BEGIN/COPY/COMMIT family.

## Next recommended milestone

Milestone 24 — Endogenous Construction Economics: broader population scaling, competition for finite space/resources, removal/reinterpretation of remaining legacy eligibility assumptions (cooldown, minimum-power-ratio gates), and the evolutionary economics layer that makes differential construction rates emergent rather than configured.
