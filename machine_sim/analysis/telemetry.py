"""Machine-native operational telemetry and diagnostic traces."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class TelemetryFrame:
    """Bounded machine-native diagnostic snapshot from a unit."""
    unit_id: str = ""
    tick: int = 0
    power_ratio: float = 0.0
    component_health_avg: float = 0.0
    sensor_health: float = 0.0
    actuator_health: float = 0.0
    movement_blocked_count: int = 0
    hazard_encounter_count: int = 0
    resource_obs_count: int = 0
    scan_count: int = 0
    signal_emit_count: int = 0
    signal_obs_count: int = 0
    local_resource_density: float = 0.0
    local_hazard_density: float = 0.0
    capsule_applied: bool = False
    warm_start_power_delta: float = 0.0
    warm_start_sensor_delta: float = 0.0
    lineage_generation: int = 0
    capsule_sparsity: float = 0.0


@dataclass
class ReconciliationRecord:
    """Neutral numeric record of telemetry overlap between units."""
    unit_a_id: str = ""
    unit_b_id: str = ""
    tick: int = 0
    power_estimate_diff: float = 0.0
    sensor_health_diff: float = 0.0
    hazard_density_diff: float = 0.0
    resource_density_diff: float = 0.0
    signal_obs_overlap: int = 0
    movement_blocked_divergence: int = 0
    capsule_sparsity_drift: float = 0.0
    warm_start_delta_drift: float = 0.0
    lineage_gen_distance: int = 0
    telemetry_divergence: float = 0.0
    telemetry_continuity: float = 0.0


@dataclass
class LineageDriftEntry:
    """Drift metric across fabrication generations."""
    lineage_source: str = ""
    generation: int = 0
    capsule_count: int = 0
    avg_sparsity: float = 0.0
    avg_power_bias: float = 0.0
    avg_sensor_calibration: float = 0.0
    avg_warm_start_power_delta: float = 0.0
    avg_warm_start_sensor_delta: float = 0.0
    source_successor_diff: float = 0.0
    continuity_score: float = 0.0
    divergence_score: float = 0.0


class TelemetryTracker:
    """Records bounded operational telemetry frames for units."""

    def __init__(self, enabled: bool = True, window_size: int = 30, max_entries: int = 50) -> None:
        self.enabled = enabled
        self.window_size = window_size
        self.max_entries = max_entries
        self._frames: List[TelemetryFrame] = []
        self._unit_buffers: Dict[str, List[TelemetryFrame]] = {}

    def record_frame(self, unit: Any, tick: int, world: Any) -> TelemetryFrame:
        """Capture a telemetry frame from a unit's current state."""
        # Gather unit state
        power_ratio = unit._power_ratio()
        comp_health = unit._avg_component_health()
        sensor = unit.components.get("sensor")
        actuator = unit.components.get("actuator")
        sensor_health = sensor.health if sensor else 0.0
        actuator_health = actuator.health if actuator else 0.0

        # Gather local world state
        cell = world.grid.get(unit.position)
        local_resource_density = cell.resource_density if cell else 0.0
        local_hazard_density = cell.hazard_intensity if cell else 0.0

        # Gather field tracker stats if available
        field_summary = None
        if hasattr(unit, '_field_tracker'):
            field_summary = unit._field_tracker.get_summary(tick)

        movement_blocked = field_summary.total_movement_blocks if field_summary else 0
        hazard_count = field_summary.total_hazards if field_summary else 0
        resource_obs = field_summary.total_signals if field_summary else 0
        scan_count = field_summary.total_scans if field_summary else 0
        signal_emit = field_summary.total_emissions if field_summary else 0
        signal_obs = field_summary.total_signals if field_summary else 0

        # Capsule metadata
        capsule_applied = getattr(unit, '_capsule_applied', False)
        ws_effect = getattr(unit, '_capsule_warm_start_effect', {})
        ws_power = ws_effect.get("power_reserve_delta", 0.0) if ws_effect else 0.0
        ws_sensor = ws_effect.get("sensor_health_delta", 0.0) if ws_effect else 0.0
        capsule = getattr(unit, '_calibration_capsule', None)
        capsule_sparsity = capsule.sparsity_score if capsule else 0.0

        frame = TelemetryFrame(
            unit_id=unit.unit_id,
            tick=tick,
            power_ratio=power_ratio,
            component_health_avg=comp_health,
            sensor_health=sensor_health,
            actuator_health=actuator_health,
            movement_blocked_count=movement_blocked,
            hazard_encounter_count=hazard_count,
            resource_obs_count=resource_obs,
            scan_count=scan_count,
            signal_emit_count=signal_emit,
            signal_obs_count=signal_obs,
            local_resource_density=local_resource_density,
            local_hazard_density=local_hazard_density,
            capsule_applied=capsule_applied,
            warm_start_power_delta=ws_power,
            warm_start_sensor_delta=ws_sensor,
            lineage_generation=getattr(unit, '_generation_index', 0),
            capsule_sparsity=capsule_sparsity,
        )

        # Store in buffer
        uid = unit.unit_id
        if uid not in self._unit_buffers:
            self._unit_buffers[uid] = []
        self._unit_buffers[uid].append(frame)
        if len(self._unit_buffers[uid]) > self.max_entries:
            self._unit_buffers[uid] = self._unit_buffers[uid][-self.max_entries:]

        self._frames.append(frame)
        if len(self._frames) > self.max_entries:
            self._frames = self._frames[-self.max_entries:]

        return frame

    def get_frames(self, unit_id: Optional[str] = None) -> List[TelemetryFrame]:
        if unit_id:
            return list(self._unit_buffers.get(unit_id, []))
        return list(self._frames)

    def get_summary(self) -> Dict[str, Any]:
        """Get telemetry summary for artifact output."""
        total = len(self._frames)
        units_tracked = len(self._unit_buffers)
        avg_power = sum(f.power_ratio for f in self._frames) / total if total else 0.0
        return {
            "total_frames": total,
            "units_tracked": units_tracked,
            "avg_power_ratio": avg_power,
        }


