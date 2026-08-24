"""Core tick-based simulation engine."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from machine_sim.agents.base import ActionType, MachineUnit
from machine_sim.agents.design_program import OPCODE_NAMES
from machine_sim.agents.neural_controller import stable_seed
from machine_sim.analysis.correlation import SignalCorrelator
from machine_sim.analysis.field_dynamics import SignalFieldDynamics
from machine_sim.analysis.pressure import PressureAnalyzer
from machine_sim.analysis.telemetry import LineageDriftAnalyzer, ReconciliationEngine, TelemetryTracker
from machine_sim.analysis.trace_compression import TraceCompressor
from machine_sim.analysis.trace_drift import TraceDriftAnalyzer
from machine_sim.analysis.summary_consistency import SummaryConsistencyAnalyzer
from machine_sim.analysis.multi_generation_trace import MultiGenerationTraceAnalyzer
from machine_sim.environment.calibration import CapsuleManager
from machine_sim.environment.fabrication import (
    FabricationEngine,
    FabricationResult,
    PendingFabrication,
)
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

# M23 construction phases, mirrored from program_construction for services use.
_PHASE_IDLE = "idle"
_PHASE_COPYING = "copying"
_PHASE_READY = "ready"


class _UnitConstructionServices:
    """Engine-provided services behind the M23 runtime construction executor.

    The executor decides WHEN construction instructions run; this class
    performs shared-world arbitration, physical cost consumption, successor
    assembly, and M22A transactional success finalization.
    """

    def __init__(self, engine: Any, unit: Any, state: Any) -> None:
        self.engine = engine
        self.unit = unit
        self.state = state

    def charge_runtime_instruction(self) -> None:
        amount = self.engine.config.runtime_instruction_power_cost
        self.unit.power_reserve = max(0.0, self.unit.power_reserve - amount)
        self.state.accumulated_copy_cost += amount

    def charge_copy_record(self) -> None:
        amount = self.engine.config.copy_record_power_cost
        self.unit.power_reserve = max(0.0, self.unit.power_reserve - amount)
        self.state.accumulated_copy_cost += amount

    def _consume_local_material(self) -> bool:
        world = self.engine.world
        cell = world.grid.get(self.unit.position)
        remaining = self.engine.config.fabrication_material_cost
        if not cell or sum(r.quantity for r in cell.resources.values()) < remaining:
            return False
        for res in cell.resources.values():
            if remaining <= 0:
                break
            if res.quantity >= remaining:
                res.quantity -= remaining
                remaining = 0.0
            else:
                remaining -= res.quantity
                res.quantity = 0
        return True

    def begin_unit_construction(self, current_tick: int) -> bool:
        engine = self.engine
        unit = self.unit
        state = self.state
        cfg = engine.config

        # Physical prerequisites only: ability to pay, local material,
        # placement availability, finite capacity. No cooldown timer and no
        # legacy eligibility ratio gates in unit-executed mode.
        if len(engine.units) >= cfg.unit_capacity:
            return False
        if unit.power_reserve < cfg.fabrication_power_cost:
            return False
        if not self._consume_local_material():
            return False
        owner_key = f"{unit.unit_id}:{state.construction_cycle_index + 1}"
        placement = engine.world.reserve_placement(unit.position, owner_key)
        if placement is None:
            return False

        # Base construction power/material consumed exactly once at BEGIN.
        unit.power_reserve = max(
            0.0, unit.power_reserve - cfg.fabrication_power_cost
        )

        fabricator = engine.fabrication_engine
        fabricator._next_unit_id += 1
        provisional_id = f"unit-{fabricator._next_unit_id:04d}"

        state.construction_cycle_index += 1
        state.source_program_digest_at_begin = (
            unit._design_program.program_digest()
        )
        state.source_cursor = 0
        state.target_copy_buffer = []
        state.reserved_target_position = placement
        state.provisional_successor_id = provisional_id
        state.cycle_start_tick = current_tick
        state.last_construction_fault = None
        state.construction_phase = _PHASE_COPYING
        # Dedicated per-cycle copy RNG seeded from stable machine-native
        # inputs; the Random object itself is preserved as future-causal RNG
        # state through checkpoints.
        if state.copy_rng is not None:
            state.copy_rng.seed(
                stable_seed(
                    "construction_copy_cycle",
                    int(cfg.seed),
                    unit.unit_id,
                    state.construction_cycle_index,
                    state.source_program_digest_at_begin,
                )
            )
        return True

    def commit_unit_construction(self) -> Dict[str, Any]:
        import random as _random

        from machine_sim.agents.design_program import (
            DesignExecutionBounds,
            DesignProgramInterpreter,
            InstructionRecord,
        )
        from machine_sim.agents.neural_architecture import resize_state_for_successor
        from machine_sim.agents.unit import MachineUnitImpl

        engine = self.engine
        unit = self.unit
        state = self.state
        cfg = engine.config
        owner_key = f"{unit.unit_id}:{state.construction_cycle_index}"
        reserved_position = state.reserved_target_position

        def fail(fault: str) -> Dict[str, Any]:
            engine.world.release_reservation(reserved_position, owner_key)
            engine._construction_cycle_trace.append({
                "tick": engine.tick_count,
                "unit_id": unit.unit_id,
                "construction_cycle_index": state.construction_cycle_index,
                "cycle_start_tick": state.cycle_start_tick,
                "cycle_end_tick": engine.tick_count,
                "status": f"failed:{fault}",
                "copied_records": state.copied_record_count,
            })
            engine._record_event(Event(
                tick=engine.tick_count,
                event_type=EventType.CONSTRUCTION_FAILED,
                unit_id=unit.unit_id,
                data={"cause": fault,
                      "construction_cycle_index": state.construction_cycle_index},
            ))
            return {"status": "failed", "fault": fault}

        # Reservation must still belong to this cycle.
        if engine.world.reserved_cells.get(reserved_position or (-1, -1)) != owner_key:
            return fail("reservation_invalidated")
        if not unit.is_active:
            return fail("source_inactive")

        target_instructions = [
            InstructionRecord.from_pair(pair) for pair in state.target_copy_buffer
        ]
        if not (cfg.program_min_length <= len(target_instructions) <= cfg.program_max_length):
            return fail("copied_length_out_of_bounds")
        target_program = type(unit._design_program)(
            schema_version=unit._design_program.schema_version,
            instruction_set_version=unit._design_program.instruction_set_version,
            instructions=target_instructions,
        )

        dev_bounds = DesignExecutionBounds(
            minimum_hidden_size=cfg.minimum_hidden_size,
            maximum_hidden_size=cfg.maximum_hidden_size,
            initial_hidden_size=cfg.initial_hidden_size,
            minimum_recurrence_density=cfg.minimum_recurrent_density,
            maximum_recurrence_density=cfg.maximum_recurrent_density,
            initial_recurrence_density=cfg.initial_recurrent_density,
            minimum_plasticity_rate=cfg.minimum_plasticity_rate,
            maximum_plasticity_rate=cfg.maximum_plasticity_rate,
            initial_plasticity_rate=cfg.neural_plasticity_rate,
            program_base_cost=cfg.program_base_cost,
            program_per_instruction_cost=cfg.program_per_instruction_cost,
        )
        decode_result = DesignProgramInterpreter(dev_bounds).execute(
            target_program,
            program_length_bounds=(cfg.program_min_length, cfg.program_max_length),
        )
        decoded = decode_result.decoded_architecture
        if decoded is None:
            return fail("copied_program_decode_failed")

        template = engine.fabrication_engine._create_template(unit, engine.rng)
        source_desc = getattr(unit, "_architecture_descriptor", None)
        successor = MachineUnitImpl(
            unit_id=state.provisional_successor_id,
            position=reserved_position,
            signal_enabled=getattr(unit, "signal_enabled", False),
            signal_pattern_count=getattr(unit, "signal_pattern_count", 3),
            signal_energy_cost=getattr(unit, "signal_energy_cost", 2.0),
            signal_default_radius=getattr(unit, "signal_default_radius", 3),
            signal_default_decay=getattr(unit, "signal_default_decay", 0.1),
            signal_default_duration=getattr(unit, "signal_default_duration", 10),
            adaptive_enabled=bool(getattr(unit, "adaptive_enabled", False)),
            neural_controller_enabled=cfg.neural_controller_enabled,
            neural_controller_mode=cfg.neural_controller_mode,
            neural_plasticity_enabled=cfg.neural_plasticity_enabled,
            neural_hidden_size=cfg.neural_hidden_size,
            neural_plasticity_rate=cfg.neural_plasticity_rate,
            neural_seed=cfg.seed,
            design_program=target_program,
            unit_executed_construction_enabled=True,
        )
        successor.max_power = template.max_power
        successor.power_reserve = template.max_power
        successor.SENSOR_RANGE = template.sensor_range
        successor._generation_index = getattr(unit, "_generation_index", 0) + 1
        if cfg.component_degradation_scale != 1.0:
            for comp in successor.components.values():
                comp.degradation_rate *= cfg.component_degradation_scale

        # Existing M19 dimension-aware neural-state transfer from the decoded
        # successor architecture.
        if (cfg.neural_controller_enabled
                and getattr(unit, "_neural_controller", None) is not None
                and successor._neural_controller is not None):
            nc_rng = _random.Random(
                engine.tick_count * 17 + stable_seed("m23_transfer", unit.unit_id)
            )
            src_state = unit._neural_controller.state
            new_h, new_w_in, new_w_rec, new_w_out, new_w_param, new_b, new_mask, _retained = \
                resize_state_for_successor(
                    src_state.hidden_state, src_state.W_in, src_state.W_rec,
                    src_state.W_out, src_state.W_param, src_state.b_hidden,
                    src_state.recurrent_mask, decoded, source_desc, nc_rng,
                    weight_bound=2.0,
                )
            from machine_sim.agents.neural_controller import NeuralProcessingState

            successor._neural_controller.set_state(NeuralProcessingState(
                hidden_state=new_h, W_in=new_w_in, W_rec=new_w_rec,
                W_out=new_w_out, W_param=new_w_param, b_hidden=new_b,
                c_action=list(src_state.c_action), c_param=list(src_state.c_param),
                recurrent_mask=new_mask,
            ))

        # Occupy the reserved target cell and register the assembled unit.
        engine.world.grid[reserved_position].unit_id = successor.unit_id
        successor.position = reserved_position
        engine.register_unit(successor)
        engine.world.release_reservation(reserved_position, owner_key)

        # M22A transactional success finalization: exactly one lineage record,
        # one success increment, one successful-fabrication tick.
        from machine_sim.environment.fabrication import PendingFabrication

        pending = PendingFabrication(
            success=True,
            source_unit=unit,
            source_id=unit.unit_id,
            successor_id=successor.unit_id,
            placement=reserved_position,
            template=template,
            fabrication_tick=engine.tick_count,
            material_cost=cfg.fabrication_material_cost,
            power_cost=cfg.fabrication_power_cost,
            source_generation=getattr(unit, "_generation_index", 0),
        )
        engine.fabrication_engine.commit_fabrication(pending)

        engine._construction_cycle_trace.append({
            "tick": engine.tick_count,
            "unit_id": unit.unit_id,
            "construction_cycle_index": state.construction_cycle_index,
            "cycle_start_tick": state.cycle_start_tick,
            "cycle_end_tick": engine.tick_count,
            "status": "complete",
            "successor_unit_id": successor.unit_id,
            "successor_program_digest": target_program.program_digest(),
            "copied_records": len(target_instructions),
        })

        engine._record_event(Event(
            tick=engine.tick_count,
            event_type=EventType.CONSTRUCTION_SUCCEEDED,
            unit_id=unit.unit_id,
            data={
                "successor_id": successor.unit_id,
                "construction_cycle_index": state.construction_cycle_index,
                "copied_program_digest": target_program.program_digest(),
                "source_program_digest": state.source_program_digest_at_begin,
                "copy_error_count": state.copy_error_count,
            },
        ))
        return {
            "status": "complete",
            "successor_unit_id": successor.unit_id,
            "successor_program_digest": target_program.program_digest(),
            "fault": None,
        }





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
        # Neural controller trace storage
        self._neural_state_trace: List[Dict[str, Any]] = []
        self._neural_action_trace: List[Dict[str, Any]] = []
        self._neural_plasticity_trace: List[Dict[str, Any]] = []
        self._neural_successor_transfer_trace: List[Dict[str, Any]] = []
        self._neural_snapshot_interval = max(1, config.max_ticks // 10)
        # M19: Architecture variation trace storage
        self._architecture_transfer_trace: List[Dict[str, Any]] = []
        self._architecture_distribution_trace: List[Dict[str, Any]] = []
        self._architecture_cost_trace: List[Dict[str, Any]] = []
        self._architecture_initial_descriptors: List[Dict[str, Any]] = []
        self._total_processing_cost: float = 0.0
        self._total_fabrication_cost: float = 0.0
        self._architecture_dist_snapshot_interval = max(1, config.max_ticks // 20)
        # M22: design-program trace storage (output-only) and cost accumulator
        self._design_program_transfer_trace: List[Dict[str, Any]] = []
        self._design_program_execution_trace: List[Dict[str, Any]] = []
        self._design_program_distribution_trace: List[Dict[str, Any]] = []
        self._design_program_dist_snapshot_interval = max(1, config.max_ticks // 20)
        # M23 output-only construction/copy trace storage
        self._construction_runtime_trace: List[Dict[str, Any]] = []
        self._program_copy_trace: List[Dict[str, Any]] = []
        self._construction_cycle_trace: List[Dict[str, Any]] = []
        self._total_program_execution_cost: float = 0.0
        # M20: per-tick digest chain value, advanced by the run controller and
        # carried through checkpoint capture so a resumed run continues the
        # same chain.
        self.run_digest_value: str = ""
        # M21 benchmark counters: observation-only, never read by the tick loop.
        self.bench_unit_decisions = 0

    def register_unit(self, unit: MachineUnit) -> None:
        self.units.append(unit)
        # M19: Record initial architecture descriptor
        if (self.config.neural_architecture_variation_enabled
                and hasattr(unit, '_architecture_descriptor')
                and unit._architecture_descriptor is not None):
            self._architecture_initial_descriptors.append(
                unit._architecture_descriptor.to_dict())

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

    # Validated event labels cache: identical strings to
    # event_type.name.lower(), validated against the allowlist once per type.
    _validated_event_labels: Dict[EventType, str] = {}

    def _record_event(self, event: Event) -> None:
        label = self._validated_event_labels.get(event.event_type)
        if label is None:
            label = event.event_type.name.lower()
            validate_event_label(label)
            self._validated_event_labels[event.event_type] = label
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
                readings = self.world.sense_tail(
                    unit.position,
                    unit.sensor_range,
                    exclude_unit_id=unit.unit_id,
                    tail=unit.sensor_readings.maxlen
                    if unit.sensor_readings.maxlen is not None
                    else 10,
                )
                unit.receive_observations(readings, self.tick_count)

        # Phase 3: Unit decision + action
        for unit in self.units:
            if unit.is_active:
                self.bench_unit_decisions += 1
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
                nearby_count, spatial_pressure = self.world.scan_neighbors(
                    unit.position, unit.sensor_range
                )
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
                validate_agent_state(unit.validation_view())

        # Phase 7: Construction
        #
        # M23 mode: successor construction arises ONLY from execution of each
        # unit's inherited runtime construction program. The engine services
        # reservations, shared-world arbitration, and transactional commits —
        # it never initiates construction merely because a unit is eligible.
        if self.config.unit_executed_construction_enabled:
            self._step_unit_executed_construction()
        elif self.config.fabrication_enabled:
            new_units = []
            for unit in self.units:
                if unit.is_active:
                    # M22A: program-enabled units use the two-phase boundary.
                    # prepare_fabricate counts the attempt and consumes base
                    # costs / reserves placement + ID, but commits none of the
                    # success-only state; commit_fabrication runs only after a
                    # successor has actually been assembled. Legacy units keep
                    # the single-call path (prepare + immediate commit).
                    unit_program_mode = (
                        getattr(self.config, 'design_program_enabled', False)
                        and getattr(unit, '_design_program', None) is not None
                        and self.config.fabrication_enabled
                    )
                    if unit_program_mode:
                        prepared = self.fabrication_engine.prepare_fabricate(
                            unit, self.tick_count, self.world,
                            len(self.units) + len(new_units), self.rng
                        )
                    else:
                        prepared = self.fabrication_engine.fabricate(
                            unit, self.tick_count, self.world,
                            len(self.units) + len(new_units), self.rng
                        )

                    failure_result = None
                    pending = None
                    if isinstance(prepared, PendingFabrication):
                        pending = prepared
                    else:
                        failure_result = prepared

                    result = pending.to_result() if pending is not None else failure_result

                    if not (result.success and result.template and result.placement):
                        if failure_result.failure_cause:
                            self._record_event(Event(
                                tick=self.tick_count,
                                event_type=EventType.FABRICATION_FAILED,
                                unit_id=unit.unit_id,
                                data={"cause": failure_result.failure_cause},
                            ))
                        continue

                    # M22: in program mode the successor's design program
                    # is transferred, varied, and interpreted BEFORE assembly
                    # is committed. A program that does not decode aborts
                    # assembly with machine-native consequences: costs already
                    # consumed stay consumed, no successor is created, no
                    # success-only state is committed, and the attempt plus a
                    # deterministic failure cause are recorded.
                    program_mode = unit_program_mode
                    successor_program = None
                    decoded_successor_arch = None
                    program_execution_bounds = None

                    if program_mode:
                        from machine_sim.agents.design_program import (
                            DesignExecutionBounds,
                            DesignProgramInterpreter,
                            DesignProgramVariationBounds,
                            vary_design_program,
                        )
                        from machine_sim.agents.neural_architecture import (
                            NeuralArchitectureConfig as _ProgramArchCfg,
                        )
                        import random as _prog_rng

                        arch_cfg_for_bounds = _ProgramArchCfg(
                            minimum_hidden_size=self.config.minimum_hidden_size,
                            maximum_hidden_size=self.config.maximum_hidden_size,
                            minimum_recurrent_density=self.config.minimum_recurrent_density,
                            maximum_recurrent_density=self.config.maximum_recurrent_density,
                            minimum_plasticity_rate=self.config.minimum_plasticity_rate,
                            maximum_plasticity_rate=self.config.maximum_plasticity_rate,
                            initial_plasticity_rate=self.config.neural_plasticity_rate,
                        )
                        program_execution_bounds = DesignExecutionBounds.from_architecture_config(
                            arch_cfg_for_bounds,
                            execution_budget=self.config.program_execution_budget,
                            program_base_cost=self.config.program_base_cost,
                            program_per_instruction_cost=self.config.program_per_instruction_cost,
                        )
                        variation_bounds = DesignProgramVariationBounds(
                            substitution_probability=self.config.program_substitution_probability,
                            operand_mutation_probability=self.config.program_operand_mutation_probability,
                            insertion_probability=self.config.program_insertion_probability,
                            deletion_probability=self.config.program_deletion_probability,
                            minimum_program_length=self.config.program_min_length,
                            maximum_program_length=self.config.program_max_length,
                        )
                        prog_rng = _prog_rng.Random(
                            self.tick_count * 11
                            + stable_seed("design_program_transfer", unit.unit_id)
                        )
                        variation_outcome = vary_design_program(
                            unit._design_program, prog_rng,
                            program_execution_bounds, variation_bounds,
                        )
                        execution_result = DesignProgramInterpreter(
                            program_execution_bounds
                        ).execute(
                            variation_outcome.program,
                            program_length_bounds=(
                                self.config.program_min_length,
                                self.config.program_max_length,
                            ),
                        )
                        successor_program = variation_outcome.program
                        decoded_successor_arch = execution_result.decoded_architecture
                        source_desc = getattr(unit, '_architecture_descriptor', None)
                        if decoded_successor_arch is not None and source_desc is not None:
                            phenotype_changed = (
                                decoded_successor_arch.hidden_size != source_desc.hidden_size
                                or round(decoded_successor_arch.recurrent_density, 9)
                                != round(source_desc.recurrent_density, 9)
                                or round(decoded_successor_arch.plasticity_rate, 9)
                                != round(source_desc.plasticity_rate, 9)
                                or decoded_successor_arch.plasticity_enabled
                                != source_desc.plasticity_enabled
                            )
                        else:
                            phenotype_changed = True
                        self._design_program_transfer_trace.append({
                            "tick": self.tick_count,
                            "source_unit_id": unit.unit_id,
                            # Provisional candidate ID (documented option
                            # A): reserved during the attempt and bound to
                            # the assembled successor on commit; a failed
                            # assembly leaves this ID unused and absent
                            # from every lineage record.
                            "successor_unit_id": result.successor_id,
                            "successor_id_provisional": True,
                            "source_generation": getattr(unit, '_generation_index', 0),
                            "source_program_digest": unit._design_program.program_digest(),
                            "source_program_length": unit._design_program.length,
                            "successor_program_digest": successor_program.program_digest(),
                            "successor_program_length": successor_program.length,
                            "variation_operations": variation_outcome.operations[:32],
                            "variation_operation_count": len(variation_outcome.operations),
                            "execution_status": execution_result.status,
                            "executed_instruction_count": execution_result.executed_instruction_count,
                            "execution_cost": round(execution_result.execution_cost, 6),
                            "decoded_hidden_size": (
                                decoded_successor_arch.hidden_size
                                if decoded_successor_arch is not None else None
                            ),
                            "decoded_recurrent_density": (
                                round(decoded_successor_arch.recurrent_density, 6)
                                if decoded_successor_arch is not None else None
                            ),
                            "decoded_plasticity_rate": (
                                round(decoded_successor_arch.plasticity_rate, 6)
                                if decoded_successor_arch is not None else None
                            ),
                            "decoded_plasticity_enabled": (
                                decoded_successor_arch.plasticity_enabled
                                if decoded_successor_arch is not None else None
                            ),
                            "phenotype_changed": phenotype_changed,
                        })
                        self._design_program_execution_trace.append({
                            "tick": self.tick_count,
                            "unit_id": result.successor_id,
                            "status": execution_result.status,
                            "executed_instruction_count": execution_result.executed_instruction_count,
                            "final_program_counter": execution_result.final_program_counter,
                            "execution_cost": round(execution_result.execution_cost, 6),
                            "fault_records": execution_result.fault_records[:16],
                        })
                        unit.power_reserve = max(
                            0.0,
                            unit.power_reserve - execution_result.execution_cost,
                        )
                        self._total_program_execution_cost += execution_result.execution_cost
                        if decoded_successor_arch is None:
                            from machine_sim.environment.fabrication import (
                                record_program_failure,
                            )
                            record_program_failure(
                                self.fabrication_engine,
                                "successor_program_invalid",
                            )
                            self._record_event(Event(
                                tick=self.tick_count,
                                event_type=EventType.FABRICATION_FAILED,
                                unit_id=unit.unit_id,
                                data={
                                    "cause": "successor_program_invalid",
                                    "execution_status": execution_result.status,
                                    "program_digest": successor_program.program_digest(),
                                    "provisional_successor_id": result.successor_id,
                                },
                            ))
                            continue

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
                        neural_controller_enabled=self.config.neural_controller_enabled,
                        neural_controller_mode=self.config.neural_controller_mode,
                        neural_plasticity_enabled=self.config.neural_plasticity_enabled,
                        neural_hidden_size=self.config.neural_hidden_size,
                        neural_plasticity_rate=self.config.neural_plasticity_rate,
                        neural_seed=self.config.seed,
                        neural_architecture_descriptor=(
                            decoded_successor_arch if program_mode else None
                        ),
                        design_program=successor_program,
                        design_execution_bounds=program_execution_bounds,
                        design_program_length_bounds=(
                            (self.config.program_min_length, self.config.program_max_length)
                            if program_mode else None
                        ),
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

                    # Transfer neural controller state from source to successor
                    if (self.config.neural_controller_enabled
                            and hasattr(unit, '_neural_controller')
                            and unit._neural_controller is not None
                            and hasattr(successor, '_neural_controller')
                            and successor._neural_controller is not None):
                        import random as _nc_rng
                        nc_rng = _nc_rng.Random(self.tick_count * 7 + stable_seed("nc_transfer", unit.unit_id))

                        # M19: Architecture variation. In M22 program mode
                        # the successor architecture comes from its decoded
                        # program, so descriptor variation is not applied
                        # to the same successor (no double mutation).
                        arch_variation_enabled = (
                            self.config.neural_architecture_variation_enabled
                            and not program_mode
                        )
                        source_arch = getattr(unit, '_architecture_descriptor', None)
                        successor_arch = None
                        transition_record = None

                        if arch_variation_enabled and source_arch is not None:
                            from machine_sim.agents.neural_architecture import (
                                vary_architecture, NeuralArchitectureConfig,
                                resize_state_for_successor, compute_recurrence_mask,
                                compute_processing_cost, compute_fabrication_cost,
                                NeuralArchitectureTransition,
                            )
                            arch_cfg = NeuralArchitectureConfig(
                                minimum_hidden_size=self.config.minimum_hidden_size,
                                maximum_hidden_size=self.config.maximum_hidden_size,
                                minimum_recurrent_density=self.config.minimum_recurrent_density,
                                maximum_recurrent_density=self.config.maximum_recurrent_density,
                                minimum_plasticity_rate=self.config.minimum_plasticity_rate,
                                maximum_plasticity_rate=self.config.maximum_plasticity_rate,
                                hidden_size_variation_probability=self.config.hidden_size_variation_probability,
                                hidden_size_variation_max_step=self.config.hidden_size_variation_max_step,
                                recurrent_density_variation_probability=self.config.recurrent_density_variation_probability,
                                recurrent_density_variation_max_step=self.config.recurrent_density_variation_max_step,
                                plasticity_rate_variation_probability=self.config.plasticity_rate_variation_probability,
                                plasticity_rate_variation_max_step=self.config.plasticity_rate_variation_max_step,
                                neural_processing_base_cost=self.config.neural_processing_base_cost,
                                neural_hidden_unit_cost=self.config.neural_hidden_unit_cost,
                                neural_recurrent_connection_cost=self.config.neural_recurrent_connection_cost,
                                neural_plastic_update_cost=self.config.neural_plastic_update_cost,
                                neural_fabrication_hidden_unit_cost=self.config.neural_fabrication_hidden_unit_cost,
                                neural_fabrication_connection_cost=self.config.neural_fabrication_connection_cost,
                            )

                            successor_arch = vary_architecture(
                                source_arch, arch_cfg, nc_rng,
                                self.tick_count, index=len(self.units))

                            # Dimension-changing transfer
                            src_state = unit._neural_controller.state
                            new_h, new_W_in, new_W_rec, new_W_out, new_W_param, new_b_h, new_mask, retained = \
                                resize_state_for_successor(
                                    src_state.hidden_state, src_state.W_in, src_state.W_rec,
                                    src_state.W_out, src_state.W_param, src_state.b_hidden,
                                    src_state.recurrent_mask, successor_arch, source_arch, nc_rng,
                                    weight_bound=2.0)

                            from machine_sim.agents.neural_controller import NeuralProcessingState
                            successor_state = NeuralProcessingState(
                                hidden_state=new_h, W_in=new_W_in, W_rec=new_W_rec,
                                W_out=new_W_out, W_param=new_W_param, b_hidden=new_b_h,
                                c_action=list(src_state.c_action),
                                c_param=list(src_state.c_param),
                                recurrent_mask=new_mask,
                            )
                            successor._neural_controller.set_state(successor_state)
                            successor._architecture_descriptor = successor_arch

                            # Compute costs
                            fab_cost = compute_fabrication_cost(successor_arch, arch_cfg)
                            self._total_fabrication_cost += fab_cost

                            # Record architecture transition
                            old_active = source_arch.active_recurrent_connections()
                            new_active = successor_arch.active_recurrent_connections()
                            delta_h = successor_arch.hidden_size - source_arch.hidden_size

                            transition_record = NeuralArchitectureTransition(
                                tick=self.tick_count,
                                source_unit_id=unit.unit_id,
                                successor_unit_id=result.successor_id,
                                source_generation=getattr(unit, '_generation_index', 0),
                                successor_generation=successor._generation_index,
                                source_architecture_id=source_arch.architecture_id,
                                successor_architecture_id=successor_arch.architecture_id,
                                source_hidden_size=source_arch.hidden_size,
                                successor_hidden_size=successor_arch.hidden_size,
                                hidden_size_delta=delta_h,
                                source_recurrent_density=source_arch.recurrent_density,
                                successor_recurrent_density=successor_arch.recurrent_density,
                                recurrent_density_delta=successor_arch.recurrent_density - source_arch.recurrent_density,
                                source_plasticity_rate=source_arch.plasticity_rate,
                                successor_plasticity_rate=successor_arch.plasticity_rate,
                                plasticity_rate_delta=successor_arch.plasticity_rate - source_arch.plasticity_rate,
                                retained_hidden_count=len(retained),
                                added_hidden_count=max(0, delta_h),
                                removed_hidden_count=max(0, -delta_h),
                                active_recurrent_connection_delta=new_active - old_active,
                                processing_cost_estimate=compute_processing_cost(successor_arch, arch_cfg),
                                fabrication_complexity_cost=fab_cost,
                                variation_applied=True,
                            )
                            self._architecture_transfer_trace.append(transition_record.to_dict())
                        elif program_mode:
                            # M22: dimension-aware state transfer from the
                            # decoded successor architecture (M19 transfer
                            # semantics preserved, descriptor variation
                            # bypassed).
                            from machine_sim.agents.neural_architecture import (
                                NeuralArchitectureConfig as _ResizeArchCfg,
                                compute_fabrication_cost,
                                resize_state_for_successor,
                            )
                            src_state = unit._neural_controller.state
                            new_h, new_W_in, new_W_rec, new_W_out, new_W_param, new_b_h, new_mask, retained = \
                                resize_state_for_successor(
                                    src_state.hidden_state, src_state.W_in, src_state.W_rec,
                                    src_state.W_out, src_state.W_param, src_state.b_hidden,
                                    src_state.recurrent_mask, decoded_successor_arch, source_arch, nc_rng,
                                    weight_bound=2.0)

                            from machine_sim.agents.neural_controller import NeuralProcessingState
                            successor_state = NeuralProcessingState(
                                hidden_state=new_h, W_in=new_W_in, W_rec=new_W_rec,
                                W_out=new_W_out, W_param=new_W_param, b_hidden=new_b_h,
                                c_action=list(src_state.c_action),
                                c_param=list(src_state.c_param),
                                recurrent_mask=new_mask,
                            )
                            successor._neural_controller.set_state(successor_state)
                            successor._architecture_descriptor = decoded_successor_arch

                            resize_cfg = _ResizeArchCfg(
                                neural_fabrication_hidden_unit_cost=self.config.neural_fabrication_hidden_unit_cost,
                                neural_fabrication_connection_cost=self.config.neural_fabrication_connection_cost,
                            )
                            program_fab_cost = compute_fabrication_cost(
                                decoded_successor_arch, resize_cfg
                            )
                            unit.power_reserve = max(
                                0.0, unit.power_reserve - program_fab_cost
                            )
                            self._total_fabrication_cost += program_fab_cost
                        else:
                            # Legacy transfer (no architecture variation)
                            source_nc_state = unit._neural_controller.state.copy()
                            successor_nc_state = unit._neural_controller.transfer_to_successor(nc_rng, variation=0.05)
                            successor._neural_controller.state = successor_nc_state

                        # Record neural successor transfer trace (always)
                        source_nc = unit._neural_controller.state
                        succ_nc = successor._neural_controller.state
                        if self.config.long_run_adaptation_enabled:
                            param_delta = unit._neural_controller.get_parameter_delta(succ_nc)
                            self._neural_successor_transfer_trace.append({
                                "tick": self.tick_count,
                                "source_unit_id": unit.unit_id,
                                "successor_unit_id": result.successor_id,
                                "source_generation": getattr(unit, '_generation_index', 0),
                                "successor_generation": successor._generation_index,
                                "source_hidden_summary": {
                                    "mean": round(sum(source_nc.hidden_state) / len(source_nc.hidden_state), 6) if source_nc.hidden_state else 0.0,
                                },
                                "successor_hidden_summary": {
                                    "mean": round(sum(succ_nc.hidden_state) / len(succ_nc.hidden_state), 6) if succ_nc.hidden_state else 0.0,
                                },
                                "parameter_delta": param_delta,
                                "transfer_variation": 0.05,
                            })

                    new_units.append(successor)

                    # M22A: the successor is fully assembled and about to
                    # be registered — commit the success-only fabrication
                    # state exactly once (success counter, lineage record,
                    # source successful-fabrication tick).
                    if pending is not None:
                        self.fabrication_engine.commit_fabrication(pending)

                    # M19: Deduct architecture fabrication cost from source unit
                    if (self.config.neural_architecture_variation_enabled
                            and successor_arch is not None):
                        from machine_sim.agents.neural_architecture import compute_fabrication_cost, NeuralArchitectureConfig as _ArchCfgFab
                        arch_fab_cfg = NeuralArchitectureConfig(
                            neural_fabrication_hidden_unit_cost=self.config.neural_fabrication_hidden_unit_cost,
                            neural_fabrication_connection_cost=self.config.neural_fabrication_connection_cost,
                        )
                        arch_fab = compute_fabrication_cost(successor_arch, arch_fab_cfg)
                        unit.power_reserve = max(0.0, unit.power_reserve - arch_fab)

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
        if self.config.adaptive_enabled or self.config.neural_controller_enabled:
            # Bucket this tick's events once per unit instead of rescanning the
            # per-tick buffer for every active unit. Every buffered event
            # carries the current tick, so per-unit buckets are equivalent to
            # the previous filtered scans.
            tick_events_by_unit: Dict[Optional[str], List[Event]] = {}
            for tick_event in self.event_log._tick_events:
                tick_events_by_unit.setdefault(tick_event.unit_id, []).append(tick_event)

        if self.config.adaptive_enabled:
            for unit in self.units:
                if unit.is_active and hasattr(unit, '_adaptive_controller') and unit._adaptive_controller.enabled:
                    # Snapshot before state
                    pre_power = unit.power_reserve
                    pre_health = unit._avg_component_health()

                    # Gather local feedback from this tick's events
                    feedback: Dict[str, float] = {}
                    power_delta = -self.config.power_drain_rate
                    for e in tick_events_by_unit.get(unit.unit_id, ()):
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

        # Phase 15b: Neural controller feedback update
        if self.config.neural_controller_enabled:
            for unit in self.units:
                if (unit.is_active
                        and hasattr(unit, '_neural_controller')
                        and unit._neural_controller is not None):
                    # Gather local feedback from this tick's events
                    nc_feedback: Dict[str, float] = {}
                    nc_power_delta = -self.config.power_drain_rate
                    for e in tick_events_by_unit.get(unit.unit_id, ()):
                        if e.tick == self.tick_count and e.unit_id == unit.unit_id:
                            if e.event_type == EventType.HAZARD_ENCOUNTER:
                                nc_feedback["hazard_exposure"] = 1.0
                                nc_power_delta -= e.data.get("intensity", 0.0) * 2.0
                            if e.event_type == EventType.UNIT_ACTION:
                                act = e.data.get("action", "")
                                if act == "HARVEST":
                                    nc_feedback["resource_extracted"] = 1.0
                                    nc_power_delta += 45.0
                                elif act == "SCAN":
                                    nc_feedback["scan_result_count"] = 1.0
                                elif act == "EMIT_SIGNAL":
                                    nc_feedback["signal_emitted"] = 1.0
                                    nc_power_delta -= unit.signal_energy_cost
                                elif act == "MOVE":
                                    if not e.data.get("success", True):
                                        nc_feedback["movement_blocked"] = 1.0
                            if e.event_type == EventType.SIGNAL_RECEIVED:
                                nc_feedback["signal_observed"] = 1.0

                    post_power_nc = unit.power_reserve
                    actual_nc_power_delta = post_power_nc - unit.power_reserve + nc_power_delta
                    nc_feedback["power_delta"] = actual_nc_power_delta if nc_feedback else 0.0

                    # Build sensor input for the neural controller
                    readings = list(unit.sensor_readings)
                    has_resource = False
                    has_hazard = False
                    res_str = 0.0
                    haz_str = 0.0
                    # Single type probe: the scalar echo attributes never exist
                    # on runtime readings, exactly as with the per-element form.
                    if readings and hasattr(readings[0], 'resource_type'):
                        for r in readings:
                            if r.resource_quantity > 0:
                                has_resource = True
                                res_str = max(res_str, r.resource_quantity)
                            if r.hazard_level > 0:
                                has_hazard = True
                                haz_str = max(haz_str, r.hazard_level)

                    field_sum_nc = unit._field_tracker.get_summary(self.tick_count)
                    signal_obs = field_sum_nc.recent_signal_count > 0
                    signal_emi = field_sum_nc.total_emissions > 0
                    mov_blk = field_sum_nc.recent_movement_blocks > 0
                    scan_ct = float(field_sum_nc.total_scans)

                    sensor_input = unit._neural_controller.build_sensor_input(
                        power_ratio=unit._power_ratio(),
                        avg_component_health=unit._avg_component_health(),
                        has_resource=has_resource,
                        resource_strength=res_str,
                        has_hazard=has_hazard,
                        hazard_strength=haz_str,
                        signal_observed=signal_obs,
                        signal_emitted=signal_emi,
                        movement_blocked=mov_blk,
                        resource_extracted=nc_feedback.get("resource_extracted", 0.0) > 0,
                        scan_result_count=min(1.0, scan_ct / 5.0),
                        previous_action=unit._previous_action_name,
                        time_since_signal=0.0,
                    )

                    import random as _nc_fb_rng
                    nc_fb_rng = _nc_fb_rng.Random(self.tick_count * 13 + stable_seed("nc_feedback", unit.unit_id))
                    pre_w_out = [list(row) for row in unit._neural_controller.state.W_out]
                    unit._neural_controller.update_from_feedback(
                        sensor_input, unit._previous_action_name, nc_feedback, nc_fb_rng
                    )

                    # Record neural action trace (sampled to stay bounded)
                    if (self.config.long_run_adaptation_enabled
                            and len(self._neural_action_trace) < 45000
                            and self.tick_count % 3 == 0):
                        last_out = unit._neural_controller._last_action_output
                        if last_out:
                            self._neural_action_trace.append({
                                "tick": self.tick_count,
                                "unit_id": unit.unit_id,
                                "action": last_out.get("action_name", "unknown"),
                                "action_logits": last_out.get("action_logits", []),
                                "action_preferences": last_out.get("action_preferences", []),
                            })

                    # Record plasticity trace if parameters changed
                    if self.config.long_run_adaptation_enabled:
                        post_w_out = unit._neural_controller.state.W_out
                        w_out_delta = sum(
                            abs(post_w_out[i][j] - pre_w_out[i][j])
                            for i in range(len(post_w_out))
                            for j in range(len(post_w_out[i]))
                        )
                        if w_out_delta > 1e-8:
                            self._neural_plasticity_trace.append({
                                "tick": self.tick_count,
                                "unit_id": unit.unit_id,
                                "w_out_delta": round(w_out_delta, 8),
                                "selected_action": unit._previous_action_name,
                            })

                    # M19: Deduct architecture-dependent processing cost
                    if (self.config.neural_architecture_variation_enabled
                            and hasattr(unit, '_architecture_descriptor')
                            and unit._architecture_descriptor is not None):
                        from machine_sim.agents.neural_architecture import (
                            compute_processing_cost, NeuralArchitectureConfig,
                        )
                        arch_cfg_cost = NeuralArchitectureConfig(
                            neural_processing_base_cost=self.config.neural_processing_base_cost,
                            neural_hidden_unit_cost=self.config.neural_hidden_unit_cost,
                            neural_recurrent_connection_cost=self.config.neural_recurrent_connection_cost,
                            neural_plastic_update_cost=self.config.neural_plastic_update_cost,
                        )
                        proc_cost = compute_processing_cost(
                            unit._architecture_descriptor, arch_cfg_cost,
                            changed_parameter_count=0)
                        unit.power_reserve = max(0.0, unit.power_reserve - proc_cost)
                        self._total_processing_cost += proc_cost

                        # Record cost trace (sampled)
                        if (self.config.long_run_adaptation_enabled
                                and self.tick_count % 100 == 0
                                and len(self._architecture_cost_trace) < 5000):
                            self._architecture_cost_trace.append({
                                "tick": self.tick_count,
                                "unit_id": unit.unit_id,
                                "processing_cost": round(proc_cost, 6),
                                "hidden_size": unit._architecture_descriptor.hidden_size,
                                "recurrent_density": round(unit._architecture_descriptor.recurrent_density, 6),
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

        # Record neural state snapshots at intervals for long-run trace
        if (self.config.neural_controller_enabled
                and self.config.long_run_adaptation_enabled
                and self.tick_count % self._neural_snapshot_interval == 0):
            for unit in self.units:
                if (hasattr(unit, '_neural_controller')
                        and unit._neural_controller is not None):
                    snap = unit._neural_controller.get_state_snapshot()
                    self._neural_state_trace.append({
                        "tick": self.tick_count,
                        "unit_id": unit.unit_id,
                        **snap,
                    })

        # M19: Record architecture distribution snapshots
        if (self.config.neural_architecture_variation_enabled
                and self.config.long_run_adaptation_enabled
                and self.tick_count % self._architecture_dist_snapshot_interval == 0):
            from collections import Counter
            active_units = [u for u in self.units if u.is_active
                           and hasattr(u, '_architecture_descriptor')
                           and u._architecture_descriptor is not None]
            if active_units:
                hidden_sizes = [u._architecture_descriptor.hidden_size for u in active_units]
                densities = [u._architecture_descriptor.recurrent_density for u in active_units]
                rates = [u._architecture_descriptor.plasticity_rate for u in active_units]
                hs_hist = dict(Counter(hidden_sizes))
                d_hist = {round(k, 2): v for k, v in Counter(densities).items()}
                r_hist = {round(k, 4): v for k, v in Counter(rates).items()}
                self._architecture_distribution_trace.append({
                    "tick": self.tick_count,
                    "active_unit_count": len(active_units),
                    "distinct_architecture_count": len(set(
                        u._architecture_descriptor.architecture_id for u in active_units)),
                    "hidden_size_histogram": hs_hist,
                    "recurrent_density_histogram": d_hist,
                    "plasticity_rate_histogram": r_hist,
                    "mean_hidden_size": round(sum(hidden_sizes) / len(hidden_sizes), 2),
                    "mean_recurrent_density": round(sum(densities) / len(densities), 4),
                })

        # M22: Record design-program distribution snapshots (output-only)
        if (getattr(self.config, 'design_program_enabled', False)
                and self.tick_count % self._design_program_dist_snapshot_interval == 0):
            from collections import Counter
            program_units = [u for u in self.units
                             if getattr(u, '_design_program', None) is not None]
            if program_units:
                lengths = [u._design_program.length for u in program_units]
                opcode_counts: Dict[str, int] = {}
                for unit_with_program in program_units:
                    for record in unit_with_program._design_program.instructions:
                        name = OPCODE_NAMES.get(record.opcode, f"op_{record.opcode}")
                        opcode_counts[name] = opcode_counts.get(name, 0) + 1
                decoded = [
                    u._architecture_descriptor.hidden_size
                    for u in program_units if u._architecture_descriptor is not None
                ]
                self._design_program_distribution_trace.append({
                    "tick": self.tick_count,
                    "program_unit_count": len(program_units),
                    "distinct_program_count": len(set(
                        u._design_program.program_digest() for u in program_units)),
                    "program_length_histogram": dict(Counter(lengths)),
                    "mean_program_length": round(sum(lengths) / len(lengths), 3),
                    "opcode_frequency": dict(sorted(opcode_counts.items())),
                    "decoded_hidden_size_histogram": dict(Counter(decoded)),
                })

    def _step_unit_executed_construction(self) -> None:
        """M23: advance every program-backed unit's runtime construction
        executor by a fixed bounded number of steps, servicing BEGIN
        reservations and COMMIT assembly through engine arbitration."""
        from machine_sim.agents.design_program import DesignExecutionBounds
        from machine_sim.agents.program_construction import (
            ConstructionExecutionBounds,
            execute_runtime_step,
            PHASE_IDLE,
        )

        cfg = self.config
        exec_bounds = ConstructionExecutionBounds(
            copy_records_per_step=max(1, int(cfg.copy_records_per_copy_instruction)),
            copy_error_probability=float(cfg.copy_error_probability),
            minimum_program_length=cfg.program_min_length,
            maximum_program_length=cfg.program_max_length,
        )
        dev_bounds = DesignExecutionBounds(
            minimum_hidden_size=cfg.minimum_hidden_size,
            maximum_hidden_size=cfg.maximum_hidden_size,
            initial_hidden_size=cfg.initial_hidden_size,
            minimum_recurrence_density=cfg.minimum_recurrent_density,
            maximum_recurrence_density=cfg.maximum_recurrent_density,
            initial_recurrence_density=cfg.initial_recurrent_density,
            minimum_plasticity_rate=cfg.minimum_plasticity_rate,
            maximum_plasticity_rate=cfg.maximum_plasticity_rate,
            initial_plasticity_rate=cfg.neural_plasticity_rate,
            program_base_cost=cfg.program_base_cost,
            program_per_instruction_cost=cfg.program_per_instruction_cost,
        )

        for unit in list(self.units):
            state = getattr(unit, "_construction_state", None)
            if state is None or not state.construction_enabled:
                continue

            # Source-inactivity policy: an unfinished cycle fails/cancels,
            # the reservation is released, consumed costs stay consumed.
            if not unit.is_active:
                if state.construction_phase != PHASE_IDLE:
                    self.world.release_reservation(
                        state.reserved_target_position,
                        f"{unit.unit_id}:{state.construction_cycle_index}",
                    )
                    state.construction_phase = PHASE_IDLE
                    state.target_copy_buffer = []
                    state.source_cursor = 0
                    state.reserved_target_position = None
                    state.provisional_successor_id = None
                    state.last_construction_fault = "source_inactive"
                    self._record_event(Event(
                        tick=self.tick_count,
                        event_type=EventType.CONSTRUCTION_FAILED,
                        unit_id=unit.unit_id,
                        data={"cause": "source_inactive",
                              "construction_cycle_index": state.construction_cycle_index},
                    ))
                continue

            services = _UnitConstructionServices(self, unit, state)
            steps_remaining = max(1, int(cfg.runtime_construction_steps_per_tick))
            while steps_remaining > 0 and unit.is_active:
                steps_remaining -= 1
                trace_row = execute_runtime_step(
                    unit._design_program, state, services, exec_bounds,
                    self.tick_count,
                )
                trace_row.update({
                    "tick": self.tick_count,
                    "unit_id": unit.unit_id,
                    "construction_cycle_index": state.construction_cycle_index,
                    "source_program_digest": (
                        state.source_program_digest_at_begin
                        or unit._design_program.program_digest()
                    ),
                })
                self._construction_runtime_trace.append(trace_row)
                if trace_row.get("copy_error_type"):
                    self._program_copy_trace.append({
                        "tick": self.tick_count,
                        "unit_id": unit.unit_id,
                        "construction_cycle_index": state.construction_cycle_index,
                        "copy_error_type": trace_row["copy_error_type"],
                        "source_cursor_after": state.source_cursor,
                        "target_buffer_length": len(state.target_copy_buffer),
                    })

    def get_neural_processing_summary(self) -> Dict[str, Any]:
        """Get neural processing summary for artifact output."""
        cfg = self.config
        return {
            "neural_controller_enabled": cfg.neural_controller_enabled,
            "neural_controller_mode": cfg.neural_controller_mode,
            "neural_plasticity_enabled": cfg.neural_plasticity_enabled,
            "run_ticks": self.tick_count,
            "neural_state_trace_count": len(self._neural_state_trace),
            "neural_action_trace_count": len(self._neural_action_trace),
            "neural_plasticity_trace_count": len(self._neural_plasticity_trace),
            "neural_successor_transfer_count": len(self._neural_successor_transfer_trace),
            "final_active_count": sum(1 for u in self.units if u.is_active),
            "total_unit_count": len(self.units),
        }

    def get_neural_vs_scalar_comparison(self, scalar_summary: Dict[str, Any]) -> Dict[str, Any]:
        """Compare neural vs scalar baseline."""
        neural_active = sum(1 for u in self.units if u.is_active)
        scalar_active = scalar_summary.get("final_active_unit_count", 0)

        # Action distribution from neural trace
        neural_actions: Dict[str, int] = {}
        for entry in self._neural_action_trace:
            a = entry.get("action", "unknown")
            neural_actions[a] = neural_actions.get(a, 0) + 1

        # Compute action distribution delta vs scalar
        scalar_summary.get("action_distribution", {})

        return {
            "scalar_active_count": scalar_active,
            "neural_active_count": neural_active,
            "scalar_transfer_count": scalar_summary.get("transfer_count", 0),
            "neural_transfer_count": len(self._neural_successor_transfer_trace),
            "scalar_signal_observations": scalar_summary.get("signal_observation_count", 0),
            "neural_signal_observations": sum(
                1 for e in self._neural_action_trace if e.get("action") == "EMIT_SIGNAL"
            ),
            "action_distribution_delta": neural_actions,
            "adaptive_state_delta_scalar": scalar_summary.get("adaptive_state_delta", {}),
            "neural_state_delta": {
                "plasticity_events": len(self._neural_plasticity_trace),
                "total_w_out_delta": round(sum(e.get("w_out_delta", 0) for e in self._neural_plasticity_trace), 6),
            },
            "neural_parameter_delta": {
                "transfer_count": len(self._neural_successor_transfer_trace),
            },
            "runtime_metric_delta_summary": {
                "neural_active": neural_active,
                "scalar_active": scalar_active,
                "difference": neural_active - scalar_active,
            },
            "nontrivial_neural_difference_detected": (
                len(self._neural_plasticity_trace) > 0
                or len(self._neural_successor_transfer_trace) > 0
                or neural_active != scalar_active
            ),
        }

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
