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
- `signal_density`: total signal observations
- `signal_observation_load`: signal emission rate
- `field_perturbation_score`: signal density × proximity pressure

## What Was Deliberately Excluded

- Social communication, teaching, learning
- Consensus, negotiation, cooperation
- Biological inheritance, parent/child framing
- Language, message, instruction concepts

## Commands Run

```bash
python -m pytest machine_sim/tests/ -v
python -m pytest machine_sim/tests/ --cov=machine_sim --cov-report=term-missing
python -m machine_sim.cli.main check
python -m machine_sim.cli.main run -c configs/milestone_9_resource_pressure.toml -t 200 -s 42 -o output/demo_m9
python -m machine_sim.cli.main inspect output/demo_m9
```

## Test Results

```
182 passed in 14.31s
```

## Coverage

```
TOTAL    936    222    84%
Total coverage: 83.75%
```

## Demo Output Summary

### Milestone 9 Resource Pressure Demo (200 ticks, 15x15, 5 units)
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

Milestone 10: Signal Pattern Correlation Analysis — cross-tick signal pattern frequency analysis, temporal signal clustering, signal-density gradient mapping, pattern-observation correlation scoring, non-semantic signal-field interpretation layer.