class ReconciliationEngine:
    """Computes neutral telemetry reconciliation between overlapping units."""

    def __init__(self, enabled: bool = True, interval: int = 5, radius: int = 3, max_pairs: int = 20) -> None:
        self.enabled = enabled
        self.interval = interval
        self.radius = radius
        self.max_pairs = max_pairs
        self._records: List[ReconciliationRecord] = []

    def reconcile(self, units: List[Any], world: Any, tick: int) -> List[ReconciliationRecord]:
        """Compute reconciliation for units within proximity."""
        records: List[ReconciliationRecord] = []
        pair_count = 0

        for i, u_a in enumerate(units):
            if not u_a.is_active or pair_count >= self.max_pairs:
                break
            for u_b in units[i+1:]:
                if not u_b.is_active:
                    continue
                # Check proximity
                dx = abs(u_a.position[0] - u_b.position[0])
                dy = abs(u_a.position[1] - u_b.position[1])
                if dx > self.radius or dy > self.radius:
                    continue

                # Compute numeric differences
                power_diff = abs(u_a._power_ratio() - u_b._power_ratio())
                sensor_a = u_a.components.get("sensor")
                sensor_b = u_b.components.get("sensor")
                sensor_diff = abs(
                    (sensor_a.health if sensor_a else 0.0) -
                    (sensor_b.health if sensor_b else 0.0)
                )
                comp_diff = abs(u_a._avg_component_health() - u_b._avg_component_health())

                # Lineage distance
                gen_a = getattr(u_a, '_generation_index', 0)
                gen_b = getattr(u_b, '_generation_index', 0)
                gen_distance = abs(gen_a - gen_b)

                # Capsule drift
                cap_a = getattr(u_a, '_calibration_capsule', None)
                cap_b = getattr(u_b, '_calibration_capsule', None)
                sparsity_drift = abs(
                    (cap_a.sparsity_score if cap_a else 0.0) -
                    (cap_b.sparsity_score if cap_b else 0.0)
                )
                ws_drift = abs(
                    (getattr(u_a, '_capsule_warm_start_effect', {}).get("power_reserve_delta", 0.0)) -
                    (getattr(u_b, '_capsule_warm_start_effect', {}).get("power_reserve_delta", 0.0))
                )

                # Divergence and continuity scores
                divergence = (power_diff + sensor_diff + comp_diff + sparsity_drift) / 4.0
                continuity = 1.0 - divergence

                record = ReconciliationRecord(
                    unit_a_id=u_a.unit_id,
                    unit_b_id=u_b.unit_id,
                    tick=tick,
                    power_estimate_diff=power_diff,
                    sensor_health_diff=sensor_diff,
                    capsule_sparsity_drift=sparsity_drift,
                    warm_start_delta_drift=ws_drift,
                    lineage_gen_distance=gen_distance,
                    telemetry_divergence=divergence,
                    telemetry_continuity=continuity,
                )
                records.append(record)
                pair_count += 1

        self._records.extend(records)
        return records

    def get_records(self) -> List[ReconciliationRecord]:
        return list(self._records)

    def get_summary(self) -> Dict[str, Any]:
        if not self._records:
            return {"total_records": 0, "avg_divergence": 0.0, "avg_continuity": 0.0}
        div_sum = sum(r.telemetry_divergence for r in self._records)
        cont_sum = sum(r.telemetry_continuity for r in self._records)
        return {
            "total_records": len(self._records),
            "avg_divergence": div_sum / len(self._records),
            "avg_continuity": cont_sum / len(self._records),
        }


