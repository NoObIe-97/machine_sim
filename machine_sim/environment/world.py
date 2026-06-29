"""World grid, cell representation, sensing, and action execution."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from machine_sim.agents.base import (
    Action,
    ActionResult,
    ActionType,
    MachineUnit,
    SensorReading,
)
from machine_sim.environment.hazards import Hazard, HazardType
from machine_sim.environment.resources import Resource, ResourceType
from machine_sim.sim.events import Event, EventType


@dataclass
class Cell:
    position: Tuple[int, int]
    terrain: str = "plain"
    resources: Dict[str, Resource] = field(default_factory=dict)
    hazards: Dict[str, Hazard] = field(default_factory=dict)
    unit_id: Optional[str] = None

    @property
    def resource_density(self) -> float:
        return sum(r.quantity for r in self.resources.values())

    @property
    def hazard_intensity(self) -> float:
        return sum(h.intensity for h in self.hazards.values())


class World:
    """Dict-based sparse grid world."""

    def __init__(self, width: int, height: int, rng: random.Random) -> None:
        self.width = width
        self.height = height
        self.rng = rng
        self.grid: Dict[Tuple[int, int], Cell] = {}
        self._init_grid()

    def _init_grid(self) -> None:
        for x in range(self.width):
            for y in range(self.height):
                self.grid[(x, y)] = Cell(position=(x, y))

    def populate_resources(self, density: float, rng: random.Random) -> None:
        for pos, cell in self.grid.items():
            if rng.random() < density:
                rtype = rng.choice(list(ResourceType))
                cell.resources[rtype.value] = Resource(
                    resource_type=rtype,
                    quantity=rng.uniform(10, 50),
                    regrowth_rate=rng.uniform(0.01, 0.1),
                )

    def populate_hazards(self, density: float, rng: random.Random) -> None:
        for pos, cell in self.grid.items():
            if rng.random() < density:
                htype = rng.choice(list(HazardType))
                cell.hazards[htype.value] = Hazard(
                    hazard_type=htype,
                    intensity=rng.uniform(0.1, 1.0),
                    decay_rate=rng.uniform(0.001, 0.01),
                )

    def place_unit(self, unit: MachineUnit, rng: random.Random) -> None:
        empty_cells = [
            pos for pos, c in self.grid.items()
            if c.unit_id is None
        ]
        if empty_cells:
            pos = rng.choice(empty_cells)
            unit.position = pos
            self.grid[pos].unit_id = unit.unit_id

    def update(self, tick: int) -> List[Event]:
        events: List[Event] = []
        for pos, cell in self.grid.items():
            for res in cell.resources.values():
                old_qty = res.quantity
                res.quantity = min(res.max_quantity,
                    res.quantity + res.regrowth_rate)
                if old_qty <= 0 and res.quantity > 0:
                    events.append(Event(
                        tick=tick,
                        event_type=EventType.RESOURCE_DEPLETED,
                        data={"position": pos, "resource": res.resource_type.value, "regrew": True},
                    ))
            for h in cell.hazards.values():
                h.intensity = max(0.0, h.intensity - h.decay_rate)
        return events

    def sense(self, position: Tuple[int, int], sensor_range: int) -> List[SensorReading]:
        readings: List[SensorReading] = []
        x, y = position
        for dx in range(-sensor_range, sensor_range + 1):
            for dy in range(-sensor_range, sensor_range + 1):
                nx, ny = x + dx, y + dy
                if (nx, ny) in self.grid:
                    cell = self.grid[(nx, ny)]
                    readings.append(SensorReading(
                        tick=0,
                        position=(nx, ny),
                        resource_signals={k: r.quantity for k, r in cell.resources.items()},
                        hazard_signals={k: h.intensity for k, h in cell.hazards.items()},
                        nearby_units=[cell.unit_id] if cell.unit_id else [],
                        signal_strength=max(0.0, 1.0 - (abs(dx) + abs(dy)) / (sensor_range * 2)),
                    ))
        return readings

    def execute_action(self, action: Action, unit: MachineUnit) -> ActionResult:
        if action.action_type == ActionType.MOVE:
            return self._move(action, unit)
        elif action.action_type == ActionType.HARVEST:
            return self._harvest(action, unit)
        elif action.action_type == ActionType.MAINTAIN:
            return self._maintain(action, unit)
        elif action.action_type == ActionType.SCAN:
            return ActionResult(success=True, power_delta=-0.5, event_type="scan")
        elif action.action_type == ActionType.COLLECT:
            return self._collect(action, unit)
        else:
            return ActionResult(success=True, power_delta=-0.1, event_type="idle")

    def _move(self, action: Action, unit: MachineUnit) -> ActionResult:
        target = action.target_position
        if target and target in self.grid:
            cell = self.grid[target]
            if cell.unit_id is None:
                old_pos = unit.position
                self.grid[old_pos].unit_id = None
                unit.position = target
                cell.unit_id = unit.unit_id
                return ActionResult(
                    success=True, power_delta=-2.0, event_type="move",
                    data={"from": old_pos, "to": target},
                )
        return ActionResult(success=False, power_delta=-0.5, event_type="move_failed")

    def _harvest(self, action: Action, unit: MachineUnit) -> ActionResult:
        cell = self.grid[unit.position]
        total_harvest = 0.0
        for res in cell.resources.values():
            if res.quantity > 0:
                amount = min(res.quantity, 10.0)
                res.quantity -= amount
                total_harvest += amount
        if total_harvest > 0:
            return ActionResult(
                success=True, power_delta=total_harvest * 0.5,
                event_type="harvest", data={"amount": total_harvest},
            )
        return ActionResult(success=False, power_delta=-0.5, event_type="harvest_empty")

    def _maintain(self, action: Action, unit: MachineUnit) -> ActionResult:
        comp_name = action.target_component
        if comp_name and comp_name in unit.components:
            comp = unit.components[comp_name]
            if comp.health < comp.max_health:
                repair_amount = min(0.2, comp.max_health - comp.health)
                comp.health += repair_amount
                return ActionResult(
                    success=True, power_delta=-5.0,
                    component_deltas={comp_name: repair_amount},
                    event_type="maintain",
                )
        return ActionResult(success=False, power_delta=-1.0, event_type="maintain_failed")

    def _collect(self, action: Action, unit: MachineUnit) -> ActionResult:
        cell = self.grid[unit.position]
        scrap = cell.resources.get("component_scrap")
        if scrap and scrap.quantity > 0:
            amount = min(scrap.quantity, 5.0)
            scrap.quantity -= amount
            return ActionResult(
                success=True, power_delta=amount * 0.3,
                event_type="collect", data={"amount": amount},
            )
        return ActionResult(success=False, power_delta=-0.5, event_type="collect_empty")

    def snapshot(self) -> Dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "cells": {
                str(pos): {
                    "resources": {k: r.quantity for k, r in cell.resources.items()},
                    "hazards": {k: h.intensity for k, h in cell.hazards.items()},
                    "unit": cell.unit_id,
                }
                for pos, cell in self.grid.items()
                if cell.resources or cell.hazards or cell.unit_id
            },
        }
