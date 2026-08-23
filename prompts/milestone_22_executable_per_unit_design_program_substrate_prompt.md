# After Silicon — MiMo Milestone 22 Goal Spec: Executable Per-Unit Design-Program Substrate

## Repository and branch

Repository: `https://github.com/NoObIe-97/machine_sim.git`

Branch: `feature/milestone-1`

Accepted Milestone 21 remote head:

```text
a171caacf1b3bfec66409636e27fcc290ae1a4cd
```

Milestone 21 is accepted. Build M22 on the accepted M14–M21 runtime, neural controller, successor-transferred architecture, checkpoint/pause/resume system, and deep deterministic semantic-state oracle.

Before final handoff, invoke and satisfy:

```text
prompts/skills/stage_closing_chores.md
```

Do not start M23.

---

# Strategic direction

M17 introduced an internal recurrent neural processor. M19 made selected processor architecture fields vary across successor construction. M21 made aggressive refactoring safe by freezing a deep future-causal semantic oracle.

M22 changes the representation that produces processor architecture.

Current conceptual path:

```text
engine-side architecture descriptor
→ bounded field variation
→ successor processor
```

Required M22 path:

```text
per-unit executable design program
→ bounded deterministic interpreter
→ decoded construction state
→ NeuralArchitectureDescriptor
→ existing neural processor construction
```

The design program is a heritable machine-native instruction sequence. It is not a neural network, not a language model, and not arbitrary Python. It must be represented as explicit bounded instruction records interpreted by an in-project deterministic virtual machine.

M22 is a developmental-program substrate milestone. It is intentionally not yet a self-replication milestone.

The most important compatibility requirement is:

> A canonical M22 program must be able to construct the same neural architecture as the accepted M19/M21 descriptor path, and the resulting unit must be semantically equivalent under the M21 deep digest when program metadata is excluded from the compatibility comparison.

Only after that compatibility path is proven should M22 enable bounded successor variation of the design program and demonstrate that changed programs can construct changed neural architectures.

---

# Scientific boundary

M22 must not externally choose a preferred program or architecture.

The simulator may define:

- the instruction set,
- legal operand ranges,
- execution limits,
- physical/resource costs,
- mutation/variation probabilities,
- deterministic error handling,
- architectural bounds.

It must not define:

- which final architecture is superior,
- which instruction sequence should persist,
- an optimization target for architecture complexity,
- an externally calculated score that changes the program during runtime.

Program variation must occur during successor construction through deterministic seeded bounded changes. Runtime post-run analysis remains read-only.

---

# Terminology boundary

Use machine-native terminology in committed runtime code, config keys, schemas, reports, and artifacts.

Prefer terms such as:

```text
design program
instruction record
instruction sequence
program counter
execution budget
construction register
construction state
program transfer
program variation
successor program
program length
program digest
program lineage
program-decoded architecture
```

Avoid anthropomorphic/social/biological wording in runtime artifacts. Do not introduce terms such as genome, chromosome, organism, parent, child, offspring, reproduction, species, fitness, brain, emotion, society, intelligence, language, meaning, knowledge, teaching, or learning into machine-native runtime schemas.

Those interpretations belong only in external scientific discussion, not runtime semantics.

---

# M22 scope

M22 must implement all of the following:

1. a per-unit immutable-or-explicitly-versioned design-program representation;
2. a deterministic bounded interpreter;
3. a minimal instruction set that can construct the accepted neural architecture descriptor;
4. execution limits and malformed-program handling;
5. canonical baseline programs corresponding to accepted fixed architectures;
6. program-to-architecture decoding;
7. compatibility mode against the current descriptor path;
8. successor transfer of the design program;
9. bounded deterministic program variation during successor construction;
10. insertion, deletion, substitution, and operand mutation support, all bounded;
11. deterministic handling of no-op/unknown/invalid instructions according to a documented policy;
12. program execution and construction cost accounting;
13. program lineage and program-length/operation-distribution artifacts;
14. M21 deep-digest integration for future-causal program state;
15. checkpoint/pause/resume preservation of program state;
16. exact-PASS-only M22 independent judge;
17. M14–M21 regression preservation.

