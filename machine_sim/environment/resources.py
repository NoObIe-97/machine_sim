"""Resource types and data."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ResourceType(Enum):
    POWER_NODE = "power_node"
    COMPONENT_SCRAP = "component_scrap"
    CONDUCTOR = "conductor"


@dataclass(slots=True)
class Resource:
    resource_type: ResourceType
    quantity: float
    max_quantity: float = 100.0
    regrowth_rate: float = 0.05
