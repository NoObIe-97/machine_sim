"""Shared test fixtures."""

from __future__ import annotations

import pytest

from machine_sim.sim.config import SimConfig


@pytest.fixture
def default_config() -> SimConfig:
    return SimConfig(
        grid_width=10,
        grid_height=10,
        resource_density=0.3,
        hazard_density=0.05,
        unit_count=3,
        power_drain_rate=1.0,
        max_ticks=100,
        seed=42,
    )