---

# Explicit non-goals

M22 must not implement:

```text
unit-executed program copying
copy pointer machinery
allocate-copy-divide instruction semantics
self-replication
replication-rate evolution
replacement competition
new population replacement rules
implicit selection redesign
rewarded task ladders
neuromodulatory affect substrate
observer-level affect labels
OOD competence probes
collective-organization labels
transformers / token models / LLMs
runtime self-modification of an already active unit's design program
external architecture optimization
```

Those belong to later milestones.

M23 is reserved for unit-executed successor construction and self-copy semantics using the M22 program substrate.

---

# Phase 0 — preserve the accepted M21 oracle

Before introducing design-program semantics:

1. run the current M21 reference/equivalence suite;
2. record the accepted M21 deep-digest schema and reference artifacts;
3. ensure all M14–M21 judges pass on the starting head;
4. add the design-program fields to the deep semantic-state schema as future-causal state;
5. prove output-only program-analysis artifacts do not affect the digest.

Do not modify the existing M21 frozen reference files in place. M22 may create new M22-specific compatibility references.

---

# Phase 1 — design-program representation

Create a focused module such as:

```text
machine_sim/agents/design_program.py
```

Exact names are implementation choices, but the public concepts must be explicit and testable.

## Program structure

Use a bounded sequence of instruction records. A reasonable abstract representation is:

```text
DesignProgram
  schema_version
  instruction_set_version
  instructions[]
  program_digest
```

Each instruction must have:

```text
opcode
bounded operands
```

Do not store executable Python callables, source code, eval strings, lambdas, imports, or dynamically resolved module paths in program records.

Program serialization must be deterministic and checkpoint-safe.

## Length bounds

Provide configurable but guarded bounds such as:

```text
min_program_length >= 1
initial/canonical length: implementation-defined
max_program_length: bounded, e.g. 128 or 256 for M22
```

Do not hard-code an architectural assumption that future programs must remain fixed-length.

M22 should intentionally support variable program length because later open-ended work depends on the hereditary representation being able to grow or contract.

---

# Phase 2 — bounded deterministic interpreter

Implement a small deterministic interpreter, for example:

```text
DesignProgramInterpreter
```

The interpreter must:

- execute instructions sequentially;
- maintain an explicit program counter;
- expose a bounded execution budget;
- use no recursion;
- perform no file/network/process operations;
- call no arbitrary Python functions;
- allocate only bounded in-memory construction state;
- produce deterministic output for the same program/config/seed;
- terminate cleanly on budget exhaustion;
- record a structured execution result.

## No unbounded control flow in M22

For M22, prefer a straight-line developmental program or only tightly bounded control flow.

Do not introduce unrestricted jumps/loops unless there is a compelling reason and a hard execution-budget proof. The future self-copy VM can extend control-flow semantics later.

The interpreter should return an object such as:

```text
ProgramExecutionResult
  status
  executed_instruction_count
  final_program_counter
  construction_state
  decoded_architecture
  execution_cost
  fault_records
```

Statuses should be machine-native and explicit, for example:

```text
complete
budget_exhausted
invalid_operand
invalid_program
```

Unknown opcode handling must be specified. Recommended M22 policy: unknown opcodes are deterministic no-ops with a fault record, unless the schema version makes them structurally invalid. This allows later mutation experiments to produce nonfunctional or partially functional programs without crashing the simulator.

---

# Phase 3 — minimal construction instruction set

The instruction set should be intentionally small and compositional.

It must be sufficient to construct the current `NeuralArchitectureDescriptor` fields at minimum:

```text
hidden_size
recurrent_density
plasticity_rate
plasticity_enabled
```

The exact opcodes are your design decision, but prefer operations that modify a construction state rather than one opcode that directly embeds a complete final descriptor.

For example, the instruction family may contain operations conceptually equivalent to:

```text
SET_HIDDEN
ADJUST_HIDDEN
SET_RECURRENCE_DENSITY
ADJUST_RECURRENCE_DENSITY
SET_PLASTICITY_RATE
ADJUST_PLASTICITY_RATE
ENABLE_PLASTICITY
DISABLE_PLASTICITY
NO_OP
END
```

