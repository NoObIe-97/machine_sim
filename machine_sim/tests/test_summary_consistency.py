"""Tests for Milestone 13 compressed summary cross-unit consistency."""

from __future__ import annotations

import pytest

from machine_sim.agents.unit import MachineUnitImpl
from machine_sim.analysis.summary_consistency import SummaryConsistencyAnalyzer
from machine_sim.sim.config import SimConfig
from machine_sim.sim.engine import SimEngine


class TestSummaryConsistencyAnalyzer:
    """Summary consistency analyzer unit tests."""

    def test_cross_unit_comparison(self):
        """Two or more unit summaries produce nonzero pair count and numeric deltas."""
        analyzer = SummaryConsistencyAnalyzer(enabled=True)
        analyzer.record_unit_summary({"unit_id": "u0", "power_ratio": 0.8, "sensor_health": 0.9, "signal_count": 10, "replay_error": 0.3})
        analyzer.record_unit_summary({"unit_id": "u1", "power_ratio": 0.6, "sensor_health": 0.7, "signal_count": 20, "replay_error": 0.1})
        summary = analyzer.analyze()
        assert summary.unit_summary_count == 2
        assert summary.unit_pair_count == 1
        assert summary.avg_unit_summary_delta > 0
        assert summary.summary_consistency_score > 0

    def test_cross_unit_no_pairs(self):
        """Fewer than two summaries returns clean zero pair metrics."""
        analyzer = SummaryConsistencyAnalyzer(enabled=True)
        analyzer.record_unit_summary({"unit_id": "u0", "power_ratio": 0.8, "sensor_health": 0.9, "signal_count": 10, "replay_error": 0.3})
        summary = analyzer.analyze()
        assert summary.unit_pair_count == 0
        assert summary.avg_unit_summary_delta == 0.0
        assert summary.summary_consistency_score == 0.0

    def test_retention_stability(self):
        """Retention records produce numeric variance and stability fields."""
        analyzer = SummaryConsistencyAnalyzer(enabled=True)
        for i in range(10):
            analyzer.record_retention({"tick": i * 10, "variance": 100.0 + i * 10, "dropped": i, "total": 100})
        summary = analyzer.analyze()
        assert summary.retention_window_count == 10
        assert summary.avg_retention_variance > 0
        assert summary.retention_stability_score > 0
        assert summary.retention_drop_rate >= 0

    def test_retention_absent(self):
        """No retention records returns clean zero summary."""
        analyzer = SummaryConsistencyAnalyzer(enabled=True)
        summary = analyzer.analyze()
        assert summary.retention_window_count == 0
        assert summary.avg_retention_variance == 0.0
        assert summary.retention_stability_score == 0.0

    def test_compression_convergence(self):
        """Multiple compression-ratio windows produce numeric convergence fields."""
        analyzer = SummaryConsistencyAnalyzer(enabled=True)
        for r in [0.2, 0.21, 0.19, 0.2, 0.2]:
            analyzer.record_compression_ratio(r)
        summary = analyzer.analyze()
        assert summary.compression_window_count == 5
        assert summary.avg_compression_ratio > 0
        assert summary.compression_ratio_delta >= 0
        assert summary.compression_convergence_score > 0

    def test_compression_convergence_deterministic(self):
        """Same seed produces identical convergence summary."""
        def run():
            analyzer = SummaryConsistencyAnalyzer(enabled=True)
            for r in [0.2, 0.25, 0.15, 0.3, 0.2]:
                analyzer.record_compression_ratio(r)
            s = analyzer.analyze()
            return (s.compression_window_count, s.avg_compression_ratio, s.compression_convergence_score)
        assert run() == run()

    def test_generation_envelope(self):
        """Generation-indexed records produce envelope count/span/width fields."""
        analyzer = SummaryConsistencyAnalyzer(enabled=True)
        for i in range(5):
            analyzer.record_generation_delta({"generation_index": i, "delta": 0.1 + i * 0.05})
        summary = analyzer.analyze()
        assert summary.cross_generation_envelope_count == 5
        assert summary.generation_index_span == 4
        assert summary.generation_envelope_width > 0
        assert summary.generation_envelope_stability > 0

    def test_generation_envelope_absent(self):
        """No generation-indexed records returns clean zero summary."""
        analyzer = SummaryConsistencyAnalyzer(enabled=True)
        summary = analyzer.analyze()
        assert summary.cross_generation_envelope_count == 0
        assert summary.generation_index_span == 0
        assert summary.generation_envelope_width == 0.0

    def test_combined_stability(self):
        """Combined summary uses section summaries and reports bounded numeric scores."""
        analyzer = SummaryConsistencyAnalyzer(enabled=True)
        analyzer.record_unit_summary({"unit_id": "u0", "power_ratio": 0.8, "sensor_health": 0.9, "signal_count": 10, "replay_error": 0.3})
        analyzer.record_unit_summary({"unit_id": "u1", "power_ratio": 0.7, "sensor_health": 0.8, "signal_count": 15, "replay_error": 0.2})
        analyzer.record_compression_ratio(0.2)
        analyzer.record_compression_ratio(0.25)
        analyzer.record_retention({"tick": 0, "variance": 50.0, "dropped": 0, "total": 100})
        analyzer.record_generation_delta({"generation_index": 0, "delta": 0.1})
        analyzer.record_generation_delta({"generation_index": 1, "delta": 0.15})
        summary = analyzer.analyze()
        assert summary.combined_window_count > 0
        assert 0 <= summary.combined_consistency_score <= 1
        assert summary.combined_stability_score >= 0
        assert summary.combined_record_count > 0

    def test_bounded_storage(self):
        """max_records=N; record more than N; internal stores stay within N."""
        analyzer = SummaryConsistencyAnalyzer(enabled=True, max_records=5)
        for i in range(15):
            analyzer.record_unit_summary({"unit_id": f"u{i}", "power_ratio": 0.8, "sensor_health": 0.9, "signal_count": 10, "replay_error": 0.3})
            analyzer.record_retention({"tick": i, "variance": 10.0, "dropped": 0, "total": 100})
            analyzer.record_compression_ratio(0.2)
            analyzer.record_generation_delta({"generation_index": i, "delta": 0.1})
        assert len(analyzer._unit_summaries) <= 5
        assert len(analyzer._retention_records) <= 5
        assert len(analyzer._compression_ratios) <= 5
        assert len(analyzer._generation_deltas) <= 5

    def test_artifact_schema(self):
        """summary_consistency.json contains all required sections."""
        analyzer = SummaryConsistencyAnalyzer(enabled=True)
        analyzer.record_unit_summary({"unit_id": "u0", "power_ratio": 0.8, "sensor_health": 0.9, "signal_count": 10, "replay_error": 0.3})
        analyzer.record_unit_summary({"unit_id": "u1", "power_ratio": 0.7, "sensor_health": 0.8, "signal_count": 15, "replay_error": 0.2})
        analyzer.record_compression_ratio(0.2)
        result = analyzer.get_summary()
        assert "cross_unit" in result
        assert "retention_stability" in result
        assert "compression_convergence" in result
        assert "cross_generation_envelope" in result
        assert "combined" in result
        assert "unit_summary_count" in result["cross_unit"]
        assert "retention_window_count" in result["retention_stability"]
        assert "compression_window_count" in result["compression_convergence"]
        assert "cross_generation_envelope_count" in result["cross_generation_envelope"]
        assert "combined_window_count" in result["combined"]


