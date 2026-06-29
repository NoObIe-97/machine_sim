# Milestone 3 Report: Non-Semantic Signaling Substrate

## Date
2026-06-29

## Summary

Implemented a non-semantic signaling substrate where units can emit physical signal pulses that propagate, decay, and are sensed by nearby units. Signals are environmental physics — no meaning, communication, or coordination is assigned.

## What Was Implemented

### 1. Signal Data Structure (world.py)
- `Signal` dataclass with: signal_id, source_unit_id, pattern_id, position, intensity, radius, decay_rate, emitted_tick, duration
- Signals are stored in `World.signals` list
- Signals are part of world state, like resources and hazards

### 2. Signal Emission (world.py, agents/base.py)
- New `ActionType.EMIT_SIGNAL` action type
- `_emit_signal()` method creates signals in the world
- Energy cost: -2.0 power per emission
- Configurable parameters: pattern_id, intensity, radius, decay_rate, duration

### 3. Signal Propagation and Decay (world.py)
- `emit_signal()` method places signals at source position
- Signals propagate within bounded radius
- `update()` method decays signal intensity each tick
- Signals expire after duration ticks
- Decay and removal are deterministic

### 4. Signal Sensing (world.py, sim/engine.py)
- `sense_signals()` returns observations visible from a position
- Source units are excluded from receiving their own signals (explicit policy)
- Observations include: signal_id, source_unit_id, pattern_id, position, intensity, signal_strength, distance
- Signal strength decreases with distance from source
- Engine emits `SIGNAL_RECEIVED` events for each visible signal

### 5. Signal Event Logging (events.py, engine.py)
- `SIGNAL_EMITTED` event when unit emits signal
- `SIGNAL_RECEIVED` event when unit senses signal
- All labels pass guardrail validation

### 6. Neutral Emission Rule (agents/unit.py)
- Units emit signals periodically (every 5 ticks) when power > 50%
- Pattern_id cycles through 0, 1, 2
- No social/cooperative/conflict meaning assigned
- Controlled by `signal_enabled` config flag

### 7. Signal Config (sim/config.py)
- `signal_enabled`: bool — enable/disable signal emission
- `signal_pattern_count`: int — number of pattern types
- `signal_energy_cost`: float — power cost per emission
- `signal_default_radius`: int — default signal range
- `signal_default_decay`: float — intensity decay per tick
- `signal_default_duration`: int — ticks before signal expires

## What Was Deliberately Excluded

- Language, messages, communication
- Cooperation, coordination, negotiation
- Warnings, requests, commands
- Meaning, symbolism, interpretation
- Trust, threat, alliance
- Deception, misleading signals
- Shared conventions or protocols

## Runtime Labels Added

| Type | Label | Description |
|------|-------|-------------|
| Action | `EMIT_SIGNAL` | Emit a physical signal pulse |
| Event | `signal_emitted` | Signal was emitted by a unit |
| Event | `signal_received` | Unit sensed a nearby signal |

## Guardrail Updates

- Added `EMIT_SIGNAL` to `ALLOWED_ACTION_NAMES`
- Added `emit_signal`, `signal_emitted`, `signal_received` to `ALLOWED_EVENT_LABELS`
- Added signal config keys to `ALLOWED_CONFIG_KEYS`
- Added `emit_signal` to `ALLOWED_MEMORY_LABELS`
- Forbidden semantic labels still rejected

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
```

## Test Results

```
92 passed in 2.34s
```

## Coverage

```
TOTAL    856    107    88%
Total coverage: 87.50%
```

## Demo Output Summary

### Milestone 1 Demo (500 ticks, 20x20, 5 units)
```
Total events: 1851
  UNIT_ACTION: 610
  UNIT_PROXIMITY: 85
  RESOURCE_DEPLETED: 156
```

### Milestone 2 Crowded Demo (100 ticks, 8x8, 6 units)
```
Total events: 1379
  UNIT_ACTION: 566
  UNIT_PROXIMITY: 465
  RESOURCE_DEPLETED: 131
  MOVEMENT_BLOCKED: 17
```

### Milestone 3 Signal Demo (100 ticks, 10x10, 4 units)
```
Total events: 1244
  UNIT_ACTION: 342
  SIGNAL_RECEIVED: 327
  UNIT_PROXIMITY: 212
  RESOURCE_DEPLETED: 102
  HAZARD_ENCOUNTER: 33
  SIGNAL_EMITTED: 28
```

## Known Limitations

1. Signal propagation is distance-based only (no terrain/obstacle attenuation)
2. Emission rule is simple periodic — no adaptive emission
3. No signal accumulation or interference model
4. Units store observations in memory but do not act on signal content
5. Pattern_id is a simple integer — no complex waveform representation

## Next Recommended Milestone

Milestone 4: Signal Correlation and Statistical Association — signal pattern correlation across ticks, temporal clustering, density mapping, adaptive emission. Still no semantic meaning assigned.