These names are examples only. Implement a clean machine-native set consistent with project style.

Important requirement:

> Avoid making the instruction encoding merely a verbose serialization of the final descriptor.

The program must actually execute through a construction state. Multiple distinct valid programs should be capable of producing the same descriptor.

That property is important because future evolutionary change should be able to alter program structure without requiring every program edit to alter the phenotype.

---

# Phase 4 — canonical compatibility programs

Create deterministic canonical programs that reproduce accepted architectures.

At minimum include:

```text
canonical baseline corresponding to hidden_size=16,
recurrent_density matching the accepted baseline,
plasticity_rate=0.01,
plasticity enabled
```

Also include canonical programs for a few M18/M19 variants where useful.

## Required compatibility test

For the canonical baseline:

```text
legacy descriptor construction
vs
program-decoded descriptor construction
```

must produce exactly equivalent descriptor fields.

Then instantiate equivalent units using both paths and verify:

- same neural dimensions;
- same recurrent mask when supplied the same deterministic seed context;
- same overlapping/init neural parameters under the same seed policy;
- same action outputs under identical local inputs;
- same future-causal runtime trajectory for a controlled compatibility run.

Because program metadata itself is new future-causal state, the full M22 deep digest will differ between legacy-only and program-backed units. Therefore implement a documented compatibility projection or architecture/runtime equivalence comparison that excludes representation-only program metadata while comparing the constructed phenotype and downstream behavior.

Do not weaken the standard M21 deep digest for normal M22 runs.

---

# Phase 5 — integrate program ownership into units

Every program-enabled unit must carry its own design program.

The current neural architecture descriptor remains the decoded construction result/phenotype.

Recommended conceptual state:

```text
unit.design_program
unit.neural_architecture_descriptor
unit.neural_controller
```

The descriptor must no longer be the only hereditary source of architecture when M22 program mode is enabled.

Program mode should be configurable so accepted earlier milestone configurations remain backward-compatible.

Do not silently reinterpret old configurations.

---

# Phase 6 — successor program transfer

When a program-enabled unit constructs a successor under the existing M21 fabrication semantics:

```text
source design program
→ deterministic transfer
→ bounded program variation
→ successor design program
→ interpreter execution
→ successor architecture descriptor
→ existing dimension-aware neural-state transfer
```

The accepted M19 dimension-changing state-transfer behavior must remain intact after the descriptor is decoded from the successor program.

The current engine-side architecture variation path should remain available for legacy configurations, but program-enabled M22 mode must not apply both descriptor variation and program variation to the same successor unless explicitly required by a controlled comparison.

Avoid double mutation.

---

# Phase 7 — bounded program variation

Add deterministic seeded program variation during successor construction.

Support at least:

```text
instruction substitution
operand mutation
instruction insertion
instruction deletion
```

Each mechanism must have configurable probabilities and bounded magnitude/rules.

## Variation requirements

- deterministic under `stable_seed()` or the accepted deterministic seed framework;
- no Python built-in `hash()`;
- respect min/max program length;
- preserve schema validity;
- never crash on mutated instructions;
- record exact source and successor program digests;
- record variation operations in order;
- allow a zero-variation transfer;
- allow phenotype-neutral program changes;
- allow phenotype-changing program changes;
- allow nonfunctional/invalid-output programs to be represented and handled through normal machine-native consequences rather than repaired by an optimizer.

Do not automatically repair a changed program toward the source architecture merely because its output is poor.

Structural safety bounds such as clamping hidden size to the accepted architecture bounds are allowed and required.

---

# Phase 8 — construction cost

Program execution must not be computationally free in simulation semantics.

Introduce a bounded construction-program cost model that is separate from host CPU benchmarking.

A reasonable form is:

```text
program_execution_cost
  = base_program_cost
  + per_instruction_cost * executed_instruction_count
  + optional construction-operation costs
```

This cost should feed into the existing successor-construction resource accounting in program-enabled mode.

Do not create a reward for longer or shorter programs. Merely expose their physical/resource burden.

Preserve the existing neural architecture fabrication cost from M19, so total successor cost can conceptually include:

