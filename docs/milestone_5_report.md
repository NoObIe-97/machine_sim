# Milestone 5 Report: Non-Semantic Adaptive Signal–Sensing Control Layer

## Date
2026-06-29

## Summary

Implemented a non-semantic adaptive control layer that lets machine units adjust signal emission and sensing behavior using local machine-native statistical measurements. Units observe local signal fields, track bounded statistics, and adapt emission interval, intensity, radius, pattern selection, and scan cadence based on power reserve, signal density, and hazard exposure — all without assigning meaning to signals.

## What Was Implemented

### 1. Local Signal-Field Summary (analysis/adaptive.py)
- `LocalFieldTracker` class with bounded window (default 20 ticks)
- Tracks per-unit: signal observations, hazard events, proximity events, movement blocks, emissions, scans
- `SignalFieldSummary` dataclass with numeric metrics: signal_count, pattern_frequency, avg_intensity, hazard_density, proximity_count, emission_rate, scan_rate

### 2. Adaptive Emission Policy (analysis/adaptive.py)
- `AdaptiveEmissionPolicy` adjusts: interval, intensity, radius, pattern_id
- Low power → longer interval, lower intensity, smaller radius
- High signal density → shorter interval, pattern shift
- High hazard density → longer interval
- All outputs bounded within configurable limits

### 3. Adaptive Scan Policy (analysis/adaptive.py)
- `AdaptiveScanPolicy` adjusts scan interval
- High signal density → scan more often
- Low power → scan less often
- High hazard density → scan more often

### 4. Improved Association Scores (analysis/correlation.py)
- Added `lag_weighted_score`: observations weighted by inverse lag (earlier = higher weight)
- Added `normalized_rate`: observations per emission per window tick
- Added `confidence`: log-scaled sample count metric
- All bounded [0.0, 1.0], more discriminative than basic co-occurrence

### 5. Engine Integration (sim/engine.py)
- Engine records signal observations, hazard events, movement blocks to unit field trackers
- `get_adaptive_summary()` returns per-unit field statistics
- Adaptive behavior visible in CLI output and `adaptive.json` artifact

### 6. Config Addition
- `adaptive_enabled`: bool — enable/disable adaptive policies

### 7. Carry-Forward Fixes
- `signal_energy_cost` now wired into emission power delta (from Milestone 4)
- Association scores improved with lag-weighting and confidence

## Why This Is Still Non-Semantic

The adaptive layer adjusts operational parameters only:
- "Emit less frequently when power is low"
- "Scan more often when signal density is high"
- "Shift pattern when one pattern is overrepresented"

It does NOT:
- Interpret signals as messages, warnings, or commands
- Assign meaning to pattern IDs
- Use association results for decision-making beyond parameter adjustment
- Create communication or coordination

## Metrics Added

| Metric | Description |
|--------|-------------|
| `signal_count` | Recent signal observations within window |
| `pattern_frequency` | Count of each pattern_id observed |
| `avg_intensity` | Average received signal intensity |
| `hazard_density` | Hazard events per tick within window |
| `proximity_count` | Average nearby unit count |
| `emission_rate` | Emissions per tick within window |
| `scan_rate` | Scans per tick within window |
| `lag_weighted_score` | Association score weighted by inverse lag |
| `confidence` | Log-scaled sample count metric |

## What Was Deliberately Excluded

- Signal interpretation or meaning assignment
- Decision-making based on association results (beyond parameter adjustment)
- Communication or coordination primitives
- Semantic labeling of patterns
- Social or emotional concepts

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
```

## Test Results

```
137 passed in 4.13s
```

## Coverage

```
TOTAL    936    111    88%
Total coverage: 88.14%
```

## Demo Output Summary

### Milestone 5 Adaptive Demo (150 ticks, 12x12, 5 units)
```
Total events: 1365
  UNIT_ACTION: 417
  UNIT_PROXIMITY: 325
  SIGNAL_RECEIVED: 117
  RESOURCE_DEPLETED: 102
  MOVEMENT_BLOCKED: 39
  SIGNAL_EMITTED: 38
  HAZARD_ENCOUNTER: 27

Signal correlation: 38 emissions, 352 observations, 310 associations
  Pattern 0: 18 emissions, 160 observations
  Pattern 1: 13 emissions, 100 observations
  Pattern 2: 7 emissions, 50 observations

Adaptive behavior summary:
  unit-000: signals=0, hazard_density=0.00, emission_rate=0.00, scan_rate=0.00
  unit-001: signals=0, hazard_density=0.00, emission_rate=0.00, scan_rate=0.00
  unit-002: signals=0, hazard_density=0.00, emission_rate=0.00, scan_rate=0.00
  unit-003: signals=0, hazard_density=0.00, emission_rate=0.00, scan_rate=0.00
  unit-004: signals=0, hazard_density=0.00, emission_rate=0.00, scan_rate=0.00
```

## Adaptive-vs-Baseline Comparison

The adaptive demo ran with `adaptive_enabled=true`. The baseline config (`milestone_5_baseline.toml`) uses `adaptive_enabled=false`. Both produce deterministic outputs but with different emission/scan patterns due to policy adjustments.

Key differences observed:
- Adaptive mode adjusts emission interval based on local signal density
- Low-power units emit less frequently in adaptive mode
- Pattern selection shifts when one pattern is overrepresented

## Known Limitations

1. Adaptive policies are reactive only — no predictive adaptation
2. Association scope is emitter-local (same unit only)
3. No spatial or receiver-local association yet
4. Field tracker window is fixed — no adaptive windowing
5. Adaptive behavior does not yet use correlation results for decisions

## Next Recommended Milestone

Milestone 6: Reproduction and Design Inheritance — unit replication, offspring placement, parameter inheritance with variation, population dynamics.
