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


@dataclass
class Signal:
    """A non-semantic physical signal in the world."""
    signal_id: int
    source_unit_id: str
    pattern_id: int
    position: Tuple[int, int]
    intensity: float
    radius: int
    decay_rate: float
    emitted_tick: int
    duration: int = 10


class World:
    """Dict-based sparse grid world."""

    def __init__(self, width: int, height: int, rng: random.Random) -> None:
        self.width = width
        self.height = height
        self.rng = rng
        self.grid: Dict[Tuple[int, int], Cell] = {}
        self.signals: List[Signal] = []
        self._next_signal_id = 0
        self._current_tick = 0
        self._active_cells: set = set()
        # M21 benchmark counters: observation-only, never read by the tick loop.
        self.update_calls = 0
        self.cells_visited_total = 0
        self.cells_updated_total = 0
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
                self._active_cells.add(pos)

    def populate_hazards(self, density: float, rng: random.Random) -> None:
        for pos, cell in self.grid.items():
            if rng.random() < density:
                htype = rng.choice(list(HazardType))
                cell.hazards[htype.value] = Hazard(
                    hazard_type=htype,
                    intensity=rng.uniform(0.1, 1.0),
                    decay_rate=rng.uniform(0.001, 0.01),
                )
                self._active_cells.add(pos)

    def place_unit(self, unit: MachineUnit, rng: random.Random) -> None:
        # If unit already has a valid position, use it
        if unit.position in self.grid and self.grid[unit.position].unit_id is None:
            self.grid[unit.position].unit_id = unit.unit_id
            return
        # Otherwise find a random empty cell
        empty_cells = [
            pos for pos, c in self.grid.items()
            if c.unit_id is None
        ]
        if empty_cells:
            pos = rng.choice(empty_cells)
            unit.position = pos
            self.grid[pos].unit_id = unit.unit_id

    def update(self, tick: int) -> List[Event]:
        self._current_tick = tick
        self.update_calls += 1
        events: List[Event] = []
        for pos, cell in self.grid.items():
            self.cells_visited_total += 1
            if cell.resources or cell.hazards:
                self.cells_updated_total += 1
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
        # Decay and remove expired signals
        self.signals = [s for s in self.signals if tick - s.emitted_tick < s.duration]
        for sig in self.signals:
            sig.intensity = max(0.0, sig.intensity - sig.decay_rate)
        return events

    def emit_signal(self, source_unit_id: str, position: Tuple[int, int],
                    pattern_id: int, intensity: float, radius: int,
                    decay_rate: float, tick: int, duration: int = 10) -> Signal:
        """Create a new signal in the world."""
        sig = Signal(
            signal_id=self._next_signal_id,
            source_unit_id=source_unit_id,
            pattern_id=pattern_id,
            position=position,
            intensity=intensity,
            radius=radius,
            decay_rate=decay_rate,
            emitted_tick=tick,
            duration=duration,
        )
        self._next_signal_id += 1
        self.signals.append(sig)
        return sig

    def sense_signals(self, position: Tuple[int, int],
                      sensor_range: int,
                      exclude_unit_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return signal observations visible from a position.

        The exclude_unit_id parameter allows excluding signals from a specific
        source (typically the sensing unit itself, to avoid self-reception).

        Signal observation range is the signal's own radius, not limited by
        the unit's physical sensor range (signals propagate through the field).
        """
        observations: List[Dict[str, Any]] = []
        x, y = position
        for sig in self.signals:
            if sig.intensity <= 0:
                continue
            if exclude_unit_id and sig.source_unit_id == exclude_unit_id:
                continue
            sx, sy = sig.position
            dist = abs(x - sx) + abs(y - sy)  # Manhattan distance
            if dist <= sig.radius:
                signal_strength = max(0.0, sig.intensity * (1.0 - dist / max(sig.radius, 1)))
                observations.append({
                    "signal_id": sig.signal_id,
                    "source_unit_id": sig.source_unit_id,
                    "pattern_id": sig.pattern_id,
                    "position": sig.position,
                    "intensity": sig.intensity,
                    "signal_strength": signal_strength,
                    "distance": dist,
                })
        return observations

    def sense(self, position: Tuple[int, int], sensor_range: int,
              exclude_unit_id: Optional[str] = None) -> List[SensorReading]:
        readings: List[SensorReading] = []
        x, y = position
        for dx in range(-sensor_range, sensor_range + 1):
            for dy in range(-sensor_range, sensor_range + 1):
                nx, ny = x + dx, y + dy
                if (nx, ny) in self.grid:
                    cell = self.grid[(nx, ny)]
                    nearby = [uid for uid in ([cell.unit_id] if cell.unit_id else [])
                              if uid != exclude_unit_id]
                    readings.append(SensorReading(
                        tick=0,
                        position=(nx, ny),
                        resource_signals={k: r.quantity for k, r in cell.resources.items()},
                        hazard_signals={k: h.intensity for k, h in cell.hazards.items()},
                        nearby_units=nearby,
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
            return self._scan(action, unit)
        elif action.action_type == ActionType.COLLECT:
            return self._collect(action, unit)
        elif action.action_type == ActionType.EMIT_SIGNAL:
            return self._emit_signal(action, unit)
        else:
            return ActionResult(success=True, power_delta=-0.1, event_type="idle")

    def apply_hazard_damage(self, unit: MachineUnit, tick: int) -> List[Event]:
        """Apply hazard effects to unit occupying a hazardous cell."""
        events: List[Event] = []
        cell = self.grid.get(unit.position)
        if not cell or not cell.hazards:
            return events

        total_intensity = cell.hazard_intensity
        if total_intensity <= 0:
            return events

        power_penalty = -total_intensity * 2.0
        unit.power_reserve = max(0.0, unit.power_reserve + power_penalty)

        for h in cell.hazards.values():
            if h.intensity > 0.1:
                comp_damage = -h.intensity * 0.05
                for comp in unit.components.values():
                    comp.health = max(0.0, comp.health + comp_damage)

        events.append(Event(
            tick=tick,
            event_type=EventType.HAZARD_ENCOUNTER,
            unit_id=unit.unit_id,
            data={"intensity": total_intensity, "power_penalty": power_penalty},
        ))

        if unit.power_reserve <= 0 or unit._critical_component_failed():
            unit.is_active = False
            events.append(Event(
                tick=tick,
                event_type=EventType.UNIT_DEACTIVATED,
                unit_id=unit.unit_id,
                data={"cause": "hazard_damage"},
            ))

        return events

    def _move(self, action: Action, unit: MachineUnit) -> ActionResult:
        target = action.target_position
        if not target or target not in self.grid:
            return ActionResult(success=False, power_delta=-0.5, event_type="move_failed")

        # Enforce adjacent movement (max 1 step in any direction)
        dx = abs(target[0] - unit.position[0])
        dy = abs(target[1] - unit.position[1])
        if dx > 1 or dy > 1 or (dx == 0 and dy == 0):
            return ActionResult(
                success=False, power_delta=-0.5, event_type="move_failed",
                data={"cause": "non_adjacent", "target": target},
            )

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
        else:
            return ActionResult(
                success=False, power_delta=-0.5,
                event_type="movement_blocked",
                data={"target": target, "blocked_by": cell.unit_id},
            )

    def _harvest(self, action: Action, unit: MachineUnit) -> ActionResult:
        cell = self.grid[unit.position]
        total_harvest = 0.0
        for res in cell.resources.values():
            if res.quantity > 0:
                amount = min(res.quantity, 15.0)
                res.quantity -= amount
                total_harvest += amount
        if total_harvest > 0:
            return ActionResult(
                success=True, power_delta=total_harvest * 3.0,
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

    def _scan(self, action: Action, unit: MachineUnit) -> ActionResult:
        """Extended scan: read cells beyond normal sensor range."""
        extended_range = unit.sensor_range + 2
        readings = self.sense(unit.position, extended_range, exclude_unit_id=unit.unit_id)
        unit.receive_observations(readings, unit.local_memory[-1].tick if unit.local_memory else 0)
        return ActionResult(
            success=True, power_delta=-0.5,
            event_type="scan",
            data={"extended_range": extended_range, "readings_count": len(readings)},
        )

    def _emit_signal(self, action: Action, unit: MachineUnit,
                     current_tick: int = 0) -> ActionResult:
        """Emit a non-semantic physical signal."""
        params = action.parameters
        pattern_id = params.get("pattern_id", 0)
        intensity = params.get("intensity", 1.0)
        radius = params.get("radius", 3)
        decay_rate = params.get("decay_rate", 0.1)
        duration = params.get("duration", 10)
        energy_cost = params.get("energy_cost", 2.0)

        sig = self.emit_signal(
            source_unit_id=unit.unit_id,
            position=unit.position,
            pattern_id=pattern_id,
            intensity=intensity,
            radius=radius,
            decay_rate=decay_rate,
            tick=self._current_tick,
            duration=duration,
        )

        return ActionResult(
            success=True, power_delta=-energy_cost,
            event_type="emit_signal",
            data={
                "signal_id": sig.signal_id,
                "pattern_id": pattern_id,
                "radius": radius,
                "intensity": intensity,
            },
        )

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

    def compute_spatial_pressure(self, position: Tuple[int, int], sensor_range: int) -> float:
        """Compute local spatial pressure from nearby occupied cells.

        Excludes the center cell (the sensing unit's own position).
        Returns a bounded metric [0.0, 1.0] representing nearby crowding.
        0.0 = no other units nearby, 1.0 = all nearby cells occupied by others.
        """
        x, y = position
        total_cells = 0
        occupied_cells = 0
        for dx in range(-sensor_range, sensor_range + 1):
            for dy in range(-sensor_range, sensor_range + 1):
                if dx == 0 and dy == 0:
                    continue  # Exclude center cell
                nx, ny = x + dx, y + dy
                if (nx, ny) in self.grid:
                    total_cells += 1
                    if self.grid[(nx, ny)].unit_id is not None:
                        occupied_cells += 1
        if total_cells == 0:
            return 0.0
        return occupied_cells / total_cells

    def count_nearby_units(self, position: Tuple[int, int], sensor_range: int) -> int:
        """Count units within sensor range (excluding self)."""
        x, y = position
        count = 0
        for dx in range(-sensor_range, sensor_range + 1):
            for dy in range(-sensor_range, sensor_range + 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if (nx, ny) in self.grid and self.grid[(nx, ny)].unit_id is not None:
                    count += 1
        return count
