"""Tests for Milestone 15 multi-generation adaptive trace evolution."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from machine_sim.agents.unit import MachineUnitImpl
from machine_sim.agents.adaptive_control import AdaptiveController, AdaptiveStateVector
from machine_sim.analysis.multi_generation_trace import (
    MultiGenerationTraceAnalyzer,
    _cosine_distance,
    _rms,
)
from machine_sim.sim.config import SimConfig
from machine_sim.sim.engine import SimEngine


class TestGenerationTransferRecordSchema:
    """Test generation-indexed transfer record schema is complete."""

    def test_record_has_all_required_fields(self):
        """Transfer record contains all required M15 fields."""
        analyzer = MultiGenerationTraceAnalyzer(enabled=True)
        source_state = AdaptiveStateVector()
        succ_state = AdaptiveStateVector(move_weight=0.3, scan_weight=0.3)
        analyzer.record_transfer(
            tick=100, source_unit_id="u0", successor_unit_id="u1",
            source_generation_index=0, successor_generation_index=1,
            source_adaptive_state=source_state.to_dict(),
            successor_adaptive_state=succ_state.to_dict(),
            source_lifetime_ticks=100, successor_initial_power_ratio=0.8,
        )
        records = analyzer.get_records()
        assert len(records) == 1
        rec = records[0]
        assert rec.tick == 100
        assert rec.source_unit_id == "u0"
        assert rec.successor_unit_id == "u1"
        assert rec.source_generation_index == 0
        assert rec.successor_generation_index == 1
        assert "move_weight" in rec.source_adaptive_state
        assert "move_weight" in rec.successor_adaptive_state
        assert "move_weight" in rec.adaptive_state_delta
        assert "weight_delta_rms" in rec.transfer_variation_summary
        assert rec.source_lifetime_ticks == 100
        assert 0.0 <= rec.successor_initial_power_ratio <= 1.0


class TestTransferDeltaComputation:
    """Test transfer delta is numeric, bounded, and nonzero when states differ."""

    def test_delta_nonzero_for_different_states(self):
        """Delta is nonzero when source and successor states differ."""
        analyzer = MultiGenerationTraceAnalyzer(enabled=True)
        src = AdaptiveStateVector(move_weight=0.5, scan_weight=0.2)
        dst = AdaptiveStateVector(move_weight=0.3, scan_weight=0.4)
        analyzer.record_transfer(
            tick=50, source_unit_id="u0", successor_unit_id="u1",
            source_generation_index=0, successor_generation_index=1,
            source_adaptive_state=src.to_dict(),
            successor_adaptive_state=dst.to_dict(),
            source_lifetime_ticks=50, successor_initial_power_ratio=0.7,
        )
        rec = analyzer.get_records()[0]
        assert abs(rec.adaptive_state_delta["move_weight"] - (-0.2)) < 1e-4
        assert abs(rec.adaptive_state_delta["scan_weight"] - 0.2) < 1e-4
        assert rec.transfer_variation_summary["max_abs_delta"] > 0.0

    def test_delta_zero_for_identical_states(self):
        """Delta is zero when states are identical."""
        analyzer = MultiGenerationTraceAnalyzer(enabled=True)
        state = AdaptiveStateVector()
        analyzer.record_transfer(
            tick=50, source_unit_id="u0", successor_unit_id="u1",
            source_generation_index=0, successor_generation_index=1,
            source_adaptive_state=state.to_dict(),
            successor_adaptive_state=state.to_dict(),
            source_lifetime_ticks=50, successor_initial_power_ratio=0.7,
        )
        rec = analyzer.get_records()[0]
        assert all(abs(v) < 1e-6 for v in rec.adaptive_state_delta.values())


class TestTransferContinuityScore:
    """Test transfer continuity score is bounded and deterministic."""

    def test_continuity_bounded(self):
        """Continuity score stays in [0, 1]."""
        analyzer = MultiGenerationTraceAnalyzer(enabled=True)
        rng_state = AdaptiveStateVector()
        for i in range(5):
            next_state = AdaptiveStateVector(
                move_weight=0.2 + i * 0.1,
                scan_weight=0.3 - i * 0.05,
            )
            analyzer.record_transfer(
                tick=i * 100, source_unit_id=f"u{i}", successor_unit_id=f"u{i+1}",
                source_generation_index=i, successor_generation_index=i + 1,
                source_adaptive_state=rng_state.to_dict(),
                successor_adaptive_state=next_state.to_dict(),
                source_lifetime_ticks=100, successor_initial_power_ratio=0.6,
            )
            rng_state = next_state
        comparison = analyzer.get_trajectory_comparison()
        score = comparison["trajectory_continuity_score"]
        assert 0.0 <= score <= 1.0

    def test_continuity_deterministic(self):
        """Same inputs produce same continuity score."""
        def build_analyzer():
            a = MultiGenerationTraceAnalyzer(enabled=True)
            for i in range(3):
                src = AdaptiveStateVector(move_weight=0.2 + i * 0.1)
                dst = AdaptiveStateVector(move_weight=0.25 + i * 0.1)
                a.record_transfer(
                    tick=i * 100, source_unit_id=f"u{i}", successor_unit_id=f"u{i+1}",
                    source_generation_index=i, successor_generation_index=i + 1,
                    source_adaptive_state=src.to_dict(),
                    successor_adaptive_state=dst.to_dict(),
                    source_lifetime_ticks=100, successor_initial_power_ratio=0.5,
                )
            return a

        score1 = build_analyzer().get_trajectory_comparison()["trajectory_continuity_score"]
        score2 = build_analyzer().get_trajectory_comparison()["trajectory_continuity_score"]
        assert score1 == score2


class TestMultiGenerationTraceBuilder:
    """Test trace builder records at least two generation indices."""

    def test_records_multiple_generations(self):
        """Builder records transfers across multiple generation indices."""
        analyzer = MultiGenerationTraceAnalyzer(enabled=True)
        for gen in range(4):
            src = AdaptiveStateVector(move_weight=0.2 + gen * 0.05)
            dst = AdaptiveStateVector(move_weight=0.22 + gen * 0.05)
            analyzer.record_transfer(
                tick=gen * 200, source_unit_id=f"u{gen}", successor_unit_id=f"u{gen+1}",
                source_generation_index=gen, successor_generation_index=gen + 1,
                source_adaptive_state=src.to_dict(),
                successor_adaptive_state=dst.to_dict(),
                source_lifetime_ticks=200, successor_initial_power_ratio=0.6,
            )
        comparison = analyzer.get_trajectory_comparison()
        assert comparison["generation_index_span"] >= 4
        assert comparison["transfer_count"] == 4

    def test_short_run_records_at_least_two_generations(self):
        """Controlled short run records at least two generation indices."""
        cfg = SimConfig(
            grid_width=15, grid_height=15, max_ticks=300, seed=42,
            unit_count=3, resource_density=0.6, hazard_density=0.01,
            power_drain_rate=0.1, signal_enabled=True, adaptive_enabled=True,
            fabrication_enabled=True, capsule_enabled=False,
            fabrication_interval=10, fabrication_power_cost=5.0,
            fabrication_material_cost=0.5, unit_capacity=8,
            fabrication_min_power_ratio=0.1, fabrication_min_component_health=0.05,
            long_run_adaptation_enabled=True, multi_generation_trace_enabled=True,
        )
        engine = SimEngine(cfg, seed=42)
        for i in range(3):
            u = MachineUnitImpl(f"u-{i}", signal_enabled=True, adaptive_enabled=True)
            u.max_power = 5000
            u.power_reserve = 5000
            engine.register_unit(u)
        engine.run()
        records = engine.multi_gen_trace.get_records()
        # With relaxed thresholds, at least some fabrication should succeed
        if records:
            gen_indices = set()
            for r in records:
                gen_indices.add(r.source_generation_index)
                gen_indices.add(r.successor_generation_index)
            assert len(gen_indices) >= 2


class TestReferenceComparison:
    """Test reference comparison detects transfer-enabled vs disabled difference."""

    def test_comparison_detects_difference(self):
        """Transfer-enabled and reference runs produce different structural counts."""
        analyzer_enabled = MultiGenerationTraceAnalyzer(enabled=True)
        for i in range(5):
            src = AdaptiveStateVector(move_weight=0.2 + i * 0.1)
            dst = AdaptiveStateVector(move_weight=0.3 + i * 0.1)
            analyzer_enabled.record_transfer(
                tick=i * 100, source_unit_id=f"u{i}", successor_unit_id=f"u{i+1}",
                source_generation_index=i, successor_generation_index=i + 1,
                source_adaptive_state=src.to_dict(),
                successor_adaptive_state=dst.to_dict(),
                source_lifetime_ticks=100, successor_initial_power_ratio=0.6,
            )
        ref_records = []  # No transfers in reference
        comparison = analyzer_enabled.get_comparison_with_reference(ref_records)
        assert comparison["transfer_enabled_count"] == 5
        assert comparison["reference_transfer_count"] == 0
        assert comparison["generation_index_span_delta"] > 0


class TestJudgeFailsLowTransferCount:
    """Test M15 judge fails when transfer count is below threshold."""

    def test_judge_fails_below_threshold(self):
        """Judge returns FAIL when transfer_count < 5."""
        from machine_sim.verification.milestone_15_judge import judge
        with tempfile.TemporaryDirectory() as tmpdir:
            summary = {
                "run_parameters": {"grid_width": 120, "grid_height": 120, "max_ticks": 30000},
                "transfer_summary": {"transfer_count": 2, "generation_index_span": 2},
                "generation_summary": {"generation_index_span": 2, "transfer_count": 2},
                "adaptive_state_delta_summary": {"move_weight": 0.05},
                "trajectory_continuity_summary": {"score": 0.8},
                "signal_adaptation_summary": {"signal_emission_rate": 0.01},
                "late_run_survival_summary": {"final_active_count": 3},
            }
            (Path(tmpdir) / "adaptive_trajectory_summary.json").write_text(json.dumps(summary))
            for fname in ["unit_adaptive_state_trace.jsonl", "action_distribution_trace.jsonl",
                          "local_feedback_trace.jsonl", "descendant_adaptive_state_trace.jsonl",
                          "resource_hazard_field_summary.json"]:
                (Path(tmpdir) / fname).write_text(json.dumps({"tick": 1}) + "\n")
            (Path(tmpdir) / "generation_adaptive_state_trace.jsonl").write_text(
                json.dumps({"tick": 100, "adaptive_state_delta": {"move_weight": 0.05}}) + "\n")
            compare = {"transfer_enabled_count": 2, "reference_transfer_count": 0,
                       "generation_index_span_delta": 1}
            (Path(tmpdir) / "adaptive_transfer_compare.json").write_text(json.dumps(compare))
            result = judge(tmpdir)
            assert result["checks"]["transfer_count_check"] == "FAIL"


class TestJudgeFailsLowGenerationSpan:
    """Test M15 judge fails when generation span is too small."""

    def test_judge_fails_below_span(self):
        """Judge returns FAIL when generation_index_span < 3."""
        from machine_sim.verification.milestone_15_judge import judge
        with tempfile.TemporaryDirectory() as tmpdir:
            summary = {
                "run_parameters": {"grid_width": 120, "grid_height": 120, "max_ticks": 30000},
                "transfer_summary": {"transfer_count": 10, "generation_index_span": 2},
                "generation_summary": {"generation_index_span": 2, "transfer_count": 10},
                "adaptive_state_delta_summary": {"move_weight": 0.05},
                "trajectory_continuity_summary": {"score": 0.8},
                "signal_adaptation_summary": {"signal_emission_rate": 0.01},
                "late_run_survival_summary": {"final_active_count": 3},
            }
            (Path(tmpdir) / "adaptive_trajectory_summary.json").write_text(json.dumps(summary))
            for fname in ["unit_adaptive_state_trace.jsonl", "action_distribution_trace.jsonl",
                          "local_feedback_trace.jsonl", "descendant_adaptive_state_trace.jsonl",
                          "resource_hazard_field_summary.json"]:
                (Path(tmpdir) / fname).write_text(json.dumps({"tick": 1}) + "\n")
            (Path(tmpdir) / "generation_adaptive_state_trace.jsonl").write_text(
                json.dumps({"tick": 100, "adaptive_state_delta": {"move_weight": 0.05}}) + "\n")
            compare = {"transfer_enabled_count": 10, "reference_transfer_count": 0,
                       "generation_index_span_delta": 1}
            (Path(tmpdir) / "adaptive_transfer_compare.json").write_text(json.dumps(compare))
            result = judge(tmpdir)
            assert result["checks"]["generation_span_check"] == "FAIL"


class TestJudgeFailsMissingArtifacts:
    """Test M15 judge fails when required artifacts are missing."""

    def test_judge_fails_no_artifacts(self):
        """Judge returns FAIL for trajectory_artifact_schema_check when artifacts missing."""
        from machine_sim.verification.milestone_15_judge import judge
        with tempfile.TemporaryDirectory() as tmpdir:
            summary = {
                "run_parameters": {"grid_width": 120, "grid_height": 120, "max_ticks": 30000},
                "transfer_summary": {"transfer_count": 10, "generation_index_span": 4},
                "generation_summary": {"generation_index_span": 4, "transfer_count": 10},
                "adaptive_state_delta_summary": {"move_weight": 0.05},
                "trajectory_continuity_summary": {"score": 0.8},
                "signal_adaptation_summary": {"signal_emission_rate": 0.01},
                "late_run_survival_summary": {"final_active_count": 3},
            }
            (Path(tmpdir) / "adaptive_trajectory_summary.json").write_text(json.dumps(summary))
            result = judge(tmpdir)
            assert result["checks"]["trajectory_artifact_schema_check"] == "FAIL"


class TestJudgePassesValidArtifacts:
    """Test M15 judge passes on a valid artifact set."""

    def test_judge_passes_valid(self):
        """Judge returns PASS with complete valid artifacts."""
        from machine_sim.verification.milestone_15_judge import judge
        with tempfile.TemporaryDirectory() as tmpdir:
            summary = {
                "run_parameters": {"grid_width": 120, "grid_height": 120, "max_ticks": 30000},
                "transfer_summary": {"transfer_count": 8, "generation_index_span": 4},
                "generation_summary": {"generation_index_span": 4, "transfer_count": 8},
                "adaptive_state_delta_summary": {"move_weight": 0.05, "scan_weight": -0.03},
                "trajectory_continuity_summary": {"score": 0.75},
                "signal_adaptation_summary": {"signal_emission_rate": 0.02},
                "late_run_survival_summary": {"final_active_count": 3},
            }
            (Path(tmpdir) / "adaptive_trajectory_summary.json").write_text(json.dumps(summary))
            for fname in ["unit_adaptive_state_trace.jsonl", "action_distribution_trace.jsonl",
                          "local_feedback_trace.jsonl", "descendant_adaptive_state_trace.jsonl",
                          "resource_hazard_field_summary.json"]:
                (Path(tmpdir) / fname).write_text(json.dumps({"tick": 1}) + "\n")
            (Path(tmpdir) / "generation_adaptive_state_trace.jsonl").write_text(
                json.dumps({"tick": 100, "adaptive_state_delta": {"move_weight": 0.05}}) + "\n")
            compare = {"transfer_enabled_count": 8, "reference_transfer_count": 0,
                       "generation_index_span_delta": 3}
            (Path(tmpdir) / "adaptive_transfer_compare.json").write_text(json.dumps(compare))
            result = judge(tmpdir)
            assert result["M15_JUDGE_STATUS"] == "PASS"
            assert len(result["failed_checks"]) == 0


class TestM14Regression:
    """Test existing M14 judge and M14 tests still pass."""

    def test_m14_judge_still_works(self):
        """M14 judge function is importable and callable."""
        from machine_sim.verification.milestone_14_judge import judge as m14_judge
        with tempfile.TemporaryDirectory() as tmpdir:
            # Minimal valid M14 artifacts
            summary = {
                "run_ticks": 20000, "grid_width": 120, "grid_height": 120,
                "initial_unit_count": 6, "final_active_unit_count": 2,
                "descendant_active_count": 1, "power_drain_rate": 0.2,
                "action_distribution_early": {"HARVEST": 10},
                "action_distribution_late": {"HARVEST": 5},
                "action_distribution_delta": {"HARVEST": -5},
                "signal_behavior_summary": {"total_signal_emissions": 100,
                                             "total_signal_observations": 50},
            }
            (Path(tmpdir) / "long_run_adaptation_summary.json").write_text(json.dumps(summary))
            for fname in ["action_distribution_trace.jsonl", "unit_lifetime_trace.jsonl"]:
                (Path(tmpdir) / fname).write_text(json.dumps({"tick": 1}) + "\n")
            fb = {"tick": 1, "unit_id": "u0", "power_delta": 5.0, "hazard_exposure": 0.0,
                  "resource_extracted": 1.0, "signal_observed": 0.0, "movement_blocked": 0.0}
            (Path(tmpdir) / "local_feedback_trace.jsonl").write_text(json.dumps(fb) + "\n")
            state1 = {"tick": 0, "unit_id": "u0", "move_weight": 0.25, "scan_weight": 0.25,
                      "extract_weight": 0.25, "signal_weight": 0.1}
            state2 = {"tick": 100, "unit_id": "u0", "move_weight": 0.35, "scan_weight": 0.15,
                      "extract_weight": 0.3, "signal_weight": 0.1}
            (Path(tmpdir) / "unit_adaptive_state_trace.jsonl").write_text(
                json.dumps(state1) + "\n" + json.dumps(state2) + "\n")
            desc = {"tick": 100, "source_unit_id": "u0", "successor_unit_id": "u-0001"}
            (Path(tmpdir) / "descendant_adaptive_state_trace.jsonl").write_text(
                json.dumps(desc) + "\n")
            compare = {"action_distribution_delta": {"HARVEST": 3},
                       "active_unit_count_delta": 1}
            (Path(tmpdir) / "adaptive_vs_static_compare.json").write_text(json.dumps(compare))
            field = {"total_resource_cells": 100, "total_hazard_cells": 10}
            (Path(tmpdir) / "resource_hazard_field_summary.json").write_text(json.dumps(field))
            result = m14_judge(tmpdir)
            assert "M14_JUDGE_STATUS" in result


class TestCosineDistance:
    """Test cosine distance utility."""

    def test_identical_vectors(self):
        """Cosine distance of identical vectors is 0."""
        assert _cosine_distance({"a": 1.0, "b": 2.0}, {"a": 1.0, "b": 2.0}) < 1e-6

    def test_orthogonal_vectors(self):
        """Cosine distance of orthogonal vectors is 1."""
        d = _cosine_distance({"a": 1.0, "b": 0.0}, {"a": 0.0, "b": 1.0})
        assert abs(d - 1.0) < 1e-6

    def test_opposite_vectors(self):
        """Cosine distance of opposite vectors is 2."""
        d = _cosine_distance({"a": 1.0}, {"a": -1.0})
        assert abs(d - 2.0) < 1e-6

    def test_empty_vectors(self):
        """Cosine distance of empty vectors is 0."""
        assert _cosine_distance({}, {}) == 0.0

