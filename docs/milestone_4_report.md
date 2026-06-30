# Milestone 4 Report: Signal Correlation and Statistical Association

## Date
2026-06-29

## Summary

Implemented a non-semantic signal correlation analysis layer that measures temporal associations between signal patterns and later machine-native observations. The system computes co-occurrence statistics without assigning meaning to signals.

## What Was Implemented

### 1. SignalCorrelator (analysis/correlation.py)
- `SignalCorrelator` class with bounded observation window
- Records signal emissions and observations
- Computes temporal associations within bounded windows
- Aggregates per-pattern statistics: emission counts, observation counts, average lag, co-occurrence scores
- Co-occurrence score bounded [0.0, 1.0]
- Deterministic replay support

### 2. Engine Integration (sim/engine.py)
- Engine records signal emissions to correlator
- Engine records proximity and hazard observations to correlator
- `get_correlation_summary()` returns full association data
- Summary exported to `correlation.json` in output directory

### 3. Signal Energy Cost Wiring (carry-forward fix)
- `signal_energy_cost` config now drives actual emission power delta
- Unit passes `energy_cost` parameter to world
- `_emit_signal()` uses `energy_cost` from action parameters

### 4. Config Addition
- `signal_observation_window`: int — bounded window for temporal association (default: 10)

### 5. CLI Enhancement
- `run` command outputs correlation summary when signals are enabled
- Writes `correlation.json` to output directory

## Why This Is Still Non-Semantic

The correlation layer measures statistical co-occurrence only:
- "Pattern 0 has 9 emissions, 60 observations within window"
- "Average lag for hazard_encounter is 2.3 ticks"

It does NOT:
- Interpret signals as messages, warnings, or commands
- Assign meaning to pattern IDs
- Use correlation results for decision-making
- Create communication or coordination

## Metrics Added

| Metric | Description |
|--------|-------------|
| `total_emissions` | Number of signal emissions recorded |
| `total_observations` | Number of observations recorded |
| `total_associations` | Number of signal-observation pairs within window |
| `pattern.emissions` | Emissions per pattern_id |
| `pattern.observations` | Observations associated per pattern |
| `pattern.observation_counts` | Breakdown by observation type |
| `pattern.avg_lag` | Average ticks between signal and observation |
| `pattern.co_occurrence_score` | Observations per emission (bounded 0-1) |

## What Was Deliberately Excluded

- Signal interpretation or meaning assignment
- Decision-making based on correlation results
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
```

## Test Results

```
111 passed in 4.46s
```

## Coverage

```
TOTAL    885    102    88%
Total coverage: 88.47%
```

## Demo Output Summary

### Milestone 4 Correlation Demo (100 ticks, 12x12, 5 units)
```
Total events: 1246
  UNIT_ACTION: 411
  UNIT_PROXIMITY: 321
  SIGNAL_RECEIVED: 113
  RESOURCE_DEPLETED: 99
  MOVEMENT_BLOCKED: 41
  SIGNAL_EMITTED: 34
  HAZARD_ENCOUNTER: 27

Signal correlation: 34 emissions, 348 observations, 270 associations
  Pattern 1: 13 emissions, 100 observations, scores={'proximity': 1.0, 'hazard_encounter': 1.0}
  Pattern 0: 11 emissions, 90 observations, scores={'proximity': 1.0, 'hazard_encounter': 1.0}
  Pattern 2: 10 emissions, 80 observations, scores={'proximity': 1.0, 'hazard_encounter': 1.0}
```

## Known Limitations

1. Correlation is co-occurrence only — no causal inference
2. Association window is fixed — no adaptive windowing
3. Observations are limited to proximity and hazard encounters
4. No multi-variate correlation (only pairwise signal-observation)
5. Correlation results not yet used for unit decisions

## Next Recommended Milestone

Milestone 5: Adaptive Signal Response — units adjust emission behavior based on local signal density and correlation metrics, still without semantic interpretation.
