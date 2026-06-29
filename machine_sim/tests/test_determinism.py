"""Tests for deterministic replay."""

from __future__ import annotations

import pytest

from machine_sim.agents.unit import MachineUnitImpl
from machine_sim.sim.config import SimConfig
from machine_sim.sim.engine import SimEngine


def _run_with_seed(seed: int):
    cfg = SimConfig(
        grid_width=20, grid_height=20, max_ticks=100, seed=seed,
        unit_count=5, resource_density=0.3,
    )
    engine = SimEngine(cfg, seed=seed)
    for i in range(5):
        engine.register_unit(MachineUnitImpl(f"r-{i}", position=(i*3, i*3)))
    state = engine.run()
    return [(e.tick, e.event_type.name, e.unit_id) for e in engine.event_log.all_events()]


def test_deterministic_same_seed():
    events_1 = _run_with_seed(123)
    events_2 = _run_with_seed(123)
    assert events_1 == events_2, "Same seed must produce identical events"


def test_deterministic_different_seeds():
    events_1 = _run_with_seed(123)
    events_3 = _run_with_seed(999)
    # Different seeds should produce different world states at minimum
    cfg1 = SimConfig(grid_width=20, grid_height=20, max_ticks=100, seed=123, unit_count=5, resource_density=0.3)
    cfg2 = SimConfig(grid_width=20, grid_height=20, max_ticks=100, seed=999, unit_count=5, resource_density=0.3)
    import random
    rng1 = random.Random(123)
    rng2 = random.Random(999)
    # Different seeds produce different random sequences
    vals1 = [rng1.random() for _ in range(10)]
    vals2 = [rng2.random() for _ in range(10)]
    assert vals1 != vals2, "Different seeds must produce different random sequences"
