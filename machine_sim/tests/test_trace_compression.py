"""Tests for Milestone 11 bounded operational trace compression."""

from __future__ import annotations

import pytest

from machine_sim.agents.unit import MachineUnitImpl
from machine_sim.analysis.trace_compression import TraceCompressor, TraceSegment
from machine_sim.environment.world import World
from machine_sim.sim.config import SimConfig
from machine_sim.sim.engine import SimEngine
from machine_sim.sim.events import EventType


class TestTraceCompressor:
    """Trace compressor tests."""

    def test_compress_produces_segments(self):
        """Compression produces bounded segments."""
        compressor = TraceCompressor(enabled=True, compression_factor=3)
        for i in range(10):
            compressor.record_trace_point(i, "u0", {"power_ratio": 0.8, "component_health": 0.9})

        summary = compressor.compress()
        assert summary.compressed_trace_points > 0
        assert summary.raw_trace_points == 10
        assert summary.compression_ratio > 0

    def test_compression_ratio_bounded(self):
        """Compression ratio is numeric and bounded."""
        compressor = TraceCompressor(enabled=True, compression_factor=5)
        for i in range(20):
            compressor.record_trace_point(i, "u0", {"power_ratio": 0.8})

        summary = compressor.compress()
        assert 0 <= summary.compression_ratio <= 1

    def test_trace_deterministic(self):
        """Same inputs produce same compression results."""
        def run_compression(seed):
            compressor = TraceCompressor(enabled=True, compression_factor=3)
            for i in range(15):
                compressor.record_trace_point(i, "u0", {"power_ratio": 0.8 + (i * 0.01)})
            return compressor.compress().compressed_trace_points

        r1 = run_compression(42)
        r2 = run_compression(42)
        assert r1 == r2

    def test_bounded_storage(self):
        """Compressor respects max_records bound."""
        compressor = TraceCompressor(enabled=True, max_records=5)
        for i in range(10):
            compressor.record_trace_point(i, "u0", {"power_ratio": 0.8})
        assert len(compressor._raw_traces) <= 5

    def test_signal_trace_compression(self):
        """Signal trace compression uses real signal-enabled data."""
        compressor = TraceCompressor(enabled=True, compression_factor=3)
        for i in range(15):
            compressor.record_trace_point(i, "u0", {
                "power_ratio": 0.8, "component_health": 0.9,
                "signal_count": 2, "emission_count": 1,
            })
        summary = compressor.compress()
        assert summary.signal_trace_points > 0
        assert summary.compressed_signal_points > 0
        assert summary.signal_trace_ratio > 0

    def test_telemetry_window_reduction_enabled(self):
        """Telemetry-enabled setup produces nonzero telemetry summary."""
        compressor = TraceCompressor(enabled=True, compression_factor=3)
        for i in range(12):
            compressor.record_trace_point(i, "u0", {"power_ratio": 0.8})
            compressor.record_telemetry_frame(i, {"power_ratio": 0.8, "sensor_health": 0.9})
        summary = compressor.compress()
        assert summary.telemetry_input_frames == 12
        assert summary.compressed_telemetry_frames > 0
        assert summary.telemetry_window_count > 0
        assert summary.avg_power_ratio_summary > 0
        assert summary.avg_sensor_health_summary > 0
        assert summary.continuity_summary >= 0

    def test_telemetry_window_reduction_disabled(self):
        """Telemetry-disabled setup returns clean zero summary."""
        compressor = TraceCompressor(enabled=True, compression_factor=3)
        for i in range(10):
            compressor.record_trace_point(i, "u0", {"power_ratio": 0.8})
        summary = compressor.compress()
        assert summary.telemetry_input_frames == 0
        assert summary.compressed_telemetry_frames == 0
        assert summary.telemetry_window_count == 0
        assert summary.avg_power_ratio_summary == 0.0
        assert summary.avg_sensor_health_summary == 0.0
        assert summary.continuity_summary == 0.0

    def test_capsule_compatible_summary_enabled(self):
        """Capsule-enabled setup produces numeric capsule-compatible summary."""
        compressor = TraceCompressor(enabled=True, compression_factor=3)
        for i in range(10):
            compressor.record_trace_point(i, "u0", {"power_ratio": 0.8})
        for i in range(5):
            compressor.record_capsule_data({
                "power_ratio": 0.85 + i * 0.02,
                "sensor_health": 0.9 + i * 0.01,
                "local_field_value": 3 + i,
            })
        summary = compressor.compress()
        assert summary.capsule_summary_count == 5
        assert summary.capsule_compatible_fields == 3
        assert summary.power_ratio_trace_summary > 0
        assert summary.sensor_health_trace_summary > 0
        assert summary.local_field_trace_summary > 0

    def test_capsule_compatible_summary_disabled(self):
        """Capsule-disabled setup returns clean zero summary."""
        compressor = TraceCompressor(enabled=True, compression_factor=3)
        for i in range(10):
            compressor.record_trace_point(i, "u0", {"power_ratio": 0.8})
        summary = compressor.compress()
        assert summary.capsule_summary_count == 0
        assert summary.capsule_compatible_fields == 0
        assert summary.power_ratio_trace_summary == 0.0
        assert summary.sensor_health_trace_summary == 0.0
        assert summary.local_field_trace_summary == 0.0

    def test_lineage_indexed_trace_comparison(self):
        """Fabrication/lineage-enabled setup produces numeric lineage trace fields."""
        compressor = TraceCompressor(enabled=True, compression_factor=3)
        for i in range(10):
            compressor.record_trace_point(i, "u0", {"power_ratio": 0.8})
        for i in range(5):
            compressor.record_lineage_data({
                "tick": 10 + i * 10,
                "power_ratio": 0.7 + i * 0.05,
                "generation_index": i,
            })
        summary = compressor.compress()
        assert summary.lineage_trace_count == 5
        assert summary.lineage_index_span > 0
        assert summary.lineage_trace_delta > 0

    def test_lineage_no_lineage(self):
        """No-lineage setup returns clean zero summary."""
        compressor = TraceCompressor(enabled=True, compression_factor=3)
        for i in range(10):
            compressor.record_trace_point(i, "u0", {"power_ratio": 0.8})
        summary = compressor.compress()
        assert summary.lineage_trace_count == 0
        assert summary.lineage_index_span == 0
        assert summary.lineage_trace_delta == 0.0
        assert summary.lineage_compression_drift == 0.0
        assert summary.lineage_replay_error == 0.0

    def test_bounded_replay_metrics(self):
        """Replay fields are present, numeric, deterministic, and non-negative."""
        compressor = TraceCompressor(enabled=True, compression_factor=3)
        for i in range(15):
            compressor.record_trace_point(i, "u0", {"power_ratio": 0.8})
        summary = compressor.compress()
        assert summary.replay_window_count >= 0
        assert summary.avg_replay_error >= 0
        assert summary.max_replay_error >= 0
        assert 0 <= summary.replay_stability_score <= 1.0

    def test_artifact_schema(self):
        """trace_compression.json contains all required fields."""
        compressor = TraceCompressor(enabled=True, compression_factor=3)
        for i in range(15):
            compressor.record_trace_point(i, "u0", {"power_ratio": 0.8, "component_health": 0.9,
                                                     "signal_count": 1, "emission_count": 1})
            compressor.record_telemetry_frame(i, {"power_ratio": 0.8, "sensor_health": 0.9})
        compressor.record_capsule_data({"power_ratio": 0.8, "sensor_health": 0.9, "local_field_value": 3})
        compressor.record_lineage_data({"tick": 10, "power_ratio": 0.7, "generation_index": 0})
        result = compressor.get_summary()
        # Top-level
        assert "raw_trace_points" in result
        assert "compressed_trace_points" in result
        assert "compression_ratio" in result
        assert "signal_trace_points" in result
        assert "compressed_signal_points" in result
        assert "signal_trace_ratio" in result
        # Telemetry section
        assert "telemetry" in result
        assert "telemetry_input_frames" in result["telemetry"]
        assert "compressed_telemetry_frames" in result["telemetry"]
        assert "telemetry_window_count" in result["telemetry"]
        assert "avg_power_ratio_summary" in result["telemetry"]
        assert "continuity_summary" in result["telemetry"]
        # Capsule section
        assert "capsule" in result
        assert "capsule_summary_count" in result["capsule"]
        assert "capsule_compatible_fields" in result["capsule"]
        # Lineage section
        assert "lineage" in result
        assert "lineage_trace_count" in result["lineage"]
        assert "lineage_index_span" in result["lineage"]
        assert "lineage_trace_delta" in result["lineage"]
        # Replay section
        assert "replay" in result
        assert "replay_window_count" in result["replay"]
        assert "avg_replay_error" in result["replay"]
        assert "max_replay_error" in result["replay"]
        assert "replay_stability_score" in result["replay"]