```text
base fabrication cost
+ program execution cost
+ neural hidden-unit cost
+ active-connection cost
```

Document the exact equation.

---

# Phase 9 — malformed and nonfunctional programs

M22 must explicitly define what happens when a transferred/varied program does not decode into a usable architecture.

Do not crash the run.

Use a bounded deterministic policy such as:

```text
program execution result invalid
→ successor construction attempt fails with a machine-native cause
→ source pays only the costs that the physical model says were already consumed
→ failure is recorded
```

or another clearly documented resource-consistent policy.

Do not automatically substitute the source descriptor as a hidden fallback, because that would erase the evolutionary consequence of program damage.

A canonical empty/fault-heavy program must be tested.

---

# Phase 10 — deterministic checkpoint and digest integration

The design program is future-causal state.

Update M21 semantic-state snapshots to include at least:

```text
program schema/instruction-set version
instruction sequence in canonical order
program digest
program execution-related hereditary/config state that affects successors
```

Output-only execution traces/analysis summaries may remain excluded if proven non-causal.

Required proofs:

1. two identical program-backed engines have identical deep digests;
2. changing one opcode changes the deep digest;
3. changing one operand changes the deep digest;
4. changing only an output analysis trace does not change the digest;
5. checkpoint encode/decode preserves design programs byte-semantically;
6. pause/resume in a separate process preserves program-backed future trajectories.

---

# Phase 11 — analysis artifacts

Create read-only analysis tooling for program evolution/variation.

Suggested module:

```text
machine_sim/analysis/design_program_lineage.py
```

The analyzer must not write into runtime state.

Produce bounded artifacts such as:

```text
output/demo_m22/design_program_initial_state.jsonl
output/demo_m22/design_program_transfer_trace.jsonl
output/demo_m22/design_program_execution_trace.jsonl
output/demo_m22/design_program_distribution_trace.jsonl
output/demo_m22/design_program_lineage_summary.json
output/demo_m22/design_program_compatibility_report.json
output/demo_m22/design_program_variation_summary.json
```

Suggested fields include:

```text
tick
source_unit_id
successor_unit_id
source_program_digest
successor_program_digest
source_program_length
successor_program_length
variation_operations
execution_status
executed_instruction_count
execution_cost
decoded_hidden_size
decoded_recurrent_density
decoded_plasticity_rate
decoded_plasticity_enabled
phenotype_changed
```

Distribution summaries should report program length and opcode frequency without assigning fitness or quality labels.

---

# Phase 12 — M22 controlled demonstrations

Create an M22 configuration that exercises the full path with enough successor transfers to demonstrate program inheritance and variation.

Required demonstrations:

## A. Canonical compatibility run

Program variation disabled.

Canonical program decodes to the accepted baseline architecture.

Show descriptor and behavioral compatibility against the legacy architecture path under controlled conditions.

## B. Variable-program run

Program variation enabled.

Require evidence of:

- at least several successful program transfers;
- at least one zero-change transfer;
- at least one program-content change;
- at least one program-length change if insertion/deletion probabilities are nonzero;
- at least one phenotype-neutral changed program if naturally produced by the configured deterministic run OR a dedicated deterministic test fixture proving this capability;
- at least one phenotype-changing program;
- at least two distinct decoded architecture descriptors across the run;
- no out-of-bound architecture values;
- no interpreter crash.

Do not force the runtime demonstration to show every rare mutation class if doing so would require artificial outcome steering; dedicated deterministic tests can prove rare variation mechanisms.

---

# Phase 13 — performance discipline

M22 adds interpreter overhead, but must not discard M21 performance discipline.

Benchmark at least:

```text
program decode throughput (programs/s)
canonical program decode cost
varied program decode cost distribution
end-to-end M22 demo ticks/s
```

Do not require M22 to match M21's exact primary throughput because new semantics are intentionally being added.

However:

- canonical program execution must be bounded and practical;
- no per-tick program interpretation is allowed unless explicitly necessary;
- normal design-program execution should occur during initial construction and successor construction, not every simulation tick;
- no O(world_size) program operation is acceptable;
- no hidden O(program_length^2) algorithm should be introduced for ordinary straight-line decoding without justification.

