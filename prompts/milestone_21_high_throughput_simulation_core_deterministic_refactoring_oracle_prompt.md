# After Silicon — MiMo Milestone 21 Goal Spec: High-Throughput Simulation Core and Deep Deterministic Refactoring Oracle

## Repository and branch

Repository: `https://github.com/NoObIe-97/machine_sim.git`

Branch: `feature/milestone-1`

Accepted pre-prompt repository head:

```text
ab20cdc4f2ea63c2a42f1ffb58c52568afebd487
```

Milestone 20 is accepted. Milestone 21 must build on the accepted M14–M20 runtime, neural-controller, successor-transferred architecture, and user-owned pause/resume/checkpoint infrastructure without changing the evolutionary/runtime semantics established so far.

Before final handoff, invoke and satisfy:

```text
prompts/skills/stage_closing_chores.md
```

---

## Strategic direction

M21 is a performance and determinism milestone, not a new behavior milestone.

The next architectural stages will require substantially larger unit counts and much longer runs. Before changing the successor-construction mechanism or introducing an executable design program, the current simulator must become much faster and must gain a stronger deterministic-equivalence oracle so internal refactoring can be performed aggressively without silently changing simulation semantics.

Current accepted M20 reference state includes:

```text
521 tests passing
77.94% coverage
M14 judge PASS
M15 judge PASS
M16 judge PASS
M17 judge PASS
M18 judge PASS
M19 judge PASS
M20 judge PASS
```

M20 also demonstrated pause/resume equivalence on a 20,000-tick run, but the reference run took approximately 1,893.72 seconds and checkpoint files grew substantially with accumulated in-engine trace buffers.

The required M21 transformation is:

```text
accepted deterministic simulator
→ deeper future-causal state digest
→ frozen reference trajectories and benchmark baseline
→ hotspot profiling
→ semantics-preserving sparse/efficient runtime refactoring
→ trace/checkpoint payload separation
→ population-scale benchmarks
→ exact equivalence verification
```

No M21 optimization is accepted merely because tests pass. It must also demonstrate deterministic semantic equivalence against the frozen reference trajectory.

---

## Explicitly observed current bottlenecks and limitations

Treat these as starting hypotheses to verify with profiling, not as the only allowed targets.

### 1. Full-grid world update

`machine_sim/environment/world.py` maintains `_active_cells`, and resource/hazard population adds cells to that set, but `World.update()` still iterates over every cell in `self.grid` on every tick.

On the current 120 × 120 field this means 14,400 cell visits per tick even when only a minority of cells contain resources or hazards.

M21 must profile and, if confirmed, replace this with a deterministic sparse update path that produces exactly the same future-causal state and event ordering as the reference implementation.

Do not iterate directly over an unordered set if doing so can alter deterministic ordering. Preserve the reference grid-order semantics where relevant.

### 2. Checkpoint payload growth

`machine_sim/sim/checkpoint.py` currently captures the entire live engine object graph through `encode_state(engine)`.

M20 documented checkpoint growth from approximately 6.6 MB around tick 2,000 to approximately 28.8 MB at tick 20,000 because accumulated observational traces are stored inside the engine object graph.

M21 must separate future-causal simulation state from output-only accumulated trace state so checkpoint size no longer scales directly with cumulative observation history.

### 3. Existing run digest is intentionally shallow

`machine_sim/sim/run_control.py::tick_observation()` currently includes only a compact view such as tick, active count, unit identity/position, power, mean component health, and active state.

That digest is valuable but insufficient as the sole refactoring oracle because hidden neural state, neural weights, architecture masks, RNG state, resources, hazards, signals, and other future-causal fields may differ while the shallow observation remains equal.

M21 must add a deep deterministic semantic-state digest while preserving the existing lightweight run digest for routine progress tracking.

### 4. Dependency policy

`pyproject.toml` currently has one runtime dependency: `click>=8.0`.

Do not add a heavy ML framework.

Algorithmic improvements and data-structure improvements come first. NumPy may be introduced only if profiler/benchmark evidence shows that batching/vectorization materially improves a remaining hot path after obvious algorithmic waste is removed. If NumPy is added, document exactly which kernels use it, the before/after benchmark, and deterministic-equivalence evidence.

Do not add PyTorch, JAX, TensorFlow, Numba, Cython, Rust, or C/C++ extensions in M21.

---

## M21 non-goals

Do **not** implement any of the following in M21:

