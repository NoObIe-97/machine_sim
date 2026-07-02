# Milestone 9 Report: Resource Pressure and Field Perturbation Analysis

## Date
2026-07-02

## Summary

Implemented deterministic resource pressure analysis, extraction-load coupling, proximity pressure envelopes, and signal-field perturbation metrics. The system measures how multiple units reshape their shared operating field through extraction, density, movement blocking, and signal activity.

## What Was Implemented

### 1. Pressure Analyzer (analysis/pressure.py)
- `PressureAnalyzer` computes resource pressure, extraction load, proximity pressure, and signal-field perturbation
- Bounded by configured window and max records
- Deterministic under same seed

### 2. Resource Pressure Metrics
- `resource_pressure_cells`: count of cells with pressure
- `avg_resource_pressure`: average pressure across active units
- `max_resource_pressure`: maximum pressure observed
- `resource_depletion_rate`: inverse of average pressure

### 3. Extraction-Load Coupling
- `total_extraction_events`: count of extraction activity
- `peak_cell_load`: maximum extraction load observed
- `avg_load_per_active_unit`: average load per active unit

### 4. Proximity Pressure Envelope
- `avg_proximity_pressure`: average nearby unit density pressure
- `max_proximity_pressure`: maximum proximity pressure
- `movement_block_pressure`: rate of movement blocks
- `active_unit_density`: units per grid cell

### 5. Signal-Field Perturbation
- `signal_density`: total signal observations (emitted + received)
- `signal_observation_load`: signal emission rate
- `field_perturbation_score`: signal density × proximity pressure

## Scope Boundary

- Signal patterns are treated only as numeric field events.
- Pressure analysis is observational and numeric only.
- Unit state is not modified by pressure summaries.
- Runtime metrics remain limited to resource, movement, signal-field, component, and density measurements.

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
```

## Test Results

```
186 passed in 16.09s
```

## Coverage

```
TOTAL    1383    231    83%
Total coverage: 83.30%
```

## M1–M9 Regression Summary

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

## M9 Pressure Output

```
Resource pressure: cells=5, avg_depletion=0.366, max_pressure=0.760
Extraction load: total=5, peak_load=0.890, avg_load=1.000
Proximity pressure: avg=0.320, max=0.600, blocked_rate=17.000
Field perturbation: density=278.0, perturbation=88.960
```

## Known Limitations

1. Pressure metrics are frame-based (sampled at intervals), not continuous
2. Extraction load is based on resource depletion level, not actual harvest events
3. Signal-field perturbation is a simple product of density and proximity
4. Reconciliation does not modify unit state — it only records and summarizes

## Next Recommended Milestone

Milestone 10: Signal Pattern Field Dynamics — cross-tick pattern frequency analysis, temporal signal-density clustering, signal-gradient mapping, pattern-observation correlation scoring, and non-semantic field dynamics summaries.