class LineageDriftAnalyzer:
    """Analyzes calibration/capsule drift across fabricated generations."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self._entries: List[LineageDriftEntry] = []

    def analyze(self, capsules: List[Any], lineage_records: List[Any]) -> List[LineageDriftEntry]:
        """Compute drift metrics per lineage."""
        # Group capsules by source lineage
        lineage_capsules: Dict[str, List[Any]] = {}
        for cap in capsules:
            key = cap.source_unit_id
            if key not in lineage_capsules:
                lineage_capsules[key] = []
            lineage_capsules[key].append(cap)

        self._entries.clear()
        for source_id, caps in lineage_capsules.items():
            generations = sorted(set(c.source_generation for c in caps))
            for gen in generations:
                gen_caps = [c for c in caps if c.source_generation == gen]
                if not gen_caps:
                    continue
                n = len(gen_caps)
                avg_sparsity = sum(c.sparsity_score for c in gen_caps) / n
                avg_power_bias = sum(c.initial_power_bias for c in gen_caps) / n
                avg_sensor_cal = sum(c.initial_sensor_calibration for c in gen_caps) / n
                avg_ws_power = sum(c.initial_power_bias for c in gen_caps) / n
                avg_ws_sensor = sum(c.initial_sensor_calibration for c in gen_caps) / n

                # Continuity: lower sparsity = higher continuity
                continuity = 1.0 - avg_sparsity
                # Divergence: higher sparsity drift = higher divergence
                divergence = avg_sparsity

                entry = LineageDriftEntry(
                    lineage_source=source_id,
                    generation=gen,
                    capsule_count=n,
                    avg_sparsity=avg_sparsity,
                    avg_power_bias=avg_power_bias,
                    avg_sensor_calibration=avg_sensor_cal,
                    avg_warm_start_power_delta=avg_ws_power,
                    avg_warm_start_sensor_delta=avg_ws_sensor,
                    continuity_score=continuity,
                    divergence_score=divergence,
                )
                self._entries.append(entry)

        return self._entries

    def get_entries(self) -> List[LineageDriftEntry]:
        return list(self._entries)

    def get_summary(self) -> Dict[str, Any]:
        if not self._entries:
            return {"total_entries": 0, "max_generation": 0}
        return {
            "total_entries": len(self._entries),
            "max_generation": max(e.generation for e in self._entries),
            "entries": [
                {
                    "source": e.lineage_source,
                    "generation": e.generation,
                    "capsule_count": e.capsule_count,
                    "avg_sparsity": e.avg_sparsity,
                    "continuity_score": e.continuity_score,
                    "divergence_score": e.divergence_score,
                }
                for e in self._entries
            ],
        }
