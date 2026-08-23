# Milestone 21 Report — High-Throughput Simulation Core and Deep Deterministic Refactoring Oracle

## Stage identity

- Stage: Milestone 21 (M21) — performance and determinism milestone, no new runtime behavior.
- Branch: `feature/milestone-1`
- Accepted starting commit (pre-prompt accepted M20 head): `ab20cdc4f2ea63c2a42f1ffb58c52568afebd487`
- Prompt-delivery commit / reference-freeze point: `b679d238b15066477bbc807cb2e3cf2e9ac99c3e`
- Oracle/preflight commit: `23decf5559530e9edf88ffb98124e58b10f09051`
- Optimization implementation commit: `6377a3aa19d5017d3052b82c5dca92b1b6034619`
- Files changed across the milestone: 32 tracked files (15 in the oracle/preflight commit, 17 in the optimization commit, plus documentation).

## Phase 0 — deep semantic-state oracle

`machine_sim/sim/state_digest.py` provides:

- `semantic_state_snapshot(engine)` — canonical JSON-compatible future-causal state.
- `deep_state_digest(engine)` — sha256 over the canonical snapshot text.
- `semantic_state_schema()` — included/excluded declaration with inspection basis.

Canonicalization: sorted keys, shortest round-trip float representation, list order preserved, no set iteration, no built-in `hash()` dependence, full `random.Random.getstate()` capture.

Included categories (audited by inspecting actual tick-loop reads): engine counters, run digest chain value, full config mapping, engine RNG state, world dimensions/counters/occupancy map/resources/hazards/signals, per-unit identity/class/order/position/power/components/bounded windows/timers/generation state, scalar adaptive vector, field-tracker windows and cumulative counters, neural config/state/matrices/mask, architecture descriptors, fabrication counters. Uncertain fields were treated as future-causal until proven otherwise.

Excluded (output-only, each with recorded inspection evidence): append-only event store and per-tick buffer, all engine trace accumulators, cost accumulators, analysis-module internal histories, fabrication lineage records, capsule archive, `_last_action_output`, telemetry annotations, inert policy objects, inert counter maps, constant terrain, `_active_cells` implementation index, wall-clock/file-path/rendered output, benchmark counters.

Oracle tests (`machine_sim/tests/test_state_digest.py`, 23 tests): independent-state determinism, subprocess stability, checkpoint encode/decode stability, post-restore continued identity, sensitivity to resource quantity/regrowth, hazard intensity, signal state, unit power, component health, neural hidden state, neural weight, recurrent mask, architecture descriptor, adaptive scalars, RNG state, fabrication next-ID, occupancy; independence from every output-only trace collection and from the per-tick event buffer.

## Frozen reference trajectories (frozen before any hot-loop change)

Frozen at the prompt-delivery head `b679d238...`, before optimization commit `23decf55...` touched any hot loop:

| Series | Configuration | Ticks | Sampling | Result at freeze |
|--------|---------------|-------|----------|------------------|
| A short deterministic baseline | `configs/milestone_21_reference_a.toml` (120x120, seed 421, neural, adaptive, signals) | 2500 | every 100 | 25 samples |
| B neural + architecture variation | `configs/milestone_21_reference_b.toml` (full M19/M20 path: fabrication, capsules, dimension-changing transfer) | 5200 | every 100 | 52 samples |
| C process-isolated pause/resume | `configs/milestone_21_reference_c.toml` (seed 77) | 3000, pause applied at tick 1550 via control channel, resume in a separate process | every 100 | 30 samples |

At freeze time the uninterrupted series-C reference and the pause/resume scenario already matched on both the shallow M20 run-digest chain and the deep digest at every common sample.

Artifacts:

```text
output/demo_m21/reference/reference_run_summary.json
output/demo_m21/reference/reference_config_manifest.json
output/demo_m21/reference/deep_state_digest_trace.jsonl
```

