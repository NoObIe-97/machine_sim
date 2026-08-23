# After Silicon — MiMo Milestone 23 Goal Spec: Unit-Executed Program Copying and Successor Construction

## Repository and branch

Repository: `https://github.com/NoObIe-97/machine_sim.git`

Branch: `feature/milestone-1`

Accepted Milestone 22 final remote head:

```text
5a86fc0a8e589b92f9af8fbc6ecb898ca243f4e5
```

M22 is accepted. Build M23 on the accepted M14–M22 runtime, M21 deep deterministic oracle, M22 executable per-unit design-program substrate, and M22A transactional fabrication-finalization boundary.

Before final handoff, invoke and satisfy:

```text
prompts/skills/stage_closing_chores.md
```

Do not start M24.

---

# Strategic transition

M22 made processor architecture a phenotype constructed by an executable per-unit design program, but the engine still decides when to attempt successor construction.

Current accepted path:

```text
engine fabrication phase
→ engine prerequisite gate / attempt
→ source program transfer + whole-program variation
→ design-program decode
→ successor assembly
→ transactional success commit
```

Required M23 path in the new unit-executed mode:

```text
unit-owned inherited program
→ unit runtime program executor
→ explicit construction-begin instruction
→ bounded instruction-by-instruction copy of the unit's own program
→ copied program validation / developmental decode
→ successor assembly
→ M22A transactional success commit
```

The engine may enforce world physics and arbitrate shared resources/space. It must no longer periodically decide that an eligible unit should produce a successor in M23 mode.

The copied instruction sequence must include the instructions responsible for copying and finalizing construction. Therefore construction capability itself is heritable, alterable, breakable, and capable of changing its execution cost and duration.

This is the defining M23 requirement.

---

# Scientific boundary

M23 is not an optimization or externally scored search milestone.

Do not introduce:

- an external score that chooses which program should persist;
- an optimizer that rewrites copy instructions;
- a post-run analyzer that modifies runtime programs;
- a preferred program length;
- a preferred construction rate;
- a repair path that restores damaged copy machinery toward an ancestor/canonical program;
- a runtime rule that gives more successful programs extra resources merely because they were successful;
- a hidden timer that causes the engine to initiate successor construction independently of program execution.

The simulator may define physical bounds, finite resources, deterministic arbitration, copy-error probabilities, instruction costs, world capacity, and malformed-state handling.

Observed differences in completed construction count or interval must arise from program execution plus local physical conditions, not a programmed fitness function.

---

# Terminology boundary

Committed runtime schemas, config keys, events, traces, reports, and judge artifacts must remain machine-native.

Prefer:

```text
runtime construction program
construction section
construction cycle
program copy
copy cursor
copy buffer
copy record
construction reservation
construction commit
construction fault
copy error
copy duration
copy cost
source program
successor program
program lineage
program closure
```

Avoid biological, anthropomorphic, social, cognitive, or teleological vocabulary in runtime artifacts. The project-level interpretation may discuss evolutionary implications outside runtime schemas, but committed machine artifacts must stay neutral.

---

# M23 architectural compatibility requirement

Do not destroy the accepted M22 developmental interpreter.

M22 currently has ten developmental opcodes in `machine_sim/agents/design_program.py` and reserved future opcode values `91`, `92`, and `93` that are deliberately unknown/no-op to the M22 developmental interpreter.

M23 should strongly prefer using those reserved values in a **separate runtime-construction interpreter/module**, while leaving the M22 developmental interpreter contract intact.

Recommended phase separation:

```text
same DesignProgram instruction sequence

phase 1: developmental decode
  instructions from index 0 through the first developmental END
  → existing M22 DesignProgramInterpreter
  → NeuralArchitectureDescriptor

phase 2: runtime construction section
  instructions after the first developmental END
  → new M23 bounded runtime-construction executor
```

Thus one inherited program contains both:

```text
developmental instructions
+
runtime construction/copy instructions
```

The M22 developmental interpreter should continue treating M23 runtime-copy opcodes as unknown/no-op if they are ever encountered by that interpreter. Do not add arbitrary code execution.

