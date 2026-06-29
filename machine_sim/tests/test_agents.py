"""Tests for machine units."""

from __future__ import annotations

import pytest

from machine_sim.agents.base import Action, ActionType, MachineState
from machine_sim.agents.unit import MachineUnitImpl
from machine_sim.agents.variants import ALL_VARIANTS


def test_unit_creation():
    unit = MachineUnitImpl("u0")
    assert unit.unit_id == "u0"
    assert unit.is_active
    assert unit.power_reserve == 100.0


def test_unit_variant_b():
    unit = MachineUnitImpl("u1", variant=ALL_VARIANTS[1])
    assert unit.max_power == 150.0


def test_unit_variant_c():
    unit = MachineUnitImpl("u2", variant=ALL_VARIANTS[2])
    assert unit.max_power == 80.0
    assert unit.sensor_range == 6  # int(5 * 1.2) = 6 due to sensor health 1.2


def test_unit_state_copy():
    unit = MachineUnitImpl("u0")
    state = unit.state_copy()
    assert isinstance(state, MachineState)
    assert state.unit_id == "u0"
    assert state.is_active


def test_unit_degrade():
    unit = MachineUnitImpl("u0")
    initial_power = unit.power_reserve
    import random
    rng = random.Random(42)
    unit.degrade(1.0, rng)
    assert unit.power_reserve < initial_power


def test_unit_power_ratio():
    unit = MachineUnitImpl("u0")
    assert unit._power_ratio() == 1.0
    unit.power_reserve = 50.0
    assert unit._power_ratio() == 0.5


def test_unit_decide_returns_action():
    unit = MachineUnitImpl("u0")
    action = unit.decide(1)
    assert action is None or isinstance(action, Action)
    if action is not None:
        assert isinstance(action.action_type, ActionType)
