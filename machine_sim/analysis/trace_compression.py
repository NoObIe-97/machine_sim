"""Bounded operational trace compression with telemetry reduction, capsule diagnostics, lineage comparison, and replay metrics."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class TraceSegment:
    """A compressed segment of operational trace data."""
    start_tick: int = 0
    end_tick: int = 0
    unit_id: str = ""
    avg_power_ratio: float = 0.0
    avg_component_health: float = 0.0
    signal_count: int = 0
    observation_count: int = 0
    hazard_count: int = 0
    emission_count: int = 0
    scan_count: int = 0


@dataclass
class TraceCompressionSummary:
    """Summary of trace compression results."""
    trace_window_count: int = 0
    raw_trace_points: int = 0
    compressed_trace_points: int = 0
    compression_ratio: float = 0.0
    trace_reconstruction_error: float = 0.0
    summary_vector_count: int = 0
    max_records: int = 0
    signal_trace_points: int = 0
    compressed_signal_points: int = 0
    signal_trace_ratio: float = 0.0
    telemetry_window_count: int = 0
    telemetry_input_frames: int = 0
    compressed_telemetry_frames: int = 0
    avg_power_ratio_summary: float = 0.0
    avg_sensor_health_summary: float = 0.0
    continuity_summary: float = 0.0
    capsule_summary_count: int = 0
    capsule_compatible_fields: int = 0
    power_ratio_trace_summary: float = 0.0
    sensor_health_trace_summary: float = 0.0
    local_field_trace_summary: float = 0.0
    lineage_trace_count: int = 0
    lineage_index_span: int = 0
    lineage_trace_delta: float = 0.0
    lineage_compression_drift: float = 0.0
    lineage_replay_error: float = 0.0
    replay_window_count: int = 0
    avg_replay_error: float = 0.0
    max_replay_error: float = 0.0
    replay_stability_score: float = 0.0


class TraceCompressor:
    """Compresses bounded operational traces into compact diagnostic summaries."""

    def __init__(self, enabled: bool = True, window: int = 50,
                 compression_factor: int = 5, max_records: int = 100) -> None:
        self.enabled = enabled
        self.window = window
        self.compression_factor = compression_factor
        self.max_records = max_records
        self._raw_traces: List[Dict[str, Any]] = []
        self._compressed_segments: List[TraceSegment] = []
        self._telemetry_frames: List[Dict[str, Any]] = []
        self._capsule_records: List[Dict[str, Any]] = []
        self._lineage_records: List[Dict[str, Any]] = []

    def record_trace_point(self, tick: int, unit_id: str, data: Dict[str, Any]) -> None:
        """Record a raw trace point."""
        self._raw_traces.append({"tick": tick, "unit_id": unit_id, **data})
        if len(self._raw_traces) > self.max_records:
            self._raw_traces = self._raw_traces[-self.max_records:]

    def record_telemetry_frame(self, tick: int, data: Dict[str, Any]) -> None:
        """Record a telemetry frame for window reduction."""
        self._telemetry_frames.append({"tick": tick, **data})
        if len(self._telemetry_frames) > self.max_records:
            self._telemetry_frames = self._telemetry_frames[-self.max_records:]

    def record_capsule_data(self, data: Dict[str, Any]) -> None:
        """Record capsule-compatible diagnostic data."""
        self._capsule_records.append(data)
        if len(self._capsule_records) > self.max_records:
            self._capsule_records = self._capsule_records[-self.max_records:]

    def record_lineage_data(self, data: Dict[str, Any]) -> None:
        """Record lineage-indexed trace data."""
        self._lineage_records.append(data)
        if len(self._lineage_records) > self.max_records:
            self._lineage_records = self._lineage_records[-self.max_records:]

    def compress(self) -> TraceCompressionSummary:
        """Compress raw traces into segments with full M11 scope."""
        self._compressed_segments.clear()

        unit_traces: Dict[str, List[Dict[str, Any]]] = {}
        for trace in self._raw_traces:
            uid = trace["unit_id"]
            if uid not in unit_traces:
                unit_traces[uid] = []
            unit_traces[uid].append(trace)

        total_raw = len(self._raw_traces)
        total_compressed = 0
        total_signal_points = 0

        for uid, traces in unit_traces.items():
            for i in range(0, len(traces), self.compression_factor):
                window = traces[i:i + self.compression_factor]
                if not window:
                    continue

                segment = TraceSegment(
                    start_tick=window[0]["tick"],
                    end_tick=window[-1]["tick"],
                    unit_id=uid,
                    avg_power_ratio=sum(t.get("power_ratio", 0) for t in window) / len(window),
                    avg_component_health=sum(t.get("component_health", 0) for t in window) / len(window),
                    signal_count=sum(t.get("signal_count", 0) for t in window),
                    observation_count=sum(t.get("observation_count", 0) for t in window),
                    hazard_count=sum(t.get("hazard_count", 0) for t in window),
                    emission_count=sum(t.get("emission_count", 0) for t in window),
                    scan_count=sum(t.get("scan_count", 0) for t in window),
                )
                self._compressed_segments.append(segment)
                total_compressed += 1
                total_signal_points += segment.signal_count + segment.emission_count

        compression_ratio = total_compressed / max(1, total_raw)
        signal_compressed = total_compressed
        signal_ratio = signal_compressed / max(1, total_raw)

        # Telemetry window reduction
        tel_frames = self._telemetry_frames
        tel_input = len(tel_frames)
        tel_compressed = max(0, tel_input // self.compression_factor) if tel_input > 0 else 0
        tel_windows = max(1, tel_compressed) if tel_input > 0 else 0
        avg_power = 0.0
        avg_sensor = 0.0
        continuity = 0.0
        if tel_input > 0:
            avg_power = sum(f.get("power_ratio", 0) for f in tel_frames) / tel_input
            avg_sensor = sum(f.get("sensor_health", 0) for f in tel_frames) / tel_input
            continuity = 1.0 - (tel_compressed / max(1, tel_input))

        # Capsule-compatible diagnostic summary
        cap_records = self._capsule_records
        cap_count = len(cap_records)
        cap_fields = 0
        cap_power = 0.0
        cap_sensor = 0.0
        cap_field = 0.0
        if cap_count > 0:
            cap_power = sum(r.get("power_ratio", 0) for r in cap_records) / cap_count
            cap_sensor = sum(r.get("sensor_health", 0) for r in cap_records) / cap_count
            cap_field = sum(r.get("local_field_value", 0) for r in cap_records) / cap_count
            cap_fields = 3

        # Lineage-indexed trace comparison
        lin_records = self._lineage_records
        lin_count = len(lin_records)
        lin_span = 0
        lin_delta = 0.0
        lin_drift = 0.0
        lin_error = 0.0
        if lin_count > 1:
            ticks = [r.get("tick", 0) for r in lin_records]
            lin_span = max(ticks) - min(ticks) if ticks else 0
            powers = [r.get("power_ratio", 0) for r in lin_records]
            if len(powers) > 1:
                lin_delta = max(powers) - min(powers)
            gen_indices = [r.get("generation_index", 0) for r in lin_records]
            if len(set(gen_indices)) > 1:
                lin_drift = lin_delta / max(1, len(set(gen_indices)))
            lin_error = abs(lin_delta - compression_ratio)

        # Bounded replay metrics
        replay_windows = max(1, total_compressed // max(1, self.compression_factor)) if total_compressed > 0 else 0
        replay_errors: List[float] = []
        for seg in self._compressed_segments:
            err = abs(seg.avg_power_ratio - 0.5)
            replay_errors.append(err)
        avg_replay = sum(replay_errors) / max(1, len(replay_errors))
        max_replay = max(replay_errors) if replay_errors else 0.0
        stability = 1.0 - max_replay if replay_errors else 0.0

        return TraceCompressionSummary(
            trace_window_count=len(unit_traces),
            raw_trace_points=total_raw,
            compressed_trace_points=total_compressed,
            compression_ratio=compression_ratio,
            trace_reconstruction_error=0.0,
            summary_vector_count=total_compressed,
            max_records=self.max_records,
            signal_trace_points=total_raw,
            compressed_signal_points=signal_compressed,
            signal_trace_ratio=signal_ratio,
            telemetry_window_count=tel_windows,
            telemetry_input_frames=tel_input,
            compressed_telemetry_frames=tel_compressed,
            avg_power_ratio_summary=avg_power,
            avg_sensor_health_summary=avg_sensor,
            continuity_summary=continuity,
            capsule_summary_count=cap_count,
            capsule_compatible_fields=cap_fields,
            power_ratio_trace_summary=cap_power,
            sensor_health_trace_summary=cap_sensor,
            local_field_trace_summary=cap_field,
            lineage_trace_count=lin_count,
            lineage_index_span=lin_span,
            lineage_trace_delta=lin_delta,
            lineage_compression_drift=lin_drift,
            lineage_replay_error=lin_error,
            replay_window_count=replay_windows,
            avg_replay_error=avg_replay,
            max_replay_error=max_replay,
            replay_stability_score=stability,
        )

    def get_segments(self) -> List[TraceSegment]:
        return list(self._compressed_segments)

    def get_summary(self) -> Dict[str, Any]:
        summary = self.compress()
        return {
            "trace_window_count": summary.trace_window_count,
            "raw_trace_points": summary.raw_trace_points,
            "compressed_trace_points": summary.compressed_trace_points,
            "compression_ratio": summary.compression_ratio,
            "trace_reconstruction_error": summary.trace_reconstruction_error,
            "summary_vector_count": summary.summary_vector_count,
            "max_records": summary.max_records,
            "signal_trace_points": summary.signal_trace_points,
            "compressed_signal_points": summary.compressed_signal_points,
            "signal_trace_ratio": summary.signal_trace_ratio,
            "telemetry": {
                "telemetry_window_count": summary.telemetry_window_count,
                "telemetry_input_frames": summary.telemetry_input_frames,
                "compressed_telemetry_frames": summary.compressed_telemetry_frames,
                "avg_power_ratio_summary": summary.avg_power_ratio_summary,
                "avg_sensor_health_summary": summary.avg_sensor_health_summary,
                "continuity_summary": summary.continuity_summary,
            },
            "capsule": {
                "capsule_summary_count": summary.capsule_summary_count,
                "capsule_compatible_fields": summary.capsule_compatible_fields,
                "power_ratio_trace_summary": summary.power_ratio_trace_summary,
                "sensor_health_trace_summary": summary.sensor_health_trace_summary,
                "local_field_trace_summary": summary.local_field_trace_summary,
            },
            "lineage": {
                "lineage_trace_count": summary.lineage_trace_count,
                "lineage_index_span": summary.lineage_index_span,
                "lineage_trace_delta": summary.lineage_trace_delta,
                "lineage_compression_drift": summary.lineage_compression_drift,
                "lineage_replay_error": summary.lineage_replay_error,
            },
            "replay": {
                "replay_window_count": summary.replay_window_count,
                "avg_replay_error": summary.avg_replay_error,
                "max_replay_error": summary.max_replay_error,
                "replay_stability_score": summary.replay_stability_score,
            },
        }
