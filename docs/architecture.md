# Architecture

## Overview

After Silicon is a tick-based simulator where autonomous post-collapse machines start with machine-native survival telemetry. Civilization-like patterns emerge from resource pressure, memory, prediction, and environmental mechanics.

## Core Components

### Simulation Engine (`sim/engine.py`)
Tick-based loop with phases per tick:
1. **ENV_UPDATE** — Resources regrow, hazards decay, signals decay
2. **SENSE** — Units read local grid cells
3. **DECIDE** — Units choose action based on state + memory
4. **ACT** — Actions execute against world (occupancy-aware, signal emission)
5. **PROXIMITY** — Compute nearby unit counts and spatial pressure
6. **SIGNAL_SENSING** — Units observe nearby signals
7. **DEGRADE** — Power drains, components wear (variant-specific)
8. **HAZARD** — Apply hazard damage to units on hazardous cells
9. **VALIDATE** — Guardrails assert machine-native state

### Machine Units (`agents/`)
- Single `MachineUnitImpl` class with hardware-variant parameters
- Machine-native state: power, components, sensor readings, local memory
- Decision logic: threshold gates, gradient following, correlation detection, reinforcement

### Environment (`environment/`)
- Dict-based sparse grid with occupancy tracking
- Resources: POWER_NODE, COMPONENT_SCRAP, CONDUCTOR
- Hazards: EM_PULSE, THERMAL_ZONE, CORROSIVE_FIELD, DEBRIS
- Signals: non-semantic physical pulses with pattern_id, intensity, radius, decay, duration
- Occupancy-aware movement: moves fail if target cell is occupied
- Spatial pressure: bounded [0.0, 1.0] metric from nearby occupancy
- Proximity detection: units detect nearby unit IDs within sensor range
- Signal emission and sensing: units emit and observe physical signal pulses

### Guardrails (`guardrails/`)
- Three-layer defense: lexical scan, AST check, runtime validation
- Prevents anthropomorphic leakage into runtime logic

### CLI (`cli/`)
- `run`, `inspect`, `check` commands
