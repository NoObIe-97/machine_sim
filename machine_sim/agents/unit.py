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
from machine_sim.analysis.adaptive import (
    AdaptiveEmissionPolicy,
    AdaptiveScanPolicy,
    LocalFieldTracker,
    SignalFieldSummary,
)
from machine_sim.agents.adaptive_control import AdaptiveController, AdaptiveStateVector
from machine_sim.agents.neural_controller import NeuralController, NeuralProcessingConfig


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
        adaptive_enabled: bool = False,
        neural_controller_enabled: bool = False,
        neural_controller_mode: str = "replace",
        neural_plasticity_enabled: bool = True,
        neural_seed: int = 42,
    ) -> None:
        self.variant = variant or ALL_VARIANTS[0]
        self.signal_enabled = signal_enabled
        self.signal_pattern_count = signal_pattern_count
        self.signal_energy_cost = signal_energy_cost
        self.signal_default_radius = signal_default_radius
        self.signal_default_decay = signal_default_decay
        self.signal_default_duration = signal_default_duration
        self.adaptive_enabled = adaptive_enabled
        self._last_signal_tick = -10
        self._last_scan_tick = -10
        self._field_tracker = LocalFieldTracker(window_size=20)
        self._emission_policy = AdaptiveEmissionPolicy()
        self._scan_policy = AdaptiveScanPolicy()
        self._adaptive_state = AdaptiveStateVector()
        self._adaptive_controller = AdaptiveController(enabled=adaptive_enabled)
        self._neural_controller_enabled = neural_controller_enabled
        self._neural_controller_mode = neural_controller_mode
        self._previous_action_name = "IDLE"
        self._neural_controller: Optional[NeuralController] = None
        if neural_controller_enabled:
            nc_cfg = NeuralProcessingConfig(plasticity_enabled=neural_plasticity_enabled)
            self._neural_controller = NeuralController(config=nc_cfg, unit_id=unit_id, seed=neural_seed)
        self._generation_index = 0
        self._lifetime_ticks = 0
        self._action_counts: Dict[str, int] = {}
        self._last_feedback: Dict[str, float] = {}
        super().__init__(
            unit_id=unit_id,
            position=position,
            max_power=self.variant.max_power,
            components=self.variant.component_factory(),
        )
        self.SENSOR_RANGE = self.variant.sensor_range

    def _default_components(self) -> Dict[str, Component]:
        return default_components()

    def get_field_summary(self, tick: int) -> SignalFieldSummary:
        """Get local signal field summary."""
        return self._field_tracker.get_summary(tick)

    def decide(self, tick: int) -> Optional[Action]:
        power_ratio = self._power_ratio()
        field_summary = self._field_tracker.get_summary(tick)
        self._lifetime_ticks = tick

        # --- Critical safety overrides (always active) ---
        if power_ratio < 0.15:
            return Action(ActionType.HARVEST)

        if power_ratio < 0.30:
            readings = list(self.sensor_readings)
            if readings:
                resource_map = build_resource_map(readings)
                best = gradient_direction(self.position, resource_map)
                if best and best != self.position:
                    return Action(ActionType.MOVE, target_position=best)
            return Action(ActionType.HARVEST)

        critical = self._weakest_critical()
        if critical and critical.health < 0.20:
            return Action(ActionType.MAINTAIN, target_component=critical.name)

        # --- Neural controller action selection (normal operating ticks) ---
        if self._neural_controller_enabled and self._neural_controller is not None:
            readings = list(self.sensor_readings)
            has_resource_nearby = False
            has_hazard_nearby = False
            resource_strength = 0.0
            hazard_strength = 0.0
            for r in readings:
                if hasattr(r, 'resource_type') and r.resource_quantity > 0:
                    has_resource_nearby = True
                    resource_strength = max(resource_strength, r.resource_quantity)
                if hasattr(r, 'hazard_level') and r.hazard_level > 0:
                    has_hazard_nearby = True
                    hazard_strength = max(hazard_strength, r.hazard_level)

            field_sum = self._field_tracker.get_summary(tick)
            signal_observed = field_sum.recent_signal_count > 0
            signal_emitted = field_sum.total_emissions > 0
            movement_blocked = field_sum.recent_movement_blocks > 0
            resource_extracted = False
            scan_count = float(field_sum.total_scans)
            time_since_sig = 0.0
            if field_sum.total_emissions > 0 and hasattr(self._field_tracker, '_emission_ticks'):
                last_emit = self._field_tracker._emission_ticks[-1] if self._field_tracker._emission_ticks else 0
                time_since_sig = min(1.0, (tick - last_emit) / 50.0) if last_emit >= 0 else 0.0

            sensor_input = self._neural_controller.build_sensor_input(
                power_ratio=power_ratio,
                avg_component_health=self._avg_component_health(),
                has_resource=has_resource_nearby,
                resource_strength=resource_strength,
                has_hazard=has_hazard_nearby,
                hazard_strength=hazard_strength,
                signal_observed=signal_observed,
                signal_emitted=signal_emitted,
                movement_blocked=movement_blocked,
                resource_extracted=resource_extracted,
                scan_result_count=min(1.0, scan_count / 5.0),
                previous_action=self._previous_action_name,
                time_since_signal=time_since_sig,
            )

            import random as _n_rng
            r = _n_rng.Random(tick * 1000 + hash(self.unit_id))
            chosen_name, param_biases, raw_logits = self._neural_controller.select_action(sensor_input, r)

            # Map neural action name to ActionType
            neural_action_map = {
                "MOVE": ActionType.MOVE,
                "SCAN": ActionType.SCAN,
                "HARVEST": ActionType.HARVEST,
                "EMIT_SIGNAL": ActionType.EMIT_SIGNAL,
                "IDLE": ActionType.IDLE,
                "MAINTAIN": ActionType.MAINTAIN,
                "FABRICATE": ActionType.IDLE,  # fabricate not directly supported
            }
            action_type = neural_action_map.get(chosen_name, ActionType.IDLE)
            self._previous_action_name = chosen_name

            if action_type == ActionType.MOVE:
                readings = list(self.sensor_readings)
                if readings:
                    resource_map = build_resource_map(readings)
                    best = gradient_direction(self.position, resource_map)
                    if best and best != self.position:
                        return Action(ActionType.MOVE, target_position=best)
                return Action(ActionType.MOVE)

            elif action_type == ActionType.SCAN:
                return Action(ActionType.SCAN)

            elif action_type == ActionType.HARVEST:
                return Action(ActionType.HARVEST)

            elif action_type == ActionType.EMIT_SIGNAL:
                if self.signal_enabled:
                    base_interval = 5
                    # Use param_biases[0] as signal intensity bias
                    intensity_bias = param_biases[0] if len(param_biases) > 0 else 0.0
                    interval = max(2, int(base_interval * (1.0 - intensity_bias * 0.3)))
                    if tick - self._last_signal_tick >= interval:
                        self._last_signal_tick = tick
                        pattern_id = tick % self.signal_pattern_count
                        intensity = 0.5 + intensity_bias * 0.5
                        # Use param_biases[1] as radius bias
                        radius_bias = param_biases[1] if len(param_biases) > 1 else 0.0
                        radius = self.signal_default_radius + int(radius_bias * 2)
                        return Action(
                            ActionType.EMIT_SIGNAL,
                            parameters={
                                "pattern_id": pattern_id,
                                "intensity": max(0.1, min(1.0, intensity)),
                                "radius": max(1, radius),
                                "decay_rate": self.signal_default_decay,
                                "duration": self.signal_default_duration,
                                "energy_cost": self.signal_energy_cost,
                            },
                        )
                return Action(ActionType.SCAN)

            elif action_type == ActionType.MAINTAIN:
                critical = self._weakest_critical()
                if critical:
                    return Action(ActionType.MAINTAIN, target_component=critical.name)
                return Action(ActionType.IDLE)

            else:
                return Action(ActionType.IDLE)

        # --- Adaptive action selection (normal operating ticks) ---
        if self.adaptive_enabled:
            readings = list(self.sensor_readings)
            has_resource_nearby = False
            has_hazard_nearby = False
            for r in readings:
                if hasattr(r, 'resource_type') and r.resource_quantity > 0:
                    has_resource_nearby = True
                if hasattr(r, 'hazard_level') and r.hazard_level > 0:
                    has_hazard_nearby = True

            scores = self._adaptive_controller.compute_action_scores(
                self._adaptive_state, power_ratio,
                has_resource_nearby, has_hazard_nearby,
            )

            # Weighted random selection from scores
            import random as _rng
            r = _rng.Random(tick * 1000 + hash(self.unit_id))
            actions_list = list(scores.keys())
            weights = [scores[a] for a in actions_list]
            total_w = sum(weights) or 1.0
            weights = [w / total_w for w in weights]
            cumul = 0.0
            roll = r.random()
            chosen = actions_list[-1]
            for a, w in zip(actions_list, weights):
                cumul += w
                if roll < cumul:
                    chosen = a
                    break

            if chosen == "move":
                readings = list(self.sensor_readings)
                if readings:
                    resource_map = build_resource_map(readings)
                    best = gradient_direction(self.position, resource_map)
                    if best and best != self.position:
                        return Action(ActionType.MOVE, target_position=best)
                return Action(ActionType.MOVE)

            elif chosen == "scan":
                return Action(ActionType.SCAN)

            elif chosen == "harvest":
                return Action(ActionType.HARVEST)

            elif chosen == "signal":
                if self.signal_enabled:
                    base_interval = 5
                    interval = max(2, int(base_interval * (2.0 - self._adaptive_state.signal_emission_rate)))
                    if tick - self._last_signal_tick >= interval:
                        self._last_signal_tick = tick
                        pattern_id = (tick + int(self._adaptive_state.signal_pattern_bias * 10)) % self.signal_pattern_count
                        intensity = 0.5 + self._adaptive_state.signal_emission_rate * 0.5
                        radius = self.signal_default_radius + int(self._adaptive_state.signal_radius_bias * 2)
                        return Action(
                            ActionType.EMIT_SIGNAL,
                            parameters={
                                "pattern_id": pattern_id,
                                "intensity": intensity,
                                "radius": radius,
                                "decay_rate": self.signal_default_decay,
                                "duration": self.signal_default_duration,
                                "energy_cost": self.signal_energy_cost,
                            },
                        )
                # Fallback if signal not ready
                return Action(ActionType.SCAN)

            else:
                return Action(ActionType.IDLE)

        # --- Static fallback (non-adaptive units) ---
        if self.signal_enabled and power_ratio > 0.5:
            if tick - self._last_signal_tick >= 5:
                self._last_signal_tick = tick
                return Action(
                    ActionType.EMIT_SIGNAL,
                    parameters={
                        "pattern_id": tick % self.signal_pattern_count,
                        "intensity": 1.0,
                        "radius": self.signal_default_radius,
                        "decay_rate": self.signal_default_decay,
                        "duration": self.signal_default_duration,
                        "energy_cost": self.signal_energy_cost,
                    },
                )

        if power_ratio < 0.7:
            if tick - self._last_scan_tick >= 3:
                self._last_scan_tick = tick
                return Action(ActionType.SCAN)

        return Action(ActionType.IDLE)

    def _weakest_critical(self) -> Optional[Component]:
        candidates = [c for c in self.components.values() if c.is_critical]
        if not candidates:
            return None
        return min(candidates, key=lambda c: c.health)
