"""Machine unit implementation — generic controller with hardware variants."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from machine_sim.agents.base import (
    Action,
    ActionResult,
    ActionType,
    Component,
    MachineUnit,
    SensorReading,
)
from machine_sim.agents.components import default_components
from machine_sim.agents.decision import (
    build_resource_map,
    gradient_direction,
    threshold_gate,
)
from machine_sim.agents.variants import ALL_VARIANTS, Variant


class MachineUnitImpl(MachineUnit):
    """Generic machine unit with configurable hardware variant."""

    def __init__(
        self,
        unit_id: str,
        position: Tuple[int, int] = (0, 0),
        variant: Optional[Variant] = None,
        signal_enabled: bool = False,
        signal_pattern_count: int = 3,
        signal_energy_cost: float = 2.0,
        signal_default_radius: int = 3,
        signal_default_decay: float = 0.1,
        signal_default_duration: int = 10,
    ) -> None:
        self.variant = variant or ALL_VARIANTS[0]
        self.signal_enabled = signal_enabled
        self.signal_pattern_count = signal_pattern_count
        self.signal_energy_cost = signal_energy_cost
        self.signal_default_radius = signal_default_radius
        self.signal_default_decay = signal_default_decay
        self.signal_default_duration = signal_default_duration
        self._last_signal_tick = -10
        super().__init__(
            unit_id=unit_id,
            position=position,
            max_power=self.variant.max_power,
            components=self.variant.component_factory(),
        )
        self.SENSOR_RANGE = self.variant.sensor_range

    def _default_components(self) -> Dict[str, Component]:
        return default_components()

    def decide(self, tick: int) -> Optional[Action]:
        power_ratio = self._power_ratio()

        # Priority 1: Critical power — harvest immediately
        if power_ratio < 0.15:
            return Action(ActionType.HARVEST)

        # Priority 2: Low power — move toward resources
        if power_ratio < 0.4:
            readings = list(self.sensor_readings)
            if readings:
                resource_map = build_resource_map(readings)
                best = gradient_direction(self.position, resource_map)
                if best and best != self.position:
                    return Action(ActionType.MOVE, target_position=best)
            return Action(ActionType.HARVEST)

        # Priority 3: Degraded critical component — maintain
        critical = self._weakest_critical()
        if critical and critical.health < 0.3:
            return Action(ActionType.MAINTAIN, target_component=critical.name)

        # Priority 4: Signal emission (periodic, neutral)
        if (self.signal_enabled and power_ratio > 0.5
                and tick - self._last_signal_tick >= 5):
            self._last_signal_tick = tick
            pattern_id = tick % self.signal_pattern_count
            return Action(
                ActionType.EMIT_SIGNAL,
                parameters={
                    "pattern_id": pattern_id,
                    "intensity": 1.0,
                    "radius": self.signal_default_radius,
                    "decay_rate": self.signal_default_decay,
                    "duration": self.signal_default_duration,
                },
            )

        # Priority 5: Moderate power — scan to update readings
        if power_ratio < 0.7:
            return Action(ActionType.SCAN)

        # Default: idle to conserve power
        return Action(ActionType.IDLE)

    def _weakest_critical(self) -> Optional[Component]:
        candidates = [c for c in self.components.values() if c.is_critical]
        if not candidates:
            return None
        return min(candidates, key=lambda c: c.health)
