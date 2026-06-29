# Architecture

## Overview

After Silicon is a tick-based simulator where autonomous post-collapse machines start with machine-native survival telemetry. Civilization-like patterns emerge from resource pressure, memory, prediction, and environmental mechanics.

## Core Components

### Simulation Engine (`sim/engine.py`)
Tick-based loop with 7 phases per tick:
1. **ENV_UPDATE** — Resources regrow, hazards decay
2. **SENSE** — Units read local grid cells
3. **DECIDE** — Units choose action based on state + memory
4. **ACT** — Actions execute against world
5. **DEGRADE** — Power drains, components wear
6. **LOG** — Events recorded to EventLog
7. **VALIDATE** — Guardrails assert machine-native state

### Machine Units (`agents/`)
- Single `MachineUnitImpl` class with hardware-variant parameters
- Machine-native state: power, components, sensor readings, local memory
- Decision logic: threshold gates, gradient following, correlation detection, reinforcement

### Environment (`environment/`)
- Dict-based sparse grid
- Resources: POWER_NODE, COMPONENT_SCRAP, CONDUCTOR
- Hazards: EM_PULSE, THERMAL_ZONE, CORROSIVE_FIELD, DEBRIS

### Guardrails (`guardrails/`)
- Three-layer defense: lexical scan, AST check, runtime validation
- Prevents anthropomorphic leakage into runtime logic

### CLI (`cli/`)
- `run`, `inspect`, `check` commands
