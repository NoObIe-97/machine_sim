"""Hardware-variant parameter sets for machine units."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict

from machine_sim.agents.base import Component
from machine_sim.agents.components import (
    balanced_components,
    power_heavy_components,
    sensor_heavy_components,
)


@dataclass(frozen=True)
class Variant:
    name: str
    max_power: float
    power_drain_rate: float
    sensor_range: int
    component_factory: Callable[[], Dict[str, Component]]


VARIANT_A = Variant(
    name="balanced",
    max_power=100.0,
    power_drain_rate=1.0,
    sensor_range=3,
    component_factory=balanced_components,
)

VARIANT_B = Variant(
    name="power_heavy",
    max_power=150.0,
    power_drain_rate=1.2,
    sensor_range=2,
    component_factory=power_heavy_components,
)

VARIANT_C = Variant(
    name="sensor_heavy",
    max_power=80.0,
    power_drain_rate=0.8,
    sensor_range=5,
    component_factory=sensor_heavy_components,
)

ALL_VARIANTS = [VARIANT_A, VARIANT_B, VARIANT_C]
