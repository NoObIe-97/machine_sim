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
- Stores capsule as metadata on successor unit
- Observable but modest effect

### 4. Capsule Manager (environment/calibration.py)
- `CapsuleManager` generates, stores, and summarizes capsules
- Integrated into fabrication pipeline
- Summary artifact for review

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
python -m machine_sim.cli.main run -c configs/milestone_6_fabrication.toml -t 200 -s 42 -o output/demo_m6
python -m machine_sim.cli.main run -c configs/milestone_7_calibration_capsules.toml -t 200 -s 42 -o output/demo_m7
```

## Test Results

```
160 passed in 11.07s
```

## Coverage

```
TOTAL    1257    172    86%
Total coverage: 86.32%
```

## Demo Output Summary

### Milestone 7 Calibration Capsule Demo (200 ticks, 20x20, 3 units)
```
Fabrication: 985 attempts, 9 successes, 9 lineage records
  Generations: {1: 2, 2: 2, 3: 2, 4: 3}
  Capsules: 9 generated, avg_sparsity=0.50
```

## Known Limitations

1. Warm-start effect is modest — sensor health adjustment and small power bias
2. Capsule does not transfer behavioral policies or decision rules
3. No capsule comparison or impact metrics yet
4. Capsule persistence is in-memory only (not disk-persistent across runs)

## Next Recommended Milestone

Milestone 8: Distributed Operational Memory — persistent memory across ticks, memory sharing, distributed consensus.
