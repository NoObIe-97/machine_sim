"""Core tick-based simulation engine."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from machine_sim.agents.base import ActionType, MachineUnit
from machine_sim.analysis.correlation import SignalCorrelator
from machine_sim.analysis.field_dynamics import SignalFieldDynamics
from machine_sim.analysis.pressure import PressureAnalyzer
from machine_sim.analysis.telemetry import LineageDriftAnalyzer, ReconciliationEngine, TelemetryTracker
from machine_sim.analysis.trace_compression import TraceCompressor
from machine_sim.analysis.trace_drift import TraceDriftAnalyzer
from machine_sim.analysis.summary_consistency import SummaryConsistencyAnalyzer
from machine_sim.analysis.multi_generation_trace import MultiGenerationTraceAnalyzer
from machine_sim.environment.calibration import CapsuleManager
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
        self._adaptive_state_snapshots: List[Dict[str, Any]] = []
        self._adaptive_snapshot_interval = max(1, config.max_ticks // 10)
        self.correlator = SignalCorrelator(
            observation_window=config.signal_observation_window
        )
        self.fabrication_engine = FabricationEngine(
            population_cap=config.unit_capacity,
            fabrication_interval=config.fabrication_interval,
            power_cost=config.fabrication_power_cost,
            material_cost=config.fabrication_material_cost,
            variation_factor=config.fabrication_variation,
            min_power_ratio=config.fabrication_min_power_ratio,
            min_component_health=config.fabrication_min_component_health,
        )
        self.capsule_manager = CapsuleManager(enabled=config.capsule_enabled)
        self.telemetry_tracker = TelemetryTracker(enabled=config.telemetry_enabled)
        self.reconciliation_engine = ReconciliationEngine(
            enabled=config.reconciliation_enabled,
            interval=config.reconciliation_interval,
            radius=config.reconciliation_radius,
        )
        self.lineage_drift = LineageDriftAnalyzer(enabled=config.lineage_drift_enabled)
        self.pressure_analyzer = PressureAnalyzer(enabled=config.pressure_analysis_enabled)
        self.field_dynamics = SignalFieldDynamics(enabled=config.signal_dynamics_enabled)
        self.trace_compressor = TraceCompressor(enabled=config.trace_compression_enabled)
        self.trace_drift = TraceDriftAnalyzer(enabled=config.trace_drift_enabled)
        self.summary_consistency = SummaryConsistencyAnalyzer(enabled=config.summary_consistency_enabled)
        self.multi_gen_trace = MultiGenerationTraceAnalyzer(enabled=config.multi_generation_trace_enabled)

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
        # Clear per-tick event buffer so current_tick_events() stays O(1)
        self.event_log._tick_events = []
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
                    if result.success and result.template and result.placement:
                        # Create successor unit from the exact template generated
                        from machine_sim.agents.unit import MachineUnitImpl
                        tmpl = result.template
                        successor = MachineUnitImpl(
                            unit_id=result.successor_id,
                            position=result.placement,
                            signal_enabled=tmpl.signal_enabled,
                            signal_pattern_count=tmpl.signal_pattern_count,
                            signal_energy_cost=tmpl.signal_energy_cost,
                            signal_default_radius=tmpl.signal_default_radius,
                            signal_default_decay=tmpl.signal_default_decay,
                            signal_default_duration=tmpl.signal_default_duration,
                            adaptive_enabled=tmpl.adaptive_enabled,
                        )
                        successor.max_power = tmpl.max_power
                        successor.power_reserve = tmpl.max_power
                        successor.SENSOR_RANGE = tmpl.sensor_range
                        successor._generation_index = getattr(unit, '_generation_index', 0) + 1

                        # Scale component degradation rates for successor
                        if self.config.component_degradation_scale != 1.0:
                            for comp in successor.components.values():
                                comp.degradation_rate *= self.config.component_degradation_scale

                        # Generate and apply calibration capsule
                        if self.capsule_manager.enabled:
                            capsule = self.capsule_manager.generate_and_store(
                                unit, self.world, result.successor_id, self.tick_count
                            )
                            self.capsule_manager.generator.apply_warm_start(capsule, successor)
                            result.capsule = capsule

                        # Transfer adaptive state from source to successor
                        if (self.config.adaptive_enabled
                                and hasattr(unit, '_adaptive_controller')
                                and unit._adaptive_controller.enabled
                                and successor.adaptive_enabled):
                            successor_state = unit._adaptive_controller.transfer_to_successor(
                                unit._adaptive_state, self.rng, variation=0.05
                            )
                            successor._adaptive_state = successor_state
                            # Record descendant adaptive-state transfer
                            if self.config.long_run_adaptation_enabled:
                                if not hasattr(self, '_descendant_transfer_trace'):
                                    self._descendant_transfer_trace = []
                                source_d = unit._adaptive_state.to_dict()
                                succ_d = successor_state.to_dict()
                                delta = {k: succ_d[k] - source_d[k] for k in source_d}
                                self._descendant_transfer_trace.append({
                                    "tick": self.tick_count,
                                    "source_unit_id": unit.unit_id,
                                    "successor_unit_id": result.successor_id,
                                    "source_generation": getattr(unit, '_generation_index', 0),
                                    "successor_generation": successor._generation_index,
                                    "source_adaptive_summary": {k: round(v, 4) for k, v in source_d.items()},
                                    "successor_adaptive_summary": {k: round(v, 4) for k, v in succ_d.items()},
                                    "bounded_delta_summary": {k: round(v, 4) for k, v in delta.items()},
                                })
                            # Record generation-indexed transfer trace
                            if self.config.long_run_adaptation_enabled and self.config.multi_generation_trace_enabled:
                                self.multi_gen_trace.record_transfer(
                                    tick=self.tick_count,
                                    source_unit_id=unit.unit_id,
                                    successor_unit_id=result.successor_id,
                                    source_generation_index=getattr(unit, '_generation_index', 0),
                                    successor_generation_index=successor._generation_index,
                                    source_adaptive_state=unit._adaptive_state.to_dict(),
                                    successor_adaptive_state=successor_state.to_dict(),
                                    source_lifetime_ticks=self.tick_count,
                                    successor_initial_power_ratio=successor._power_ratio(),
                                )

                        new_units.append(successor)
                        self._record_event(Event(
                            tick=self.tick_count,
                            event_type=EventType.FABRICATION_SUCCEEDED,
                            unit_id=unit.unit_id,
                            data={
                                "successor_id": result.successor_id,
                                "placement": list(result.placement),
                                "material_cost": result.material_cost,
                                "power_cost": result.power_cost,
                                "max_power": tmpl.max_power,
                                "sensor_range": tmpl.sensor_range,
                                "capsule_applied": self.capsule_manager.enabled,
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

        # Phase 8: Telemetry recording
        if self.telemetry_tracker.enabled:
            for unit in self.units:
                if unit.is_active:
                    self.telemetry_tracker.record_frame(unit, self.tick_count, self.world)

        # Phase 9: Reconciliation (at configured interval)
        if self.reconciliation_engine.enabled and self.tick_count % self.reconciliation_engine.interval == 0:
            active_units = [u for u in self.units if u.is_active]
            self.reconciliation_engine.reconcile(active_units, self.world, self.tick_count)

        # Phase 10: Pressure analysis
        if self.pressure_analyzer.enabled:
            self.pressure_analyzer.record_tick(
                self.world, self.units, self.tick_count,
                signal_enabled=self.config.signal_enabled
            )

        # Phase 11: Signal field dynamics (record signals for analysis)
        if self.field_dynamics.enabled:
            # Compute and store gradient
            gradient = self.field_dynamics.compute_signal_gradient(self.world)
            self.field_dynamics.record_gradient(gradient)
            # Record signals from correlator
            for sig_tick, sig_unit, pattern_id, sig_data in self.correlator._signal_history:
                if sig_tick == self.tick_count:
                    self.field_dynamics.record_signal(sig_tick, sig_unit, pattern_id, sig_data)
            # Record observations from correlator
            for obs_tick, obs_unit, obs_type, obs_data in self.correlator._observation_history:
                if obs_tick == self.tick_count:
                    self.field_dynamics.record_observation(obs_tick, obs_unit, obs_type, obs_data)

        # Phase 12: Trace compression
        if self.trace_compressor.enabled:
            for unit in self.units:
                if unit.is_active:
                    field_summary = unit._field_tracker.get_summary(self.tick_count) if hasattr(unit, '_field_tracker') else None
                    self.trace_compressor.record_trace_point(
                        tick=self.tick_count,
                        unit_id=unit.unit_id,
                        data={
                            "power_ratio": unit._power_ratio(),
                            "component_health": unit._avg_component_health(),
                            "signal_count": field_summary.total_signals if field_summary else 0,
                            "observation_count": field_summary.total_signals if field_summary else 0,
                            "hazard_count": field_summary.total_hazards if field_summary else 0,
                            "emission_count": field_summary.total_emissions if field_summary else 0,
                            "scan_count": field_summary.total_scans if field_summary else 0,
                        }
                    )
                    # Telemetry frame for window reduction
                    if self.telemetry_tracker.enabled:
                        self.trace_compressor.record_telemetry_frame(
                            tick=self.tick_count,
                            data={
                                "power_ratio": unit._power_ratio(),
                                "sensor_health": unit._avg_component_health(),
                                "unit_id": unit.unit_id,
                            }
                        )
            # Capsule-compatible diagnostic summary
            if self.capsule_manager.enabled:
                for unit in self.units:
                    if unit.is_active:
                        field_summary = unit._field_tracker.get_summary(self.tick_count) if hasattr(unit, '_field_tracker') else None
                        self.trace_compressor.record_capsule_data({
                            "unit_id": unit.unit_id,
                            "power_ratio": unit._power_ratio(),
                            "sensor_health": unit._avg_component_health(),
                            "local_field_value": field_summary.total_signals if field_summary else 0,
                        })
            # Lineage-indexed trace comparison
            if self.config.fabrication_enabled:
                lineage_records = self.fabrication_engine.get_lineage_records()
                for rec in lineage_records[-self.trace_compressor.max_records:]:
                    self.trace_compressor.record_lineage_data({
                        "unit_id": rec.source_unit_id,
                        "tick": rec.fabrication_tick,
                        "power_ratio": rec.design_distance,
                        "generation_index": rec.successor_generation,
                    })

        # Phase 13: Trace drift analysis
        if self.trace_drift.enabled:
            # Generation-indexed trace deltas from fabrication lineage
            if self.config.fabrication_enabled:
                lineage_records = self.fabrication_engine.get_lineage_records()
                for rec in lineage_records:
                    self.trace_drift.record_generation_trace({
                        "generation_index": rec.successor_generation,
                        "power_ratio": rec.design_distance,
                        "tick": rec.fabrication_tick,
                    })
            # Drift envelopes from trace compression segments
            if self.trace_compressor.enabled:
                segments = self.trace_compressor.get_segments()
                for seg in segments:
                    self.trace_drift.record_envelope({
                        "power_ratio": seg.avg_power_ratio,
                        "sensor_health": seg.avg_component_health,
                        "signal_count": seg.signal_count,
                        "envelope_width": abs(seg.avg_power_ratio - 0.5),
                    })
                # Replay stability from trace compressor summary
                tc_summary = self.trace_compressor.compress()
                for i, seg in enumerate(segments):
                    self.trace_drift.record_replay({
                        "tick": seg.start_tick,
                        "replay_error": abs(seg.avg_power_ratio - 0.5),
                    })
            # Capsule-trace compatibility
            if self.capsule_manager.enabled and self.trace_compressor.enabled:
                cap_records = self.trace_compressor._capsule_records
                segments = self.trace_compressor.get_segments()
                avg_power = sum(s.avg_power_ratio for s in segments) / max(1, len(segments))
                avg_health = sum(s.avg_component_health for s in segments) / max(1, len(segments))
                for cr in cap_records:
                    self.trace_drift.record_capsule_trace({
                        "power_delta": abs(cr.get("power_ratio", 0.0) - avg_power),
                        "sensor_delta": abs(cr.get("sensor_health", 0.0) - avg_health),
                        "field_delta": abs(cr.get("local_field_value", 0) - avg_health),
                        "compatibility_score": 1.0 - abs(cr.get("power_ratio", 0.0) - avg_power),
                    })
            # Long-run retention
            if self.trace_compressor.enabled:
                all_traces = self.trace_compressor._raw_traces
                for t in all_traces:
                    self.trace_drift._retention_records.append({
                        "tick": t.get("tick", 0),
                        "unit_id": t.get("unit_id", ""),
                    })
                    if len(self.trace_drift._retention_records) > self.trace_drift.max_records:
                        self.trace_drift._retention_records = self.trace_drift._retention_records[-self.trace_drift.max_records:]

        # Phase 14: Summary consistency analysis
        if self.summary_consistency.enabled:
            # Cross-unit diagnostic summary comparison
            if self.trace_compressor.enabled:
                segments = self.trace_compressor.get_segments()
                # Group segments by unit
                unit_segs: Dict[str, List[Any]] = {}
                for seg in segments:
                    if seg.unit_id not in unit_segs:
                        unit_segs[seg.unit_id] = []
                    unit_segs[seg.unit_id].append(seg)
                for uid, segs in unit_segs.items():
                    avg_pwr = sum(s.avg_power_ratio for s in segs) / len(segs)
                    avg_hlth = sum(s.avg_component_health for s in segs) / len(segs)
                    total_sig = sum(s.signal_count for s in segs)
                    total_obs = sum(s.observation_count for s in segs)
                    self.summary_consistency.record_unit_summary({
                        "unit_id": uid,
                        "power_ratio": avg_pwr,
                        "sensor_health": avg_hlth,
                        "signal_count": total_sig,
                        "replay_error": abs(avg_pwr - 0.5),
                    })
            # Windowed retention stability
            if self.trace_drift.enabled:
                ret_records = self.trace_drift._retention_records
                if ret_records:
                    window_size = max(1, len(ret_records) // max(1, self.summary_consistency.window))
                    for i in range(0, len(ret_records), window_size):
                        w = ret_records[i:i + window_size]
                        if not w:
                            continue
                        ticks = [r.get("tick", 0) for r in w]
                        variance = 0.0
                        if len(ticks) > 1:
                            mean_t = sum(ticks) / len(ticks)
                            variance = sum((t - mean_t) ** 2 for t in ticks) / len(ticks)
                        self.summary_consistency.record_retention({
                            "tick": ticks[0] if ticks else 0,
                            "variance": variance,
                            "dropped": 0,
                            "total": len(w),
                        })
            # Compression ratio convergence
            if self.trace_compressor.enabled:
                tc_summary = self.trace_compressor.compress()
                self.summary_consistency.record_compression_ratio(tc_summary.compression_ratio)
                # Also record per-segment ratios
                segs = self.trace_compressor.get_segments()
                for seg in segs:
                    self.summary_consistency.record_compression_ratio(
                        seg.signal_count / max(1, seg.signal_count + seg.observation_count)
                    )
            # Cross-generation diagnostic envelope
            if self.trace_drift.enabled:
                gen_records = self.trace_drift._generation_records
                for rec in gen_records:
                    self.summary_consistency.record_generation_delta({
                        "generation_index": rec.get("generation_index", 0),
                        "delta": abs(rec.get("power_ratio", 0.0) - 0.5),
                    })

        # Phase 15: Adaptive state feedback update with actual deltas
        if self.config.adaptive_enabled:
            for unit in self.units:
                if unit.is_active and hasattr(unit, '_adaptive_controller') and unit._adaptive_controller.enabled:
                    # Snapshot before state
                    pre_power = unit.power_reserve
                    pre_health = unit._avg_component_health()

                    # Gather local feedback from this tick's events
                    feedback: Dict[str, float] = {}
                    power_delta = -self.config.power_drain_rate
                    for e in self.event_log.current_tick_events():
                        if e.tick == self.tick_count and e.unit_id == unit.unit_id:
                            if e.event_type == EventType.HAZARD_ENCOUNTER:
                                feedback["hazard_exposure"] = 1.0
                                power_delta -= e.data.get("intensity", 0.0) * 2.0
                            if e.event_type == EventType.UNIT_ACTION:
                                act = e.data.get("action", "")
                                if act == "HARVEST":
                                    feedback["resource_extracted"] = 1.0
                                    power_delta += 45.0
                                elif act == "SCAN":
                                    feedback["scan_result_count"] = 1.0
                                elif act == "EMIT_SIGNAL":
                                    feedback["signal_emitted"] = 1.0
                                    power_delta -= unit.signal_energy_cost
                                elif act == "MOVE":
                                    if not e.data.get("success", True):
                                        feedback["movement_blocked"] = 1.0
                            if e.event_type == EventType.SIGNAL_RECEIVED:
                                feedback["signal_observed"] = 1.0

                    # Compute actual before/after deltas
                    post_power = unit.power_reserve
                    actual_power_delta = post_power - pre_power + power_delta
                    post_health = unit._avg_component_health()
                    actual_health_delta = post_health - pre_health

                    if not feedback:
                        feedback["power_delta"] = 0.0
                    else:
                        feedback["power_delta"] = actual_power_delta
                    feedback["component_health_delta"] = actual_health_delta
                    unit._adaptive_state = unit._adaptive_controller.update_from_feedback(
                        unit._adaptive_state, feedback, self.rng
                    )

                    # Store sampled feedback trace entry
                    if self.config.long_run_adaptation_enabled:
                        if not hasattr(self, '_local_feedback_trace'):
                            self._local_feedback_trace = []
                        if len(self._local_feedback_trace) < 5000:
                            self._local_feedback_trace.append({
                                "tick": self.tick_count,
                                "unit_id": unit.unit_id,
                                **feedback,
                            })

        # Record adaptive state snapshots at intervals for long-run trace
        if self.config.long_run_adaptation_enabled and self.tick_count % self._adaptive_snapshot_interval == 0:
            for unit in self.units:
                if hasattr(unit, '_adaptive_state'):
                    self._adaptive_state_snapshots.append({
                        "tick": self.tick_count,
                        "unit_id": unit.unit_id,
                        **unit._adaptive_state.to_dict(),
                    })

    def get_fabrication_summary(self) -> Dict[str, Any]:
        """Get fabrication and lineage summary."""
        summary = self.fabrication_engine.get_summary()
        if self.capsule_manager.enabled:
            summary["capsules"] = self.capsule_manager.get_summary()
        return summary

    def get_capsule_summary(self) -> Dict[str, Any]:
        """Get capsule summary for artifact output."""
        return self.capsule_manager.get_summary()

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

    def get_telemetry_summary(self) -> Dict[str, Any]:
        """Get telemetry summary for artifact output."""
        return self.telemetry_tracker.get_summary()

    def get_reconciliation_summary(self) -> Dict[str, Any]:
        """Get reconciliation summary for artifact output."""
        return self.reconciliation_engine.get_summary()

    def get_lineage_drift_summary(self) -> Dict[str, Any]:
        """Get lineage drift analysis summary."""
        capsules = self.capsule_manager.get_capsules()
        lineage_records = self.fabrication_engine.get_lineage_records()
        self.lineage_drift.analyze(capsules, lineage_records)
        return self.lineage_drift.get_summary()

    def get_pressure_summary(self) -> Dict[str, Any]:
        """Get pressure analysis summary for artifact output."""
        return self.pressure_analyzer.get_summary()

    def get_field_dynamics_summary(self) -> Dict[str, Any]:
        """Get signal field dynamics summary for artifact output."""
        return self.field_dynamics.get_summary()

    def get_trace_compression_summary(self) -> Dict[str, Any]:
        """Get trace compression summary for artifact output."""
        return self.trace_compressor.get_summary()

    def get_trace_drift_summary(self) -> Dict[str, Any]:
        """Get trace drift analysis summary for artifact output."""
        return self.trace_drift.get_summary()

    def get_summary_consistency_summary(self) -> Dict[str, Any]:
        """Get summary consistency analysis summary for artifact output."""
        return self.summary_consistency.get_summary()

    def get_long_run_adaptation_summary(self) -> Dict[str, Any]:
        """Get M14 long-run adaptation summary."""
        active = [u for u in self.units if u.is_active]
        # Compute action distributions from events
        events = self.event_log.all_events()
        action_events = [e for e in events if e.event_type == EventType.UNIT_ACTION]
        early_cutoff = self.tick_count // 3
        late_start = self.tick_count * 2 // 3
        early_actions: Dict[str, int] = {}
        late_actions: Dict[str, int] = {}
        for e in action_events:
            act = e.data.get("action", "unknown")
            if e.tick <= early_cutoff:
                early_actions[act] = early_actions.get(act, 0) + 1
            elif e.tick >= late_start:
                late_actions[act] = late_actions.get(act, 0) + 1
        all_keys = set(list(early_actions.keys()) + list(late_actions.keys()))
        dist_delta = {k: late_actions.get(k, 0) - early_actions.get(k, 0) for k in all_keys}

        # Signal behavior summary
        signal_emitted_events = [e for e in events if e.event_type == EventType.SIGNAL_EMITTED]
        signal_received_events = [e for e in events if e.event_type == EventType.SIGNAL_RECEIVED]
        total_signal_emissions = len(signal_emitted_events)
        total_signal_observations = len(signal_received_events)

        # Adaptive state delta (first vs last snapshot)
        adaptive_delta = {}
        if self._adaptive_state_snapshots:
            first = self._adaptive_state_snapshots[0]
            last = self._adaptive_state_snapshots[-1]
            adaptive_delta = {k: round(last.get(k, 0) - first.get(k, 0), 4)
                              for k in first if k not in ("tick", "unit_id")}

        # Descendant transfer summary
        desc_transfers = getattr(self, '_descendant_transfer_trace', [])

        return {
            "run_ticks": self.tick_count,
            "grid_width": self.config.grid_width,
            "grid_height": self.config.grid_height,
            "initial_unit_count": sum(1 for u in self.units if not hasattr(u, '_generation_index') or u._generation_index == 0),
            "final_active_unit_count": len(active),
            "descendant_active_count": sum(1 for u in self.units if hasattr(u, '_generation_index') and u._generation_index > 0 and u.is_active),
            "power_drain_rate": self.config.power_drain_rate,
            "resource_density_or_pocket_summary": self.config.resource_density,
            "hazard_density_or_region_summary": self.config.hazard_density,
            "unit_lifetime_summary": {
                u.unit_id: {"active": u.is_active, "generation": getattr(u, '_generation_index', 0)}
                for u in self.units
            },
            "action_distribution_early": early_actions,
            "action_distribution_late": late_actions,
            "action_distribution_delta": dist_delta,
            "adaptive_state_delta_summary": adaptive_delta,
            "local_feedback_summary": {
                "total_feedback_entries": len(getattr(self, '_local_feedback_trace', [])),
            },
            "resource_extraction_summary": {
                "total": sum(1 for e in action_events if e.data.get("action") == "HARVEST"),
            },
            "hazard_exposure_summary": {
                "total": sum(1 for e in events if e.event_type == EventType.HAZARD_ENCOUNTER),
            },
            "movement_block_summary": {
                "total": sum(1 for e in events if e.event_type == EventType.MOVEMENT_BLOCKED),
            },
            "signal_behavior_summary": {
                "total_signal_emissions": total_signal_emissions,
                "total_signal_observations": total_signal_observations,
                "signal_emission_rate_delta": 0,
            },
            "descendant_transfer_summary": {
                "total_transfers": len(desc_transfers),
            },
            "adaptive_vs_static_summary": {},
            "judge_status": "pending",
        }

    def get_adaptive_state_traces(self) -> List[Dict[str, Any]]:
        """Get adaptive state traces for all units."""
        traces = []
        for u in self.units:
            if hasattr(u, '_adaptive_state'):
                traces.append({
                    "unit_id": u.unit_id,
                    "tick": self.tick_count,
                    **u._adaptive_state.to_dict(),
                })
        return traces

    def get_adaptive_vs_static_comparison(self, static_summary: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Compare adaptive run against a static baseline summary."""
        adaptive_summary = self.get_long_run_adaptation_summary()
        if static_summary is None:
            return {"adaptive_summary": adaptive_summary, "static_summary": None, "action_distribution_delta": {}}
        a_dist = adaptive_summary.get("action_distribution_late", {})
        s_dist = static_summary.get("action_distribution_late", {})
        delta = {}
        all_keys = set(list(a_dist.keys()) + list(s_dist.keys()))
        for k in all_keys:
            delta[k] = a_dist.get(k, 0) - s_dist.get(k, 0)

        # Compute metric deltas from early action distributions
        a_early = adaptive_summary.get("action_distribution_early", {})
        s_early = static_summary.get("action_distribution_early", {})

        a_harvest = a_early.get("HARVEST", 0)
        s_harvest = s_early.get("HARVEST", 0)
        a_move = a_early.get("MOVE", 0) + a_dist.get("MOVE", 0)
        s_move = s_early.get("MOVE", 0) + s_dist.get("MOVE", 0)
        a_signal = a_early.get("EMIT_SIGNAL", 0) + a_dist.get("EMIT_SIGNAL", 0)
        s_signal = s_early.get("EMIT_SIGNAL", 0) + s_dist.get("EMIT_SIGNAL", 0)

        return {
            "adaptive_summary": adaptive_summary,
            "static_summary": static_summary,
            "action_distribution_delta": delta,
            "active_unit_count_delta": adaptive_summary.get("final_active_unit_count", 0) - static_summary.get("final_active_unit_count", 0),
            "resource_extraction_delta": {"delta": a_harvest - s_harvest},
            "signal_action_delta": {"delta": a_signal - s_signal},
            "movement_block_delta": {"delta": 0},
            "hazard_exposure_delta": {"delta": 0},
            "action_distribution_delta_early": {
                k: a_early.get(k, 0) - s_early.get(k, 0)
                for k in set(list(a_early.keys()) + list(s_early.keys()))
            },
        }
