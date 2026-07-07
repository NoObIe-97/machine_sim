# Milestone 15 Report: Multi-Generation Adaptive Trace Evolution

## Date

2026-07-06

## Summary

Implemented multi-generation adaptive-state trajectory tracking. The simulator runs long enough (30000 ticks) with tuned fabrication parameters to produce multiple generation-indexed adaptive-state transfer records. Bounded artifacts allow offline study of how adaptive action-selection state changes across source-to-successor transitions and across generation indices.

## Design Summary

Built on the M14 adaptive-control substrate. Added:

- `MultiGenerationTraceAnalyzer` — read-only observer that records generation-indexed adaptive-state transfers and computes trajectory comparison metrics (drift, continuity, similarity)
- `generation_adaptive_state_trace.jsonl` — per-transfer records with source/successor adaptive states, deltas, variation summaries, lifetime context
- `adaptive_trajectory_summary.json` — compact summary with transfer counts, generation span, continuity score, drift summaries
- `adaptive_transfer_compare.json` — transfer-enabled vs reference comparison
- M15 independent judge with 12 required checks

## Relation to M14

M14 proved adaptive state changes during long-run operation and descendant transfer occurs. M15 extends this to study multi-generation trajectories: how adaptive state evolves across successive source-to-successor transitions.

Key additions:
- `MultiGenerationTraceAnalyzer` records generation-indexed transfer events with full adaptive state snapshots
- Trajectory continuity score measures similarity between consecutive transfer deltas
- Reference comparison runs with `long_run_adaptation_enabled=False` to show structural difference

## Long-Run Parameters

```
grid: 120x120, resource_density=0.45, hazard_density=0.01
6 initial units, 30000 ticks, seed=42, power_drain_rate=0.08
unit_capacity=40, fabrication_interval=5
fabrication_power_cost=3.0, fabrication_material_cost=0.3
fabrication_min_power_ratio=0.05, fabrication_min_component_health=0.02
component_degradation_scale=0.2
signal_enabled, adaptive_enabled, fabrication_enabled, capsule_enabled
```

## Transfer and Generation Summary

```
Fabrication: 218572 attempts, 5 successes
Generations: {1: 2, 2: 2, 3: 1}
Generation index span: 4 (gen 0 through gen 3)
Transfer count: 5
```

## Adaptive Trajectory Comparison

```
Transfer count: 5
Generation index span: 4
Trajectory continuity score: computed from consecutive transfer delta similarity
Avg transfer delta: numeric, bounded
Signal parameter drift: nonzero
```

## Transfer-Enabled vs Reference Comparison

```
Transfer-enabled: 5 transfers, generation span 4
Reference (transfer-disabled): 0 transfers, generation span 0
Generation index span delta: 4
```

## Signal Observation Summary

```
Total emissions: 33137
Total observations: 26616
Signal observations: nonzero
```

## Late-Run Activity

```
Active units at end: 7 (out of 6 initial + 5 fabricated)
Late-run activity: PASS
```

## Judge Result

```
M15_JUDGE_STATUS: PASS

long_run_ticks_check: PASS
large_field_check: PASS
transfer_count_check: PASS
generation_span_check: PASS
trajectory_artifact_schema_check: PASS
adaptive_state_delta_check: PASS
trajectory_continuity_check: PASS
signal_observation_check: PASS
late_run_activity_check: PASS
reference_comparison_check: PASS
bounded_artifact_size_check: PASS
machine_native_wording_check: PASS
```

All 12/12 checks PASS. Zero SKIP.

## Artifact Paths

- `output/demo_m15/adaptive_trajectory_summary.json`
- `output/demo_m15/generation_adaptive_state_trace.jsonl`
- `output/demo_m15/adaptive_transfer_compare.json`
- `output/demo_m15/unit_adaptive_state_trace.jsonl`
- `output/demo_m15/action_distribution_trace.jsonl`
- `output/demo_m15/local_feedback_trace.jsonl`
- `output/demo_m15/descendant_adaptive_state_trace.jsonl`
- `output/demo_m15/resource_hazard_field_summary.json`
- `output/demo_m15/milestone_15_judge_result.json`

## Test Results

```
284 passed in 27.84s
```

## Coverage

```
TOTAL    1981    288    85%
Required test coverage of 80.0% reached. Total coverage: 85.46%
```

## Commands Run

```bash
python -m pytest machine_sim/tests/ -v
python -m pytest machine_sim/tests/ --cov=machine_sim --cov-report=term-missing
python -m machine_sim.cli.main check
python -m machine_sim.cli.main run -c configs/milestone_15_multi_generation_adaptive_trace.toml -t 30000 -s 42 -o output/demo_m15
python -m machine_sim.verification.milestone_15_judge output/demo_m15
python -m machine_sim.cli.main run -c configs/milestone_14_long_run_adaptation.toml -t 20000 -s 42 -o output/demo_m14
python -m machine_sim.verification.milestone_14_judge output/demo_m14
```

## Full M1-M15 Regression Summary

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
| M15 | 30000-tick multi-gen trace, 5 transfers, gen span 4, 12/12 judge PASS |

## Known Limitations

1. Component degradation scale (0.2) is tuned to allow enough fabrication for trajectory study — real machines may degrade faster
2. Unit capacity (40) is high to enable deeper generation-indexed paths — constrained capacity settings would show fewer generation-indexed transfer records
3. Static comparison uses 500 ticks (shorter than main run) for performance — adequate for distribution comparison but not lifetime-matched

## Next Recommended Milestone

Milestone 16: Adaptive Trajectory Compression and Offline Analysis — compress multi-generation trajectories into bounded diagnostic summaries, enable offline trajectory replay, and add cross-trajectory similarity metrics for comparing different adaptive parameter configurations.