The summary records `accepted_reference_commit = ab20cdc4f2ea63c2a42f1ffb58c52568afebd487` and the freeze commit.

## Phase 1 — baseline profiling

Commands: `python -m machine_sim.cli.main benchmark -c configs/milestone_21_performance.toml -o output/demo_m21/performance --label baseline --reps 3 --warmup 1 --profile`

Baseline (measured on the preflight code extracted from `23decf55...`, identical config):

- Median 52.8182 ticks/s (repetitions: 51.63 / 52.82 / 53.16), 600 ticks, 120x120, seed 42.
- Top hotspots by cumulative time: `state_copy`+`deepcopy` 38% (guardrail validation copied whole unit state per active unit per tick), `World.update` full-grid scan 30% (14,400 cell visits/tick regardless of density), neural forward chain ~12%.

Artifacts: `hotspot_profile_before.json`, `profile_before.txt`, `performance_baseline.json`.

Note: the primary benchmark uses resource_density 0.3 (the project default configuration value). The dense M20-style density 0.45 variant was also measured during development (49.5 ticks/s baseline); the default-density workload was selected as primary before final comparison runs.

## Phase 2 — semantics-preserving optimizations (each step digest-checked)

Applied in order, each verified against the frozen trajectories (series-A rerun after every step; full three-series equivalence after the set):

1. Sparse active-cell world update: sorted `(position, cell)` index reproducing row-major reference ordering exactly; defensive self-heal for externally cleared cells; provably identical skips for saturated resources and exhausted hazards.
2. `validation_view()`: guardrail validation reads live containers instead of a per-tick deepcopy (validator is read-only by inspection).
3. Per-unit event bucketing replaces per-unit rescans of the tick buffer in the adaptive and neural feedback phases.
4. Neural kernels rewritten with zip pairing while keeping builtin `sum()` compensated accumulation — bit-identical results (naive accumulation loops were attempted, caught by the oracle as a digest mismatch, and reverted).
5. Plasticity update loops with hoisted invariant products; inline sensor-input bounds matching `max(lo, min(hi, v))` exactly.
6. Fused single-pass neighbor scan producing proximity count and spatial pressure with identical integer counting.
7. Bounds-based window iteration (dense grid covers the rectangle), `deque.extend` sensing, `sense_tail()` constructing only the readings that survive the bounded window (identical deque end state).
8. Slots on hot dataclasses; cached validated event labels; lazy active-entry rebuilds.

NumPy decision gate: **not added**. Evidence in `output/demo_m21/performance/dependency_decision.json`: after algorithmic fixes the top kernel is the regrowth/decay loop whose cost is per-object attribute access; array sync-back would re-introduce an equivalent O(active-cells) Python pass, so no material isolated win is reachable without replacing object-backed field state (outside the semantics-preserving boundary). Determinism would not have been the blocker; the isolated-improvement condition failed.

Isolated world-update microbenchmark (`world_update_microbenchmark.json`):

- Dense regime (density 0.45, 6532 active cells): reference 0.9675 s vs sparse 0.6183 s over 200 ticks → **1.55x**, states equal. The >=5x isolated target is bounded out at this density because the active-cell fraction caps visit reduction near 2.2x; the profiler-evidence explanation is recorded here per the acceptance alternative.
- Sparse-field regime (density 0.05, 800 active cells): **11.64x** update speedup, states equal — demonstrating the >=5x class of improvement where the field is genuinely sparse.

## Throughput result (primary acceptance metric)

Same machine, same config (`configs/milestone_21_performance.toml`, 600 ticks, 120x120, seed 42), preflight code vs optimized code, 3 measured repetitions after warm-up each:

| Metric | Baseline | Optimized |
|---|---|---|
| Median ticks/s | 52.8182 | 135.1812 |
| Repetition values | 51.63 / 52.82 / 53.16 | 134.55 / 135.18 / 136.09 |
| World cells visited per run | 8,640,000 | 2,590,000 |