This phase separation is recommended because it permits M22 regression compatibility while making the same inherited program causally responsible for both processor construction and future program copying.

If you choose an equivalent design, document and prove the same properties.

---

# Required M23 construction instruction semantics

Use a minimal machine-native copy instruction family. A recommended mapping onto the existing reserved values is conceptually:

```text
91  CONSTRUCTION_BEGIN
92  COPY_RECORD
93  CONSTRUCTION_COMMIT
```

Exact symbolic names are implementation choices, but the semantics below are required.

## CONSTRUCTION_BEGIN

When executed by a unit runtime program:

- if no construction cycle is active, request a deterministic construction reservation from the engine/world;
- verify only the physical constraints required in M23 mode;
- reserve an adjacent target location deterministically;
- reserve a provisional successor ID;
- consume the configured base construction power/material cost exactly once;
- initialize copy cursor/buffer/runtime state;
- establish a dedicated deterministic per-cycle copy RNG state;
- record the construction-cycle start tick;
- do not increment success or append lineage.

If reservation cannot be created, record a machine-native begin failure and continue according to documented runtime-PC semantics. Do not fabricate a successor.

## COPY_RECORD

This is the core self-copy operation.

Each execution must process **at most one source instruction record** before yielding, unless a separately configured small bounded `copy_records_per_step` value is used and explicitly justified. The M23 canonical demonstration should use one copied source record per COPY_RECORD execution.

Required behavior:

```text
source_program[source_cursor]
→ bounded copy-error channel
→ zero / one / bounded-extra target records
→ target copy buffer
→ source_cursor advances
```

While source records remain, the runtime executor may keep the program counter on the COPY_RECORD instruction so the same inherited instruction performs repeated bounded work over multiple ticks. Once the source sequence is exhausted, execution advances to the next runtime instruction.

This stateful repeat is acceptable for M23 and avoids introducing unrestricted jumps before they are scientifically needed.

Copy the **entire source DesignProgram**, including its developmental section, developmental END marker, and runtime construction section. The successor must therefore receive the instructions that permit later construction cycles.

## CONSTRUCTION_COMMIT

This instruction may succeed only when:

- a construction reservation exists;
- the source copy is complete;
- the target buffer satisfies program-length/schema bounds;
- the copied program can be serialized canonically;
- the copied program's developmental phase produces a usable architecture;
- successor assembly succeeds.

Then and only then:

```text
copied target program
→ M22 developmental decode
→ successor architecture descriptor
→ existing M19 dimension-aware neural state transfer
→ successor object assembly
→ M22A commit_fabrication() success finalization
```

Success-only state must be committed exactly once.

On copied-program failure, decode failure, assembly failure, source loss, reservation invalidation, or any other pre-commit fault:

- no successful lineage edge;
- no success increment;
- no successor registration;
- no occupied target cell;
- no FABRICATION_SUCCEEDED-equivalent event;
- consumed physical/copy costs stay consumed according to the documented cost model;
- reservations are released deterministically;
- the failure cause is recorded once.

---

# Runtime executor

Create a focused M23 module, for example:

```text
machine_sim/agents/program_construction.py
```

Do not put arbitrary runtime-copy APIs into the M22 developmental interpreter merely to make the old module do two unrelated jobs.

A unit in M23 mode must carry explicit future-causal runtime construction state, e.g.:

```text
construction_enabled
runtime_section_start
runtime_program_counter
construction_cycle_index
construction_phase
source_program_digest_at_begin
source_cursor
target_copy_buffer
reserved_target_position
provisional_successor_id
copy_rng_state
cycle_start_tick
executed_runtime_instruction_count
copied_record_count
copy_error_count
accumulated_copy_cost
last_construction_fault
```

Exact fields are implementation choices, but every field that can affect future execution must be represented in the deep semantic state and checkpoint.

## Runtime stepping

Use a fixed bounded number of runtime construction instructions per active unit per simulation tick.

Recommended M23 default/demo:

```text
runtime_construction_steps_per_tick = 1
copy_records_per_copy_instruction = 1
```

This ensures construction duration is observable in world ticks.

The executor must never run unbounded loops inside one simulator tick.

## Program-counter behavior

A recommended policy:

- runtime execution begins at the first instruction after the first developmental `END`;
- ordinary developmental opcodes encountered in the runtime section are runtime no-ops that still consume a runtime instruction step/cost;
- `CONSTRUCTION_BEGIN` advances after its bounded work;
- `COPY_RECORD` remains on itself while records remain, then advances;
- `CONSTRUCTION_COMMIT` advances after success/failure;
- reaching the physical end of the instruction sequence wraps to the runtime-section start for a future construction cycle;
- a program with no valid runtime section simply never initiates construction.

This permits repeated construction cycles without an engine cooldown scheduler.

Document exact behavior and test it.

---

# Engine scheduling change — load-bearing requirement

M23 must add an explicit mode such as:

```text
unit_executed_construction_enabled = true
```

or equivalent.

When this mode is enabled:

**The existing Phase 7 engine loop must not iterate over all active units and call `fabricate()`/`prepare_fabricate()` because they are eligible.**

Instead, the engine should only service construction operations emitted/executed by each unit's runtime construction program.

The engine remains responsible for shared-world arbitration and transactional commit, not construction initiation.

Required negative proof:

> A program-backed unit with abundant power/material/space but no executable CONSTRUCTION_BEGIN/COPY_RECORD/CONSTRUCTION_COMMIT path must produce zero successors indefinitely under the controlled test horizon.

If the engine still produces a successor for such a unit, M23 fails.

---

# M23 physical prerequisite path

Do not route M23 unit-executed construction through the old periodic eligibility model unchanged.

Legacy configurations must preserve the old M22 fabrication path for regressions.

M23 mode should use a dedicated reservation/preparation path based on physical ability to pay and shared-world constraints.

At minimum:

```text
source unit is active
sufficient actual power exists to pay the begin/base cost
sufficient local material exists to pay the material cost
target placement is available
configured finite world/capacity limit is not exceeded
```

In M23 unit-executed mode, do **not** use the old `fabrication_interval` or `_last_fabrication_attempt_tick` cooldown as the mechanism that determines construction rate.

Also avoid an arbitrary minimum power-ratio/health threshold if the actual physical cost and ordinary active/critical-component semantics already determine viability. If compatibility requires retaining such gates temporarily, they must be disabled in the primary M23 scientific demonstration and explicitly documented as legacy-only constraints to be removed in M24.

Construction interval in the M23 primary demonstration should therefore be determined mainly by:

```text
runtime program path length
+ source program length
+ copy instruction throughput
+ local resource/power availability
+ target-space availability
```

not by an engine timer.

---

# Copy-error channel

M23 program variation must happen primarily **during instruction-by-instruction copy**, not as a whole-program engine-side mutation after the copy has completed.

In M23 mode, bypass the M22 whole-program `vary_design_program()` successor variation path to avoid double variation.

Support bounded deterministic per-copy mechanisms corresponding to:

```text
opcode substitution
operand perturbation
record insertion
record deletion
```

Copy errors must be driven by a dedicated deterministic per-construction RNG seeded from stable machine-native inputs and then preserved as future-causal RNG state through checkpoint/resume.

Recommended seed basis:

```text
simulation seed
source unit id
construction cycle index
source program digest
```

Do not use Python built-in `hash()`.

The copy-error opcode universe in M23 must include both:

```text
M22 developmental opcodes
+
M23 runtime construction opcodes
```

so runtime construction instructions can be lost, changed, or arise through copy error. Do not make construction opcodes permanently protected from variation.

However, all variation remains bounded by program min/max length and record schema constraints.

## Important distinction

The base copy-error probabilities may remain experiment-configured in M23. M23 does not yet require a program to encode its own error probability.

Later milestones may allow effective fidelity control to emerge through additional instructions or redundancy.

---

# Construction capability must be heritable and breakable

M23 must prove causally that construction success depends on inherited runtime program content.

Create controlled program fixtures with identical developmental phenotype where possible:

## Copy-capable canonical program

```text
canonical M22 developmental prefix
END
CONSTRUCTION_BEGIN
COPY_RECORD
CONSTRUCTION_COMMIT
```

or equivalent.

