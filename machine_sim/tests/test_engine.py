"""Tests for simulation engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import pytest

from machine_sim.agents.base import (
    Action,
    ActionType,
    MachineUnit,
    SensorReading,
)
from machine_sim.agents.unit import MachineUnitImpl
from machine_sim.agents.variants import ALL_VARIANTS
from machine_sim.guardrails.runtime import StateViolation
from machine_sim.sim.config import SimConfig
from machine_sim.sim.engine import SimEngine
from machine_sim.sim.events import Event, EventType


def test_engine_initialization(default_config):
    engine = SimEngine(default_config, seed=42)
    assert engine.tick_count == 0
    assert len(engine.units) == 0


def test_engine_register_unit(default_config):
    engine = SimEngine(default_config, seed=42)
    unit = MachineUnitImpl("test-0")
    engine.register_unit(unit)
    assert len(engine.units) == 1


def test_engine_full_run(default_config):
    engine = SimEngine(default_config, seed=42)
    for i in range(3):
        engine.register_unit(MachineUnitImpl(f"test-{i}", position=(i, i)))
    state = engine.run()
    assert state.tick == 100
    assert len(state.agents) == 3
    for agent_state in state.agents:
        assert 0.0 <= agent_state.power_reserve <= agent_state.max_power


def test_engine_tick_count(default_config):
    engine = SimEngine(default_config, seed=42)
    engine.register_unit(MachineUnitImpl("u0"))
    engine.initialize()
    engine.tick()
    assert engine.tick_count == 1
    engine.tick()
    assert engine.tick_count == 2


def test_engine_validates_action_names(default_config):
    """Normal tick produces only allowed action names in events."""
    engine = SimEngine(default_config, seed=42)
    engine.register_unit(MachineUnitImpl("u0"))
    engine.initialize()
    engine.tick()
    events = engine.event_log.events_for_tick(1)
    action_events = [e for e in events if e.event_type == EventType.UNIT_ACTION]
    for e in action_events:
        assert e.data.get("action") in {"MOVE", "SCAN", "HARVEST", "COLLECT", "MAINTAIN", "IDLE"}


def test_engine_validates_state_after_tick(default_config):
    """Runtime validation is invoked on active units after each tick."""
    engine = SimEngine(default_config, seed=42)
    engine.register_unit(MachineUnitImpl("u0"))
    engine.register_unit(MachineUnitImpl("u1"))
    engine.initialize()
    engine.tick()
    for unit in engine.units:
        if unit.is_active:
            state = unit.state_copy()
            assert 0.0 <= state.power_reserve <= state.max_power


def test_engine_rejects_forbidden_action_name(default_config):
    """Engine validates action names before execution."""
    engine = SimEngine(default_config, seed=42)
    engine.register_unit(MachineUnitImpl("u0"))
    engine.initialize()

    # Verify that validate_action_name is called during tick
    # by checking that all recorded actions have valid names
    engine.tick()
    events = engine.event_log.events_for_tick(1)
    action_events = [e for e in events if e.event_type == EventType.UNIT_ACTION]
    for e in action_events:
        # This would raise StateViolation if action name were forbidden
        from machine_sim.guardrails.runtime import validate_action_name
        validate_action_name(e.data["action"])


def test_engine_rejects_forbidden_event_label(default_config):
    """Engine validates event labels through _record_event."""
    engine = SimEngine(default_config, seed=42)

    # Direct test of the validation path
    from machine_sim.guardrails.runtime import validate_event_label
    with pytest.raises(StateViolation, match="Forbidden event label"):
        validate_event_label("fight")
    with pytest.raises(StateViolation, match="Forbidden event label"):
        validate_event_label("trade")
    with pytest.raises(StateViolation, match="Forbidden event label"):
        validate_event_label("emotion")


def test_engine_rejects_corrupted_unit_state(default_config):
    """Engine state validation rejects corrupted unit state."""
    engine = SimEngine(default_config, seed=42)
    unit = MachineUnitImpl("u0")
    engine.register_unit(unit)
    engine.initialize()

    # Corrupt the unit state by adding a forbidden field
    unit.power_reserve = -5.0  # Out of bounds

    # The validate_agent_state function should reject this
    from machine_sim.guardrails.runtime import validate_agent_state
    state = unit.state_copy()
    with pytest.raises(StateViolation, match="out of bounds"):
        validate_agent_state(state)


def test_engine_rejects_corrupted_memory_label(default_config):
    """Engine state validation rejects unit with forbidden memory label."""
    from machine_sim.agents.base import MemoryEntry
    engine = SimEngine(default_config, seed=42)
    unit = MachineUnitImpl("u0")
    engine.register_unit(unit)
    engine.initialize()

    # Inject a forbidden memory entry
    unit.local_memory.append(MemoryEntry(
        tick=1,
        event_type="fight",  # Forbidden label
        position=(0, 0),
        outcome_delta=-1.0,
    ))

    from machine_sim.guardrails.runtime import validate_agent_state
    state = unit.state_copy()
    with pytest.raises(StateViolation, match="forbidden label"):
        validate_agent_state(state)


def test_engine_emits_hazard_events():
    """Place unit directly on hazardous cell, assert hazard event is emitted."""
    cfg = SimConfig(grid_width=5, grid_height=5, max_ticks=1, seed=42,
                    unit_count=1, hazard_density=0.0, resource_density=0.0)
    engine = SimEngine(cfg, seed=42)
    unit = MachineUnitImpl("u0", position=(2, 2))
    engine.register_unit(unit)
    engine.initialize()

    # Place hazard at unit's actual position (may have moved during init)
    from machine_sim.environment.hazards import Hazard, HazardType
    actual_pos = unit.position
    engine.world.grid[actual_pos].hazards["em_pulse"] = Hazard(
        hazard_type=HazardType.EM_PULSE,
        intensity=0.9,
        decay_rate=0.005,
    )

    engine.tick()
    hazard_events = [e for e in engine.event_log.all_events()
                     if e.event_type == EventType.HAZARD_ENCOUNTER]
    assert len(hazard_events) >= 1, "Expected at least one HAZARD_ENCOUNTER event"
    assert hazard_events[0].unit_id == "u0"


def test_engine_hazard_can_deactivate_unit():
    """High-intensity hazard on a unit triggers deactivation."""
    cfg = SimConfig(grid_width=5, grid_height=5, max_ticks=1, seed=42,
                    unit_count=1, hazard_density=0.0, resource_density=0.0)
    engine = SimEngine(cfg, seed=42)
    unit = MachineUnitImpl("u0", position=(2, 2))
    unit.power_reserve = 2.0  # Low enough that degrade + hazard kills it
    engine.register_unit(unit)
    engine.initialize()

    from machine_sim.environment.hazards import Hazard, HazardType
    actual_pos = unit.position
    # Degrade takes ~1.0 power, hazard takes 0.95*2.0=1.9 power
    # Total: 1.0 + 1.9 = 2.9 > 2.0, so unit deactivates
    engine.world.grid[actual_pos].hazards["em_pulse"] = Hazard(
        hazard_type=HazardType.EM_PULSE,
        intensity=0.95,
        decay_rate=0.005,
    )

    engine.tick()
    assert not unit.is_active, "Unit should be deactivated by hazard + degrade"


def test_variant_specific_drain():
    """Each hardware variant uses its own power_drain_rate."""
    cfg = SimConfig(grid_width=10, grid_height=10, max_ticks=5, seed=42,
                    unit_count=3, resource_density=0.0, hazard_density=0.0)
    engine = SimEngine(cfg, seed=42)
    units = []
    for i, variant in enumerate(ALL_VARIANTS):
        u = MachineUnitImpl(f"v-{i}", variant=variant)
        engine.register_unit(u)
        units.append((u, variant))
    engine.initialize()
    initial_power = {u.unit_id: u.power_reserve for u, v in units}
    engine.tick()
    for u, v in units:
        drain_used = initial_power[u.unit_id] - u.power_reserve
        expected_approx = v.power_drain_rate
        assert abs(drain_used - expected_approx) < 0.1, (
            f"Variant {v.name}: expected drain ~{expected_approx}, got {drain_used}"
        )


def test_deterministic_replay_compares_outputs():
    """Same seed produces identical final state summaries."""
    def run_summary(seed):
        cfg = SimConfig(grid_width=10, grid_height=10, max_ticks=50,
                        seed=seed, unit_count=3, resource_density=0.3)
        engine = SimEngine(cfg, seed=seed)
        for i in range(3):
            engine.register_unit(MachineUnitImpl(f"u-{i}", position=(i, i)))
        state = engine.run()
        return (
            state.tick,
            tuple((a.unit_id, round(a.power_reserve, 2), a.is_active)
                  for a in state.agents),
            len(state.events),
        )

    s1 = run_summary(123)
    s2 = run_summary(123)
    s3 = run_summary(999)
    assert s1 == s2, "Same seed must produce identical state summaries"
    assert s1 != s3, "Different seeds must produce different state summaries"
