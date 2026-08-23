# Milestone 22 Report — Executable Per-Unit Design-Program Substrate

## Stage identity

- Stage: Milestone 22 (M22) — heritable representation milestone; no self-replication.
- Branch: `feature/milestone-1`
- Accepted starting commit (accepted M21 head): `a171caacf1b3bfec66409636e27fcc290ae1a4cd`
- Prompt-delivery head: `180e7089e10132d7f680d49576c67a230b1e0bc5`
- Implementation commit: `0e4602ec417807f7cf5e0ddd6a834b313d9b3ae0`
- M22A correction commit: `8191b187f99a7b7e0aed9db4f2ca768be840bd84`

## Design rationale

M19 made selected processor architecture fields vary through engine-side bounded field adjustment. M22 replaces the *representation that produces architecture*: each program-enabled unit carries an explicit bounded sequence of instruction records, and a deterministic in-project interpreter executes that sequence to produce a `NeuralArchitectureDescriptor`, which then flows through the unchanged M17/M19 neural construction and dimension-aware successor-transfer path.

The program is a developmental construction recipe, not a serialized descriptor: instructions mutate a construction state (set/adjust steps), so multiple distinct programs decode to the same descriptor — the property later open-ended work needs when program structure changes without phenotype change. No Python callables, source text, eval strings, or dynamic imports are representable in programs. No externally computed score touches programs at runtime; post-run analysis is strictly read-only.

## Instruction set and schema

- Program schema version: `1.0.0`; instruction-set version: `1`.
- Record: `(opcode: int, operand: float)` — finite operands only.
- Opcodes (10): `SET_HIDDEN`, `ADJUST_HIDDEN`, `SET_RECURRENCE_DENSITY`, `ADJUST_RECURRENCE_DENSITY`, `SET_PLASTICITY_RATE`, `ADJUST_PLASTICITY_RATE`, `ENABLE_PLASTICITY`, `DISABLE_PLASTICITY`, `NO_OP`, `END`.
- Reserved future opcodes (91–93) are absent from dispatch; they execute as documented unknown-opcode no-ops with fault records.
- Digest: sha256 over canonical JSON of schema version + instruction-set version + instruction pairs.
- Serialization is canonical JSON; digest mismatch on load raises `DesignProgramError`.

Program length bounds: minimum 1, maximum 128 (configurable via `program_min_length` / `program_max_length`). Variable length is intentional and preserved by every variation mechanism.

## Interpreter semantics

`DesignProgramInterpreter.execute(program, program_length_bounds)`:

1. Rejects wrong schema/instruction-set versions, empty programs, and out-of-bounds lengths with status `invalid_program`.
2. Executes sequentially with an explicit program counter and hard budget (`program_execution_budget`, default 512 executed instructions); budget exhaustion yields `budget_exhausted` with no decode.
3. Construction state starts at accepted defaults (hidden 16, density 1.0, rate from config, plasticity enabled). SET ops clamp operands into architecture bounds with `operand_clamped` fault records; ADJUST ops clamp results with `result_clamped` records.
4. Non-finite operands halt immediately with status `invalid_operand`.
5. Unknown opcodes are deterministic no-ops with `unknown_opcode_no_op` fault records.
6. `END` halts; running past the final record completes normally. Decode succeeds only on status `complete`, producing a descriptor whose identifier derives from the program digest.
7. No recursion, no jumps, no file/network/process access, no arbitrary code paths.

Canonical baseline program (compact form):

```text
SET_HIDDEN 8; ADJUST_HIDDEN 8;            -> hidden 16 (exact integer steps)
SET_RECURRENCE_DENSITY 0.5; ADJUST_RECURRENCE_DENSITY 0.5;  -> density 1.0 exact
SET_PLASTICITY_RATE <configured rate>; ENABLE_PLASTICITY; END
```

A second canonical form uses direct SETs only; both decode to identical descriptor fields, proving execution-through-state rather than descriptor serialization.

## Compatibility evidence (legacy descriptor path vs program path)

Documented projection: the M21 semantic snapshot minus representation-only metadata (per-unit design-program records/flags/status, the enabling configuration flag, and the architecture identifier string) is digested for comparison. The standard M21 deep digest is never weakened.

Live probe plus demonstration artifact (`design_program_compatibility_report.json`):

- Canonical program decodes exactly to hidden 16, density 1.0, rate 0.01, plasticity enabled — equal to the legacy descriptor fields.
- Twin units (same unit id/seed) share identical weight matrices, biases, and mask state across both paths.
- Identical action outputs under identical sensor inputs across decision ticks.
- Engine-level controlled run (fabrication disabled, 60 ticks, 4 units): shallow observation chains match at every sample and projected deep digests match at all 6 sampled ticks; the unweakened deep digest still distinguishes the two representations (program metadata is future-causal).

