# Milestone 7 Report: Calibration Assist and Operational Memory Capsule Transfer

## Date
2026-07-02

## Summary

Implemented machine-native calibration capsules that transfer bounded operational statistics from source units to fabricated successors during creation. Capsules contain numerical summaries of source unit state and local world conditions, applied as warm-start calibration to successor units.

## What Was Implemented

### 1. Calibration Capsule Model (environment/calibration.py)
- `CalibrationCapsule` dataclass with bounded machine-native fields
- Source unit snapshot: power ratio, component health, sensor/actuator health
- Local field summaries: hazard density, proximity count, movement blocks, emission/scan rates, signal count/intensity
- Resource density summary
- Warm-start calibration values: sensor calibration, power bias, scan cadence, field pressure
- Sparsity and completeness metrics

### 2. Capsule Generation (environment/calibration.py)
- `CapsuleGenerator` creates capsules from real source unit and world state
- Deterministic under same seed
- Bounded by configured window and entry limits
- No semantic meaning assigned — purely numerical

### 3. Warm-Start Application (environment/calibration.py)
- `apply_warm_start()` modifies successor sensor health and power reserve
- Records before/after deltas as `_capsule_warm_start_effect` metadata
- Observable but modest effect

### 4. Capsule Manager (environment/calibration.py)
- `CapsuleManager` generates, stores, and summarizes capsules
- `compute_capsule_impact()` compares capsule-enabled vs capsule-disabled successors
- Integrated into fabrication pipeline

### 5. Engine Integration (sim/engine.py)
- Capsule generated during successful fabrication
- Warm-start applied to successor before registration
- Capsule summary accessible via `get_capsule_summary()`
- `capsules.json` artifact written to output directory

### 6. Config
- `capsule_enabled`: bool — enable/disable capsule generation

## What Was Deliberately Excluded

- Teaching, learning, knowledge transfer semantics
- Parent/child/offspring biological framing
- Language, message, instruction concepts
- Culture, tradition, social inheritance
- Semantic signal interpretation

## Capsule Fields

| Field | Description |
|-------|-------------|
| source_unit_id | ID of fabricating unit |
| successor_unit_id | ID of created unit |
| fabrication_tick | Tick when fabricated |
| source_generation | Source's generation index |
| successor_generation | Source generation + 1 |
| source_power_ratio | Power reserve / max_power at fabrication |
| source_component_health | Average component health |
| source_sensor_health | Sensor component health |
| source_actuator_health | Actuator component health |
| source_hazard_density | Recent hazard encounter rate |
| source_proximity_count | Average nearby unit count |
| source_movement_blocks | Total movement blocks |
| source_emission_rate | Signal emission rate |
| source_scan_rate | Scan rate |
| source_signal_count | Total signals received |
| source_signal_intensity | Average signal intensity |
| local_resource_density | Resource density at source position |
| initial_sensor_calibration | Warm-start sensor health value |
| initial_power_bias | Warm-start power adjustment |
| initial_scan_cadence | Warm-start scan interval |
| initial_field_pressure | Warm-start field pressure |
| sparsity_score | 0.0 = complete, 1.0 = empty |
| capsule_entries | Number of populated fields |

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
```

## Test Results

```
165 passed in 11.01s
```

## Coverage

```
TOTAL    1325    208    84%
Total coverage: 84.30%
```

## Demo Output Summary

### M1: Survival Substrate (500 ticks, 20x20, 5 units)
```
Total events: 1851
  UNIT_ACTION: 610
  UNIT_PROXIMITY: 85
  RESOURCE_DEPLETED: 156
```

### M2: Interaction Substrate (100 ticks, 8x8, 6 units)
```
Total events: 1388
  UNIT_ACTION: 566
  UNIT_PROXIMITY: 479
  RESOURCE_DEPLETED: 113
  MOVEMENT_BLOCKED: 17
```

### M3: Signal Emission (100 ticks, 10x10, 4 units)
```
Total events: 1060
  UNIT_ACTION: 352
  UNIT_PROXIMITY: 220
  SIGNAL_RECEIVED: 127
  RESOURCE_DEPLETED: 96
  HAZARD_ENCOUNTER: 36
  SIGNAL_EMITTED: 29
```

### M4: Correlation (100 ticks, 12x12, 5 units)
```
Total events: 1260
  UNIT_ACTION: 420
  UNIT_PROXIMITY: 328
  SIGNAL_RECEIVED: 113
  RESOURCE_DEPLETED: 95
  MOVEMENT_BLOCKED: 42
  SIGNAL_EMITTED: 35
  HAZARD_ENCOUNTER: 27
```

### M5: Adaptive Control (150 ticks, 12x12, 5 units)
```
Total events: 1511
  UNIT_ACTION: 417+
  Adaptive behavior summary (cumulative):
    unit-000: total_signals=91, total_emissions=9, total_scans=8
    unit-001: total_signals=0, total_emissions=9, total_scans=9
    unit-002: total_signals=63, total_emissions=9, total_scans=6
    unit-003: total_signals=63, total_emissions=9, total_scans=8
    unit-004: total_signals=63, total_emissions=13, total_scans=15
```

### M5 Comparison (Baseline vs Adaptive)
```
  Metric                 Baseline   Adaptive      Delta
  --------------------------------------------------
  total_events               1434       1511 +       77
  emitted                      39         49 +       10
  received                    300        400 +      100
  blocked                      16         17 +        1
```

### M6: Fabrication (200 ticks, 20x20, 3 units)
```
Fabrication: 985 attempts, 9 successes, 9 lineage records
  Failures: {'insufficient_material': 77, 'fabrication_cooldown': 31, 'insufficient_power': 19, 'population_capacity': 849}
  Generations: {1: 2, 2: 2, 3: 2, 4: 3}
```

### M7: Calibration Capsules (200 ticks, 20x20, 3 units)
```
Fabrication: 985 attempts, 9 successes, 9 lineage records
  Capsules: 9 generated, avg_sparsity=0.50
```

### Capsule Impact Comparison
```
Capsule Impact Comparison:
  Metric                             Disabled      Enabled        Delta
  ------------------------------------------------------------------
  count                                  9.00         9.00        +0.00
  avg_power                            0.0000       0.0000      +0.0000
  avg_sensor_health                    0.9660       0.9660      +0.0000
  active_count                           0.00         0.00        +0.00
  warm_start_power_delta               0.0000       1.8906      +1.8906
  warm_start_sensor_delta              0.0000       0.0000      +0.0000
  capsule_applied                         N/A            9
  neutral_metric_delta_detected           yes          yes
```

## Known Limitations

1. Warm-start effect is modest — primarily power reserve adjustment (bounded)
2. Capsule does not transfer behavioral policies or decision rules
3. Capsule persistence is in-memory only (not disk-persistent across runs)

## Next Recommended Milestone

Milestone 8: Distributed Operational Telemetry Reconciliation and Lineage Calibration Drift — operational state continuity, redundant-state reconciliation, capsule lineage comparison, machine-native memory compression, diagnostic trace continuity.
