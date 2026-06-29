"""Tests for environment modules."""

from __future__ import annotations

import random

import pytest

from machine_sim.agents.unit import MachineUnitImpl
from machine_sim.environment.hazards import Hazard, HazardType
from machine_sim.environment.world import World
from machine_sim.sim.events import EventType


def test_world_initialization():
    rng = random.Random(42)
    world = World(10, 10, rng)
    assert len(world.grid) == 100


def test_world_populate_resources():
    rng = random.Random(42)
    world = World(10, 10, rng)
    world.populate_resources(0.5, rng)
    cells_with_resources = sum(1 for c in world.grid.values() if c.resources)
    assert cells_with_resources > 0


def test_world_populate_hazards():
    rng = random.Random(42)
    world = World(10, 10, rng)
    world.populate_hazards(0.2, rng)
    cells_with_hazards = sum(1 for c in world.grid.values() if c.hazards)
    assert cells_with_hazards > 0


def test_world_place_unit():
    rng = random.Random(42)
    world = World(10, 10, rng)
    unit = MachineUnitImpl("u0")
    world.place_unit(unit, rng)
    assert unit.position in world.grid
    assert world.grid[unit.position].unit_id == "u0"


def test_world_sense():
    rng = random.Random(42)
    world = World(10, 10, rng)
    world.populate_resources(0.5, rng)
    unit = MachineUnitImpl("u0", position=(5, 5))
    readings = world.sense(unit.position, 2)
    assert len(readings) > 0
    assert all(hasattr(r, "resource_signals") for r in readings)


def test_world_update():
    rng = random.Random(42)
    world = World(10, 10, rng)
    world.populate_resources(0.5, rng)
    events = world.update(1)
    assert isinstance(events, list)


def test_hazard_damage_reduces_power():
    """Unit on a hazardous cell loses power proportional to hazard intensity."""
    rng = random.Random(42)
    world = World(5, 5, rng)
    unit = MachineUnitImpl("u0", position=(2, 2))
    world.grid[(2, 2)].unit_id = "u0"
    world.grid[(2, 2)].hazards["em_pulse"] = Hazard(
        hazard_type=HazardType.EM_PULSE, intensity=0.8, decay_rate=0.005
    )
    initial_power = unit.power_reserve
    events = world.apply_hazard_damage(unit, 1)
    assert unit.power_reserve < initial_power
    assert len(events) >= 1
    assert events[0].event_type == EventType.HAZARD_ENCOUNTER


def test_hazard_damage_degrades_components():
    """Strong hazards degrade unit components."""
    rng = random.Random(42)
    world = World(5, 5, rng)
    unit = MachineUnitImpl("u0", position=(2, 2))
    world.grid[(2, 2)].unit_id = "u0"
    world.grid[(2, 2)].hazards["thermal_zone"] = Hazard(
        hazard_type=HazardType.THERMAL_ZONE, intensity=0.9, decay_rate=0.005
    )
    initial_health = {c.name: c.health for c in unit.components.values()}
    world.apply_hazard_damage(unit, 1)
    degraded = any(unit.components[c].health < initial_health[c] for c in initial_health)
    assert degraded, "At least one component should degrade from high-intensity hazard"


def test_no_hazard_no_damage():
    """Unit on a clean cell takes no hazard damage."""
    rng = random.Random(42)
    world = World(5, 5, rng)
    unit = MachineUnitImpl("u0", position=(2, 2))
    world.grid[(2, 2)].unit_id = "u0"
    initial_power = unit.power_reserve
    events = world.apply_hazard_damage(unit, 1)
    assert unit.power_reserve == initial_power
    assert len(events) == 0
