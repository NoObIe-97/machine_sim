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
