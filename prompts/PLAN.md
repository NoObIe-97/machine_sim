# After Silicon: Bias-Guarded Machine Civilization Emergence Simulator

## Implementation Plan v2.0

---

## 1. Technology Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Language | Python 3.11+ | match/case, type hints, `tomllib` in stdlib |
| Testing | pytest + pytest-cov | Rich fixture system, coverage reporting |
| CLI | click | Composable, testable, declarative |
| Config | TOML via `tomllib` | Stdlib, no extra deps |
| Logging | `logging` + custom `EventLog` | Standard + domain-specific event stream |

Single external dependency: `click`.

---

## 2. Project Structure

```
machine_sim/
├── pyproject.toml
├── README.md
├── machine_sim/
│   ├── __init__.py
│   ├── sim/
│   │   ├── __init__.py
│   │   ├── engine.py         # SimEngine — tick loop
│   │   ├── config.py         # SimConfig dataclass + TOML loader
│   │   ├── events.py         # Event types + EventLog
│   │   ├── state.py          # SimulationState snapshot
│   │   └── seed.py           # Deterministic seeding utilities
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py           # MachineUnit ABC + MachineState + Action/ActionResult
│   │   ├── variants.py       # Hardware-variant units (configurable parameters, not roles)
│   │   ├── decision.py       # Decision primitives: threshold, gradient, correlation, reinforcement
│   │   └── components.py     # Component definitions (sensor, actuator, processor, power_cell)
│   ├── environment/
│   │   ├── __init__.py
│   │   ├── world.py          # World grid, Cell, sensing, action execution
│   │   ├── resources.py      # ResourceType enum + Resource dataclass
│   │   ├── hazards.py        # HazardType enum + Hazard dataclass
│   │   └── terrain.py        # Terrain types
│   ├── guardrails/
│   │   ├── __init__.py
│   │   ├── lexical.py        # Regex scan for anthropomorphic terms
│   │   ├── codecheck.py      # AST-level anthropomorphic checker
│   │   ├── runtime.py        # State/action/config/label validation
│   │   └── config.py         # Forbidden terms, allowed fields, allowed labels
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── interpreter.py    # Observer-level interpretation (later milestone)
│   │   └── metrics.py        # Civilization emergence metrics (later milestone)
│   ├── cli/
│   │   ├── __init__.py
│   │   └── main.py           # click CLI: run, inspect, check
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py
│       ├── test_engine.py
│       ├── test_agents.py
│       ├── test_environment.py
│       ├── test_guardrails.py
│       ├── test_determinism.py
│       └── test_cli.py
├── configs/
│   └── milestone_1.toml
└── output/                   # gitignored
```

---

## 3. Core Architecture

### 3.1 Simulation Loop

Tick lifecycle:

```
TICK N:
  1. ENV_UPDATE    — Resources regrow/decay, hazards shift
  2. SENSE         — Units read local grid cells
  3. DECIDE        — Units choose action based on state + memory
  4. ACT           — Actions execute against world (conflict resolution)
  5. DEGRADE       — Power drains, components wear
  6. LOG           — All events recorded to EventLog
  7. VALIDATE      — Guardrails assert state is machine-native only
```

The engine accepts a `SimConfig`, creates a `World` with a `random.Random` instance for deterministic seeding, registers machine units, and runs the tick loop until `max_ticks` or all units deactivated.

### 3.2 Event System

Event types are machine-native labels: `tick_begin`, `tick_end`, `unit_action`, `resource_harvest`, `resource_depleted`, `component_damage`, `component_repair`, `unit_deactivated`, `hazard_encounter`, `environment_update`.

Events are frozen dataclasses with tick, event_type, unit_id (optional), and data dict. The `EventLog` is append-only, queryable by tick and unit, and serializable to JSON.

---

## 4. Machine Unit Design (Milestone 1)

### 4.1 Unit State — Machine-Native Only

A `MachineState` frozen dataclass contains ONLY:

| Field | Type | Description |
|-------|------|-------------|
| `unit_id` | str | Unique identifier |
| `position` | Tuple[int, int] | Grid coordinates |
| `power_reserve` | float | 0.0 – max_power |
| `max_power` | float | Capacity |
| `components` | Dict[str, Component] | Named components with health |
| `sensor_readings` | deque | Bounded recent observations |
| `local_memory` | deque | Bounded event history |
| `action_budget` | int | Actions remaining this tick |
| `is_active` | bool | False = shut down |
| `unit_class` | str | Hardware variant identifier |

