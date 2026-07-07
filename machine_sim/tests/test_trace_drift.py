"""Tests for Milestone 12 multi-generation trace drift and compression stability."""

from __future__ import annotations

import pytest

from machine_sim.agents.unit import MachineUnitImpl
from machine_sim.analysis.trace_drift import TraceDriftAnalyzer
from machine_sim.sim.config import SimConfig
from machine_sim.sim.engine import SimEngine


class TestTraceDriftAnalyzer:
    """Trace drift analyzer unit tests."""

    def test_generation_indexed_trace_deltas(self):
        """Enabled setup produces numeric generation trace counts and deltas."""
        analyzer = TraceDriftAnalyzer(enabled=True)
        for i in range(5):
            analyzer.record_generation_trace({
                "generation_index": i,
                "power_ratio": 0.7 + i * 0.05,
                "tick": i * 10,
            })
        summary = analyzer.analyze()
        assert summary.generation_trace_count == 5
        assert summary.generation_index_span == 4
        assert summary.avg_generation_trace_delta > 0
        assert summary.max_generation_trace_delta > 0
        assert summary.lineage_trace_delta_count > 0

    def test_generation_no_records(self):
        """No-generation setup returns clean zero summary."""
        analyzer = TraceDriftAnalyzer(enabled=True)
        summary = analyzer.analyze()
        assert summary.generation_trace_count == 0
        assert summary.generation_index_span == 0
        assert summary.avg_generation_trace_delta == 0.0
        assert summary.max_generation_trace_delta == 0.0
        assert summary.lineage_trace_delta_count == 0

    def test_drift_envelope_fields(self):
        """Drift envelope fields are present, numeric, bounded, non-negative."""
        analyzer = TraceDriftAnalyzer(enabled=True)
        for i in range(5):
            analyzer.record_envelope({
                "power_ratio": 0.6 + i * 0.05,
                "sensor_health": 0.8 + i * 0.02,
                "signal_count": 10 + i * 2,
                "envelope_width": 0.1 + i * 0.05,
            })
        summary = analyzer.analyze()
        assert summary.drift_envelope_count == 5
        assert summary.avg_drift_envelope_width > 0
        assert summary.max_drift_envelope_width > 0
        assert summary.power_ratio_drift_range >= 0
        assert summary.sensor_health_drift_range >= 0
        assert summary.signal_trace_drift_range >= 0

    def test_drift_envelope_deterministic(self):
        """Same seed produces identical envelope summary."""
        def run_drift():
            analyzer = TraceDriftAnalyzer(enabled=True)
            for i in range(10):
                analyzer.record_envelope({
                    "power_ratio": 0.5 + i * 0.03,
                    "sensor_health": 0.8 + i * 0.01,
                    "signal_count": 10 + i,
                    "envelope_width": 0.05 + i * 0.02,
                })
            s = analyzer.analyze()
            return (s.drift_envelope_count, s.avg_drift_envelope_width, s.max_drift_envelope_width)
        assert run_drift() == run_drift()

    def test_replay_error_stability(self):
        """Uses replay metrics, produces numeric stability fields."""
        analyzer = TraceDriftAnalyzer(enabled=True)
        for i in range(10):
            analyzer.record_replay({
                "tick": i * 10,
                "replay_error": 0.3 + (i % 3) * 0.05,
            })
        summary = analyzer.analyze()
        assert summary.replay_error_window_count == 10
        assert summary.avg_replay_error_delta >= 0
        assert summary.max_replay_error_delta >= 0
        assert summary.replay_stability_floor >= 0
        assert summary.replay_stability_variance >= 0

    def test_replay_absent(self):
        """Safe zero output when replay metrics are absent."""
        analyzer = TraceDriftAnalyzer(enabled=True)
        summary = analyzer.analyze()
        assert summary.replay_error_window_count == 0
        assert summary.avg_replay_error_delta == 0.0
        assert summary.replay_stability_floor == 0.0

    def test_capsule_trace_compatibility(self):
        """Capsule-enabled setup produces numeric compatibility fields."""
        analyzer = TraceDriftAnalyzer(enabled=True)
        for i in range(5):
            analyzer.record_capsule_trace({
                "power_delta": 0.1 + i * 0.02,
                "sensor_delta": 0.05 + i * 0.01,
                "field_delta": 0.02 + i * 0.01,
                "compatibility_score": 0.9 - i * 0.05,
            })
        summary = analyzer.analyze()
        assert summary.capsule_trace_check_count == 5
        assert summary.capsule_trace_power_delta > 0
        assert summary.capsule_trace_sensor_delta > 0
        assert summary.capsule_trace_compatibility_score > 0

    def test_capsule_trace_disabled(self):
        """Capsule-disabled setup returns clean zero summary."""
        analyzer = TraceDriftAnalyzer(enabled=True)
        summary = analyzer.analyze()
        assert summary.capsule_trace_check_count == 0
        assert summary.capsule_trace_power_delta == 0.0
        assert summary.capsule_trace_compatibility_score == 0.0

    def test_retention_bounded(self):
        """max_records=N; record more than N; internal stores stay within N."""
        analyzer = TraceDriftAnalyzer(enabled=True, max_records=5)
        for i in range(20):
            analyzer.record_generation_trace({"generation_index": i, "power_ratio": 0.5, "tick": i})
            analyzer.record_envelope({"power_ratio": 0.5, "sensor_health": 0.8, "signal_count": 10, "envelope_width": 0.1})
            analyzer.record_replay({"tick": i, "replay_error": 0.3})
            analyzer.record_capsule_trace({"power_delta": 0.1, "sensor_delta": 0.05, "field_delta": 0.02, "compatibility_score": 0.9})
        assert len(analyzer._generation_records) <= 5
        assert len(analyzer._envelope_records) <= 5
        assert len(analyzer._replay_records) <= 5
        assert len(analyzer._capsule_trace_records) <= 5

    def test_retention_metrics(self):
        """Retention metrics report retained/dropped counts."""
        analyzer = TraceDriftAnalyzer(enabled=True, retention_window=10, max_records=50)
        for i in range(30):
            analyzer._retention_records.append({"tick": i, "unit_id": "u0"})
        summary = analyzer.analyze()
        assert summary.retention_record_count == 30
        assert summary.retained_summary_count > 0
        assert summary.retention_compression_ratio > 0

    def test_artifact_schema(self):
        """trace_drift.json contains all required sections."""
        analyzer = TraceDriftAnalyzer(enabled=True)
        analyzer.record_generation_trace({"generation_index": 0, "power_ratio": 0.7, "tick": 0})
        analyzer.record_generation_trace({"generation_index": 1, "power_ratio": 0.75, "tick": 10})
        analyzer.record_envelope({"power_ratio": 0.6, "sensor_health": 0.8, "signal_count": 10, "envelope_width": 0.1})
        analyzer.record_replay({"tick": 0, "replay_error": 0.3})
        analyzer.record_capsule_trace({"power_delta": 0.1, "sensor_delta": 0.05, "field_delta": 0.02, "compatibility_score": 0.9})
        result = analyzer.get_summary()
        assert "generation" in result
        assert "drift_envelope" in result
        assert "replay_stability" in result
        assert "capsule_trace" in result
        assert "retention" in result
        assert "generation_trace_count" in result["generation"]
        assert "drift_envelope_count" in result["drift_envelope"]
        assert "replay_error_window_count" in result["replay_stability"]
        assert "capsule_trace_check_count" in result["capsule_trace"]
        assert "retention_record_count" in result["retention"]


