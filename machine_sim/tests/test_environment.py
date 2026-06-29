"""Tests for environment modules."""

from __future__ import annotations

import random

import pytest

from machine_sim.agents.unit import MachineUnitImpl
from machine_sim.environment.world import World


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