It must successfully copy the complete source program and produce a successor that carries the copied program.

## Broken program A — no COPY_RECORD

Same developmental phenotype, but runtime construction section cannot complete copying.

Expected: no successfully constructed successor within the controlled horizon.

## Broken program B — no CONSTRUCTION_COMMIT

Copy buffer may complete, but no successor is finalized.

Expected: no successful lineage edge.

## Slower neutral runtime program

Same developmental phenotype and same valid copy semantics, but contains extra runtime no-op steps.

Expected under matched resources/world/error-free copy:

- same decoded neural architecture;
- longer construction-cycle duration or lower completed-cycle rate than the compact copy-capable program.

This is not a fitness judgment; it is a mechanistic proof that inherited program structure changes copy throughput.

---

# Program-length cost must be real

A longer copied source program must require more COPY_RECORD executions than a shorter source program under `copy_records_per_step = 1`.

Required controlled comparison:

```text
short program and long program
same developmental phenotype
same runtime copy machinery
same source power/material/world conditions
copy errors disabled
```

Show:

```text
long_program.copied_record_count > short_program.copied_record_count
long_program.copy_duration_ticks >= short_program.copy_duration_ticks
long_program.copy_energy_cost > short_program.copy_energy_cost
```

unless exact scheduling creates an equal wall-tick duration due a documented multi-step-per-tick setting; for the canonical M23 demonstration use one step/record so duration should scale directly.

Do not reward short programs. Merely impose the actual operation burden.

---

# Runtime construction cost model

Define explicit simulation-semantic costs distinct from host CPU time.

A reasonable model:

```text
construction_begin_power_cost = existing base fabrication power cost
construction_begin_material_cost = existing base material cost
runtime_instruction_power_cost = bounded cost per executed runtime instruction
copy_record_power_cost = bounded incremental cost per source record copied
program_decode_cost = existing M22 developmental execution cost
neural_architecture_cost = existing M19 architecture fabrication cost
```

Avoid accidental double charging.

Document exactly when each term is charged and whether it is retained after failure.

The primary judge must use live probes to prove exact accounting on:

- successful cycle;
- invalid copied program;
- incomplete copy;
- source becoming inactive mid-cycle.

---

# Multiple construction cycles per source

The canonical M23 runtime program must be able to execute more than one construction cycle over a unit lifetime if resources and target space allow.

Do not preserve the current practical limitation where a unit receives only one meaningful construction opportunity because of engine cooldown semantics.

Required controlled demonstration:

- at least one source completes two distinct construction cycles in a resource-rich deterministic fixture, OR a live test proves the same path with exact accounting;
- each successful cycle creates exactly one lineage edge and one actual successor;
- no hidden engine timer is the limiting factor.

---

# Closure proof: copied units can copy

M23 must demonstrate program-copy closure beyond one transfer.

At minimum:

```text
unit A executes its runtime copy section
→ creates unit B with copied program
→ unit B executes the copied runtime copy section
→ creates unit C
```

Use copy errors disabled for this closure proof so the mechanism itself is isolated.

Required evidence:

- A/B/C program digests equal in the zero-error canonical closure run;
- B's construction was initiated/executed by B's runtime program state, not by an engine periodic fabrication loop;
- lineage contains A→B and B→C exactly;
- generation indices are coherent;
- each commit corresponds to a real registered unit.

This is the minimum M23 multi-generation self-copy demonstration.

---

# Copy errors must be capable of changing future construction capability

Use deterministic tests/fixtures, not forced primary-run outcomes, to prove at least one copy error can alter/remove a runtime construction opcode such that the copied successor remains a valid unit/program but no longer completes the same construction cycle.

Do not repair that copied program toward the source.

Also prove the converse representational capability: because the M23 opcode universe includes runtime construction opcodes, bounded copy errors can create/add such an opcode where program-length/schema bounds permit. This is a substrate-capability proof only; do not claim that construction capability emerged spontaneously from a long run in M23.

---

# ActionType.FABRICATE and neural controller

`ActionType.FABRICATE` already exists, while M17 intentionally mapped the neural `FABRICATE` output to `IDLE` because construction was engine-gated.