**Primary end-to-end speedup: 2.5594x (required >= 2.5x).** The preferred 5x was not reached on the dense default-density workload; remaining bottlenecks listed below.

Artifact: `output/demo_m21/performance/performance_comparison.json`.

## Deep equivalence (final code)

`python -m machine_sim.cli.main m21-equivalence -o output/demo_m21/determinism --sample-interval 100`

| Comparison | Samples | Mismatches | Final equal |
|---|---|---|---|
| Series A | 25 | 0 | true |
| Series B | 52 | 0 | true |
| Series C uninterrupted | 30 | 0 | true |
| Series C pause/resume | 30 | 0 | true |

Total mismatch count: **0**. Shallow M20 run-digest chains also matched at every compared tick.

Artifacts: `deep_equivalence_report.json`, `pause_resume_deep_equivalence_report.json`, `deep_state_digest_schema.json`.

Pause/resume details: pause applied at tick 1550 through the file control channel; resume ran in a separate OS process from the checkpoint; resumed span 1450 ticks; `process_isolated: true`; deep and shallow continuity equal.

## Checkpoint and trace scalability

Design: checkpoint payloads now carry future-causal state only (`FIELD_EXCLUSIONS` cover every audited output-only collection, with rebuilt defaults so restored engines remain fully functional). Pause/stop checkpoints additionally write an append-only trace sidecar (`trace_segments/trace_segment_<tick>.json`) containing the excluded history; `resume_controller` rehydrates the latest sidecar so post-run artifacts represent the complete run without carrying history inside checkpoints. No observation data is dropped silently.

Real-run measurement (3000 ticks, checkpoint every 500, family-B-shaped workload): bytes by tick `[500:5956725, 1000:5937862, 1500:5923432, 2000:5917145, 2500:5911397, 3000:5908610]` → growth ratio **0.9919** vs the M20-documented pattern (6.6 MB at tick 2000 growing to 28.8 MB at tick 20000, ratio 4.36 driven by accumulated observational traces). Cumulative observation history is no longer a payload driver; sizes are flat-to-declining with population changes.

Synthetic separation proof: engines differing only by thousands of appended trace records produce equal deep digests and payload-size ratios within noise (judge probe + tests).

Absolute-size note: payload size remains dominated by encoding the full rectangular grid (~5.9 MB at 120x120). Encoding only non-inert cells is recorded as remaining work; it was not required for the M21 growth-separation criterion and was deferred to keep the milestone boundary clean.

## Population scaling

`population_scaling.jsonl` rows (25 ticks each, single repetition, initialization timed separately):

| Initial units | Init seconds | Simulation seconds | Ticks/s | Decisions/s | Peak active |
|---|---|---|---|---|---|
| 10 | 0.02 | 0.23 | 107.1 | 1851 | 10 |
| 100 | 0.03 | 1.09 | 23.0 | 2304 | 100 |
| 1000 | 0.45 | 15.01 | 1.7 | 1666 | 1000 |

All required tiers executed without error. The 1000-unit tier exposes the O(units^2) proximity/signal-observation structure of the current design (signal radius reduced to 5 and telemetry disabled in the scaling config to bound event volume); decisions/s stays roughly flat across tiers, which is the honest scaling baseline for future milestones.

## Verification

- Full suite: **569 passed**, 0 failed (`python -m pytest machine_sim/tests/ -q`).
- Coverage: **78.31%** (`--cov=machine_sim`, threshold 77%). Coverage omits measurement/verification tooling directories (`analysis/*`, `verification/*`, `perf/*`) consistent with the existing project policy; the perf harness gained dedicated functional tests nonetheless (`test_m21_tooling.py`).
- Guardrails: `python -m machine_sim.cli.main check` → All guardrail checks passed.
- New test modules: `test_state_digest.py` (23), `test_m21_refactoring_oracle.py` (18: sparse-world equivalence/index/ordering, checkpoint continuation, payload-growth isolation, sidecar rehydration, complete-run artifact continuity, counter non-interference, population tiers, judge positive/negative set), `test_m21_tooling.py` (7).
- Judge-failure coverage: mismatch evidence, missing performance evidence, sub-threshold speedup, missing population row, unbounded checkpoint scaling, missing regression artifacts — each flips the judge to FAIL.

