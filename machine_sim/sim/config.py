"""Simulation configuration."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

from machine_sim.guardrails.runtime import StateViolation, validate_config_keys


@dataclass
class SimConfig:
    grid_width: int = 20
    grid_height: int = 20
    resource_density: float = 0.3
    hazard_density: float = 0.05
    unit_count: int = 5
    power_drain_rate: float = 1.0
    max_ticks: int = 500
    seed: int = 42
    signal_enabled: bool = False
    signal_pattern_count: int = 3
    signal_energy_cost: float = 2.0
    signal_default_radius: int = 3
    signal_default_decay: float = 0.1
    signal_default_duration: int = 10
    signal_observation_window: int = 10
    adaptive_enabled: bool = False

    @classmethod
    def from_toml(cls, path: Path) -> SimConfig:
        with open(path, "rb") as f:
            data = tomllib.load(f)
        sim_data = data.get("simulation", {})
        validate_config_keys(set(sim_data.keys()))
        return cls(**sim_data)

    def to_dict(self) -> Dict[str, Any]:
        from dataclasses import asdict
        return asdict(self)