## Successor transfer and variation

In program-enabled mode the successor pipeline is: source program → deterministic seeded variation → interpreter → decoded successor descriptor → existing dimension-aware neural-state transfer (M19 `resize_state_for_successor` unchanged) → successor owns its own program. Descriptor variation is not applied to the same successor (no double mutation); legacy configurations keep the exact M19 path.

Variation mechanisms (deterministic under the stable-seed framework, per-index roll order deletion → substitution → operand change → insertion after index):

| Mechanism | Configured probability |
|---|---|
| Opcode substitution | 0.05 |
| Operand change | 0.05 |
| Insertion | 0.03 |
| Deletion | 0.03 |

Length bounds are respected throughout; structural value bounds are enforced only by interpreter clamps. Malformed or nonfunctional programs are never repaired toward the source: they either decode to whatever architecture their state describes (clamped) or fail assembly deterministically.

Malformed-program policy: interpretation failure after physical fabrication gates have passed aborts successor assembly — consumed costs stay consumed, a `FABRICATION_FAILED` event records cause `successor_program_invalid` with the execution status and program digest, and no successor is created.

## Construction cost equation

```text
program_execution_cost = program_base_cost (= 0.5)
                       + program_per_instruction_cost (= 0.01) x executed_instruction_count
```

Charged to the constructing unit during successor construction in program mode, alongside the unchanged M19 neural fabrication cost (hidden-unit + active-connection coefficients), so total successor burden is base fabrication + program execution + neural architecture cost. Monotonicity under the same operation class is tested; no quality-based reward exists.

## Deep-digest and checkpoint integration

The M21 snapshot now includes, per program-backed unit: schema version, instruction-set version, canonical instruction sequence, program digest, enabled flag, and recorded execution status. Output-only program analysis traces remain excluded from both the digest and checkpoint payloads (declared in the schema artifact and `FIELD_EXCLUSIONS`).

Proofs (live judge probes and tests): identical engines → identical digests; one opcode change flips the digest; one operand change flips the digest; output-only trace appends do not; checkpoint encode/decode preserves programs byte-semantically and continues identically.

## Process-isolated pause/resume equivalence

Demonstration via real subprocesses (run → file control request → pause → separate resume process → complete): pause applied at tick 650, resumed span 250 ticks, 9 common samples — deep-digest mismatch count **0**, shallow chain mismatch count **0** (`program_pause_resume_equivalence_report.json`).

During bring-up this check caught a genuine defect: resumed controllers defaulted digest advancement off (config default false while fresh runs force it on), freezing the M20 chain value after resume. Fixed in the CLI resume path (controller parity) and in `configs/milestone_22_pause_resume.toml`.

## Demonstration runs

Compatibility run (`configs/milestone_22_compatibility.toml`, variation disabled): compatible = true across all 6 samples.

Variable run (`configs/milestone_22_variable.toml`, 2400 ticks, 24 initial units):

```text
successful transfers        : 6 / 6 attempted
content-changed transfers   : 4
zero-change transfers       : 2   (phenotype-neutral capability)
length-changed transfers    : 2   (insertion/deletion active)
phenotype-changed transfers : 3
distinct decoded architectures: 4
out-of-bound architectures  : 0
interpreter crashes         : 0
variation operations seen   : substitution 2, operand change 3, deletion 3
```

Performance: variable run 80–189 ticks/s depending on phase (new semantics intentionally add successor-construction work; M21 primary throughput discipline is otherwise intact and no per-tick interpretation occurs). Decode throughput: **63,397 programs/s** canonical, 60,754 programs/s varied mean (`design_program_performance.json`). Execution happens only at initial/successor construction — never per tick — and no operation scales with world size.

## Tests and coverage

- Full suite: **614 passed**, 0 failed.
- Coverage: **79.78%** (threshold 77%).
- New modules/tests: `test_design_program.py` (26), `test_design_program_compatibility.py` (6), `test_milestone_22_judge.py` (8 incl. seven negative judge cases), `test_m22a_finalization.py` (6), `test_m21_tooling.py` retained.
- Guardrails: all checks pass.

## Regression judges (subprocess-captured on the M22 implementation)

M14 PASS, M15 PASS, M16 PASS, M17 PASS, M18 PASS, M19 PASS, M20 PASS, M21 PASS — capture artifact `output/demo_m22/regression/m14_m21_subprocess_results.json`. The M21 oracle artifacts were regenerated fresh on the start head before any M22 change (zero mismatches) and re-verified by the M21 judge afterward.

## Independent M22 judge

`python -m machine_sim.verification.milestone_22_judge output/demo_m22`

