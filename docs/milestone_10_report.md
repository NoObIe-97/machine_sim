# Milestone 10 Report: Signal Pattern Field Dynamics

## Date
2026-07-02

## Summary

Implemented cross-tick signal pattern field dynamics analysis, including pattern frequency analysis, temporal signal-density clustering, signal-gradient mapping, and pattern-observation correlation scoring. The system provides diagnostic metrics for signal field behavior without assigning semantic meaning.

## What Was Implemented

### 1. Signal Field Dynamics (analysis/field_dynamics.py)
- `SignalFieldDynamics` class with bounded storage
- Pattern frequency analysis across ticks
- Temporal signal-density clustering
- Spatial signal-gradient mapping
- Pattern-observation correlation scoring

### 2. Pattern Frequency
- `pattern_frequency_total`: count of each pattern
- `pattern_tick_span`: time range of pattern activity
- `pattern_recurrence_score`: ratio of active ticks to span
- `most_frequent_pattern_id`: most common pattern

### 3. Density Clusters
- `density_window_count`: number of temporal clusters
- `peak_cluster_density`: maximum density in any cluster
- `cluster_tick_span`: time range of each cluster

### 4. Signal Gradient
- `signal_gradient_cells`: cells with gradient data
- `avg_signal_gradient`: average gradient strength
- `max_signal_gradient`: maximum gradient strength

### 5. Pattern-Observation Correlation
- `pattern_observation_correlation`: correlation score per pattern
- `pattern_persistence_score`: diversity of observation types
- `lag_window_score`: average lag for observations

## Scope Boundary

- Signal patterns are treated only as numeric field events.
- No semantic interpretation is assigned to patterns.
- Correlation scores are observational, not causal.
- Unit state is not modified by field dynamics summaries.

## Commands Run

```bash
python -m pytest machine_sim/tests/ -v
python -m pytest machine_sim/tests/ --cov=machine_sim --cov-report=term-missing
python -m machine_sim.cli.main check

python -m machine_sim.cli.main run -c configs/milestone_1.toml -t 500 -s 42 -o output/demo_m1
python -m machine_sim.cli.main inspect output/demo_m1

python -m machine_sim.cli.main run -c configs/milestone_2_crowded.toml -t 100 -s 42 -o output/demo_m2
python -m machine_sim.cli.main inspect output/demo_m2

python -m machine_sim.cli.main run -c configs/milestone_3_signals.toml -t 100 -s 42 -o output/demo_m3
python -m machine_sim.cli.main inspect output/demo_m3

python -m machine_sim.cli.main run -c configs/milestone_4_correlation.toml -t 100 -s 42 -o output/demo_m4
python -m machine_sim.cli.main inspect output/demo_m4

python -m machine_sim.cli.main run -c configs/milestone_5_adaptive.toml -t 150 -s 42 -o output/demo_m5
python -m machine_sim.cli.main inspect output/demo_m5
python -m machine_sim.cli.main compare -c configs/milestone_5_adaptive.toml -t 150 -s 42

python -m machine_sim.cli.main run -c configs/milestone_6_fabrication.toml -t 200 -s 42 -o output/demo_m6
python -m machine_sim.cli.main inspect output/demo_m6

python -m machine_sim.cli.main run -c configs/milestone_7_calibration_capsules.toml -t 200 -s 42 -o output/demo_m7
python -m machine_sim.cli.main inspect output/demo_m7
python -m machine_sim.cli.main capsule-compare -c configs/milestone_7_calibration_capsules.toml -t 200 -s 42

python -m machine_sim.cli.main run -c configs/milestone_8_telemetry_reconciliation.toml -t 200 -s 42 -o output/demo_m8
python -m machine_sim.cli.main inspect output/demo_m8

python -m machine_sim.cli.main run -c configs/milestone_9_resource_pressure.toml -t 200 -s 42 -o output/demo_m9
python -m machine_sim.cli.main inspect output/demo_m9

python -m machine_sim.cli.main run -c configs/milestone_10_signal_field_dynamics.toml -t 200 -s 42 -o output/demo_m10
python -m machine_sim.cli.main inspect output/demo_m10
```

## Test Results

```
194 passed in 16.14s
```

## Coverage

```
TOTAL    1405    238    83%
Total coverage: 83.06%
```

## M1–M10 Regression Summary

| Milestone | Key Metrics |
|-----------|-------------|
| M1 | 1881 events, 0/5 active |
| M2 | 1388 events, 3/6 active, 17 MOVEMENT_BLOCKED |
| M3 | 1060 events, 1/4 active, 29 SIGNAL_EMITTED |
| M4 | 1260 events, 1/5 active, 35 SIGNAL_EMITTED |
| M5 | 1511 events, 0/5 active |
| M5 compare | adaptive +77 events, +10 emissions, +100 received |
| M6 | 985 attempts, 9 successes, 9 lineage records |
| M7 | 9 capsules, avg_sparsity=0.50 |
| M7 compare | warm_start_power_delta +1.8906 |
| M8 | 50 frames, 182 reconciliation, 5 drift entries |
| M9 | 5 pressure cells, avg_depletion=0.366, max_pressure=0.760 |
| M10 | 3 patterns, 30 signals, 4 clusters, avg_score=12.295, gradient cells=4 |

## M10 Signal Dynamics Output

```
Signal dynamics: patterns=3, total_signals=30, clusters=4
Pattern correlation: records=3, avg_score=12.295, max_score=21.538
Signal gradient: cells=4, avg_gradient=1.180, max_gradient=3.701
```

## Artifact Paths
- `output/demo_m10/signal_field_dynamics.json`
- `output/demo_m9/pressure_analysis.json`
- `output/demo_m8/telemetry.json`
- `output/demo_m8/reconciliation.json`
- `output/demo_m8/lineage_drift.json`

## Known Limitations

1. Pattern frequency is computed from signal emission records only
2. Density clustering uses simple proximity thresholding
3. Signal gradient is derived from resource/hazard density, not actual signal field
4. Correlation scores are basic co-occurrence, not normalized or lag-weighted

## Next Recommended Milestone

Milestone 11: Operational Memory Compression — bounded signal history compression, pattern摘要, cross-unit memory sharing, lineage memory inheritance.
