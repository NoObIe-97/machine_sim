"""Core tick-based simulation engine."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from machine_sim.agents.base import ActionType, MachineUnit
from machine_sim.analysis.correlation import SignalCorrelator
from machine_sim.environment.fabrication import FabricationEngine, FabricationResult
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
        self.correlator = SignalCorrelator(
            observation_window=config.signal_observation_window
        )
        self.fabrication_engine = FabricationEngine(
            population_cap=config.population_cap,
            fabrication_interval=config.fabrication_interval,
            power_cost=config.fabrication_power_cost,
            material_cost=config.fabrication_material_cost,
            variation_factor=config.fabrication_variation,
        )

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
                        # Record for field tracker
                        if hasattr(unit, '_field_tracker'):
                            unit._field_tracker.record_movement_block(self.tick_count)
                    # Emit signal events
                    if result.event_type == "emit_signal":
                        self._record_event(Event(
                            tick=self.tick_count,
                            event_type=EventType.SIGNAL_EMITTED,
                            unit_id=unit.unit_id,
                            data=result.data,
                        ))
                        # Record for correlation analysis
                        self.correlator.record_signal_emission(
                            tick=self.tick_count,
                            unit_id=unit.unit_id,
                            pattern_id=result.data.get("pattern_id", 0),
                            data=result.data,
                        )
                        # Record for field tracker
                        if hasattr(unit, '_field_tracker'):
                            unit._field_tracker.record_emission(self.tick_count)
                    # Record scans for field tracker
                    if action.action_type == ActionType.SCAN:
                        if hasattr(unit, '_field_tracker'):
                            unit._field_tracker.record_scan(self.tick_count)

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
                    # Record for correlation analysis
                    self.correlator.record_observation(
                        tick=self.tick_count,
                        unit_id=unit.unit_id,
                        observation_type="proximity",
                        data={"nearby_count": nearby_count, "spatial_pressure": spatial_pressure},
                    )

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
                    # Record for field tracker
                    if hasattr(unit, '_field_tracker'):
                        unit._field_tracker.record_signal_observation(
                            self.tick_count,
                            obs.get("pattern_id", 0),
                            obs.get("intensity", 0.0),
                        )

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
                    # Record hazard encounters for correlation analysis
                    if e.event_type == EventType.HAZARD_ENCOUNTER:
                        self.correlator.record_observation(
                            tick=self.tick_count,
                            unit_id=unit.unit_id,
                            observation_type="hazard_encounter",
                            data=e.data,
                        )
                        # Record for field tracker
                        if hasattr(unit, '_field_tracker'):
                            unit._field_tracker.record_hazard_event(self.tick_count)

        # Phase 6: Validate state
        for unit in self.units:
            if unit.is_active:
                validate_agent_state(unit.state_copy())

        # Phase 7: Fabrication (if enabled)
        if self.config.fabrication_enabled:
            new_units = []
            for unit in self.units:
                if unit.is_active:
                    result = self.fabrication_engine.fabricate(
                        unit, self.tick_count, self.world,
                        len(self.units) + len(new_units), self.rng
                    )
                    if result.success:
                        # Create successor unit from design template
                        from machine_sim.agents.unit import MachineUnitImpl
                        template = self.fabrication_engine._create_template(unit, self.rng)
                        placement = self.fabrication_engine._find_placement(
                            unit.position, self.world
                        )
                        successor = MachineUnitImpl(
                            unit_id=result.successor_id,
                            position=placement or unit.position,
                            signal_enabled=template.signal_enabled,
                            signal_pattern_count=template.signal_pattern_count,
                            signal_energy_cost=template.signal_energy_cost,
                            signal_default_radius=template.signal_default_radius,
                            signal_default_decay=template.signal_default_decay,
                            signal_default_duration=template.signal_default_duration,
                            adaptive_enabled=template.adaptive_enabled,
                        )
                        successor._generation_index = getattr(unit, '_generation_index', 0) + 1
                        new_units.append(successor)
                        self._record_event(Event(
                            tick=self.tick_count,
                            event_type=EventType.FABRICATION_SUCCEEDED,
                            unit_id=unit.unit_id,
                            data={
                                "successor_id": result.successor_id,
                                "material_cost": result.material_cost,
                                "power_cost": result.power_cost,
                            },
                        ))
                    elif result.failure_cause:
                        self._record_event(Event(
                            tick=self.tick_count,
                            event_type=EventType.FABRICATION_FAILED,
                            unit_id=unit.unit_id,
                            data={"cause": result.failure_cause},
                        ))

            # Register new units
            for new_unit in new_units:
                self.register_unit(new_unit)
                self.world.place_unit(new_unit, self.rng)

        self._record_event(Event(tick=self.tick_count, event_type=EventType.TICK_END))

    def get_fabrication_summary(self) -> Dict[str, Any]:
        """Get fabrication and lineage summary."""
        return self.fabrication_engine.get_summary()

    def snapshot(self) -> SimulationState:
        # Compute final associations
        self.correlator.compute_associations()
        return SimulationState(
            tick=self.tick_count,
            agents=[u.state_copy() for u in self.units],
            world=self.world.snapshot(),
            events=self.event_log.all_events(),
        )

    def get_correlation_summary(self) -> Dict[str, Any]:
        """Get signal correlation summary after simulation."""
        self.correlator.compute_associations()
        return self.correlator.get_summary()

    def get_adaptive_summary(self) -> Dict[str, Any]:
        """Get adaptive behavior summary for all units."""
        summaries = {}
        for unit in self.units:
            if hasattr(unit, '_field_tracker'):
                field_summary = unit._field_tracker.get_summary(self.tick_count)
                summaries[unit.unit_id] = {
                    # Recent window stats
                    "signal_count": field_summary.recent_signal_count,
                    "pattern_frequency": dict(field_summary.pattern_frequency),
                    "avg_intensity": field_summary.avg_received_intensity,
                    "hazard_density": field_summary.local_hazard_density,
                    "proximity_count": field_summary.local_proximity_count,
                    "movement_blocks": field_summary.recent_movement_blocks,
                    "emission_rate": field_summary.emission_rate,
                    "scan_rate": field_summary.scan_rate,
                    # Cumulative run-level stats
                    "total_signals": field_summary.total_signals,
                    "total_hazards": field_summary.total_hazards,
                    "total_proximity": field_summary.total_proximity,
                    "total_movement_blocks": field_summary.total_movement_blocks,
                    "total_emissions": field_summary.total_emissions,
                    "total_scans": field_summary.total_scans,
                    "adaptive_enabled": getattr(unit, 'adaptive_enabled', False),
                }
        return summaries
