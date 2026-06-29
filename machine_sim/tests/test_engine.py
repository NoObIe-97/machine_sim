"""Tests for simulation engine."""

from __future__ import annotations

import pytest

from machine_sim.agents.unit import MachineUnitImpl
from machine_sim.sim.config import SimConfig
from machine_sim.sim.engine import SimEngine


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