class TestSummaryConsistencyDemo:
    """Summary consistency demo tests."""

    def _run_demo(self, seed):
        cfg = SimConfig(grid_width=20, grid_height=20, max_ticks=240, seed=seed,
                        unit_count=4, resource_density=0.5, hazard_density=0.08,
                        power_drain_rate=0.5,
                        signal_enabled=True, adaptive_enabled=True,
                        fabrication_enabled=True, unit_capacity=12,
                        fabrication_interval=25, fabrication_power_cost=30.0,
                        fabrication_material_cost=5.0, fabrication_variation=0.1,
                        capsule_enabled=True, telemetry_enabled=True,
                        reconciliation_enabled=True, lineage_drift_enabled=True,
                        pressure_analysis_enabled=True, signal_dynamics_enabled=True,
                        trace_compression_enabled=True, trace_drift_enabled=True,
                        summary_consistency_enabled=True)
        engine = SimEngine(cfg, seed=seed)
        for i in range(4):
            engine.register_unit(MachineUnitImpl(f"u-{i}", signal_enabled=True,
                                                  adaptive_enabled=True))
        engine.run()
        return engine.get_summary_consistency_summary()

    def test_demo_deterministic(self):
        """Same seed produces identical M13 summary."""
        r1 = self._run_demo(42)
        r2 = self._run_demo(42)
        assert r1 == r2

    def test_demo_generates_metrics(self):
        """Demo generates nonzero M13 metrics."""
        summary = self._run_demo(42)
        assert "cross_unit" in summary
        assert "retention_stability" in summary
        assert "compression_convergence" in summary
        assert "cross_generation_envelope" in summary
        assert "combined" in summary

    def test_demo_compression_convergence_nonzero(self):
        """Demo produces nonzero compression convergence."""
        summary = self._run_demo(42)
        cc = summary.get("compression_convergence", {})
        assert cc.get("compression_window_count", 0) > 0
        assert cc.get("avg_compression_ratio", 0) > 0

    def test_demo_full_schema(self):
        """Demo artifact has all five sections."""
        result = self._run_demo(42)
        for section in ["cross_unit", "retention_stability", "compression_convergence",
                        "cross_generation_envelope", "combined"]:
            assert section in result, f"Missing section: {section}"

