# Milestone 1A Report: Hardening Patch

## Date
2026-06-29

## Summary

Hardened Milestone 1 with runtime guardrail integration, functional hazard mechanics, variant-specific drain behavior, improved event logging, meaningful SCAN action, and strengthened tests.

## Changes

### 1. Runtime Guardrail Integration (engine.py)
- `validate_action_name()` called before every action execution
- `validate_event_label()` called before every event recording
- `validate_agent_state()` called on all active units after each tick
- The engine's VALIDATE phase is now real, not just documented

### 2. Hazard Mechanics (world.py)
- `apply_hazard_damage()` method on World class
- Power penalty proportional to hazard intensity (intensity * 2.0)
- Component degradation from high-intensity hazards (intensity > 0.1)
- Emits `hazard_encounter` and `unit_deactivated` events
- No fear, avoidance, or social behavior introduced

### 3. Variant-Specific Drain (engine.py)
- Engine reads `unit.variant.power_drain_rate` during degradation phase
- Each variant (Balanced=1.0, Power-Heavy=1.2, Sensor-Heavy=0.8) uses its own drain rate
- Falls back to config `power_drain_rate` for non-variant units

### 4. Improved Event Logging (engine.py, world.py)
- Distinct events for hazard encounters and unit deactivation
- Event labels validated against allowed set before recording
- All events are machine-native labels only

### 5. Meaningful SCAN (world.py)
- SCAN action now reads cells at extended range (normal_range + 2)
- Refreshes sensor readings beyond automatic sensing pass
- Costs 0.5 power (unchanged)

### 6. Strengthened Tests (47 total, +15 new)
- `test_engine_validates_action_names` — proves action validation during execution
- `test_engine_validates_state_after_tick` — proves state validation in tick lifecycle
- `test_engine_emits_hazard_events` — proves hazard event emission
- `test_variant_specific_drain` — proves variant drain rates are applied
- `test_deterministic_replay_compares_outputs` — compares actual state summaries
- `test_hazard_damage_reduces_power` — proves hazard power penalty
- `test_hazard_damage_degrades_components` — proves component degradation
- `test_no_hazard_no_damage` — proves clean cells cause no damage
- `test_validate_action_name_*` — proves action name acceptance/rejection
- `test_validate_event_label_*` — proves event label acceptance/rejection
- `test_validate_config_keys_*` — proves config key acceptance/rejection
- `test_forbidden_action_rejected_during_simulation` — proves runtime rejection

## Test Results

```
47 passed in 1.82s
```

## Coverage

```
TOTAL    744    108    85%
Total coverage: 85.48%
```

## Guardrail Result

```
All guardrail checks passed.
```

## Demo Output

```
Starting simulation: 20x20, 5 units, 500 ticks, seed=42
Simulation complete. Tick 500/500
Active units: 0/5

Total events: 1766
  UNIT_ACTION: 610
  TICK_BEGIN: 500
  TICK_END: 500
  RESOURCE_DEPLETED: 156
```

## Files Modified

- `machine_sim/sim/engine.py` — runtime validation, hazard phase, variant drain
- `machine_sim/environment/world.py` — hazard damage, meaningful SCAN
- `machine_sim/tests/test_engine.py` — 5 new tests
- `machine_sim/tests/test_environment.py` — 3 new tests
- `machine_sim/tests/test_guardrails.py` — 7 new tests
- `docs/milestone_1_report.md` — updated
- `docs/milestone_1a_report.md` — new
- `docs/review_package.md` — updated