Components: `sensor`, `actuator`, `processor`, `power_cell` — each with `health` (0.0–1.0), `max_health`, `degradation_rate`, `is_critical`.

### 4.2 Milestone 1 Primitive Actions

Only these actions exist in Milestone 1:

| Action | Description | Cost |
|--------|-------------|------|
| `MOVE` | Move to adjacent cell | power -2.0 |
| `SCAN` | Read local grid cells (sensing is implicit but explicit scan refreshes buffer) | power -0.5 |
| `HARVEST` | Collect resource at current position | power -0.5, gains power |
| `COLLECT` | Pick up inert material (component scrap) | power -1.0 |
| `MAINTAIN` | Self-repair a degraded component using stored energy | power -5.0 |
| `IDLE` | Do nothing, conserve power | power -0.1 |

**NOT in Milestone 1**: salvage, blocking, signaling, resource denial, inter-agent exploitation, collision mechanics.

### 4.3 Hardware-Variant Units

Rather than role-named agents (Survivor, Scavenger, Harvester), Milestone 1 uses a single `MachineUnit` class parameterized by hardware variant. Variants differ only in numeric parameters, not behavior logic:

| Parameter | Variant A (Balanced) | Variant B (Power-Heavy) | Variant C (Sensor-Heavy) |
|-----------|---------------------|------------------------|------------------------|
| max_power | 100.0 | 150.0 | 80.0 |
| power_drain_rate | 1.0 | 1.2 | 0.8 |
| sensor_range | 3 | 2 | 5 |
| component health profile | balanced | power_cell +20%, sensor -10% | sensor +20%, actuator -10% |

All variants use the same `decide()` method. Specialization and role emergence happen in later milestones.

### 4.4 Decision Logic

The `decide()` method uses only machine-native primitives:

- **Threshold gate**: if power_reserve / max_power < threshold, choose action
- **Gradient following**: move toward higher resource density in sensor readings
- **Correlation detection**: if pattern X appeared in recent memory, respond
- **Reinforcement**: repeat actions that historically improved power_reserve

No goals, desires, preferences, social reasoning, or anthropomorphic logic.

---

## 5. Environment Design

### 5.1 World Grid

Dict-based sparse representation: `{(x, y): Cell}`. Each cell holds resources, hazards, terrain type, and optionally a unit reference.

- `populate_resources(density, rng)`: Place resources randomly
- `populate_hazards(density, rng)`: Place hazards randomly
- `place_unit(unit, rng)`: Place unit on empty cell
- `update(tick)`: Resource regrowth, hazard decay
- `sense(position, sensor_range)`: Return SensorReadings for nearby cells
- `execute_action(action, unit)`: Dispatch to action handler, return ActionResult

### 5.2 Resources

`ResourceType` enum: `POWER_NODE`, `COMPONENT_SCRAP`, `CONDUCTOR`.

Each `Resource` has quantity, max_quantity, and regrowth_rate.

### 5.3 Hazards

`HazardType` enum: `EM_PULSE`, `THERMAL_ZONE`, `CORROSIVE_FIELD`, `DEBRIS`.

Each `Hazard` has intensity, decay_rate, damage_per_tick.

---

## 6. Guardrail System

### 6.1 Bias Firewall — What Is Banned

**BANNED in runtime machine logic** (agent code, environment interaction logic):

- Anthropomorphic: goal, desire, want, wish, intend, aim, motivation
- Emotional: love, hate, fear, anger, joy, sadness, happy, angry, afraid, mood, temperament
- Moral/ethical: moral, ethical, virtue, sin, guilt, shame, conscience
- Social: social, society, community, friend, enemy, ally, tribe, family, group
- Language/communication: language, speak, word, sentence, communicate, talk, dialogue
- Consciousness: consciousness, awareness, sentient, sentience, experience
- Institutional: law, crime, trade, commerce, economy, government, leadership
- Identity: personality, character, identity, self, ego

**NOT banned** (legitimate machine-adaptation terms allowed):