Do not make M23 depend on a hidden reintroduction of the old engine scheduler.

The preferred M23 design is that the runtime construction section executes as its own bounded per-unit machine process, analogous to the unit's inherited program machinery, so successor construction capability exists even independently of whether the neural controller emits a FABRICATE action.

If you choose to make neural `FABRICATE` intent gate/trigger runtime construction execution, then M23 must additionally prove:

- the engine never initiates without unit intent;
- the runtime copy program still performs the actual copy work;
- broken copy instructions remain unable to succeed even when intent is asserted;
- construction-rate differences are not dominated by a fixed engine cooldown;
- a deterministic non-neural compatibility path exists for testing the copy mechanism itself.

Do not simply map neural `FABRICATE` to a one-shot engine `fabricate()` call. That would not satisfy M23.

---

# Shared-world reservations and concurrency

Construction is now multi-tick, so placement reservation becomes future-causal.

Implement deterministic reservation semantics so two simultaneous construction cycles cannot both believe they own the same target cell.

Required:

- reserved cells are distinguishable from occupied cells;
- deterministic tie/arbitration order;
- reservation identity bound to the source/cycle;
- reservation released on failure, cancellation, source inactivity, or successful commit;
- a reservation does not create a lineage edge or registered unit;
- checkpoint/resume preserves reservations exactly;
- deep digest covers reservation state.

A concurrency live test must show two units contending for the same small placement region cannot create overlapping successors or duplicate commits.

---

# Source inactivity / interruption policy

Define deterministic behavior if a source unit becomes inactive during an unfinished construction cycle.

Recommended policy:

```text
source inactive
→ pending construction cycle fails/cancels
→ reservation released
→ partial copy buffer discarded or archived only as output evidence
→ consumed costs remain consumed
→ no success / lineage / unit registration
```

Do not allow an inactive source's executor to keep advancing unless explicitly justified as a physically independent subsystem.

Test the chosen policy.

---

# Deep semantic digest integration

M21's deep state oracle must cover every future-causal M23 field.

At minimum include:

```text
runtime construction enabled flag
runtime section start
runtime program counter
construction phase
construction cycle index
source program digest captured at begin
source cursor
target copy buffer canonical contents
reserved target position / reservation id
provisional successor id
per-cycle copy RNG state
executed runtime instruction count
copied record count
copy error count
accumulated semantic cost if future-causal
```

Required live sensitivity probes:

- changing runtime PC changes deep digest;
- changing source cursor changes digest;
- changing one copied buffer opcode changes digest;
- changing reservation target changes digest;
- changing copy RNG state changes digest;
- changing cycle index changes digest;
- output-only copy trace append does not change digest.

Do not weaken M21's normal digest.

---

# Checkpoint and process-isolated pause/resume

M23 must support pause/resume **mid-copy**, not only between completed cycles.

Required scenario:

```text
source has active reservation
source_cursor is strictly between 0 and source program length
copy buffer is partially populated
pause requested
checkpoint written
process exits
separate process resumes
copy continues
successor commit occurs
```

Compare against uninterrupted execution under identical config/seed.

Acceptance:

```text
deep digest mismatch count = 0
shallow M20 chain mismatch count = 0
final copied program digest equal
final lineage equal
final construction accounting equal
```

The checkpoint must not duplicate copy records, costs, reservations, or commits after resume.

---

# Legacy compatibility

M23 mode must be opt-in/configurable.

When disabled:

- legacy M22/M22A fabrication behavior remains unchanged;
- M22 design-program whole-program variation path remains unchanged;
- old configs do not silently gain runtime construction execution;
- M14–M22 regressions remain valid.

When enabled:

- no periodic engine fabrication scheduler initiates construction;
- M22 whole-program successor variation is bypassed;
- copy errors happen through the M23 copy channel;
- M22A transactional commit is retained as the success-finalization boundary.

---

# Performance discipline

M23 changes semantics, so exact M21 reference equivalence is not expected in M23-enabled runs.

However, M23-disabled runs must not suffer a major throughput regression merely because the code exists.

Required:

- benchmark the accepted M21 primary workload with M23 disabled before/after;
- target <= 10% throughput regression; >10% requires profiling evidence and explicit justification;
- runtime construction executor must be O(runtime steps) per active unit and must not scan the entire world per copy record;
- use existing placement/reservation indices where possible;
- no unbounded trace accumulation inside checkpoints.

Do not start another broad M21 optimization campaign in this milestone.

---

# M23 analysis artifacts

Create read-only M23 analysis tooling and bounded artifacts.

Suggested paths:

```text
output/demo_m23/construction_runtime_trace.jsonl
output/demo_m23/program_copy_trace.jsonl
output/demo_m23/construction_cycle_trace.jsonl
output/demo_m23/construction_lineage_summary.json
output/demo_m23/copy_error_summary.json
output/demo_m23/program_length_cost_comparison.json
output/demo_m23/copy_capability_comparison.json
output/demo_m23/canonical_closure_report.json
output/demo_m23/midcopy_pause_resume_equivalence_report.json
output/demo_m23/performance_regression.json
output/demo_m23/test_summary.json
output/demo_m23/milestone_23_judge_result.json
```

Runtime/copy trace rows should be bounded or sidecar-managed so checkpoints do not grow with cumulative observational history.

Suggested fields:

```text
tick
unit_id
construction_cycle_index
runtime_pc
runtime_opcode
phase
source_program_digest
source_cursor
target_buffer_length
reserved_position
copy_operation
copy_error_type
instruction_power_cost
copy_power_cost
cycle_start_tick
cycle_end_tick
cycle_status
successor_unit_id
successor_program_digest
```

Analysis must be read-only and must not feed results into runtime selection/programs.

---

# Required controlled demonstrations

M23 must produce reproducible evidence for all of the following.

## A. Engine-scheduler removal proof

M23 mode, abundant resources/space, program with no valid runtime construction section.

Expected:

```text
0 successful successors
0 successful lineage edges
0 engine-initiated construction commits
```

## B. Canonical copy-capable program

Zero copy error.

Expected:

- full source program copied record-for-record;
- copied program digest equals source digest;
- successful successor created;
- copied runtime construction instructions present in successor.

## C. Two-generation closure

A→B→C zero-error construction through unit runtime execution.

## D. Broken copy program

Remove COPY_RECORD or COMMIT from an otherwise same-phenotype program.

Expected no successful completion.

## E. Runtime-padding comparison

Compact vs extra-runtime-NO_OP program; same developmental phenotype.

Expected compact program has shorter cycle time/higher mechanistic completion rate under matched conditions.

## F. Program-length copy-cost comparison

Short vs long same-phenotype program, same copy section.

Expected longer program copies more records, takes more copy steps/ticks, and costs more.

## G. Copy-error demonstration

Enable bounded errors and prove copied program variation arises from per-record copy operations, not M22 post-copy whole-program variation.

## H. Mid-copy pause/resume

Separate-process resume with zero divergence.

## I. Concurrent reservation contention

No overlapping target reservation/commit.

---

# M23 independent judge

Create:

```text
machine_sim/verification/milestone_23_judge.py
```

Overall status is PASS only if every required check is exactly `PASS`.

No:

```text
PARTIAL
SKIP
UNKNOWN
NOT_FOUND
missing-evidence pass
default pass
```

Required checks should include at least:

1. `m23_mode_opt_in_check`
2. `runtime_construction_section_present_check`
3. `m22_developmental_interpreter_compatibility_check`
4. `engine_periodic_construction_disabled_in_m23_check`
5. `no_program_no_successor_check`
6. `construction_begin_reservation_check`
7. `copy_record_single_step_progress_check`
8. `whole_source_program_copy_check`
9. `construction_opcode_closure_check`
10. `construction_commit_requires_complete_copy_check`
11. `broken_copy_record_program_fails_check`
12. `broken_commit_program_fails_check`
13. `copy_capability_program_causality_check`
14. `program_length_copy_duration_check`
15. `program_length_copy_cost_check`
16. `runtime_padding_rate_difference_check`
17. `multiple_cycles_per_source_check`
18. `two_generation_copy_closure_check`
19. `copy_error_determinism_check`
20. `copy_error_mechanisms_check`
21. `copy_error_can_change_construction_opcode_check`
22. `m22_whole_program_variation_bypassed_check`
23. `exact_success_cost_accounting_check`
24. `exact_failed_copy_cost_accounting_check`
25. `source_inactive_cleanup_check`
26. `reservation_exclusivity_check`
27. `transactional_success_finalization_check`
28. `no_phantom_lineage_check`
29. `deep_digest_runtime_state_sensitivity_check`
30. `deep_digest_output_trace_independence_check`
31. `checkpoint_midcopy_roundtrip_check`
32. `process_isolated_midcopy_pause_resume_check`
33. `analysis_read_only_check`
34. `m23_disabled_performance_regression_check`
35. `m14_m15_m16_m17_m18_m19_m20_m21_m22_regression_check`
36. `tests_and_coverage_check`
37. `machine_native_wording_check`