```text
unit-executed successor construction
executable hereditary/design program substrate
new replication semantics
new architecture-variation semantics
new selection mechanism
new affect/modulatory substrate
collective-organization interpretation
OOD intelligence probes
transformer/token/LLM controller
new externally optimized controller configuration
```

M21 must not alter which actions units can take, when current fabrication is permitted, how current architecture variation occurs, or how current local plasticity works.

The next architecture-changing milestones will build on M21 only after deterministic high-throughput infrastructure is accepted.

---

# Phase 0 — Freeze the deterministic oracle before optimization

This phase must be completed before modifying hot-loop semantics.

## 1. Add a deep semantic-state digest

Add a module such as:

```text
machine_sim/sim/state_digest.py
```

Suggested public functions:

```text
semantic_state_snapshot(engine) -> canonical JSON-compatible structure
deep_state_digest(engine) -> sha256 hex string
semantic_state_schema() -> included/excluded field declaration
```

The deep digest must cover state that can affect future simulation behavior.

At minimum audit and include, where applicable:

```text
engine tick/state counters
engine RNG state
world RNG state if distinct
unit identity and deterministic ordering
unit position
unit active state
unit power reserve and max power
component health and other future-causal component state
unit action/control timers and previous-action state
scalar adaptive-control state
neural architecture descriptor
neural hidden/recurrent state
neural weight matrices
neural recurrent mask / active connection representation
plastic parameters and eligibility state that affect future updates
signal-local runtime state that affects future actions
world resource quantities/regrowth parameters
world hazard intensities/decay parameters
active signals and their full future-causal parameters
fabrication/successor-construction counters required for future IDs or eligibility
current architecture-transfer state required for future behavior
configuration values that affect future runtime behavior
```

The audit must also identify output-only state that should **not** influence the semantic digest, such as:

```text
wall-clock timestamps
file paths
rendered status output
run-manifest timestamps
accumulated output-only trace history
post-run analysis caches
purely observational counters that cannot affect future decisions
```

Do not guess whether a field is observational. Inspect actual engine reads. If uncertain, treat it as future-causal until proven otherwise.

## 2. Canonicalization requirements

The semantic snapshot/digest must be:

- deterministic across independent Python processes,
- deterministic across checkpoint encode/decode,
- stable under dictionary/set representation differences when those differences are not runtime-causal,
- sensitive to every audited future-causal state mutation tested,
- insensitive to mutation of explicitly classified output-only trace history,
- free of Python built-in `hash()` dependence.

Include `random.Random` state or an equivalent future-RNG-state representation.

## 3. Deep-digest tests

Required tests must demonstrate that the digest changes when representative future-causal state changes, including at least:

```text
resource quantity
hazard intensity
signal state
unit power
component health
neural hidden state
neural weight
recurrent connection mask
architecture descriptor
adaptive scalar state
RNG state
fabrication next-ID/counter state if future-causal
```

Also prove the digest does **not** change when only an explicitly output-only trace record is appended.

## 4. Freeze reference trajectories

Before hot-loop optimization, run deterministic reference configurations from the accepted M20 behavior and record deep digest samples.

Required reference families:

```text
A. short deterministic baseline: >= 2,000 ticks
B. neural + architecture-variation baseline: >= 5,000 ticks
C. pause/resume reference using M20 controls: pause, process restart, resume, complete
```

Sample the deep digest at a fixed interval, recommended every 100–500 ticks.

Write:

```text
output/demo_m21/reference/deep_state_digest_trace.jsonl
output/demo_m21/reference/reference_run_summary.json
output/demo_m21/reference/reference_config_manifest.json
```

The reference artifact must record the accepted pre-optimization commit hash.

Prefer committing the oracle/preflight implementation as a distinct implementation commit before performance refactors begin.

---

# Phase 1 — Profiling and benchmark substrate

## 5. Add a repeatable benchmark harness

Add a module/CLI such as:

```text
machine_sim/perf/benchmark.py
machine-sim benchmark
```

or an equivalent clean structure.

Use `time.perf_counter()` and standard-library profiling first.

Required measured metrics:

```text
initialization_seconds
simulation_seconds
wall_seconds
ticks_per_second
unit_decisions_total
unit_decisions_per_second
neural_forward_evaluations_total
neural_forward_evaluations_per_second
world_update_calls
world_cells_visited_total
world_cells_updated_total
checkpoint_write_seconds if enabled
checkpoint_bytes_written if enabled
peak or representative active-unit count
```