The 1,000-unit M21 bottleneck in proximity/signal handling is not an M22 optimization target.

---

# Required tests

Add focused tests covering at least:

## Program representation

- canonical deterministic serialization;
- program digest stability across processes;
- variable program lengths;
- min/max length enforcement;
- invalid schema rejection.

## Interpreter

- deterministic execution;
- execution budget enforcement;
- all opcodes;
- operand clamping/validation;
- unknown opcode policy;
- END/termination behavior;
- no-op behavior;
- no arbitrary-code execution path.

## Compatibility

- canonical baseline program decodes to accepted baseline descriptor;
- descriptor equality against legacy path;
- deterministic processor construction equivalence;
- controlled downstream behavior equivalence.

## Variation

- zero variation;
- substitution;
- operand mutation;
- insertion;
- deletion;
- deterministic variation under same seed;
- different seed can produce different variation;
- bounds preserved;
- program digest changes when content changes;
- neutral-content change capability;
- phenotype-changing capability.

## Successor integration

- source program transfer;
- successor program ownership;
- descriptor generated from successor program;
- dimension-changing neural state transfer still correct;
- no double descriptor+program variation in program mode;
- malformed program failure path.

## Cost

- instruction-count cost monotonicity under same operation class;
- total fabrication accounting includes program and neural architecture costs;
- zero hidden reward/bonus based on quality labels.

## Digest/checkpoint

- design-program future-causal sensitivity;
- analysis-trace independence;
- checkpoint round-trip;
- process-isolated pause/resume equivalence.

## Judge negative tests

Missing or malformed evidence for any required M22 acceptance check must make the judge fail.

---

# M22 independent judge

Create:

```text
machine_sim/verification/milestone_22_judge.py
```

The judge must use exact-PASS-only semantics.

No required check may yield PARTIAL, SKIP, UNKNOWN, NOT_FOUND, soft-default PASS, or missing-evidence PASS.

Suggested required checks:

1. `design_program_schema_check`
2. `program_digest_determinism_check`
3. `bounded_interpreter_check`
4. `instruction_set_completeness_check`
5. `canonical_descriptor_compatibility_check`
6. `canonical_behavior_compatibility_check`
7. `per_unit_program_ownership_check`
8. `successor_program_transfer_check`
9. `program_variation_determinism_check`
10. `program_insertion_deletion_substitution_check`
11. `program_bounds_check`
12. `program_to_architecture_causality_check`
13. `dimension_changing_transfer_regression_check`
14. `program_execution_cost_check`
15. `malformed_program_handling_check`
16. `deep_digest_program_sensitivity_check`
17. `checkpoint_program_roundtrip_check`
18. `pause_resume_program_equivalence_check`
19. `analysis_read_only_check`
20. `m21_oracle_regression_check`
21. `m14_m15_m16_m17_m18_m19_m20_m21_regression_check`
22. `tests_and_coverage_check`
23. `machine_native_wording_check`
24. `no_self_replication_semantics_check`

The judge may use live deterministic probes where appropriate instead of trusting summary booleans.

Overall status:

```text
M22_JUDGE_STATUS = PASS
```

only if every required check is exactly `PASS`.

---

# Required artifacts

At minimum, produce:

```text
output/demo_m22/design_program_initial_state.jsonl
output/demo_m22/design_program_transfer_trace.jsonl
output/demo_m22/design_program_execution_trace.jsonl
output/demo_m22/design_program_distribution_trace.jsonl
output/demo_m22/design_program_lineage_summary.json
output/demo_m22/design_program_compatibility_report.json
output/demo_m22/design_program_variation_summary.json
output/demo_m22/design_program_run_summary.json
output/demo_m22/program_pause_resume_equivalence_report.json
output/demo_m22/regression/m14_m21_subprocess_results.json
output/demo_m22/test_summary.json
output/demo_m22/milestone_22_judge_result.json
```

Use bounded artifact sizes and preserve the M21 checkpoint/trace separation.

---

# Regression requirements

Before M22 acceptance, rerun all required accepted regression judges:

```text
M14 PASS
M15 PASS
M16 PASS
M17 PASS
M18 PASS
M19 PASS
M20 PASS
M21 PASS
```

