"""Core tick-based simulation engine."""

from __future__ import annotations

import logging
from typing import List, Optional

from machine_sim.agents.base import MachineUnit
from machine_sim.environment.world import World
from machine_sim.guardrails.runtime import (
    StateViolation,
    validate_action_name,
    validate_agent_state,
    validate_event_label,
)
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

    def _record_event(self, event: Event) -> None:
        validate_event_label(event.event_type.name.lower())
        self.event_log.record(event)

    def tick(self) -> None:
        self.tick_count += 1
        self._record_event(Event(tick=self.tick_count, event_type=EventType.TICK_BEGIN))

        # Phase 1: Environment update
        env_events = self.world.update(self.tick_count)
        for e in env_events:
            self._record_event(e)

        # Phase 2: Unit sensing
        for unit in self.units:
            if unit.is_active:
                readings = self.world.sense(unit.position, unit.sensor_range,
                                           exclude_unit_id=unit.unit_id)
                unit.receive_observations(readings, self.tick_count)

        # Phase 3: Unit decision + action
        for unit in self.units:
            if unit.is_active:
                action = unit.decide(self.tick_count)
                if action is not None:
                    validate_action_name(action.action_type.name)
                    result = self.world.execute_action(action, unit)
                    unit.apply_result(result, self.tick_count)
                    self._record_event(Event(
                        tick=self.tick_count,
                        event_type=EventType.UNIT_ACTION,
                        unit_id=unit.unit_id,
                        data={"action": action.action_type.name, "success": result.success},
                    ))
                    # Emit interaction events for blocked movement
                    if result.event_type == "movement_blocked":
                        self._record_event(Event(
                            tick=self.tick_count,
                            event_type=EventType.MOVEMENT_BLOCKED,
                            unit_id=unit.unit_id,
                            data=result.data,
                        ))
                    # Emit signal events
                    if result.event_type == "emit_signal":
                        self._record_event(Event(
                            tick=self.tick_count,
                            event_type=EventType.SIGNAL_EMITTED,
                            unit_id=unit.unit_id,
                            data=result.data,
                        ))

        # Phase 3b: Proximity detection and spatial pressure
        for unit in self.units:
            if unit.is_active:
                nearby_count = self.world.count_nearby_units(unit.position, unit.sensor_range)
                spatial_pressure = self.world.compute_spatial_pressure(unit.position, unit.sensor_range)
                if nearby_count > 0:
                    self._record_event(Event(
                        tick=self.tick_count,
                        event_type=EventType.UNIT_PROXIMITY,
                        unit_id=unit.unit_id,
                        data={"nearby_count": nearby_count, "spatial_pressure": spatial_pressure},
                    ))

        # Phase 3c: Signal sensing (source units excluded from own signals)
        for unit in self.units:
            if unit.is_active:
                signal_obs = self.world.sense_signals(unit.position, unit.sensor_range,
                                                      exclude_unit_id=unit.unit_id)
                for obs in signal_obs:
                    self._record_event(Event(
                        tick=self.tick_count,
                        event_type=EventType.SIGNAL_RECEIVED,
                        unit_id=unit.unit_id,
                        data=obs,
                    ))

        # Phase 4: Unit degradation (variant-specific drain)
        for unit in self.units:
            if unit.is_active:
                drain = getattr(unit, 'variant', None)
                drain_rate = drain.power_drain_rate if drain else self.config.power_drain_rate
                unit.degrade(drain_rate, self.rng)

        # Phase 5: Hazard damage
        for unit in self.units:
            if unit.is_active:
                hazard_events = self.world.apply_hazard_damage(unit, self.tick_count)
                for e in hazard_events:
                    self._record_event(e)

        # Phase 6: Validate state
        for unit in self.units:
            if unit.is_active:
                validate_agent_state(unit.state_copy())

        self._record_event(Event(tick=self.tick_count, event_type=EventType.TICK_END))

    def snapshot(self) -> SimulationState:
        return SimulationState(
            tick=self.tick_count,
            agents=[u.state_copy() for u in self.units],
            world=self.world.snapshot(),
            events=self.event_log.all_events(),
        )
