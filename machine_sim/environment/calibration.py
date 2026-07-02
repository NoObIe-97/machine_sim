"""Machine-native calibration capsule and warm-start transfer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class CalibrationCapsule:
    """Bounded machine-native initialization data transferred during fabrication.

    Contains statistical summaries from source unit and local world state.
    Purely numerical calibration data with no interpretive labels.
    """
    source_unit_id: str = ""
    successor_unit_id: str = ""
    fabrication_tick: int = 0
    source_generation: int = 0
    successor_generation: int = 0

    # Source unit calibration snapshot
    source_power_ratio: float = 0.0
    source_component_health: float = 0.0
    source_sensor_health: float = 0.0
    source_actuator_health: float = 0.0

    # Local field summaries from source's recent history
    source_hazard_density: float = 0.0
    source_proximity_count: float = 0.0
    source_movement_blocks: int = 0
    source_emission_rate: float = 0.0
    source_scan_rate: float = 0.0
    source_signal_count: int = 0
    source_signal_intensity: float = 0.0

    # Local resource summary
    local_resource_density: float = 0.0

    # Warm-start calibration values (applied to successor)
    initial_sensor_calibration: float = 1.0
    initial_power_bias: float = 0.0
    initial_scan_cadence: int = 3
    initial_field_pressure: float = 0.0

    # Completeness metrics
    sparsity_score: float = 0.0
    capsule_entries: int = 0


class CapsuleGenerator:
    """Generates calibration capsules from source unit and world state.

    Produces bounded, deterministic machine-native initialization data.
    Capsule contents are purely numerical without interpretive labels.
    """

    def __init__(self, window_size: int = 20, max_entries: int = 12) -> None:
        self.window_size = window_size
        self.max_entries = max_entries

    def generate(
        self,
        source_unit: Any,
        world: Any,
        successor_id: str,
        tick: int,
    ) -> CalibrationCapsule:
        """Generate a calibration capsule from source unit and local world state."""
        # Source unit snapshot
        source_power_ratio = source_unit._power_ratio()
        source_component_health = source_unit._avg_component_health()
        sensor = source_unit.components.get("sensor")
        actuator = source_unit.components.get("actuator")
        source_sensor_health = sensor.health if sensor else 0.0
        source_actuator_health = actuator.health if actuator else 0.0

        # Local field summaries from field tracker
        field_summary = None
        if hasattr(source_unit, '_field_tracker'):
            field_summary = source_unit._field_tracker.get_summary(tick)

        source_hazard_density = field_summary.local_hazard_density if field_summary else 0.0
        source_proximity_count = float(field_summary.local_proximity_count) if field_summary else 0.0
        source_movement_blocks = field_summary.total_movement_blocks if field_summary else 0
        source_emission_rate = field_summary.emission_rate if field_summary else 0.0
        source_scan_rate = field_summary.scan_rate if field_summary else 0.0
        source_signal_count = field_summary.total_signals if field_summary else 0
        source_signal_intensity = field_summary.avg_received_intensity if field_summary else 0.0

        # Local resource density
        cell = world.grid.get(source_unit.position)
        local_resource_density = cell.resource_density if cell else 0.0

        # Compute warm-start calibration values
        initial_sensor_calibration = min(1.0, source_sensor_health * 1.1)
        initial_power_bias = (source_power_ratio - 0.5) * 0.1
        initial_scan_cadence = max(1, min(5, int(3 - source_hazard_density * 10)))
        initial_field_pressure = source_proximity_count / max(1, source_signal_count + 1)

        # Compute sparsity score
        entries = sum([
            1 if source_power_ratio > 0 else 0,
            1 if source_component_health > 0 else 0,
            1 if source_hazard_density > 0 else 0,
            1 if source_proximity_count > 0 else 0,
            1 if source_signal_count > 0 else 0,
            1 if local_resource_density > 0 else 0,
        ])
        sparsity_score = 1.0 - (entries / 6.0)

        source_gen = getattr(source_unit, '_generation_index', 0)

        return CalibrationCapsule(
            source_unit_id=source_unit.unit_id,
            successor_unit_id=successor_id,
            fabrication_tick=tick,
            source_generation=source_gen,
            successor_generation=source_gen + 1,
            source_power_ratio=source_power_ratio,
            source_component_health=source_component_health,
            source_sensor_health=source_sensor_health,
            source_actuator_health=source_actuator_health,
            source_hazard_density=source_hazard_density,
            source_proximity_count=source_proximity_count,
            source_movement_blocks=source_movement_blocks,
            source_emission_rate=source_emission_rate,
            source_scan_rate=source_scan_rate,
            source_signal_count=source_signal_count,
            source_signal_intensity=source_signal_intensity,
            local_resource_density=local_resource_density,
            initial_sensor_calibration=initial_sensor_calibration,
            initial_power_bias=initial_power_bias,
            initial_scan_cadence=initial_scan_cadence,
            initial_field_pressure=initial_field_pressure,
            sparsity_score=sparsity_score,
            capsule_entries=entries,
        )

    def apply_warm_start(self, capsule: CalibrationCapsule, successor: Any) -> Dict[str, Any]:
        """Apply calibration capsule to successor unit as warm-start.

        Returns a dict recording before/after deltas for impact traceability.
        """
        # Record pre-state
        pre_sensor = successor.components.get("sensor")
        pre_sensor_health = pre_sensor.health if pre_sensor else 0.0
        pre_power = successor.power_reserve

        # Sensor calibration: adjust effective sensor range
        if pre_sensor:
            pre_sensor.health = min(pre_sensor.health, capsule.initial_sensor_calibration)

        # Power bias: shift initial power reserve slightly
        successor.power_reserve = max(
            0.0,
            successor.power_reserve + capsule.initial_power_bias * successor.max_power
        )

        # Compute deltas
        post_sensor_health = pre_sensor.health if pre_sensor else 0.0
        post_power = successor.power_reserve
        sensor_delta = post_sensor_health - pre_sensor_health
        power_delta = post_power - pre_power

        # Store capsule and effect metadata on successor
        successor._calibration_capsule = capsule
        successor._capsule_applied = True
        successor._capsule_warm_start_effect = {
            "pre_sensor_health": pre_sensor_health,
            "post_sensor_health": post_sensor_health,
            "sensor_health_delta": sensor_delta,
            "pre_power_reserve": pre_power,
            "post_power_reserve": post_power,
            "power_reserve_delta": power_delta,
        }

        return successor._capsule_warm_start_effect


class CapsuleManager:
    """Manages capsule generation, storage, and artifact output."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self.generator = CapsuleGenerator()
        self._capsules: List[CalibrationCapsule] = []
        self._capsule_count = 0

    def generate_and_store(
        self,
        source_unit: Any,
        world: Any,
        successor_id: str,
        tick: int,
    ) -> CalibrationCapsule:
        """Generate capsule, store it, and return it."""
        capsule = self.generator.generate(source_unit, world, successor_id, tick)
        self._capsules.append(capsule)
        self._capsule_count += 1
        return capsule

    def get_capsules(self) -> List[CalibrationCapsule]:
        return list(self._capsules)

    def get_summary(self) -> Dict[str, Any]:
        """Get capsule summary for artifact output."""
        if not self._capsules:
            return {"total_capsules": 0, "avg_sparsity": 0.0, "capsules": []}

        sparsity_sum = sum(c.sparsity_score for c in self._capsules)
        return {
            "total_capsules": self._capsule_count,
            "avg_sparsity": sparsity_sum / len(self._capsules),
            "capsules": [
                {
                    "source": c.source_unit_id,
                    "successor": c.successor_unit_id,
                    "tick": c.fabrication_tick,
                    "source_gen": c.source_generation,
                    "successor_gen": c.successor_generation,
                    "sparsity": c.sparsity_score,
                    "entries": c.capsule_entries,
                    "source_power_ratio": c.source_power_ratio,
                    "source_hazard_density": c.source_hazard_density,
                    "source_signal_count": c.source_signal_count,
                    "local_resource_density": c.local_resource_density,
                    "applied_sensor_calibration": c.initial_sensor_calibration,
                    "applied_power_bias": c.initial_power_bias,
                }
                for c in self._capsules
            ],
        }


