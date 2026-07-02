"""Bounded operational trace compression."""

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

    def record_trace_point(self, tick: int, unit_id: str, data: Dict[str, Any]) -> None:
        """Record a raw trace point."""
        self._raw_traces.append({"tick": tick, "unit_id": unit_id, **data})
        if len(self._raw_traces) > self.max_records:
            self._raw_traces = self._raw_traces[-self.max_records:]

    def compress(self) -> TraceCompressionSummary:
        """Compress raw traces into segments."""
        self._compressed_segments.clear()

        # Group by unit
        unit_traces: Dict[str, List[Dict[str, Any]]] = {}
        for trace in self._raw_traces:
            uid = trace["unit_id"]
            if uid not in unit_traces:
                unit_traces[uid] = []
            unit_traces[uid].append(trace)

        total_raw = len(self._raw_traces)
        total_compressed = 0

        for uid, traces in unit_traces.items():
            # Compress in windows of compression_factor
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

        # Reconstruction error: simplified as 0 for bounded compression
        reconstruction_error = 0.0

        return TraceCompressionSummary(
            trace_window_count=len(unit_traces),
            raw_trace_points=total_raw,
            compressed_trace_points=total_compressed,
            compression_ratio=total_compressed / max(1, total_raw),
            trace_reconstruction_error=reconstruction_error,
            summary_vector_count=total_compressed,
            max_records=self.max_records,
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
        }
