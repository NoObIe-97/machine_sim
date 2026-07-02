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

    def apply_warm_start(self, capsule: CalibrationCapsule, successor: Any) -> None:
        """Apply calibration capsule to successor unit as warm-start."""
        # Sensor calibration: adjust effective sensor range
        sensor = successor.components.get("sensor")
        if sensor:
            sensor.health = min(sensor.health, capsule.initial_sensor_calibration)

        # Power bias: shift initial power reserve slightly
        successor.power_reserve = max(
            0.0,
            successor.power_reserve + capsule.initial_power_bias * successor.max_power
        )

        # Store capsule as metadata on successor
        successor._calibration_capsule = capsule
        successor._capsule_applied = True


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
                }
                for c in self._capsules
            ],
        }
