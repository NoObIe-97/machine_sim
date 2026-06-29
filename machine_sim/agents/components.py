"""Component definitions for machine units."""

from __future__ import annotations

from typing import Dict

from machine_sim.agents.base import Component


def default_components() -> Dict[str, Component]:
    """Standard component loadout for a machine unit."""
    return {
        "sensor": Component("sensor", 1.0, 1.0, 0.0005, is_critical=False),
        "actuator": Component("actuator", 1.0, 1.0, 0.001, is_critical=False),
        "processor": Component("processor", 1.0, 1.0, 0.0003, is_critical=True),
        "power_cell": Component("power_cell", 1.0, 1.0, 0.002, is_critical=True),
    }


def balanced_components() -> Dict[str, Component]:
    return default_components()


def power_heavy_components() -> Dict[str, Component]:
    comps = default_components()
    comps["power_cell"].max_health = 1.2
    comps["power_cell"].health = 1.2
    comps["sensor"].max_health = 0.9
    comps["sensor"].health = 0.9
    return comps


def sensor_heavy_components() -> Dict[str, Component]:
    comps = default_components()
    comps["sensor"].max_health = 1.2
    comps["sensor"].health = 1.2
    comps["actuator"].max_health = 0.9
    comps["actuator"].health = 0.9
    return comps