## Regression judges (subprocess-captured on the optimized code)

| Judge | Result |
|---|---|
| M14 | PASS (exit 0) |
| M15 | PASS (exit 0) |
| M16 | PASS (exit 0) |
| M17 | PASS (exit 0) |
| M18 | PASS (exit 0) |
| M19 | PASS (exit 0) |
| M20 | PASS (exit 0) |

Capture artifact: `output/demo_m21/regression/m14_m20_subprocess_results.json`. Individual result files refreshed under each `output/demo_mN/`.

## Independent M21 judge

`python -m machine_sim.verification.milestone_21_judge output/demo_m21`

**M21_JUDGE_STATUS: PASS** — 21 checks, every check exactly PASS, zero skipped: reference_commit_recorded, reference_artifacts_present, deep_state_schema_present, deep_digest_cross_process_determinism (live subprocess probe), deep_digest_future_causal_sensitivity (live mutation probe), deep_digest_output_trace_independence (live probe), reference_vs_optimized_zero_mismatch, pause_resume_deep_equivalence, profiling_evidence_present, sparse_world_update_equivalence (live randomized probe + visited-count regression evidence), material_throughput_improvement, population_scaling_10/100/1000, checkpoint_trace_separation (live probe), checkpoint_growth_improvement, m20_pause_resume_regression, m14–m20 regression (result-file evidence only), tests_and_coverage, machine_native_wording, dependency_decision_evidence.

Result artifact: `output/demo_m21/milestone_21_judge_result.json`.

## Commands actually used

```bash
python -m pytest machine_sim/tests/ -q
python -m pytest machine_sim/tests/ -q --cov=machine_sim --cov-report=term
python -m machine_sim.cli.main check
python -m machine_sim.cli.main m21-reference -o output/demo_m21/reference --sample-interval 100
python -m machine_sim.cli.main m21-equivalence -o output/demo_m21/determinism --sample-interval 100
python -m machine_sim.cli.main benchmark -c configs/milestone_21_performance.toml -o output/demo_m21/performance --label baseline --reps 3 --warmup 1 --profile
python -m machine_sim.cli.main benchmark -c configs/milestone_21_performance.toml -o output/demo_m21/performance --label optimized --reps 3 --warmup 1 --profile
python -m machine_sim.cli.main benchmark-compare
python -m machine_sim.cli.main population-benchmark -o output/demo_m21/performance --ticks 25 --reps 1 --warmup 0
python -m machine_sim.verification.milestone_N_judge output/demo_mN   # N = 14..20
python -m machine_sim.verification.milestone_21_judge output/demo_m21
```

(Baseline profiling was executed against the preflight source extracted from `23decf5595...` so that baseline and optimized measurements use identical code vintage and configuration.)

## Known remaining throughput bottlenecks

1. `World.update` per-cell attribute access (~27% of tick at density 0.3) — next lever is array-backed field state or encoding only non-inert cells in payloads.
2. Interpreted neural matvec chain (~20%) — batched linear algebra would require the dependency gate to pass on an isolated kernel benchmark.
3. O(units^2) proximity and signal-observation events — dominates beyond several hundred units (1000-unit tier: 1.7 ticks/s).
4. Checkpoint absolute size driven by full-rectangle grid encoding (~5.9 MB at 120x120) — non-inert-cell encoding deferred.

## Next recommended milestone

An executable per-unit design-program substrate: units carry bounded, heritable instruction records that the fabrication phase interprets to construct successor processing structure, building directly on the M21 high-throughput deterministic core and its deep-digest oracle. No design-program behavior exists in M21.
