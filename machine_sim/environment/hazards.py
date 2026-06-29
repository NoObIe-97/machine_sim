"""Hazard types and data."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class HazardType(Enum):
    EM_PULSE = "em_pulse"
    THERMAL_ZONE = "thermal_zone"
    CORROSIVE_FIELD = "corrosive_field"
    DEBRIS = "debris"


@dataclass
class Hazard:
    hazard_type: HazardType
    intensity: float
    decay_rate: float = 0.005
    damage_per_tick: float = 1.0
