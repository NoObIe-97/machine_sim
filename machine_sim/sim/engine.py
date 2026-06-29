"""Core tick-based simulation engine."""

from __future__ import annotations

import logging
from typing import List, Optional

from machine_sim.agents.base import MachineUnit
from machine_sim.environment.world import World
from machine_sim.sim.config import SimConfig
from machine_sim.sim.events import Event, EventLog, EventType
from machine_sim.sim.state import SimulationState

logger = logging.getLogger(__name__)


class SimEngine:
    """Tick-based simulation engine with deterministic seeding."""

    def __init__(self, config: SimConfig, seed: Optional[int] = None) -> None:
        self.config = config
        import random as _random
        self.rng = _random.Random(seed)
        self.world = World(config.grid_width, config.grid_height, self.rng)
        self.units: List[MachineUnit] = []
        self.event_log = EventLog()
        self.tick_count = 0
        self.max_ticks = config.max_ticks

    def register_unit(self, unit: MachineUnit) -> None:
        self.units.append(unit)

    def initialize(self) -> None:
        self.world.populate_resources(self.config.resource_density, self.rng)
        self.world.populate_hazards(self.config.hazard_density, self.rng)
        for unit in self.units:
            self.world.place_unit(unit, self.rng)

    def run(self) -> SimulationState:
        self.initialize()
        while self.tick_count < self.max_ticks:
            self.tick()
        return self.snapshot()

    def tick(self) -> None:
        self.tick_count += 1
        self.event_log.begin_tick(self.tick_count)

        # Phase 1: Environment update
        env_events = self.world.update(self.tick_count)
        for e in env_events:
            self.event_log.record(e)

        # Phase 2: Unit sensing
        for unit in self.units:
            if unit.is_active:
                readings = self.world.sense(unit.position, unit.sensor_range)
                unit.receive_observations(readings, self.tick_count)

        # Phase 3: Unit decision + action
        for unit in self.units:
            if unit.is_active:
                action = unit.decide(self.tick_count)
                if action is not None:
                    result = self.world.execute_action(action, unit)
                    unit.apply_result(result, self.tick_count)
                    self.event_log.record(Event(
                        tick=self.tick_count,
                        event_type=EventType.UNIT_ACTION,
                        unit_id=unit.unit_id,
                        data={"action": action.action_type.name, "success": result.success},
                    ))

        # Phase 4: Unit degradation
        for unit in self.units:
            if unit.is_active:
                unit.degrade(self.config.power_drain_rate, self.rng)

        self.event_log.end_tick(self.tick_count)

    def snapshot(self) -> SimulationState:
        return SimulationState(
            tick=self.tick_count,
            agents=[u.state_copy() for u in self.units],
            world=self.world.snapshot(),
            events=self.event_log.all_events(),
        )