Instrumentation must not change simulation outcomes. Performance counters used only for benchmarking must be excluded from the semantic digest unless they influence runtime behavior.

## 6. Benchmark suites

Required suites:

### Primary sparse-world throughput benchmark

Use a fixed seed and a representative 120 × 120 field with current neural processing enabled. Choose a tick count long enough to amortize startup cost but practical for repeated local measurement.

Run at least 3 measured repetitions after one warm-up. Report median and individual values.

### Population-scaling benchmark

Run at least:

```text
10 initial units
100 initial units
1,000 initial units
```

for a bounded tick count suitable for scaling measurement.

Record initialization time separately from simulation time.

An exploratory 5,000 or 10,000-unit measurement is encouraged if practical but is not mandatory for M21 acceptance.

### Controlled/checkpoint benchmark

Measure M20-style checkpoint overhead separately from pure simulation throughput.

## 7. Profile before optimizing

Produce a standard-library profiler summary before hot-loop refactoring.

Write:

```text
output/demo_m21/performance/hotspot_profile_before.json
output/demo_m21/performance/performance_baseline.json
```

The report must identify the top runtime contributors by cumulative time and call count.

Do not claim a bottleneck solely from code inspection if profiling contradicts it.

---

# Phase 2 — Semantics-preserving runtime optimization

## 8. Sparse world update

If profiling confirms the full-grid update cost, implement a deterministic active-cell update representation.

Requirements:

- Cells containing future-updated resources/hazards must be tracked correctly.
- The optimized iteration order must reproduce reference event ordering where ordering is observable.
- No active resource/hazard cell may be skipped.
- Empty inert cells must not be visited in the hot update loop merely because they exist in the rectangular grid.
- Existing sensing, placement, resource, hazard, and signal behavior must remain unchanged.

Add a direct reference-vs-optimized world update equivalence test across many ticks and randomized fixture states.

Record:

```text
world_cells_visited_before
world_cells_visited_after
world_update_speedup
```

## 9. Optimize only measured hot paths

After the sparse-world refactor, re-profile.

Additional allowed optimizations include, only when measured:

```text
avoid repeated full-grid empty-cell scans
reduce repeated temporary-list allocations
cache deterministic derived values that are invalidated correctly
batch neural forward evaluation where semantics permit
replace repeated O(N*M) scans with deterministic indexes
reduce repeated JSON/object construction inside the tick loop
improve signal lookup with deterministic spatial indexing if it is a measured hotspot
```

Every optimization must preserve the deep-digest reference trajectory.

Do not trade deterministic behavior for speed.

## 10. NumPy decision gate

NumPy is optional, not required.

Only add it if all of the following are true:

```text
profiling identifies a numerical kernel as a major remaining cost
algorithmic/data-structure fixes have already been applied
an isolated benchmark shows material improvement
cross-process deterministic reference traces remain identical
```

If introduced, record a dependency decision artifact:

```text
output/demo_m21/performance/dependency_decision.json
```

with:

```text
added: true/false
reason
profile evidence
kernel affected
before_seconds
after_seconds
speedup
semantic_digest_equal
```

---

# Phase 3 — Checkpoint and trace scalability

## 11. Separate future-causal state from cumulative output history

The checkpoint must continue to restore all state required for exact future continuation, but it should not serialize unbounded accumulated output-only traces merely because they live as engine attributes.

Perform an explicit engine-state audit and classify each large trace/counter collection as either:

```text
future-causal
or
output-only
```

For output-only history, implement one of the following or an equivalent robust design:

```text
append-only trace sink outside checkpoint state
bounded in-engine recent window + append-only full trace artifact
checkpoint exclusion with independently persistent artifact continuation
```

Do not drop trace data silently.

## 12. Resume must preserve full-run observational continuity

M20 notes that the append-only event store is not restored and some post-run summaries after resume can represent only the resumed segment.

M21 should improve this where feasible: output artifacts and summary readers should represent the complete run across pre-pause and post-resume segments without requiring the full historical event store inside the checkpoint.

The preferred model is:

```text
checkpoint = future-causal state
append-only artifacts = observation history
manifest/index = segment continuity metadata
```

## 13. Checkpoint scaling tests

Required synthetic test:

- Create identical future-causal engine states.
- Add a large number of output-only trace records to one instance.
- Checkpoint both.
- Demonstrate that checkpoint state digest/future continuation remains equivalent and checkpoint payload size is not proportional to the added historical trace count.