- learning, adaptation, model_update, correlation, prediction, optimization
- calibration, tuning, parameter_adjustment, weight_update, signal_processing
- pattern_recognition, gradient, reinforcement, memory_recall, state_estimation

These are machine-native concepts. The ban targets human/social/emotional/moral/institutional leakage, not legitimate computational terminology.

### 6.2 Three-Layer Defense

**Layer 1 — Lexical Scan** (`guardrails/lexical.py`):
- Regex scan of non-test `.py` files for banned anthropomorphic terms
- Skips comments and docstrings
- Excludes `tests/`, `docs/`, `__pycache__`

**Layer 2 — AST Check** (`guardrails/codecheck.py`):
- Parses Python AST to detect:
  - Forbidden variable assignments (`goal = ...`, `desire = ...`)
  - Forbidden class bases (`SocialAgent`, `EmotionalAgent`, etc.)
  - Forbidden function parameters
  - Forbidden decorators

**Layer 3 — Runtime Validation** (`guardrails/runtime.py`):
- Validates `MachineState` fields against allowed set
- Validates power_reserve in bounds
- Validates component names against allowed set
- Validates action types against allowed set
- Validates event labels against allowed set
- Validates config keys against allowed set
- Validates memory entry event_type labels against allowed set
- Validates exported metric names against allowed set

### 6.3 Guardrail Scope

The runtime guardrail checks are comprehensive:

| Check | What | Where |
|-------|------|-------|
| State fields | Only allowed fields in MachineState | Every unit.state_copy() |
| Component names | Only: sensor, actuator, processor, power_cell (+ variant-specific) | Every unit component dict |
| Action names | Only: MOVE, SCAN, HARVEST, COLLECT, MAINTAIN, IDLE | Every decide() return |
| Event labels | Only machine-native labels | Every Event event_type |
| Config keys | Only allowed simulation parameters | Config load |
| Memory labels | Only machine-native event_type strings | Every MemoryEntry |
| Agent class names | No anthropomorphic class names | Class definitions |
| Metric names | Only machine-native metric labels | Analysis module (later) |

---

## 7. Configuration

`SimConfig` dataclass loaded from TOML:

```toml
[simulation]
grid_width = 20
grid_height = 20
resource_density = 0.3
hazard_density = 0.05
unit_count = 5
power_drain_rate = 1.0
max_ticks = 500
seed = 42
```

---

## 8. CLI Design

Three commands:

- `run` — Execute simulation with config, seed override, tick override, output path, verbose flag
- `inspect` — Read output directory, show event counts by type
- `check` — Run guardrail lexical + AST scan on all source code

---

## 9. Milestone 1 Implementation Phases

### Phase 1: Foundation
1. Project structure, `pyproject.toml`, `__init__.py` files
2. `sim/config.py` — SimConfig + TOML loader
3. `sim/events.py` — Event types + EventLog
4. `sim/engine.py` — SimEngine tick loop skeleton
5. `sim/state.py` — SimulationState snapshot
6. `configs/milestone_1.toml`

### Phase 2: Environment
1. `environment/resources.py` — ResourceType + Resource
2. `environment/hazards.py` — HazardType + Hazard
3. `environment/world.py` — World grid, Cell, sensing, action execution
4. `environment/terrain.py` — Terrain types

### Phase 3: Machine Units
1. `agents/base.py` — MachineUnit ABC + MachineState + Action/ActionResult
2. `agents/components.py` — Component definitions
3. `agents/variants.py` — Hardware-variant parameter sets
4. `agents/decision.py` — Threshold, gradient, correlation, reinforcement primitives

### Phase 4: Guardrails
1. `guardrails/config.py` — Forbidden terms, allowed fields, allowed labels
2. `guardrails/lexical.py` — Regex scanner
3. `guardrails/codecheck.py` — AST checker
4. `guardrails/runtime.py` — State/action/config/label validator

### Phase 5: CLI + Integration
1. `cli/main.py` — click CLI
2. Integration test: full 500-tick sim
3. Determinism test: same seed → same output
4. Demo run, capture output

### Phase 6: Polish
1. pytest-cov, 80%+ coverage target
2. Type hints throughout
3. README.md
4. Final guardrail scan + full test pass