Add more if required by implementation details.

Every scientifically important claim should have at least one live probe rather than artifact-presence-only evidence.

---

# Required failure-injection tests

Add tests that deliberately prove the judge fails when evidence is corrupted or the mechanism is bypassed.

At minimum:

- engine produces successor without runtime program initiation → judge FAIL;
- broken runtime copy program still produces successor → FAIL;
- copied program omits source runtime construction section unexpectedly → FAIL;
- copy duration does not reflect source program length in canonical one-record-per-step mode → FAIL;
- M22 whole-program variation is accidentally applied after copy → FAIL;
- incomplete copy commits success → FAIL;
- failed copy appends lineage → FAIL;
- duplicate commit creates two lineage edges → FAIL;
- reservation collision creates overlapping target → FAIL;
- mid-copy checkpoint resumes with duplicate/skipped copy record → FAIL;
- deep digest ignores copy cursor/buffer/RNG → FAIL;
- analysis mutates runtime state → FAIL;
- missing M14–M22 regression evidence → FAIL.

---

# M14–M22 regression preservation

Run all applicable previous judges and preserve their accepted behaviors.

Special M22 compatibility note:

M23 should extend construction behavior in a separate runtime module/phase so the M22 developmental interpreter remains historically valid. The M22 reserved copy opcode values may become meaningful to the M23 runtime interpreter while remaining unknown/no-op to the M22 developmental interpreter.

Do not weaken the M22 judge merely to make M23 pass.

If an old judge asserts a milestone-specific non-goal globally in a way that genuinely cannot coexist with M23, preserve its historical contract through mode/module scoping and document the resolution rather than deleting the check.

---

# M23 report

Create:

```text
docs/milestone_23_report.md
```

It must clearly explain:

- the accepted M22 starting commit;
- why engine-scheduled fabrication was insufficient for M23 goals;
- the runtime construction section architecture;
- exact M23 opcode semantics;
- how the same program carries developmental + copy machinery;
- runtime PC/cursor/buffer state;
- physical reservation semantics;
- exact cost equation;
- copy-error path;
- why M22 whole-program variation is bypassed in M23 mode;
- canonical copy closure A→B→C;
- broken-program controls;
- short/long and compact/padded mechanistic comparisons;
- mid-copy checkpoint/pause-resume proof;
- concurrency/reservation proof;
- performance impact when M23 is disabled;
- test count and coverage;
- M14–M22 regression results;
- independent M23 judge status;
- known limitations.

Do not claim open-ended evolution, intelligence, affect, or social organization from this engineering milestone.

---

# Known limitations M23 should explicitly preserve for later work

M23 is the first unit-executed copy mechanism, not the final evolutionary economics layer.

It is acceptable for M23 to retain, as explicit environment constraints:

- finite world size;
- finite configured capacity if not binding in the primary experiment;
- experiment-configured copy-error probabilities;
- bounded program length;
- fixed instruction semantic costs;
- simple deterministic placement policy.

M24 will address broader endogenous construction economics, population scaling, competition for finite space/resources, and removal/reinterpretation of remaining legacy eligibility assumptions.

Do not start M24 inside M23.

---

# Acceptance criteria

All must be true:

```text
M23_UNIT_EXECUTED_CONSTRUCTION_MODE_PRESENT: yes
M23_ENGINE_PERIODIC_FABRICATION_DISABLED_IN_NEW_MODE: yes
M23_SAME_INHERITED_PROGRAM_CONTAINS_DEVELOPMENT_AND_COPY_SECTION: yes
M23_COPY_INSTRUCTIONS_ARE_THEMSELVES_COPIED: yes
M23_CONSTRUCTION_CAPABILITY_DEPENDS_ON_PROGRAM_CONTENT: yes
M23_BROKEN_COPY_PROGRAM_CAN_FAIL_TO_PRODUCE_SUCCESSOR: yes
M23_COPY_DURATION_DEPENDS_ON_PROGRAM_EXECUTION: yes
M23_PROGRAM_LENGTH_INCREASES_COPY_WORK_AND_COST: yes
M23_MULTIPLE_CONSTRUCTION_CYCLES_PER_SOURCE_POSSIBLE: yes
M23_A_TO_B_TO_C_ZERO_ERROR_COPY_CLOSURE: yes
M23_COPY_ERRORS_OCCUR_DURING_RECORD_COPY: yes
M23_COPY_ERRORS_CAN_CHANGE_RUNTIME_CONSTRUCTION_OPCODES: yes
M23_M22_WHOLE_PROGRAM_VARIATION_BYPASSED_IN_NEW_MODE: yes
M23_TRANSACTIONAL_FINALIZATION_PRESERVED: yes
M23_NO_PHANTOM_LINEAGE: yes
M23_RESERVATIONS_DETERMINISTIC_AND_EXCLUSIVE: yes
M23_DEEP_DIGEST_COVERS_RUNTIME_COPY_STATE: yes
M23_MIDCOPY_CHECKPOINT_ROUNDTRIP: yes
M23_PROCESS_ISOLATED_MIDCOPY_PAUSE_RESUME_EQUIVALENCE: yes
M23_ANALYSIS_READ_ONLY: yes
M23_DISABLED_MODE_PERFORMANCE_REGRESSION_WITHIN_BOUND_OR_JUSTIFIED: yes
M14_M15_M16_M17_M18_M19_M20_M21_M22_REGRESSIONS_PASS: yes
M23_INDEPENDENT_JUDGE_EXACT_PASS_ONLY: yes
M23_STAGE_CLOSING_CHORES_SATISFIED: yes
MILESTONE_23_STATUS: ACCEPTED
READY_FOR_MILESTONE_24: YES
```

---

# Suggested implementation sequence

Use separate commits where practical.

## Commit A — runtime copy oracle/substrate

- M23 runtime construction state;
- separate runtime construction interpreter;
- reserved copy-op semantics;
- deep-digest/checkpoint fields;
- unit tests for bounded stepping;
- no engine scheduling change yet if that makes review safer.

Run tests.

## Commit B — unit-executed integration

- M23 mode flag;
- disable periodic engine fabrication in M23 mode;
- construction reservation service;
- copy buffer and per-record error channel;
- transactional assembly/commit;
- legacy path preserved.

Run tests/regressions.

## Commit C — controlled demonstrations + judge

- closure run;
- broken-program controls;
- length/cost comparison;
- padded-runtime comparison;
- copy-error demonstration;
- contention test;
- mid-copy pause/resume;
- independent strict judge.

## Commit D — stage closing

- report;
- review package;
- final tests/coverage/regressions;
- stage-closing skill;
- push clean tree.

---

# Final handoff requirements

Return a `GITHUB_HANDOFF` containing:

- repository;
- branch;
- accepted starting commit;
- implementation commit(s);
- final remote commit;
- files changed;
- full test count;
- coverage;
- guardrail result;
- M14–M22 regression statuses;
- exact M23 judge count/status;
- engine-periodic-fabrication-disabled assertion for M23 mode;
- A→B→C closure evidence;
- broken-copy-program evidence;
- compact-vs-padded comparison;
- short-vs-long program copy duration/cost comparison;
- copy-error mechanism evidence;
- reservation/concurrency evidence;
- mid-copy pause/resume mismatch counts;
- performance regression evidence with M23 disabled;
- clean-worktree state;
- stage-closing result.

Do not start M24.
