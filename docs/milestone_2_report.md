# Milestone 2 Report: Interaction Substrate

## Date
2026-06-29

## Summary

Implemented the first layer of machine-machine interaction: unit proximity detection, occupancy-aware movement, collision/movement-denial mechanics, and local spatial pressure metric. All mechanics are machine-native with no social/emotional interpretation.

## What Was Implemented

### 1. Unit Proximity Detection (world.py)
- `SensorReading.nearby_units` populated accurately for cells within sensor range
- `count_nearby_units()` method on World class
- Proximity events emitted when units detect nearby units
- No relationship, alliance, threat, or intent inference

### 2. Occupancy-Aware Movement (world.py)
- `_move()` method checks target cell occupancy before allowing movement
- Move into occupied cell fails with `movement_blocked` event type
- Unit remains in original position on failed move
- Power penalty applied for failed movement (-0.5)
- Both unit positions remain valid after failed movement

### 3. Collision/Contact Event Logging (events.py, engine.py)
- New event types: `MOVEMENT_BLOCKED`, `OCCUPANCY_CONSTRAINT`, `UNIT_PROXIMITY`, `CONTACT_EVENT`
- Events emitted during engine tick lifecycle
- All labels pass guardrail validation

### 4. Local Spatial Pressure Metric (world.py)
- `compute_spatial_pressure()` returns bounded [0.0, 1.0] metric
- Computed from nearby occupied cells / total nearby cells
- `count_nearby_units()` for raw count
- Deterministic for fixed seed
- Neutral metric, no social/emotional interpretation

### 5. Crowded Scenario (configs/milestone_2_crowded.toml)
- 8x8 grid, 6 units, low resource density
- Deterministic seed (42)
- Generates proximity and movement-blocked events reliably

## What Was Deliberately Excluded

- Semantic signaling
- Bit-pattern signaling
- Resource sharing
- Cooperation logic
- Hostility logic
- Attack/fight mechanics
- Blocking as intentional behavior
- Resource denial strategy
- Salvage/inter-unit exploitation
- Reproduction, inheritance, teaching
- Affect interpretation
- Observer-level emotion labels
- Society/civilization scoring
- Role-based agents

## Event Labels Added

| Label | Description |
|-------|-------------|
| `movement_blocked` | Move attempted into occupied cell |
| `occupancy_constraint` | Movement constraint due to occupancy |
| `unit_proximity` | Unit detected nearby units |
| `contact_event` | Physical co-presence event |

## Guardrail Updates

- Added new event labels to `ALLOWED_EVENT_LABELS`
- Added `movement_blocked`, `occupancy_constraint` to `ALLOWED_MEMORY_LABELS`
- All new labels are machine-native, no social/emotional terms
- Forbidden labels still rejected

## Commands Run

```bash
python -m pytest machine_sim/tests/ -v
python -m pytest machine_sim/tests/ --cov=machine_sim --cov-report=term-missing
python -m machine_sim.cli.main check
python -m machine_sim.cli.main run -c configs/milestone_1.toml -t 500 -s 42 -o output/demo_m1
python -m machine_sim.cli.main inspect output/demo_m1
python -m machine_sim.cli.main run -c configs/milestone_2_crowded.toml -t 100 -s 42 -o output/demo_m2
python -m machine_sim.cli.main inspect output/demo_m2
```

## Test Results

```
71 passed in 2.27s
```

## Coverage

```
TOTAL    787    107    86%
Total coverage: 86.40%
```

## Demo Output Summary

### Milestone 1 Demo (500 ticks, 20x20, 5 units)
```
Total events: 1851
  UNIT_ACTION: 610
  TICK_BEGIN: 500
  TICK_END: 500
  RESOURCE_DEPLETED: 156
  UNIT_PROXIMITY: 85
```

### Milestone 2 Crowded Demo (100 ticks, 8x8, 6 units)
```
Total events: 1379
  UNIT_ACTION: 566
  UNIT_PROXIMITY: 465
  RESOURCE_DEPLETED: 131
  TICK_BEGIN: 100
  TICK_END: 100
  MOVEMENT_BLOCKED: 17
```

## Known Limitations

1. Movement failure is simple (unit stays, power penalty) — no rerouting or pathfinding
2. Spatial pressure is a local metric only — no global coordination
3. No persistence of proximity data across ticks (computed fresh each tick)
4. Crowded scenario generates interactions but units still deactivate from power depletion

## Next Recommended Milestone

Milestone 3: Non-Semantic Signaling — bit-pattern emission/detection, signal correlation, coordination primitives.

---

## Milestone 2A Correction Notes

### What Was Fixed

1. **Self excluded from proximity sensing**
   - `World.sense()` now accepts `exclude_unit_id` parameter
   - Engine sensing and SCAN action both exclude the scanning unit itself
   - Unit no longer sees itself as a "nearby unit"

2. **Movement strictly adjacent**
   - `_move()` now rejects non-adjacent targets (distance > 1 in any axis)
   - Self-move (same cell) also rejected
   - Non-adjacent moves emit `move_failed` with power penalty
   - World occupancy remains consistent after rejection

3. **Spatial pressure excludes center cell**
   - `compute_spatial_pressure()` now skips `(dx == 0, dy == 0)`
   - Lone unit with no neighbors has pressure 0.0
   - Measures nearby crowding only, not self-contribution

4. **Unused event labels removed**
   - Removed `OCCUPANCY_CONSTRAINT` and `CONTACT_EVENT` from allowed labels
   - Only `UNIT_PROXIMITY` and `MOVEMENT_BLOCKED` are emitted in Milestone 2
   - Documentation updated to match actual emitted events

5. **Crowded scenario test tightened**
   - Added `test_forced_blocked_movement_in_engine` that proves MOVEMENT_BLOCKED emission
   - Proximity test remains for determinism verification