Required real-run measurement:

```text
checkpoint_bytes_by_tick
checkpoint_write_seconds_by_tick
checkpoint_growth_ratio
```

Compare against the M20 documented pattern and report improvement.

Do not use a brittle absolute-byte acceptance threshold tied to one machine or one run. The judge should verify that cumulative observational trace growth is no longer the dominant driver of checkpoint payload growth.

---

# Phase 4 — Deterministic refactoring equivalence

## 14. Reference-vs-optimized digest comparison

After all M21 optimizations, rerun the exact frozen reference configurations from Phase 0.

For every sampled tick:

```text
reference_deep_digest == optimized_deep_digest
```

Required artifact:

```text
output/demo_m21/determinism/deep_equivalence_report.json
```

Required fields:

```text
accepted_reference_commit
optimized_commit
config_digest
seed
sample_interval
sample_count
matching_sample_count
mismatch_count
first_mismatch_tick
final_reference_digest
final_optimized_digest
final_equal
```

Acceptance requires:

```text
mismatch_count == 0
final_equal == true
```

for every required reference family.

## 15. Preserve M20 continuation equivalence

Run an actual process-isolated pause/resume test after optimization.

Both the existing shallow run digest and the new deep semantic digest must match the uninterrupted reference at equivalent checkpoints/final state.

---

# Performance acceptance targets

M21 is a substantial throughput milestone. Absolute runtime depends on hardware, so acceptance is based primarily on same-machine before/after ratios.

Required:

```text
primary_end_to_end_ticks_per_second_speedup >= 2.5x
```

Preferred target:

```text
>= 5x
```

For the isolated sparse-world update benchmark, if the current full-grid scan is confirmed as a major hotspot:

```text
world_update_speedup >= 5x
```

or provide profiler evidence explaining why the target is not applicable after semantic constraints.

The independent judge should fail M21 if there is no material throughput improvement. A technically elegant refactor with negligible speedup is not sufficient.

Population scaling must successfully execute the required 10/100/1,000-unit benchmark set without error and report decisions/second.

Do not claim Avida-equivalent throughput. M21 establishes a measured scaling baseline and materially improves the current simulator; later milestones may require compiled kernels or additional architectural changes.

---

# Required artifacts

Main output directory:

```text
output/demo_m21/
```

Required artifacts:

```text
output/demo_m21/reference/reference_run_summary.json
output/demo_m21/reference/reference_config_manifest.json
output/demo_m21/reference/deep_state_digest_trace.jsonl
output/demo_m21/determinism/deep_state_digest_schema.json
output/demo_m21/determinism/deep_equivalence_report.json
output/demo_m21/determinism/pause_resume_deep_equivalence_report.json
output/demo_m21/performance/hotspot_profile_before.json
output/demo_m21/performance/hotspot_profile_after.json
output/demo_m21/performance/performance_baseline.json
output/demo_m21/performance/performance_optimized.json
output/demo_m21/performance/performance_comparison.json
output/demo_m21/performance/population_scaling.jsonl
output/demo_m21/performance/checkpoint_growth_comparison.json
output/demo_m21/performance/dependency_decision.json
output/demo_m21/milestone_21_judge_result.json
```

Optional useful artifacts:

```text
output/demo_m21/performance/profile_before.txt
output/demo_m21/performance/profile_after.txt
output/demo_m21/performance/world_update_microbenchmark.json
output/demo_m21/performance/signal_lookup_microbenchmark.json
```

Keep generated artifacts bounded.

---

# Independent M21 judge

Add:

```text
machine_sim/verification/milestone_21_judge.py
```

Overall PASS only when every required check is exactly `PASS`.

Required checks:

```text
reference_commit_recorded_check
reference_artifacts_present_check
deep_state_schema_present_check
deep_digest_cross_process_determinism_check
deep_digest_future_causal_sensitivity_check
deep_digest_output_trace_independence_check
reference_vs_optimized_zero_mismatch_check
pause_resume_deep_equivalence_check
profiling_evidence_present_check
sparse_world_update_equivalence_check
material_throughput_improvement_check
population_scaling_10_check
population_scaling_100_check
population_scaling_1000_check
checkpoint_trace_separation_check
checkpoint_growth_improvement_check
m20_pause_resume_regression_check
m14_m15_m16_m17_m18_m19_m20_regression_check
tests_and_coverage_check
machine_native_wording_check
```