**M22_JUDGE_STATUS: PASS** — 31 checks, every check exactly PASS: schema, digest determinism (subprocess probe), bounded interpreter, instruction-set completeness, canonical descriptor compatibility (live), canonical behavior compatibility (artifact), per-unit ownership (live), successor transfer, variation determinism/mechanisms/bounds (live), causality (live opcode+operand+independence probes), dimension-changing transfer regression (live resize probe), execution cost monotonicity (live), malformed handling (live), deep-digest sensitivity (live), checkpoint roundtrip (live), pause/resume equivalence, read-only analysis (live), M21 oracle regression, M14–M21 regression chain, tests and coverage, wording screen, no-self-replication structural probe, variable-run demonstration completeness, plus the six M22A transactional-finalization probes (failure accounting, failure-event exactness, phantom-lineage prevention, exact program-cost accounting, exactly-once success finalization, failed-then-valid sequence).

## M22A correction — transactional fabrication finalization and lineage consistency

Independent review held M22 acceptance on one accounting/causality inconsistency: `FabricationEngine.fabricate()` finalized success-only state (success counter, lineage record, source successful-fabrication tick) before program interpretation could reject assembly, so a failed successor program left a success count and lineage edge with no unit behind them.

Correction (commit `8191b187f99a7b7e0aed9db4f2ca768be840bd84`): a deterministic two-phase boundary inside `FabricationEngine`.

```text
prepare_fabricate()   attempt phase + consumption/reservation phase
  - _fabrication_attempts += 1
  - prerequisite gates and cooldown policy unchanged
  - base power (30.0) and material consumed exactly once
  - placement reserved; successor ID reserved (documented option A:
    failed assembly leaves gaps; reserved IDs never appear in lineage)
  - NO success increment, NO lineage record, NO successful-fabrication tick

<engine program transfer + interpretation>

commit_fabrication(pending)   successful-construction commit, called only
  when an assembled successor is about to be registered
  - _fabrication_successes += 1 (exactly once)
  - exactly one LineageRecord appended
  - source _last_fabrication_tick advanced
```

`fabricate()` remains as an exact legacy wrapper (prepare + immediate commit) so every pre-M22A configuration keeps byte-identical outcomes; legacy equivalence is covered by the untouched M6–M21 fabrication/engine suites and judges.

Invalid-program accounting (live fixtures and live judge probes):

```text
attempts +1; successes +0; failures[successor_program_invalid] +1;
lineage +0; units +0; occupied cells +0;
_last_fabrication_tick unchanged; _last_fabrication_attempt_tick == attempt tick;
exactly one FABRICATION_FAILED(cause=successor_program_invalid) event;
zero FABRICATION_SUCCEEDED events;
power delta exactly -(base power + program execution cost);
material reduced exactly once by the base material cost.
```

Valid-program accounting: attempts/successes/lineage/units/occupancy each +1 exactly once, one success event, no program-invalid failure event, and the single lineage edge names the assembled successor's real identifier. The failed-then-valid sequence leaves no phantom generation or lineage edge: failed provisional IDs never appear in lineage records, and all recorded edges reference the one real successor at generation 1.

Transfer-trace rows mark candidate IDs explicitly (`successor_id_provisional: true`), so failed attempts are summarized separately without inflating successful transfer counts, lineage depth, or success rates. The read-only lineage analyzer already filtered on completed executions; its summaries now also expose failure counts distinctly through the fabrication subsystem summary.

Judge hardening: six new live checks (`m22a_program_failure_accounting_check`, `m22a_failure_event_exactness_check`, `m22a_phantom_lineage_prevention_check`, `m22a_program_cost_accounting_exact_check`, `m22a_success_finalization_once_check`, `m22a_failed_then_valid_sequence_check`) run deterministic invalid/valid scenarios on every judge invocation — 31 checks total, still exact-PASS-only.

## Known limitations

- One real fabrication evaluation per unit lifetime under accepted cooldown semantics caps natural transfer counts; demonstration configs compensate with more initial fabricators (no semantic change).
- Interpreter control flow is deliberately straight-line; loops/jumps await the copy-semantics milestone with budget proofs.
- Program identifiers derive from content digests; two identical programs on different units share an identifier string (identity metadata only).
- Checkpoint payload size remains dominated by full-grid encoding (deferred from M21).

## Self-replication statement

M22 does **not** implement unit-executed program copying, copy pointers, allocate/copy/divide operations, self-replication, replication-rate dynamics, replacement competition, or runtime self-modification of an active unit's program. The judge verifies structurally that the instruction set contains none of these operations and that reserved future opcodes fall through to the documented no-op policy.

## Next recommended milestone

Milestone 23 — Unit-Executed Program Copying and Successor Construction: extend the M22 executable substrate with bounded copy/allocation/division-like machine operations so producing a successor becomes behavior executed by the unit's program rather than an engine-scheduled capability, using the M21 performance discipline and the M22 digest/checkpoint machinery as the safety envelope.
