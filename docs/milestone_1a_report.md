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
55 passed in 1.71s
```

## Coverage

```
TOTAL    747    104    86%
Total coverage: 86.08%
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

---

## Milestone 1B Correction Notes

### What Was Fixed

1. **Config-key validation integrated into config loading**
   - `SimConfig.from_toml()` now calls `validate_config_keys()` before constructing `SimConfig`
   - Unknown keys like `social_graph` or `morale_level` are rejected at load time
   - Tests prove both rejection of invalid keys and acceptance of valid keys

2. **Runtime validation tests strengthened**
   - `test_engine_rejects_forbidden_action_name` — verifies action validation path in engine
   - `test_engine_rejects_forbidden_event_label` — verifies event label validation
   - `test_engine_rejects_corrupted_unit_state` — proves out-of-bounds power is rejected
   - `test_engine_rejects_corrupted_memory_label` — proves forbidden memory labels are rejected

3. **Weak hazard test fixed**
   - `test_engine_emits_hazard_events` now places hazard at unit's actual position (after random init)
   - Asserts at least one HAZARD_ENCOUNTER event is emitted
   - `test_engine_hazard_can_deactivate_unit` proves deactivation from combined degrade + hazard damage

4. **Event logging scope clarified**
   - Harvest/maintain/component events are captured as action result labels in `UNIT_ACTION` logs
   - Hazard encounters and unit deactivation have dedicated `EventType` entries
   - All event labels are machine-native

### Honest Assessment

- Runtime validation is integrated into the engine tick lifecycle and rejects forbidden labels at the engine level
- Config validation now happens at load time, not just in isolated tests
- Hazard mechanics are functional and provably emit events and cause deactivation
- The substrate is ready for Milestone 2 interaction mechanics