No `PARTIAL`, `SKIP`, `UNKNOWN`, missing-evidence, or default-pass path may result in overall PASS.

For regression evidence, require actual judge-result artifacts or explicitly captured subprocess judge results. Do not accept a self-declared `"regression": "PASS"` field without underlying evidence.

---

# Required tests

Add focused tests for M21. At minimum cover:

1. Deep digest deterministic for identical independently created states.
2. Deep digest stable across subprocess boundary.
3. Deep digest stable across checkpoint encode/decode.
4. Deep digest changes for each representative future-causal field category.
5. Deep digest unchanged for output-only trace append.
6. Sparse world update matches reference world update over many ticks.
7. Sparse world active index remains correct after resource/hazard fixture changes.
8. Deterministic event ordering preserved by sparse update.
9. Checkpoint restore remains continuation-equivalent.
10. Output-only trace growth does not materially inflate checkpoint payload.
11. Full-run observation artifacts remain continuous across pause/resume where M21 changes trace persistence.
12. Benchmark counters do not influence simulation state.
13. Population benchmark supports 10 units.
14. Population benchmark supports 100 units.
15. Population benchmark supports 1,000 units.
16. M21 judge fails on a deep-digest mismatch.
17. M21 judge fails when performance evidence is missing.
18. M21 judge fails when speedup is below required threshold.
19. M21 judge fails when a required population-scale row is missing.
20. M21 judge fails when checkpoint historical-trace scaling remains unbounded.
21. M21 judge passes a valid fixture set.
22. Existing M14–M20 tests and judges remain compatible.

Maintain repository coverage at or above the current project threshold of 77%.

---

# Documentation

Add:

```text
docs/milestone_21_report.md
```

Update:

```text
docs/review_package.md
```

M21 report must include:

- accepted starting commit,
- Phase 0 oracle/preflight commit,
- final optimization commit,
- baseline profiler results,
- final profiler results,
- top hotspots before and after,
- deep semantic-state schema summary,
- fields intentionally excluded from semantic digest and why,
- reference-vs-optimized digest comparison,
- pause/resume deep-equivalence result,
- sparse-world implementation details,
- benchmark methodology,
- median before/after throughput,
- speedup ratio,
- population-scaling table,
- checkpoint-size/write-time comparison,
- trace-state separation design,
- NumPy decision and evidence,
- tests and coverage,
- M14–M20 regression judge results,
- M21 exact-PASS judge result,
- actual command list,
- known remaining throughput bottlenecks,
- next recommended milestone.

Do not describe a speedup using only one timing sample.

Do not call the result "Avida-class throughput" unless a separate future benchmark justifies that statement.

---

# Recommended implementation sequence

Use this order unless a concrete repository constraint requires an adjustment:

```text
1. add deep semantic-state oracle
2. test oracle thoroughly
3. capture frozen reference trajectories
4. capture baseline performance/profiler artifacts
5. commit oracle/preflight
6. optimize World.update active-cell path
7. rerun deep-equivalence before proceeding
8. re-profile
9. optimize next measured hot paths
10. rerun deep-equivalence after each substantial optimization
11. externalize/exclude output-only trace history from checkpoint state
12. verify process-isolated pause/resume equivalence
13. run population-scaling benchmark
14. run full tests/coverage
15. run M14–M20 regression judges
16. run M21 judge
17. update report/review package
18. invoke stage-closing chores and push clean remote state
```

Do not batch several semantics-affecting optimizations together before checking the deep digest. The oracle exists specifically to localize regressions.

---

# Suggested verification commands

Adjust exact CLI names to the implementation, but final report must list commands actually used.

```bash
python -m pytest machine_sim/tests/ -q
python -m pytest machine_sim/tests/ -q --cov=machine_sim --cov-report=term
python -m machine_sim.cli.main check

python -m machine_sim.cli.main benchmark -c configs/milestone_21_performance.toml -o output/demo_m21/performance
python -m machine_sim.cli.main population-benchmark -c configs/milestone_21_population_scaling.toml -o output/demo_m21/performance
python -m machine_sim.cli.main m21-reference -c configs/milestone_21_reference.toml -o output/demo_m21/reference
python -m machine_sim.cli.main m21-equivalence -o output/demo_m21/determinism

python -m machine_sim.verification.milestone_21_judge output/demo_m21
python -m machine_sim.verification.milestone_20_judge output/demo_m20
python -m machine_sim.verification.milestone_19_judge output/demo_m19
python -m machine_sim.verification.milestone_18_judge output/demo_m18
python -m machine_sim.verification.milestone_17_judge output/demo_m17
python -m machine_sim.verification.milestone_16_judge output/demo_m16
python -m machine_sim.verification.milestone_15_judge output/demo_m15
python -m machine_sim.verification.milestone_14_judge output/demo_m14
```

