"""Tests for simulation configuration."""

from __future__ import annotations

from pathlib import Path

import pytest

from machine_sim.sim.config import SimConfig


def test_config_defaults():
    cfg = SimConfig()
    assert cfg.grid_width == 20
    assert cfg.grid_height == 20
    assert cfg.seed == 42
    assert cfg.max_ticks == 500


def test_config_from_toml():
    path = Path(__file__).parent.parent.parent / "configs" / "milestone_1.toml"
    cfg = SimConfig.from_toml(path)
    assert cfg.grid_width == 20
    assert cfg.unit_count == 5
    assert cfg.seed == 42


def test_config_to_dict():
    cfg = SimConfig(grid_width=5, grid_height=5)
    d = cfg.to_dict()
    assert d["grid_width"] == 5
    assert d["grid_height"] == 5
    assert isinstance(d, dict)