def compute_capsule_impact(
    capsule_enabled_units: List[Any],
    capsule_disabled_units: List[Any],
) -> Dict[str, Any]:
    """Compare capsule-enabled vs capsule-disabled successor units.

    Returns neutral machine-native metrics showing measurable differences.
    """
    EPS = 1e-6

    def unit_stats(units: List[Any]) -> Dict[str, Any]:
        if not units:
            return {"count": 0, "avg_power": 0.0, "avg_sensor_health": 0.0,
                    "active_count": 0, "capsule_applied_count": 0,
                    "warm_start_power_delta": 0.0, "warm_start_sensor_delta": 0.0}
        active = [u for u in units if u.is_active]
        power_vals = [u.power_reserve for u in units]
        sensor_vals = [u.components.get("sensor", type("", (), {"health": 0.0})()).health
                       for u in units]
        capsule_count = sum(1 for u in units if getattr(u, '_capsule_applied', False))

        # Collect warm-start deltas from units that have them
        ws_power_deltas = [u._capsule_warm_start_effect.get("power_reserve_delta", 0.0)
                           for u in units if hasattr(u, '_capsule_warm_start_effect')]
        ws_sensor_deltas = [u._capsule_warm_start_effect.get("sensor_health_delta", 0.0)
                            for u in units if hasattr(u, '_capsule_warm_start_effect')]

        return {
            "count": len(units),
            "avg_power": sum(power_vals) / len(power_vals) if power_vals else 0.0,
            "avg_sensor_health": sum(sensor_vals) / len(sensor_vals) if sensor_vals else 0.0,
            "active_count": len(active),
            "capsule_applied_count": capsule_count,
            "warm_start_power_delta": sum(ws_power_deltas) / len(ws_power_deltas) if ws_power_deltas else 0.0,
            "warm_start_sensor_delta": sum(ws_sensor_deltas) / len(ws_sensor_deltas) if ws_sensor_deltas else 0.0,
        }

    enabled_stats = unit_stats(capsule_enabled_units)
    disabled_stats = unit_stats(capsule_disabled_units)

    # Check if any neutral metric delta is meaningful
    power_diff = abs(enabled_stats["avg_power"] - disabled_stats["avg_power"])
    sensor_diff = abs(enabled_stats["avg_sensor_health"] - disabled_stats["avg_sensor_health"])
    ws_power_diff = abs(enabled_stats["warm_start_power_delta"] - disabled_stats["warm_start_power_delta"])
    ws_sensor_diff = abs(enabled_stats["warm_start_sensor_delta"] - disabled_stats["warm_start_sensor_delta"])

    neutral_delta_detected = (power_diff > EPS or sensor_diff > EPS or
                              ws_power_diff > EPS or ws_sensor_diff > EPS)

    return {
        "capsule_enabled": enabled_stats,
        "capsule_disabled": disabled_stats,
        "delta": {
            "power_diff": enabled_stats["avg_power"] - disabled_stats["avg_power"],
            "sensor_health_diff": enabled_stats["avg_sensor_health"] - disabled_stats["avg_sensor_health"],
            "active_count_diff": enabled_stats["active_count"] - disabled_stats["active_count"],
            "warm_start_power_delta": enabled_stats["warm_start_power_delta"],
            "warm_start_sensor_delta": enabled_stats["warm_start_sensor_delta"],
            "neutral_metric_delta_detected": neutral_delta_detected,
            "impact_metric_names": ["power_diff", "sensor_health_diff", "warm_start_power_delta", "warm_start_sensor_delta"],
        },
    }
