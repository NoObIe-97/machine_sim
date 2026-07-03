"""Multi-generation trace drift and compression stability analysis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class TraceDriftSummary:
    """Summary of generation-indexed trace drift analysis."""
    generation_trace_count: int = 0
    generation_index_span: int = 0
    avg_generation_trace_delta: float = 0.0
    max_generation_trace_delta: float = 0.0
    compressed_summary_delta: float = 0.0
    lineage_trace_delta_count: int = 0
    drift_envelope_count: int = 0
    avg_drift_envelope_width: float = 0.0
    max_drift_envelope_width: float = 0.0
    power_ratio_drift_range: float = 0.0
    sensor_health_drift_range: float = 0.0
    signal_trace_drift_range: float = 0.0
    replay_error_window_count: int = 0
    avg_replay_error_delta: float = 0.0
    max_replay_error_delta: float = 0.0
    replay_stability_floor: float = 0.0
    replay_stability_variance: float = 0.0
    capsule_trace_check_count: int = 0
    capsule_trace_power_delta: float = 0.0
    capsule_trace_sensor_delta: float = 0.0
    capsule_trace_field_delta: float = 0.0
    capsule_trace_compatibility_score: float = 0.0
    retention_record_count: int = 0
    retention_window_span: int = 0
    retention_compression_ratio: float = 0.0
    retained_summary_count: int = 0
    retention_drop_count: int = 0


class TraceDriftAnalyzer:
    """Analyzes generation-indexed trace drift and compression stability."""

    def __init__(self, enabled: bool = True, window: int = 50,
                 sample_interval: int = 5, max_records: int = 100,
                 retention_window: int = 50) -> None:
        self.enabled = enabled
        self.window = window
        self.sample_interval = sample_interval
        self.max_records = max_records
        self.retention_window = retention_window
        self._generation_records: List[Dict[str, Any]] = []
        self._envelope_records: List[Dict[str, Any]] = []
        self._replay_records: List[Dict[str, Any]] = []
        self._capsule_trace_records: List[Dict[str, Any]] = []
        self._retention_records: List[Dict[str, Any]] = []

    def record_generation_trace(self, data: Dict[str, Any]) -> None:
        """Record a generation-indexed trace point."""
        self._generation_records.append(data)
        if len(self._generation_records) > self.max_records:
            self._generation_records = self._generation_records[-self.max_records:]

    def record_envelope(self, data: Dict[str, Any]) -> None:
        """Record a drift envelope observation."""
        self._envelope_records.append(data)
        if len(self._envelope_records) > self.max_records:
            self._envelope_records = self._envelope_records[-self.max_records:]

    def record_replay(self, data: Dict[str, Any]) -> None:
        """Record replay-error stability data."""
        self._replay_records.append(data)
        if len(self._replay_records) > self.max_records:
            self._replay_records = self._replay_records[-self.max_records:]

    def record_capsule_trace(self, data: Dict[str, Any]) -> None:
        """Record capsule-trace compatibility data."""
        self._capsule_trace_records.append(data)
        if len(self._capsule_trace_records) > self.max_records:
            self._capsule_trace_records = self._capsule_trace_records[-self.max_records:]

    def analyze(self) -> TraceDriftSummary:
        """Compute full trace drift summary."""
        # Generation-indexed trace deltas
        gen_records = self._generation_records
        gen_count = len(gen_records)
        gen_span = 0
        avg_delta = 0.0
        max_delta = 0.0
        compressed_delta = 0.0
        delta_count = 0

        if gen_count > 1:
            gens = [r.get("generation_index", 0) for r in gen_records]
            gen_span = max(gens) - min(gens)
            deltas = []
            powers = [r.get("power_ratio", 0.0) for r in gen_records]
            for i in range(1, len(powers)):
                d = abs(powers[i] - powers[i - 1])
                deltas.append(d)
                delta_count += 1
            if deltas:
                avg_delta = sum(deltas) / len(deltas)
                max_delta = max(deltas)
                compressed_delta = sum(deltas) / max(1, gen_count)

        # Drift envelopes
        env_records = self._envelope_records
        env_count = len(env_records)
        avg_width = 0.0
        max_width = 0.0
        pwr_range = 0.0
        sen_range = 0.0
        sig_range = 0.0

        if env_count > 0:
            widths = [r.get("envelope_width", 0.0) for r in env_records]
            avg_width = sum(widths) / len(widths)
            max_width = max(widths)
            pwr_vals = [r.get("power_ratio", 0.0) for r in env_records]
            sen_vals = [r.get("sensor_health", 0.0) for r in env_records]
            sig_vals = [r.get("signal_count", 0.0) for r in env_records]
            if len(pwr_vals) > 1:
                pwr_range = max(pwr_vals) - min(pwr_vals)
                sen_range = max(sen_vals) - min(sen_vals)
                sig_range = max(sig_vals) - min(sig_vals)

        # Replay-error stability
        rep_records = self._replay_records
        rep_count = len(rep_records)
        avg_rep_delta = 0.0
        max_rep_delta = 0.0
        rep_floor = 0.0
        rep_variance = 0.0

        if rep_count > 1:
            errors = [r.get("replay_error", 0.0) for r in rep_records]
            deltas = [abs(errors[i] - errors[i - 1]) for i in range(1, len(errors))]
            if deltas:
                avg_rep_delta = sum(deltas) / len(deltas)
                max_rep_delta = max(deltas)
            rep_floor = min(errors) if errors else 0.0
            if errors:
                mean_err = sum(errors) / len(errors)
                rep_variance = sum((e - mean_err) ** 2 for e in errors) / len(errors)

        # Capsule-trace compatibility
        cap_records = self._capsule_trace_records
        cap_count = len(cap_records)
        cap_power = 0.0
        cap_sensor = 0.0
        cap_field = 0.0
        cap_compat = 0.0

        if cap_count > 0:
            cap_power = sum(r.get("power_delta", 0.0) for r in cap_records) / cap_count
            cap_sensor = sum(r.get("sensor_delta", 0.0) for r in cap_records) / cap_count
            cap_field = sum(r.get("field_delta", 0.0) for r in cap_records) / cap_count
            compat_scores = [r.get("compatibility_score", 0.0) for r in cap_records]
            cap_compat = sum(compat_scores) / len(compat_scores)

        # Long-run retention
        ret_records = self._retention_records
        ret_count = len(ret_records)
        ret_span = 0
        ret_ratio = 0.0
        retained = 0
        dropped = 0

        if ret_count > 0:
            ticks = [r.get("tick", 0) for r in ret_records]
            ret_span = max(ticks) - min(ticks) if len(ticks) > 1 else 0
            retained = min(ret_count, self.retention_window)
            dropped = max(0, ret_count - self.retention_window)
            ret_ratio = retained / max(1, ret_count)

        return TraceDriftSummary(
            generation_trace_count=gen_count,
            generation_index_span=gen_span,
            avg_generation_trace_delta=avg_delta,
            max_generation_trace_delta=max_delta,
            compressed_summary_delta=compressed_delta,
            lineage_trace_delta_count=delta_count,
            drift_envelope_count=env_count,
            avg_drift_envelope_width=avg_width,
            max_drift_envelope_width=max_width,
            power_ratio_drift_range=pwr_range,
            sensor_health_drift_range=sen_range,
            signal_trace_drift_range=sig_range,
            replay_error_window_count=rep_count,
            avg_replay_error_delta=avg_rep_delta,
            max_replay_error_delta=max_rep_delta,
            replay_stability_floor=rep_floor,
            replay_stability_variance=rep_variance,
            capsule_trace_check_count=cap_count,
            capsule_trace_power_delta=cap_power,
            capsule_trace_sensor_delta=cap_sensor,
            capsule_trace_field_delta=cap_field,
            capsule_trace_compatibility_score=cap_compat,
            retention_record_count=ret_count,
            retention_window_span=ret_span,
            retention_compression_ratio=ret_ratio,
            retained_summary_count=retained,
            retention_drop_count=dropped,
        )

    def get_summary(self) -> Dict[str, Any]:
        s = self.analyze()
        return {
            "generation": {
                "generation_trace_count": s.generation_trace_count,
                "generation_index_span": s.generation_index_span,
                "avg_generation_trace_delta": s.avg_generation_trace_delta,
                "max_generation_trace_delta": s.max_generation_trace_delta,
                "compressed_summary_delta": s.compressed_summary_delta,
                "lineage_trace_delta_count": s.lineage_trace_delta_count,
            },
            "drift_envelope": {
                "drift_envelope_count": s.drift_envelope_count,
                "avg_drift_envelope_width": s.avg_drift_envelope_width,
                "max_drift_envelope_width": s.max_drift_envelope_width,
                "power_ratio_drift_range": s.power_ratio_drift_range,
                "sensor_health_drift_range": s.sensor_health_drift_range,
                "signal_trace_drift_range": s.signal_trace_drift_range,
            },
            "replay_stability": {
                "replay_error_window_count": s.replay_error_window_count,
                "avg_replay_error_delta": s.avg_replay_error_delta,
                "max_replay_error_delta": s.max_replay_error_delta,
                "replay_stability_floor": s.replay_stability_floor,
                "replay_stability_variance": s.replay_stability_variance,
            },
            "capsule_trace": {
                "capsule_trace_check_count": s.capsule_trace_check_count,
                "capsule_trace_power_delta": s.capsule_trace_power_delta,
                "capsule_trace_sensor_delta": s.capsule_trace_sensor_delta,
                "capsule_trace_field_delta": s.capsule_trace_field_delta,
                "capsule_trace_compatibility_score": s.capsule_trace_compatibility_score,
            },
            "retention": {
                "retention_record_count": s.retention_record_count,
                "retention_window_span": s.retention_window_span,
                "retention_compression_ratio": s.retention_compression_ratio,
                "retained_summary_count": s.retained_summary_count,
                "retention_drop_count": s.retention_drop_count,
            },
        }