---

## 10. Test Strategy

| Category | What | Key Assertions |
|----------|------|----------------|
| Unit | Each module | Correct types, bounds, behavior |
| Integration | Full 100-tick run | All units have valid power/component bounds |
| Determinism | Same seed twice | Identical event sequences |
| Guardrails | All source code | No anthropomorphic terms, no AST violations, valid state |

---

## 11. Verification Plan

```bash
pip install -e .
pytest machine_sim/tests/ -v
pytest --cov=machine_sim --cov-report=term-missing
python -m machine_sim.cli.main run -c configs/milestone_1.toml -t 100 -s 42
python -m machine_sim.cli.main check
python -m machine_sim.cli.main inspect output/demo/
```

---

## 12. Future Milestone Roadmap

### Milestone 2: Interaction Substrate
- Unit-unit proximity detection
- Collision mechanics
- Environmental modification (terrain alteration)
- Spatial territory patterns

### Milestone 3: Non-Semantic Signaling
- Bit-pattern signal emission and detection
- Signal correlation across units
- Signal-based coordination primitives
- Environmental signal propagation

### Milestone 4: Conflict/Cooperation Through Resource Pressure
- Resource competition mechanics
- Resource sharing (proximity-based, no social logic)
- Resource denial (blocking access, not intent-based)
- Territorial behavior emergence

### Milestone 5: Reproduction and Design Inheritance
- Unit replication (copy parameters + noise)
- Offspring placement
- Design inheritance with variation
- Population dynamics

### Milestone 6: Mutation and Lineage Divergence
- Parameter mutation during replication
- Lineage tracking
- Fitness-proportional selection pressure
- Lineage divergence and specialization

### Milestone 7: Calibration Assist and Knowledge Transfer
- Parent-like parameter calibration for offspring
- Experience capsule transfer (memory snapshots passed to offspring)
- Calibration refinement through feedback loops
- Knowledge accumulation across generations

### Milestone 8: Distributed Operational Memory
- Persistent memory across ticks (survives deactivation/reactivation)
- Memory sharing via physical proximity
- Distributed consensus primitives
- Memory corruption and repair

### Milestone 9: Conflict/Cooperation Experiments
- Multi-unit resource competition scenarios
- Cooperative resource extraction
- Deception-like signaling (misleading signals, not intent-based)
- Alliance-like coordination patterns

### Milestone 10: Observer-Level Affect Interpretation
- Analysis module that interprets behavioral patterns
- Map machine-native patterns to human-affective labels (observer only)
- Civilization emergence metrics
- Long-horizon experiment suite and replay analysis

---

## 13. Review Package Specification

For each milestone handoff, produce a review package containing:

| Item | Description |
|------|-------------|
| Commit hash | Exact commit being reviewed |
| File tree | `find . -type f | grep -v __pycache__ | sort` output |
| Commands run | Exact pip install, pytest, CLI commands executed |
| Test results | Full pytest output with pass/fail counts |
| Coverage report | pytest-cov terminal output |
| Guardrail output | `check` command output (must show "All guardrail checks passed") |
| Demo output | Sample simulation run output (event counts, unit survival) |
| Report path | Path to markdown summary of what was built, what works, what's excluded |
| Known limitations | What's not yet implemented, edge cases, performance notes |

---

## 14. Design Risks

| Risk | Mitigation |
|------|-----------|
| Guardrail regex too aggressive | Maintain allowlist for false positives; test guardrails themselves |
| Units too simple to produce interesting patterns | Milestone 1 is substrate-only; complexity emerges later |
| Determinism breaks with floating-point | Use integer-safe operations where possible; test replay explicitly |
| Grid too small for spatial emergence | Configurable grid size; increase for later experiments |
| Hardware variants too similar | Variants only differ numerically; specialization is explicitly deferred |

---

## 15. Git Discipline

- **Branch naming**: `feature/milestone-1`, `feature/milestone-2`, etc.
- **Commits**: Conventional commits (`feat:`, `fix:`, `test:`, `docs:`)
- **Working tree**: Must be clean before merging
- **Final summary**: PR description with review package contents

---

*Plan v2.0 — Revised to remove premature role assignments, restrict Milestone 1 scope, refine bias firewall, and add review package specification.*
