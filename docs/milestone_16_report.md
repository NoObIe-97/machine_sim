# Milestone 16 Report: Adaptive Trajectory Compression and Offline Analysis

## Date

2026-07-06

## Summary

Implemented bounded compression and offline analysis for multi-generation adaptive trajectories. The `AdaptiveTrajectoryCompressor` reads M15-style transfer traces and produces bounded compressed segments with offline replay metrics and cross-trajectory similarity comparison.

## Design Summary

Built as a read-only post-processing layer on top of M14/M15 substrates. No changes to unit action selection, adaptive update rules, fabrication, or signal behavior.

- `AdaptiveTrajectoryCompressor` — consumes transfer records, action traces, feedback traces, and adaptive state traces; produces bounded compressed segments
- `compare_trajectories()` — compares two compressors' trajectory signatures
- `compress` CLI command — runs compression on existing simulation output
- M16 independent judge with 12 required checks

## Relation to M14/M15

M14 proved adaptive state changes during long-run operation. M15 generated generation-indexed transfer traces. M16 compresses those traces into bounded segments for offline comparison across configurations.

## Compression Method

Transfer records are divided into bounded segments (configurable max). Each segment aggregates:
- Generation index range and transfer count
- Average and range of adaptive states
- Average and max transfer deltas
- Action distribution summary
- Signal, resource, and hazard response summaries
- Feedback event summaries
- Deterministic segment signature (SHA-256 hash)

## Replay Metric Definitions

- `avg_trajectory_replay_error`: mean deviation between source stats and segment-preserved stats
- `max_trajectory_replay_error`: worst-case deviation
- `adaptive_state_replay_error`: per-key adaptive state deviation
- `action_distribution_replay_error`: action distribution preservation error
- `transfer_delta_replay_error`: transfer delta preservation error
- `replay_stability_score`: 1 - variance of per-segment errors (bounded [0, 1])

## Cross-Trajectory Comparison Setup

Primary run: M15-style config (seed=42, 30000 ticks, 6 units, 120x120 grid)
Comparison run: Same config with different seed (seed=43, 200 ticks) for structural difference detection

## Long-Run Parameters

```
grid: 120x120, resource_density=0.45, hazard_density=0.01
6 initial units, 30000 ticks, seed=42, power_drain_rate=0.08
unit_capacity=40, fabrication_interval=5
fabrication_power_cost=3.0, fabrication_material_cost=0.3
component_degradation_scale=0.2
```

## Source Trace Count and Compressed Segments

```
Source transfer records: 6
Compressed segments: 3
Compression ratio: 0.695
```

## Replay Error Metrics

```
Replay window count: 3
Avg trajectory replay error: 0.000000
Replay stability score: 1.000
```

## Cross-Trajectory Similarity

```
Overall trajectory similarity: 0.636
Nontrivial difference detected: True
```

## M15 Regression

M15 judge: PASS (12/12 checks) — verified on M15 artifacts

## M16 Judge Result

```
M16_JUDGE_STATUS: PASS

long_run_ticks_check: PASS
source_trace_available_check: PASS
compression_segment_check: PASS
compression_ratio_check: PASS
replay_metrics_check: PASS
cross_trajectory_similarity_check: PASS
nontrivial_difference_check: PASS
transfer_generation_check: PASS
signal_observation_check: PASS
artifact_schema_check: PASS
bounded_artifact_size_check: PASS
machine_native_wording_check: PASS
```

All 12/12 checks PASS. Zero SKIP.

## Artifact Paths

- `output/demo_m16/compressed_trajectory_capsule.json`
- `output/demo_m16/trajectory_compression_summary.json`
- `output/demo_m16/compressed_trajectory_segments.jsonl`
- `output/demo_m16/trajectory_replay_metrics.json`
- `output/demo_m16/cross_trajectory_compare.json`
- `output/demo_m16/adaptive_trajectory_summary.json`
- `output/demo_m16/generation_adaptive_state_trace.jsonl`
- `output/demo_m16/milestone_16_judge_result.json`

## Test Results

```
301 passed in 38.16s
```

## Coverage

```
TOTAL    2054    354    83%
Required test coverage of 80.0% reached. Total coverage: 82.77%
```

## Commands Run

```bash
python -m pytest machine_sim/tests/ -v
python -m pytest machine_sim/tests/ --cov=machine_sim --cov-report=term-missing
python -m machine_sim.cli.main check
python -m machine_sim.cli.main run -c configs/milestone_16_adaptive_trajectory_compression.toml -t 30000 -s 42 -o output/demo_m16
python -m machine_sim.cli.main compress output/demo_m16 --max-segments 32
python -m machine_sim.verification.milestone_16_judge output/demo_m16
```

## Full M1-M16 Regression Summary

| Milestone | Key Metrics |
|-----------|-------------|
| M1 | Survival substrate established |
| M2 | Interaction/proximity/collision events |
| M3 | Non-semantic signaling |
| M4 | Signal correlation analysis |
| M5 | Adaptive signal control |
| M6 | Fabrication and lineage tracking |
| M7 | Calibration capsules and warm start |
| M8 | Telemetry reconciliation |
| M9 | Resource pressure analysis |
| M10 | Signal field dynamics and gradient |
| M11 | Trace compression and replay metrics |
| M12 | Multi-generation trace drift |
| M13 | Cross-unit summary consistency |
| M14A | 20000-tick 120x120 adaptive control, 12/12 judge PASS |
| M15 | 30000-tick multi-gen trace, 5+ transfers, 12/12 judge PASS |
| M16 | Trajectory compression, ratio 0.695, replay stable, 12/12 judge PASS |

## Known Limitations

1. Small transfer counts (6 records) limit compression ratio improvement — larger runs would compress better
2. Cross-trajectory comparison uses a short 200-tick alternate run — longer comparison runs would provide richer signatures
3. Segment signatures are hash-based, not structural-metric equivalent — two structurally similar but differently-hashed segments appear different

## Next Recommended Milestone

Milestone 17: Cross-Configuration Adaptive Comparison — systematic comparison of adaptive trajectories across multiple parameter configurations, automated parameter sensitivity analysis, and trajectory-based configuration recommendation.
