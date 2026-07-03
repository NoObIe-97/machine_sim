# Milestone 13 Report: Compressed Summary Cross-Unit Consistency

## Date
2026-07-02

## Summary

Implemented compressed summary cross-unit consistency and windowed retention stability analysis. The system compares diagnostic summaries across units, retention windows, compression windows, and generation-indexed envelopes. All outputs are observational, numeric, and bounded.

## What Was Implemented

### 1. SummaryConsistencyAnalyzer (analysis/summary_consistency.py)
- Cross-unit diagnostic summary comparison
- Windowed retention stability from M12 retention records
- Long-run compression ratio convergence from M11 compression data
- Bounded cross-generation diagnostic envelope from M12 generation data
- Combined stability summary

### 2. Cross-Unit Diagnostic Summary Comparison
- `unit_summary_count`, `unit_pair_count`
- `avg_unit_summary_delta`, `max_unit_summary_delta`
- `avg_power_ratio_delta`, `avg_sensor_health_delta`, `avg_signal_trace_delta`, `avg_replay_error_delta`
- `summary_consistency_score` [0, 1]

### 3. Windowed Retention Stability
- `retention_window_count`, `retention_window_span`
- `avg_retention_variance`, `max_retention_variance`
- `retention_stability_score` [0, 1], `retention_drop_rate`

### 4. Compression Ratio Convergence
- `compression_window_count`, `avg_compression_ratio`
- `compression_ratio_delta`, `compression_ratio_variance`
- `compression_convergence_score` [0, 1]

### 5. Cross-Generation Diagnostic Envelope
- `cross_generation_envelope_count`, `generation_index_span`
- `generation_envelope_width`, `generation_delta_floor`, `generation_delta_ceiling`
- `generation_envelope_stability` [0, 1]

### 6. Combined Stability Summary
- `combined_window_count`, `combined_consistency_score`
- `combined_stability_score`, `combined_delta_score`, `combined_record_count`

## Config Keys
- `summary_consistency_enabled`: bool (default False)

## Scope Boundary
- Observational and numeric only. No unit state modification.
- Does not alter capsule, fabrication, trace compression, or trace drift.

## Commands Run

```bash
python -m pytest machine_sim/tests/ -v
python -m pytest machine_sim/tests/ --cov=machine_sim --cov-report=term-missing
python -m machine_sim.cli.main check

python -m machine_sim.cli.main run -c configs/milestone_1.toml -t 500 -s 42 -o output/demo_m1
python -m machine_sim.cli.main run -c configs/milestone_2_crowded.toml -t 100 -s 42 -o output/demo_m2
python -m machine_sim.cli.main run -c configs/milestone_3_signals.toml -t 100 -s 42 -o output/demo_m3
python -m machine_sim.cli.main run -c configs/milestone_4_correlation.toml -t 100 -s 42 -o output/demo_m4
python -m machine_sim.cli.main compare -c configs/milestone_5_adaptive.toml -t 150 -s 42
python -m machine_sim.cli.main run -c configs/milestone_6_fabrication.toml -t 200 -s 42 -o output/demo_m6
python -m machine_sim.cli.main capsule-compare -c configs/milestone_7_calibration_capsules.toml -t 200 -s 42
python -m machine_sim.cli.main run -c configs/milestone_8_telemetry_reconciliation.toml -t 200 -s 42 -o output/demo_m8
python -m machine_sim.cli.main run -c configs/milestone_9_resource_pressure.toml -t 200 -s 42 -o output/demo_m9
python -m machine_sim.cli.main run -c configs/milestone_10_signal_field_dynamics.toml -t 200 -s 42 -o output/demo_m10
python -m machine_sim.cli.main run -c configs/milestone_11_trace_compression.toml -t 200 -s 42 -o output/demo_m11
python -m machine_sim.cli.main run -c configs/milestone_12_trace_drift.toml -t 220 -s 42 -o output/demo_m12
python -m machine_sim.cli.main run -c configs/milestone_13_summary_consistency.toml -t 240 -s 42 -o output/demo_m13
```

## Test Results

```
243 passed in 24.80s
```

## Coverage

```
TOTAL    1546    286    82%
Total coverage: 81.50%
```

## Full M1-M13 Regression Summary

| Milestone | Key Metrics |
|-----------|-------------|
| M1 | 0/5 active at 500 ticks |
| M2 | 3/6 active at 100 ticks |
| M3 | 1/4 active, 30 emissions, 235 observations |
| M4 | 1/5 active, 39 emissions, 295 observations |
| M5 compare | adaptive +77 events, +10 emissions |
| M6 | 985 attempts, 9 successes, 9 lineage records |
| M7 compare | warm_start_power_delta +1.8906 |
| M8 | 50 frames, 182 reconciliation, 5 drift entries |
| M9 | 5 pressure cells, avg_depletion=0.366 |
| M10 | 3 patterns, 30 signals, 4 clusters |
| M11 | raw=100, compressed=20, ratio=0.200, stability=0.656 |
| M12 | generations=100, envelope=100, capsule_compat=0.985, retention=100/50 |
| M13 | units=100, pairs=4950, consistency=0.961, compression_score=0.800, combined_stability=0.925 |

## M13 Demo Output

```
Summary consistency: units=100, pairs=4950, avg_delta=0.039, score=0.961
Retention stability: windows=100, variance=0.250, stability=0.975, drop_rate=0.000
Compression convergence: windows=100, ratio=0.008, delta=0.200, score=0.800
Generation envelope: records=100, span=2, width=0.000, stability=1.000
Combined stability: windows=100, consistency=0.961, stability=0.925, delta=0.163
```

## Artifact Paths
- `output/demo_m13/summary_consistency.json`
- `output/demo_m12/trace_drift.json`
- `output/demo_m11/trace_compression.json`
- `output/demo_m10/signal_field_dynamics.json`
- `output/demo_m9/pressure_analysis.json`
- `output/demo_m8/telemetry.json`
- `output/demo_m8/reconciliation.json`
- `output/demo_m8/lineage_drift.json`

## Known Limitations
1. Cross-unit comparison normalizes signal_count delta by /100, may need tuning
2. Retention stability uses sqrt(variance)/20 normalization
3. Compression convergence is snapshot-based, not time-series windowed
4. Combined score is equal-weight average of section scores

## Next Recommended Milestone

Milestone 14: Long-Run Diagnostic Convergence and Bounded Cross-Window Stability — cross-window diagnostic convergence tracking, long-run compression ratio plateau detection, retention stability floor monitoring, and bounded cross-generation envelope refinement.