---

# Stage-closing evidence required

Final handoff must include at least:

```text
TASK_STATUS: PASS or PARTIAL_PASS
MILESTONE_21_STATUS: ACCEPTED or HOLD
READY_FOR_MILESTONE_22: YES or NO
Branch:
Accepted starting commit:
Oracle/preflight commit:
Optimization implementation commit:
Final remote commit:
Files changed:
Tests:
Coverage:
Guardrails:
M14 judge:
M15 judge:
M16 judge:
M17 judge:
M18 judge:
M19 judge:
M20 judge:
M21 judge:
Reference deep-digest sample count:
Deep-digest mismatch count:
Pause/resume deep-digest mismatch count:
Primary benchmark baseline median ticks/s:
Primary benchmark optimized median ticks/s:
Primary throughput speedup:
World-update speedup:
Population benchmark 10-unit result:
Population benchmark 100-unit result:
Population benchmark 1000-unit result:
Checkpoint growth before/after:
Dependency decision:
Known remaining hotspots:
Stage-closing chores result:
Clean working tree:
```

Required explicit assertions:

```text
M21_DEEP_SEMANTIC_ORACLE_PRESENT: yes
M21_REFERENCE_TRAJECTORY_FROZEN_BEFORE_HOT_LOOP_REFACTOR: yes
M21_REFERENCE_VS_OPTIMIZED_MISMATCH_COUNT: 0
M21_PROCESS_ISOLATED_PAUSE_RESUME_DEEP_EQUIVALENCE: yes
M21_MATERIAL_THROUGHPUT_IMPROVEMENT: yes
M21_POPULATION_1000_BENCHMARK_COMPLETED: yes
M21_CHECKPOINT_TRACE_SCALING_FIXED: yes
M21_NO_RUNTIME_BEHAVIOR_FEATURE_ADDED: yes
M14_M15_M16_M17_M18_M19_M20_REGRESSION_JUDGES_STILL_PASS: yes
M21_INDEPENDENT_JUDGE_STATUS: PASS
M21_NO_SKIPPED_REQUIRED_JUDGE_CHECKS: yes
```

---

# Acceptance criteria

```text
M21_DEEP_SEMANTIC_STATE_DIGEST: PASS
M21_CAUSAL_STATE_AUDIT: PASS
M21_FROZEN_REFERENCE_TRAJECTORIES: PASS
M21_PROFILE_BEFORE_OPTIMIZATION: PASS
M21_SPARSE_WORLD_UPDATE_EQUIVALENCE: PASS
M21_MATERIAL_RUNTIME_SPEEDUP: PASS
M21_POPULATION_SCALING_10_100_1000: PASS
M21_CHECKPOINT_TRACE_STATE_SEPARATION: PASS
M21_CHECKPOINT_GROWTH_IMPROVEMENT: PASS
M21_PROCESS_ISOLATED_RESUME_EQUIVALENCE: PASS
M21_REFERENCE_VS_OPTIMIZED_ZERO_DEEP_DIGEST_MISMATCHES: PASS
M21_DEPENDENCY_DECISION_EVIDENCE: PASS
M21_INDEPENDENT_JUDGE_EXACT_PASS_ONLY: PASS
M14_M15_M16_M17_M18_M19_M20_REGRESSION: PASS
TESTS_AND_COVERAGE: PASS
GUARDRAILS: PASS
MILESTONE_21_REPORT_CURRENT: PASS
REVIEW_PACKAGE_CURRENT: PASS
STAGE_CLOSING_CHORES_SATISFIED: PASS
CLEAN_WORKTREE_AND_PUSHED_REMOTE: PASS
```

---

# Boundary for the next milestone

M21 prepares the simulator for the next foundational architecture change.

Do not implement that change here.

The intended next milestone is an executable per-unit design-program substrate that can eventually construct the unit's processing structure and later support unit-executed successor construction.

M21 succeeds by making the current simulator fast enough and deterministic enough that this future change can be studied rather than confounded with performance and refactoring errors.