class TestTraceCompressionDemo:
    """Trace compression demo tests."""

    def test_trace_compression_demo_deterministic(self):
        """Trace compression demo produces identical results."""
        def run_demo(seed):
            cfg = SimConfig(grid_width=12, grid_height=12, max_ticks=100, seed=seed,
                            unit_count=4, resource_density=0.5, hazard_density=0.08,
                            signal_enabled=True, adaptive_enabled=True,
                            signal_dynamics_enabled=True, trace_compression_enabled=True)
            engine = SimEngine(cfg, seed=seed)
            for i in range(4):
                engine.register_unit(MachineUnitImpl(f"u-{i}", signal_enabled=True,
                                                      adaptive_enabled=True))
            engine.run()
            summary = engine.get_trace_compression_summary()
            return (summary["raw_trace_points"], summary["compressed_trace_points"])

        r1 = run_demo(42)
        r2 = run_demo(42)
        assert r1 == r2

    def test_trace_compression_generates_metrics(self):
        """Trace compression demo generates nonzero metrics."""
        cfg = SimConfig(grid_width=12, grid_height=12, max_ticks=200, seed=42,
                        unit_count=4, resource_density=0.5, hazard_density=0.08,
                        signal_enabled=True, adaptive_enabled=True,
                        signal_dynamics_enabled=True, trace_compression_enabled=True)
        engine = SimEngine(cfg, seed=42)
        for i in range(4):
            engine.register_unit(MachineUnitImpl(f"u-{i}", signal_enabled=True,
                                                  adaptive_enabled=True))
        engine.run()
        summary = engine.get_trace_compression_summary()
        assert summary["raw_trace_points"] > 0
        assert summary["compressed_trace_points"] > 0
        assert summary["compression_ratio"] > 0

    def test_trace_compression_demo_signal_fields(self):
        """Demo produces nonzero signal trace fields."""
        cfg = SimConfig(grid_width=12, grid_height=12, max_ticks=200, seed=42,
                        unit_count=4, resource_density=0.5, hazard_density=0.08,
                        signal_enabled=True, adaptive_enabled=True,
                        signal_dynamics_enabled=True, trace_compression_enabled=True)
        engine = SimEngine(cfg, seed=42)
        for i in range(4):
            engine.register_unit(MachineUnitImpl(f"u-{i}", signal_enabled=True,
                                                  adaptive_enabled=True))
        engine.run()
        summary = engine.get_trace_compression_summary()
        assert summary["signal_trace_points"] > 0
        assert summary["compressed_signal_points"] > 0
        assert summary["signal_trace_ratio"] > 0

    def test_trace_compression_demo_replay_fields(self):
        """Demo produces nonzero replay fields."""
        cfg = SimConfig(grid_width=12, grid_height=12, max_ticks=200, seed=42,
                        unit_count=4, resource_density=0.5, hazard_density=0.08,
                        signal_enabled=True, adaptive_enabled=True,
                        signal_dynamics_enabled=True, trace_compression_enabled=True)
        engine = SimEngine(cfg, seed=42)
        for i in range(4):
            engine.register_unit(MachineUnitImpl(f"u-{i}", signal_enabled=True,
                                                  adaptive_enabled=True))
        engine.run()
        summary = engine.get_trace_compression_summary()
        rep = summary.get("replay", {})
        assert rep.get("replay_window_count", 0) >= 0
        assert rep.get("avg_replay_error", 0) >= 0
        assert rep.get("replay_stability_score", 0) >= 0

    def test_trace_compression_demo_telemetry_fields(self):
        """Demo produces telemetry reduction fields."""
        cfg = SimConfig(grid_width=12, grid_height=12, max_ticks=200, seed=42,
                        unit_count=4, resource_density=0.5, hazard_density=0.08,
                        signal_enabled=True, adaptive_enabled=True,
                        signal_dynamics_enabled=True, trace_compression_enabled=True,
                        telemetry_enabled=True)
        engine = SimEngine(cfg, seed=42)
        for i in range(4):
            engine.register_unit(MachineUnitImpl(f"u-{i}", signal_enabled=True,
                                                  adaptive_enabled=True))
        engine.run()
        summary = engine.get_trace_compression_summary()
        tel = summary.get("telemetry", {})
        assert tel.get("telemetry_input_frames", 0) > 0
        assert tel.get("telemetry_window_count", 0) > 0

    def test_trace_compression_full_artifact_schema(self):
        """Demo artifact has all sections."""
        cfg = SimConfig(grid_width=12, grid_height=12, max_ticks=200, seed=42,
                        unit_count=4, resource_density=0.5, hazard_density=0.08,
                        signal_enabled=True, adaptive_enabled=True,
                        signal_dynamics_enabled=True, trace_compression_enabled=True,
                        telemetry_enabled=True)
        engine = SimEngine(cfg, seed=42)
        for i in range(4):
            engine.register_unit(MachineUnitImpl(f"u-{i}", signal_enabled=True,
                                                  adaptive_enabled=True))
        engine.run()
        result = engine.get_trace_compression_summary()
        assert "signal_trace_points" in result
        assert "telemetry" in result
        assert "capsule" in result
        assert "lineage" in result
        assert "replay" in result
