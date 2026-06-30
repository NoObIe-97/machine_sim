# Milestone 6 Report: Fabricated Descent, Design Inheritance, and Population Dynamics

## Date
2026-06-29

## Summary

Implemented machine-native fabrication where units create successor units through a constrained fabrication process with resource costs, placement rules, and deterministic design variation. Introduced lineage tracking, population dynamics, and fabrication summaries.

## What Was Implemented

### 1. Fabrication Engine (environment/fabrication.py)
- `FabricationEngine` class with configurable constraints
- Prerequisite checks: power, component health, cooldown, material, placement, population cap
- Resource costs: power deduction, material consumption from local resources
- Placement: finds empty adjacent cell for successor
- Deterministic design variation via `DesignTemplate` with bounded noise

### 2. Design Template (environment/fabrication.py)
- `DesignTemplate` dataclass with bounded machine-native parameters
- Inherits from source unit with deterministic variation (configurable `variation_factor`)
- Parameters: variant_name, max_power, sensor_range, power_drain_rate, signal settings, adaptive setting

### 3. Lineage Tracking (environment/fabrication.py)
- `LineageRecord` dataclass with: source_unit_id, successor_unit_id, generation indices, fabrication_tick
- Lineage records stored and queryable via `get_lineage_records()`
- Generation distribution computed in summary

### 4. Engine Integration (sim/engine.py)
- Phase 7: Fabrication phase in tick lifecycle
- Creates successor units from design templates
- Registers new units in world with placement
- Emits `FABRICATION_SUCCEEDED` and `FABRICATION_FAILED` events

### 5. Population Dynamics
- Population cap enforced by FabricationEngine
- Fabrication attempts/successes/failures tracked
- Generation distribution computed
- Active unit count visible in CLI output

### 6. Config and CLI
- `fabrication_enabled`, `population_cap`, `fabrication_interval`, `fabrication_power_cost`, `fabrication_material_cost`, `fabrication_variation`
- CLI outputs fabrication summary with attempts, successes, failures, lineage
- `fabrication.json` artifact written to output directory

## What Was Deliberately Excluded

- Biological reproduction concepts
- Family, tribe, kin, ancestor/descendant labels
- Social inheritance or heredity
- Mating, birth, fertility concepts
- Emotional attachment to successors

## Event Labels Added

| Label | Description |
|-------|-------------|
| `fabrication_attempted` | Fabrication process initiated |
| `fabrication_succeeded` | Successor unit created |
| `fabrication_failed` | Fabrication attempt failed |

## Failure Reasons (machine-native)

| Cause | Description |
|-------|-------------|
| `insufficient_power` | Source unit lacks power |
| `insufficient_material` | Local resources too low |
| `placement_unavailable` | No empty adjacent cell |
| `population_capacity` | Population cap reached |
| `source_unstable` | Source component health too low |
| `fabrication_cooldown` | Cooldown period not elapsed |

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
python -m machine_sim.cli.main run -c configs/milestone_6_fabrication.toml -t 250 -s 42 -o output/demo_m6
python -m machine_sim.cli.main inspect output/demo_m6
```

## Test Results

```
150 passed in 5.96s
```

## Coverage

```
TOTAL    1144    155    86%
Total coverage: 86.45%
```

## Demo Output Summary

### Milestone 6 Fabrication Demo (250 ticks, 15x15, 4 units)
```
Total events: 2245
  UNIT_ACTION: 629
  FABRICATION_FAILED: 617
  FABRICATION_SUCCEEDED: 4
  RESOURCE_DEPLETED: 233
  UNIT_PROXIMITY: 144
  SIGNAL_RECEIVED: 69
  SIGNAL_EMITTED: 49

Fabrication: 621 attempts, 4 successes, 4 lineage records
  Failures: {'insufficient_material': 105, 'fabrication_cooldown': 31, 'insufficient_power': 481}
  Generations: {1: 2, 2: 2}
```

## Known Limitations

1. Fabrication is purely reactive — no predictive or strategic fabrication
2. Design variation is bounded but simple — no complex mutation
3. No cross-unit design comparison or competition
4. Population dynamics are local — no global population pressure model
5. Fabrication does not yet influence adaptive behavior or signal patterns

## Next Recommended Milestone

Milestone 7: Calibration Assist and Knowledge Transfer — parameter calibration for successors, experience capsule transfer, knowledge accumulation across generations.
