"""Tests for simulation configuration."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from machine_sim.guardrails.runtime import StateViolation
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


def test_config_from_toml_rejects_unknown_keys():
    """Config loading rejects TOML files with forbidden keys."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write('[simulation]\ngrid_width = 10\nsocial_graph = "friends"\n')
        f.flush()
        with pytest.raises(StateViolation, match="Forbidden config keys"):
            SimConfig.from_toml(Path(f.name))


def test_config_from_toml_rejects_morale_level():
    """Config loading rejects morale_level key."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write('[simulation]\ngrid_width = 10\nmorale_level = 5\n')
        f.flush()
        with pytest.raises(StateViolation, match="Forbidden config keys"):
            SimConfig.from_toml(Path(f.name))


def test_config_from_toml_accepts_valid_keys():
    """Config loading accepts all valid keys."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write('[simulation]\ngrid_width = 10\ngrid_height = 10\nseed = 99\n')
        f.flush()
        cfg = SimConfig.from_toml(Path(f.name))
        assert cfg.grid_width == 10
        assert cfg.seed == 99
