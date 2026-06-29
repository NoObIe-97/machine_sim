"""Machine-native agent base class and state definitions."""

from __future__ import annotations

import copy
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple


class ActionType(Enum):
    MOVE = auto()
    SCAN = auto()
    HARVEST = auto()
    COLLECT = auto()
    MAINTAIN = auto()
    IDLE = auto()


@dataclass(frozen=True, slots=True)
class Action:
    action_type: ActionType
    target_position: Optional[Tuple[int, int]] = None
    target_component: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ActionResult:
    success: bool
    power_delta: float
    component_deltas: Dict[str, float] = field(default_factory=dict)
    event_type: str = ""
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Component:
    name: str
    max_health: float = 1.0
    health: float = 1.0
    degradation_rate: float = 0.001
    is_critical: bool = False


@dataclass
class SensorReading:
    tick: int
    position: Tuple[int, int]
    resource_signals: Dict[str, float] = field(default_factory=dict)
    hazard_signals: Dict[str, float] = field(default_factory=dict)
    nearby_units: List[str] = field(default_factory=list)
    signal_strength: float = 1.0


@dataclass
class MemoryEntry:
    tick: int
    event_type: str
    position: Tuple[int, int]
    outcome_delta: float = 0.0
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MachineState:
    """Immutable snapshot of unit state. ONLY machine-native fields."""
    unit_id: str
    position: Tuple[int, int]
    power_reserve: float
    max_power: float
    components: Dict[str, Component]
    sensor_readings: tuple
    local_memory: tuple
    action_budget: int
    is_active: bool
    unit_class: str


class MachineUnit(ABC):
    """Base class for all machine-native units."""

    SENSOR_RANGE: int = 3
    MEMORY_CAPACITY: int = 50
    SENSOR_BUFFER: int = 10
    ACTIONS_PER_TICK: int = 2

    def __init__(
        self,
        unit_id: str,
        position: Tuple[int, int] = (0, 0),
        max_power: float = 100.0,
        components: Optional[Dict[str, Component]] = None,
    ) -> None:
        self.unit_id = unit_id
        self.position = position
        self.power_reserve = max_power
        self.max_power = max_power
        self.components = components or self._default_components()
        self.sensor_readings: deque[SensorReading] = deque(maxlen=self.SENSOR_BUFFER)
        self.local_memory: deque[MemoryEntry] = deque(maxlen=self.MEMORY_CAPACITY)
        self.action_budget = self.ACTIONS_PER_TICK
        self.is_active = True

    @abstractmethod
    def _default_components(self) -> Dict[str, Component]:
        ...

    @abstractmethod
    def decide(self, tick: int) -> Optional[Action]:
        ...

    def receive_observations(self, readings: List[SensorReading], tick: int) -> None:
        for r in readings:
            self.sensor_readings.append(r)

    def apply_result(self, result: ActionResult, tick: int) -> None:
        self.power_reserve = max(0.0, min(self.max_power,
            self.power_reserve + result.power_delta))
        for comp_name, health_delta in result.component_deltas.items():
            if comp_name in self.components:
                c = self.components[comp_name]
                c.health = max(0.0, min(c.max_health, c.health + health_delta))
        self.local_memory.append(MemoryEntry(
            tick=tick,
            event_type=result.event_type,
            position=self.position,
            outcome_delta=result.power_delta,
        ))
        if self.power_reserve <= 0 or self._critical_component_failed():
            self.is_active = False

    def degrade(self, drain_rate: float, rng: Any) -> None:
        self.power_reserve = max(0.0, self.power_reserve - drain_rate)
        for comp in self.components.values():
            noise = rng.uniform(0.5, 1.5)
            comp.health = max(0.0, comp.health - comp.degradation_rate * noise)
        if self.power_reserve <= 0 or self._critical_component_failed():
            self.is_active = False

    def state_copy(self) -> MachineState:
        return MachineState(
            unit_id=self.unit_id,
            position=self.position,
            power_reserve=self.power_reserve,
            max_power=self.max_power,
            components=copy.deepcopy(self.components),
            sensor_readings=tuple(copy.deepcopy(self.sensor_readings)),
            local_memory=tuple(copy.deepcopy(self.local_memory)),
            action_budget=self.action_budget,
            is_active=self.is_active,
            unit_class=type(self).__name__,
        )

    def _critical_component_failed(self) -> bool:
        return any(c.health <= 0 and c.is_critical for c in self.components.values())

    def _power_ratio(self) -> float:
        return self.power_reserve / self.max_power if self.max_power > 0 else 0.0

    def _avg_component_health(self) -> float:
        if not self.components:
            return 0.0
        return sum(c.health for c in self.components.values()) / len(self.components)

    @property
    def sensor_range(self) -> int:
        sensor = self.components.get("sensor")
        if sensor and sensor.health > 0:
            return max(1, int(self.SENSOR_RANGE * sensor.health))
        return 1
