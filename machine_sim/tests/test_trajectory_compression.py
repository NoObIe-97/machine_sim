"""Tests for Milestone 16 adaptive trajectory compression."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from machine_sim.analysis.adaptive_trajectory_compression import (
    AdaptiveTrajectoryCompressor,
    CompressedSegment,
    compare_trajectories,
    load_jsonl,
    _mean,
    _rms,
    _cosine_distance,
)


def _make_transfer_record(tick, gen_src=0, gen_succ=1, delta_override=None):
    """Create a synthetic transfer record for testing."""
    src_state = {"move_weight": 0.25, "scan_weight": 0.25, "extract_weight": 0.25,
                 "signal_weight": 0.1, "conserve_weight": 0.15}
    succ_state = {"move_weight": 0.3, "scan_weight": 0.2, "extract_weight": 0.3,
                  "signal_weight": 0.1, "conserve_weight": 0.1}
    delta = {k: succ_state[k] - src_state[k] for k in src_state}
    if delta_override:
        delta.update(delta_override)
    return {
        "tick": tick,
        "source_unit_id": f"u{gen_src}",
        "successor_unit_id": f"u{gen_succ}",
        "source_generation_index": gen_src,
        "successor_generation_index": gen_succ,
        "source_adaptive_state_summary": src_state,
        "successor_adaptive_state_summary": succ_state,
        "adaptive_state_delta": delta,
        "transfer_variation_summary": {"weight_delta_rms": 0.05, "max_abs_delta": 0.1},
        "source_lifetime_ticks_at_transfer": 100,
        "successor_initial_power_ratio": 0.8,
    }


class TestCompressorCreatesBoundedSegments:
    """Test trajectory compressor creates bounded segments from synthetic traces."""

    def test_creates_segments_from_records(self):
        """Compressor produces segments from transfer records."""
        compressor = AdaptiveTrajectoryCompressor(max_segments=8)
        records = [_make_transfer_record(i * 100, gen_src=i, gen_succ=i + 1) for i in range(10)]
        compressor.load_transfer_records(records)
        segments = compressor.compress()
        assert len(segments) > 0
        assert len(segments) <= 8

    def test_single_record_produces_one_segment(self):
        """A single transfer record produces exactly one segment."""
        compressor = AdaptiveTrajectoryCompressor(max_segments=10)
        compressor.load_transfer_records([_make_transfer_record(100)])
        segments = compressor.compress()
        assert len(segments) == 1

    def test_bounded_by_max_segments(self):
        """Segment count never exceeds max_segments."""
        compressor = AdaptiveTrajectoryCompressor(max_segments=3)
        records = [_make_transfer_record(i * 50) for i in range(20)]
        compressor.load_transfer_records(records)
        segments = compressor.compress()
        assert len(segments) <= 3


class TestSegmentSummaryFields:
    """Test segment summaries include all required fields."""

    def test_segment_has_all_fields(self):
        """Segment contains generation range, transfer count, state summary, action summary, signature."""
        compressor = AdaptiveTrajectoryCompressor(max_segments=4)
        records = [_make_transfer_record(i * 100, gen_src=i, gen_succ=i + 1) for i in range(8)]
        compressor.load_transfer_records(records)
        compressor.load_action_trace([
            {"tick": 50, "unit_id": "u0", "action": "HARVEST"},
            {"tick": 150, "unit_id": "u1", "action": "SCAN"},
            {"tick": 250, "unit_id": "u2", "action": "MOVE"},
        ])
        compressor.load_feedback_trace([
            {"tick": 50, "unit_id": "u0", "power_delta": 5.0, "hazard_exposure": 0.0},
        ])
        segments = compressor.compress()
        assert len(segments) > 0
        seg = segments[0]
        assert isinstance(seg.segment_index, int)
        assert isinstance(seg.start_tick, int)
        assert isinstance(seg.end_tick, int)
        assert isinstance(seg.generation_index_min, int)
        assert isinstance(seg.generation_index_max, int)
        assert isinstance(seg.transfer_count, int)
        assert isinstance(seg.avg_adaptive_state, dict)
        assert isinstance(seg.adaptive_state_range, dict)
        assert isinstance(seg.avg_transfer_delta, dict)
        assert isinstance(seg.max_transfer_delta, dict)
        assert isinstance(seg.action_distribution_summary, dict)
        assert isinstance(seg.signal_parameter_summary, dict)
        assert isinstance(seg.segment_signature, str)
        assert len(seg.segment_signature) > 0


class TestCompressionRatio:
    """Test compression ratio calculation is numeric and bounded."""

    def test_ratio_bounded(self):
        """Compression ratio is numeric and between 0 and 1."""
        compressor = AdaptiveTrajectoryCompressor(max_segments=5)
        records = [_make_transfer_record(i * 100) for i in range(10)]
        compressor.load_transfer_records(records)
        compressor.compress()
        size_est = compressor.get_compressed_size_estimate()
        ratio = size_est["trajectory_compression_ratio"]
        assert isinstance(ratio, float)
        assert 0.0 <= ratio <= 1.0

    def test_compressed_smaller_than_source(self):
        """Compressed artifact is smaller than source when there are many records."""
        compressor = AdaptiveTrajectoryCompressor(max_segments=4)
        records = [_make_transfer_record(i * 10) for i in range(50)]
        compressor.load_transfer_records(records)
        compressor.compress()
        size_est = compressor.get_compressed_size_estimate()
        assert size_est["compressed_artifact_size_bytes"] <= size_est["source_artifact_size_bytes"]


class TestReplayMetrics:
    """Test replay metrics are numeric and bounded."""

    def test_replay_metrics_bounded(self):
        """All replay metrics are numeric and stability is in [0, 1]."""
        compressor = AdaptiveTrajectoryCompressor(max_segments=5)
        records = [_make_transfer_record(i * 100, gen_src=i, gen_succ=i + 1) for i in range(10)]
        compressor.load_transfer_records(records)
        compressor.load_action_trace([
            {"tick": i * 100, "unit_id": "u0", "action": "HARVEST"} for i in range(10)
        ])
        compressor.compress()
        replay = compressor.get_replay_metrics()
        assert isinstance(replay["replay_window_count"], int)
        assert isinstance(replay["avg_trajectory_replay_error"], float)
        assert isinstance(replay["max_trajectory_replay_error"], float)
        assert isinstance(replay["replay_stability_score"], float)
        assert 0.0 <= replay["replay_stability_score"] <= 1.0
        assert replay["avg_trajectory_replay_error"] >= 0.0
        assert replay["max_trajectory_replay_error"] >= replay["avg_trajectory_replay_error"]


class TestCrossTrajectoryComparison:
    """Test cross-trajectory comparison detects differences."""

    def test_detects_difference(self):
        """Two compressors with different data produce nontrivial difference."""
        comp1 = AdaptiveTrajectoryCompressor(max_segments=4)
        records1 = [_make_transfer_record(i * 100, delta_override={"move_weight": 0.1}) for i in range(8)]
        comp1.load_transfer_records(records1)
        comp1.compress()

        comp2 = AdaptiveTrajectoryCompressor(max_segments=4)
        records2 = [_make_transfer_record(i * 100, delta_override={"move_weight": -0.1}) for i in range(8)]
        comp2.load_transfer_records(records2)
        comp2.compress()

        result = compare_trajectories(comp1, comp2)
        assert isinstance(result["overall_trajectory_similarity"], float)
        assert 0.0 <= result["overall_trajectory_similarity"] <= 1.0
        assert isinstance(result["nontrivial_difference_detected"], bool)

    def test_same_data_high_similarity(self):
        """Two compressors with identical data have high similarity."""
        def build():
            c = AdaptiveTrajectoryCompressor(max_segments=4)
            records = [_make_transfer_record(i * 100) for i in range(8)]
            c.load_transfer_records(records)
            c.compress()
            return c

        result = compare_trajectories(build(), build())
        assert result["overall_trajectory_similarity"] > 0.9


class TestCompressorDeterministic:
    """Test compressor output is deterministic for identical inputs."""

    def test_same_input_same_output(self):
        """Identical inputs produce identical segments and signatures."""
        def build():
            c = AdaptiveTrajectoryCompressor(max_segments=4)
            records = [_make_transfer_record(i * 100, gen_src=i, gen_succ=i + 1) for i in range(8)]
            c.load_transfer_records(records)
            c.compress()
            return c

        c1 = build()
        c2 = build()
        sig1 = c1.get_trajectory_signature()
        sig2 = c2.get_trajectory_signature()
        assert sig1["signature_hash"] == sig2["signature_hash"]
        assert sig1["segment_count"] == sig2["segment_count"]
        assert sig1["avg_transfer_delta_rms"] == sig2["avg_transfer_delta_rms"]


class TestJudgeFailsMissingSegments:
    """Test M16 judge fails when compressed segments are missing."""

    def test_judge_fails_no_segments(self):
        """Judge returns FAIL for compression_segment_check when segments missing."""
        from machine_sim.verification.milestone_16_judge import judge
        with tempfile.TemporaryDirectory() as tmpdir:
            capsule = {
                "run_parameters": {"max_ticks": 30000},
                "compression_parameters": {"max_segments": 32},
                "segment_summaries": [],
                "trajectory_signature": {"segment_count": 0},
                "replay_metrics": {"avg_trajectory_replay_error": 0.0, "replay_stability_score": 1.0},
                "cross_trajectory_similarity": {"overall_trajectory_similarity": 0.5,
                                                 "nontrivial_difference_detected": True},
                "artifact_size_summary": {
                    "source_trace_record_count": 10,
                    "compressed_segment_count": 0,
                    "trajectory_compression_ratio": 0.0,
                },
                "judge_status": "pending",
            }
            (Path(tmpdir) / "compressed_trajectory_capsule.json").write_text(json.dumps(capsule))
            for fname in ["trajectory_compression_summary.json", "trajectory_replay_metrics.json",
                          "cross_trajectory_compare.json", "adaptive_trajectory_summary.json"]:
                (Path(tmpdir) / fname).write_text(json.dumps({}))
            (Path(tmpdir) / "compressed_trajectory_segments.jsonl").write_text("")
            (Path(tmpdir) / "generation_adaptive_state_trace.jsonl").write_text(
                json.dumps({"tick": 100, "adaptive_state_delta": {"move_weight": 0.05}}) + "\n")
            result = judge(tmpdir)
            assert result["checks"]["compression_segment_check"] == "FAIL"


class TestJudgeFailsMissingReplay:
    """Test M16 judge fails when replay metrics are missing."""

    def test_judge_fails_no_replay(self):
        """Judge returns FAIL for replay_metrics_check when replay missing."""
        from machine_sim.verification.milestone_16_judge import judge
        with tempfile.TemporaryDirectory() as tmpdir:
            capsule = {
                "run_parameters": {"max_ticks": 30000},
                "compression_parameters": {"max_segments": 32},
                "segment_summaries": [{"segment_index": 0}],
                "trajectory_signature": {"segment_count": 1},
                "replay_metrics": {},
                "cross_trajectory_similarity": {"overall_trajectory_similarity": 0.5,
                                                 "nontrivial_difference_detected": True},
                "artifact_size_summary": {
                    "source_trace_record_count": 5,
                    "compressed_segment_count": 1,
                    "trajectory_compression_ratio": 0.3,
                },
                "judge_status": "pending",
            }
            (Path(tmpdir) / "compressed_trajectory_capsule.json").write_text(json.dumps(capsule))
            for fname in ["trajectory_compression_summary.json", "trajectory_replay_metrics.json",
                          "cross_trajectory_compare.json", "adaptive_trajectory_summary.json"]:
                (Path(tmpdir) / fname).write_text(json.dumps({}))
            (Path(tmpdir) / "compressed_trajectory_segments.jsonl").write_text(
                json.dumps({"segment_index": 0}) + "\n")
            (Path(tmpdir) / "generation_adaptive_state_trace.jsonl").write_text(
                json.dumps({"tick": 100, "adaptive_state_delta": {"move_weight": 0.05}}) + "\n")
            result = judge(tmpdir)
            assert result["checks"]["replay_metrics_check"] == "FAIL"


class TestJudgeFailsMissingComparison:
    """Test M16 judge fails when cross-trajectory comparison is missing."""

    def test_judge_fails_no_comparison(self):
        """Judge returns FAIL for cross_trajectory_similarity_check when missing."""
        from machine_sim.verification.milestone_16_judge import judge
        with tempfile.TemporaryDirectory() as tmpdir:
            capsule = {
                "run_parameters": {"max_ticks": 30000},
                "compression_parameters": {"max_segments": 32},
                "segment_summaries": [{"segment_index": 0}],
                "trajectory_signature": {"segment_count": 1},
                "replay_metrics": {"avg_trajectory_replay_error": 0.01, "replay_stability_score": 0.9},
                "cross_trajectory_similarity": {},
                "artifact_size_summary": {
                    "source_trace_record_count": 5,
                    "compressed_segment_count": 1,
                    "trajectory_compression_ratio": 0.3,
                },
                "judge_status": "pending",
            }
            (Path(tmpdir) / "compressed_trajectory_capsule.json").write_text(json.dumps(capsule))
            for fname in ["trajectory_compression_summary.json", "trajectory_replay_metrics.json",
                          "cross_trajectory_compare.json", "adaptive_trajectory_summary.json"]:
                (Path(tmpdir) / fname).write_text(json.dumps({}))
            (Path(tmpdir) / "compressed_trajectory_segments.jsonl").write_text(
                json.dumps({"segment_index": 0}) + "\n")
            (Path(tmpdir) / "generation_adaptive_state_trace.jsonl").write_text(
                json.dumps({"tick": 100, "adaptive_state_delta": {"move_weight": 0.05}}) + "\n")
            result = judge(tmpdir)
            assert result["checks"]["cross_trajectory_similarity_check"] == "FAIL"


class TestJudgePassesValidArtifacts:
    """Test M16 judge passes on a valid fixture set."""

    def test_judge_passes_valid(self):
        """Judge returns PASS with complete valid artifacts."""
        from machine_sim.verification.milestone_16_judge import judge
        with tempfile.TemporaryDirectory() as tmpdir:
            capsule = {
                "run_parameters": {"max_ticks": 30000},
                "compression_parameters": {"max_segments": 32},
                "segment_summaries": [{"segment_index": i} for i in range(4)],
                "trajectory_signature": {"segment_count": 4, "total_transfer_count": 10},
                "replay_metrics": {"avg_trajectory_replay_error": 0.01, "replay_stability_score": 0.85,
                                   "max_trajectory_replay_error": 0.03},
                "cross_trajectory_similarity": {
                    "overall_trajectory_similarity": 0.7,
                    "nontrivial_difference_detected": True,
                },
                "artifact_size_summary": {
                    "source_trace_record_count": 10,
                    "compressed_segment_count": 4,
                    "trajectory_compression_ratio": 0.4,
                },
                "judge_status": "pending",
            }
            (Path(tmpdir) / "compressed_trajectory_capsule.json").write_text(json.dumps(capsule))
            for fname in ["trajectory_compression_summary.json", "trajectory_replay_metrics.json",
                          "cross_trajectory_compare.json"]:
                (Path(tmpdir) / fname).write_text(json.dumps({}))
            traj_summary = {
                "transfer_summary": {"transfer_count": 8},
                "generation_summary": {"generation_index_span": 4},
            }
            (Path(tmpdir) / "adaptive_trajectory_summary.json").write_text(json.dumps(traj_summary))
            with open(Path(tmpdir) / "compressed_trajectory_segments.jsonl", "w") as f:
                for i in range(4):
                    f.write(json.dumps({"segment_index": i}) + "\n")
            (Path(tmpdir) / "generation_adaptive_state_trace.jsonl").write_text(
                json.dumps({"tick": 100, "adaptive_state_delta": {"signal_emission_rate": 0.02}}) + "\n")
            result = judge(tmpdir)
            assert result["M16_JUDGE_STATUS"] == "PASS"
            assert len(result["failed_checks"]) == 0


class TestM15Regression:
    """Test M15 judge still works."""

    def test_m15_judge_still_works(self):
        """M15 judge function is importable and callable."""
        from machine_sim.verification.milestone_15_judge import judge as m15_judge
        with tempfile.TemporaryDirectory() as tmpdir:
            summary = {
                "run_parameters": {"grid_width": 120, "grid_height": 120, "max_ticks": 30000},
                "transfer_summary": {"transfer_count": 8, "generation_index_span": 4},
                "generation_summary": {"generation_index_span": 4, "transfer_count": 8},
                "adaptive_state_delta_summary": {"move_weight": 0.05},
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
            result = m15_judge(tmpdir)
            assert result["M15_JUDGE_STATUS"] == "PASS"


class TestLoadJsonl:
    """Test JSONL loading utility."""

    def test_loads_valid_jsonl(self):
        """Loads valid JSONL file into list of dicts."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"a": 1}\n{"b": 2}\n')
            f.flush()
            records = load_jsonl(Path(f.name))
            assert len(records) == 2
            assert records[0]["a"] == 1

    def test_handles_missing_file(self):
        """Missing file returns empty list."""
        records = load_jsonl(Path("/nonexistent/file.jsonl"))
        assert records == []