class TestTraceDriftDemo:
    """Trace drift demo tests."""

    def test_trace_drift_demo_deterministic(self):
        """Same seed produces identical M12 summary."""
        def run_demo(seed):
            cfg = SimConfig(grid_width=20, grid_height=20, max_ticks=220, seed=seed,
                            unit_count=3, resource_density=0.5, hazard_density=0.08,
                            power_drain_rate=0.5,
                            signal_enabled=True, adaptive_enabled=True,
                            fabrication_enabled=True, unit_capacity=12,
                            fabrication_interval=25, fabrication_power_cost=30.0,
                            fabrication_material_cost=5.0, fabrication_variation=0.1,
                            capsule_enabled=True, telemetry_enabled=True,
                            reconciliation_enabled=True, lineage_drift_enabled=True,
                            pressure_analysis_enabled=True, signal_dynamics_enabled=True,
                            trace_compression_enabled=True, trace_drift_enabled=True)
            engine = SimEngine(cfg, seed=seed)
            for i in range(3):
                engine.register_unit(MachineUnitImpl(f"u-{i}", signal_enabled=True,
                                                      adaptive_enabled=True))
            engine.run()
            return engine.get_trace_drift_summary()

        r1 = run_demo(42)
        r2 = run_demo(42)
        assert r1 == r2

    def test_trace_drift_demo_generates_metrics(self):
        """Demo generates nonzero trace drift metrics."""
        cfg = SimConfig(grid_width=20, grid_height=20, max_ticks=220, seed=42,
                        unit_count=3, resource_density=0.5, hazard_density=0.08,
                        power_drain_rate=0.5,
                        signal_enabled=True, adaptive_enabled=True,
                        fabrication_enabled=True, unit_capacity=12,
                        fabrication_interval=25, fabrication_power_cost=30.0,
                        fabrication_material_cost=5.0, fabrication_variation=0.1,
                        capsule_enabled=True, telemetry_enabled=True,
                        reconciliation_enabled=True, lineage_drift_enabled=True,
                        pressure_analysis_enabled=True, signal_dynamics_enabled=True,
                        trace_compression_enabled=True, trace_drift_enabled=True)
        engine = SimEngine(cfg, seed=42)
        for i in range(3):
            engine.register_unit(MachineUnitImpl(f"u-{i}", signal_enabled=True,
                                                  adaptive_enabled=True))
        engine.run()
        summary = engine.get_trace_drift_summary()
        assert "generation" in summary
        assert "drift_envelope" in summary
        assert "replay_stability" in summary
        assert "capsule_trace" in summary
        assert "retention" in summary

    def test_trace_drift_demo_envelope_nonzero(self):
        """Demo produces nonzero drift envelope from trace compression segments."""
        cfg = SimConfig(grid_width=20, grid_height=20, max_ticks=220, seed=42,
                        unit_count=3, resource_density=0.5, hazard_density=0.08,
                        power_drain_rate=0.5,
                        signal_enabled=True, adaptive_enabled=True,
                        fabrication_enabled=True, unit_capacity=12,
                        fabrication_interval=25, fabrication_power_cost=30.0,
                        fabrication_material_cost=5.0, fabrication_variation=0.1,
                        capsule_enabled=True, telemetry_enabled=True,
                        reconciliation_enabled=True, lineage_drift_enabled=True,
                        pressure_analysis_enabled=True, signal_dynamics_enabled=True,
                        trace_compression_enabled=True, trace_drift_enabled=True)
        engine = SimEngine(cfg, seed=42)
        for i in range(3):
            engine.register_unit(MachineUnitImpl(f"u-{i}", signal_enabled=True,
                                                  adaptive_enabled=True))
        engine.run()
        summary = engine.get_trace_drift_summary()
        env = summary.get("drift_envelope", {})
        assert env.get("drift_envelope_count", 0) > 0
        assert env.get("avg_drift_envelope_width", 0) > 0

    def test_trace_drift_demo_full_schema(self):
        """Demo artifact has all five sections."""
        cfg = SimConfig(grid_width=20, grid_height=20, max_ticks=220, seed=42,
                        unit_count=3, resource_density=0.5, hazard_density=0.08,
                        power_drain_rate=0.5,
                        signal_enabled=True, adaptive_enabled=True,
                        fabrication_enabled=True, unit_capacity=12,
                        fabrication_interval=25, fabrication_power_cost=30.0,
                        fabrication_material_cost=5.0, fabrication_variation=0.1,
                        capsule_enabled=True, telemetry_enabled=True,
                        reconciliation_enabled=True, lineage_drift_enabled=True,
                        pressure_analysis_enabled=True, signal_dynamics_enabled=True,
                        trace_compression_enabled=True, trace_drift_enabled=True)
        engine = SimEngine(cfg, seed=42)
        for i in range(3):
            engine.register_unit(MachineUnitImpl(f"u-{i}", signal_enabled=True,
                                                  adaptive_enabled=True))
        engine.run()
        result = engine.get_trace_drift_summary()
        for section in ["generation", "drift_envelope", "replay_stability", "capsule_trace", "retention"]:
            assert section in result, f"Missing section: {section}"

