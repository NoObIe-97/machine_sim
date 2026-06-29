# Milestone 1 Report: After Silicon Survival Substrate

## Date
2026-06-29

## Summary

Implemented the executable, tested, bias-guarded survival substrate for the After Silicon machine civilization emergence simulator. The system runs deterministic tick-based simulations with machine-native units that survive through resource harvesting, component maintenance, and power management.

## What Was Built

### Simulation Engine
- Tick-based loop with 7 phases: ENV_UPDATE → SENSE → DECIDE → ACT → DEGRADE → LOG → VALIDATE
- Deterministic seeding via isolated `random.Random` instances
- Configurable grid size, resource/hazard density, unit count, tick count

### Machine Units
- Single generic `MachineUnitImpl` class with 3 hardware-variant parameter sets (Balanced, Power-Heavy, Sensor-Heavy)
- Machine-native state: power_reserve, components (sensor, actuator, processor, power_cell), sensor_readings, local_memory
- Decision logic uses only threshold gates, gradient following, correlation detection, and reinforcement scoring
- No anthropomorphic concepts in runtime logic

### Milestone 1 Primitive Actions
- MOVE — adjacent cell traversal (cost: -2.0 power)
- SCAN — refresh sensor buffer (cost: -0.5 power)
- HARVEST — collect resources at current position (cost: -0.5, gains power)
- COLLECT — pick up inert material (cost: -1.0 power)
- MAINTAIN — self-repair component (cost: -5.0 power)
- IDLE — conserve power (cost: -0.1 power)

### Environment
- Dict-based sparse grid with resources (POWER_NODE, COMPONENT_SCRAP, CONDUCTOR) and hazards (EM_PULSE, THERMAL_ZONE, CORROSIVE_FIELD, DEBRIS)
- Resource regrowth and hazard decay mechanics
- Local sensing within configurable range

### Guardrail System
- **Lexical scan**: regex detection of anthropomorphic terms in agent/environment code
- **AST check**: forbidden assignments, class bases, and parameters
- **Runtime validation**: state fields, component names, action names, event labels, config keys, memory labels
- Guardrails, CLI, and test directories excluded from self-scan

### CLI
- `run` — execute simulation with config overrides and output artifacts
- `inspect` — display event counts from a completed run
- `check` — run guardrail lexical + AST scan

### Event Logging
- Append-only event log with JSON serialization
- Event types: TICK_BEGIN, TICK_END, UNIT_ACTION, RESOURCE_DEPLETED, etc.

## Test Results

```
32 passed in 0.50s
Coverage: 85.14%
```

## Guardrail Result

```
All guardrail checks passed.
```

## Demo Output

- 500-tick simulation, 5 units, 20x20 grid, seed=42
- 1802 total events (643 UNIT_ACTION, 500 TICK_BEGIN, 500 TICK_END, 159 RESOURCE_DEPLETED)
- All units deactivated by tick 500 (expected — power depletion is the survival pressure)

## Files Created

```
pyproject.toml
configs/milestone_1.toml
machine_sim/__init__.py
machine_sim/sim/__init__.py
machine_sim/sim/config.py
machine_sim/sim/events.py
machine_sim/sim/engine.py
machine_sim/sim/state.py
machine_sim/sim/seed.py
machine_sim/agents/__init__.py
machine_sim/agents/base.py
machine_sim/agents/unit.py
machine_sim/agents/components.py
machine_sim/agents/variants.py
machine_sim/agents/decision.py
machine_sim/environment/__init__.py
machine_sim/environment/world.py
machine_sim/environment/resources.py
machine_sim/environment/hazards.py
machine_sim/environment/terrain.py
machine_sim/guardrails/__init__.py
machine_sim/guardrails/config.py
machine_sim/guardrails/lexical.py
machine_sim/guardrails/codecheck.py
machine_sim/guardrails/runtime.py
machine_sim/analysis/__init__.py
machine_sim/cli/__init__.py
machine_sim/cli/main.py
machine_sim/tests/__init__.py
machine_sim/tests/conftest.py
machine_sim/tests/test_config.py
machine_sim/tests/test_engine.py
machine_sim/tests/test_agents.py
machine_sim/tests/test_environment.py
machine_sim/tests/test_guardrails.py
machine_sim/tests/test_determinism.py
machine_sim/tests/test_cli.py
output/demo/state.json
output/demo/events.json
docs/architecture.md
docs/roadmap.md
docs/guardrails.md
docs/milestone_1_plan.md
docs/review_package_spec.md
```

## Known Limitations

1. **All units deactivate within 500 ticks** — power drain outpaces harvesting with current parameters. This is expected survival pressure, not a bug. Tuning config parameters (lower drain rate, higher resource density) would extend survival.
2. **No inter-unit interaction** — Milestone 1 has no collision, signaling, or resource competition between units.
3. **Terrain module is defined but not yet integrated** into the world grid.
4. **Decision logic is purely reactive** — no multi-step planning or prediction. This is intentional for Milestone 1.

## Recommended Next Steps (Milestone 2)

- Add unit-unit proximity detection and collision mechanics
- Implement environmental modification (terrain alteration)
- Add spatial territory patterns
- Introduce non-semantic signaling (bit-pattern emission/detection)
