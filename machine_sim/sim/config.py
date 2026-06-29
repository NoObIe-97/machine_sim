"""Simulation configuration."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict


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

    @classmethod
    def from_toml(cls, path: Path) -> SimConfig:
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return cls(**data.get("simulation", {}))

    def to_dict(self) -> Dict[str, Any]:
        from dataclasses import asdict
        return asdict(self)