M21 deep-state oracle behavior, sparse-world optimization, checkpoint trace separation, and M20 pause/resume control must remain operational.

Do not modify old artifact files merely to make old judges pass unless the new runtime genuinely remains compatible.

---

# Documentation requirements

Create/update:

```text
docs/milestone_22_report.md
docs/review_package.md
```

The report must include:

- design rationale;
- instruction-set version and schema;
- exact interpreter semantics;
- execution-budget rules;
- canonical program examples in compact form;
- compatibility evidence;
- variation mechanisms and probabilities;
- program length bounds;
- malformed-program policy;
- construction cost equation;
- checkpoint/digest integration;
- program lineage evidence;
- performance measurements;
- tests and coverage;
- M14–M22 judge results;
- known limitations;
- explicit statement that self-copy/self-replication is not implemented in M22;
- recommended M23 direction.

Recommended M23 wording:

```text
Milestone 23 — Unit-Executed Program Copying and Successor Construction
```

M23 should extend the M22 executable design-program substrate with bounded copy/allocation/division-like machine operations so the ability to produce a successor becomes behavior executed by the unit rather than an engine-scheduled capability.

Do not implement that in M22.

---

# Stage-closing workflow

Before final handoff:

1. run full tests;
2. run coverage and keep project threshold satisfied;
3. run guardrails;
4. run the canonical compatibility demonstration;
5. run the variable-program demonstration;
6. run process-isolated pause/resume program equivalence;
7. run M14–M21 regression judges;
8. run M22 judge;
9. invoke `prompts/skills/stage_closing_chores.md`;
10. update milestone report and review package with actual final values;
11. ensure no stale `(pending)`, old test counts, old coverage values, or intermediate commit IDs are reported as final;
12. push a clean working tree.

---

# Required final handoff format

Return a concise handoff containing at least:

```text
GITHUB_HANDOFF:
    repository: NoObIe-97/machine_sim
    branch: feature/milestone-1
    commit_sha: <final remote hash>
    summary: M22 Executable Per-Unit Design-Program Substrate — COMPLETE

    accepted_starting_commit: a171caacf1b3bfec66409636e27fcc290ae1a4cd
    implementation_commit: <hash>
    final_remote_commit: <hash>

    tests: <passed>/<total>
    coverage: <percent>
    guardrails: PASS

    M14_JUDGE_STATUS: PASS
    M15_JUDGE_STATUS: PASS
    M16_JUDGE_STATUS: PASS
    M17_JUDGE_STATUS: PASS
    M18_JUDGE_STATUS: PASS
    M19_JUDGE_STATUS: PASS
    M20_JUDGE_STATUS: PASS
    M21_JUDGE_STATUS: PASS
    M22_JUDGE_STATUS: PASS

    M22_CANONICAL_PROGRAM_DECODES_BASELINE_ARCHITECTURE: yes
    M22_CANONICAL_BEHAVIOR_COMPATIBILITY: yes
    M22_PER_UNIT_PROGRAM_PRESENT: yes
    M22_PROGRAM_TRANSFER_PRESENT: yes
    M22_PROGRAM_VARIATION_PRESENT: yes
    M22_INSERTION_DELETION_SUBSTITUTION_SUPPORTED: yes
    M22_PROGRAM_LENGTH_VARIABLE: yes
    M22_PROGRAM_EXECUTION_BOUNDED: yes
    M22_PROGRAM_COST_ACCOUNTED: yes
    M22_DEEP_DIGEST_INCLUDES_PROGRAM: yes
    M22_PROCESS_ISOLATED_PAUSE_RESUME_EQUIVALENCE: yes
    M22_ANALYSIS_READ_ONLY: yes
    M22_SELF_REPLICATION_NOT_IMPLEMENTED: yes
    M14_M15_M16_M17_M18_M19_M20_M21_REGRESSIONS_STILL_PASS: yes
    MILESTONE_22_STATUS: ACCEPTED
    READY_FOR_MILESTONE_23: YES
```

Do not claim ACCEPTED unless the independent M22 judge passes every required check exactly and all required regressions pass.
