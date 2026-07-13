"""Tests for M18 neural controller variant sensitivity comparison."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Dict, List

import pytest

from machine_sim.agents.neural_controller import (
    ACTION_NAMES,
    NeuralController,
    NeuralProcessingConfig,
    SENSOR_INPUT_SIZE,
)
from machine_sim.agents.unit import MachineUnitImpl
from machine_sim.analysis.neural_variant_comparison import (
    _action_distribution_similarity,
    _cosine_similarity,
    _count_action_distribution,
    _load_variant_summary,
    _neural_state_feature_vector,
    build_similarity_matrix,
    compute_sensitivity_summary,
)


class TestCosineSimiliarty:
    def test_identical_vectors(self):
        assert abs(_cosine_similarity([1.0, 2.0], [1.0, 2.0]) - 1.0) < 1e-6

    def test_orthogonal_vectors(self):
        assert abs(_cosine_similarity([1.0, 0.0], [0.0, 1.0])) < 1e-6

    def test_empty_vectors(self):
        assert _cosine_similarity([], []) == 0.0

    def test_zero_vector(self):
        assert _cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0


class TestActionDistributionSimilarity:
    def test_identical_distributions(self):
        a = {"MOVE": 10, "SCAN": 5}
        assert abs(_action_distribution_similarity(a, a) - 1.0) < 1e-6

    def test_different_distributions(self):
        a = {"MOVE": 10, "SCAN": 0}
        b = {"MOVE": 0, "SCAN": 10}
        assert _action_distribution_similarity(a, b) < 0.01

    def test_empty_distributions(self):
        assert _action_distribution_similarity({}, {}) == 1.0


class TestVariantSweepConfig:
    def test_config_loads_at_least_5_variants(self):
        config_path = Path("configs/milestone_18_neural_controller_variant_sensitivity.toml")
        if not config_path.exists():
            pytest.skip("M18 config not found")
        import tomllib
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        variants = data.get("m18_variants", [])
        assert len(variants) >= 5

    def test_m17_baseline_variant_present(self):
        config_path = Path("configs/milestone_18_neural_controller_variant_sensitivity.toml")
        if not config_path.exists():
            pytest.skip("M18 config not found")
        import tomllib
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        variants = data.get("m18_variants", [])
        has_m17 = any(
            v.get("neural_hidden_size") == 16 and v.get("neural_plasticity_rate") == 0.01
            for v in variants
        )
        assert has_m17

    def test_hidden_size_variant_exists(self):
        config_path = Path("configs/milestone_18_neural_controller_variant_sensitivity.toml")
        if not config_path.exists():
            pytest.skip("M18 config not found")
        import tomllib
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        variants = data.get("m18_variants", [])
        has_hidden_diff = any(v.get("neural_hidden_size", 16) != 16 for v in variants)
        assert has_hidden_diff

    def test_plasticity_disabled_variant_exists(self):
        config_path = Path("configs/milestone_18_neural_controller_variant_sensitivity.toml")
        if not config_path.exists():
            pytest.skip("M18 config not found")
        import tomllib
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        variants = data.get("m18_variants", [])
        has_disabled = any(not v.get("neural_plasticity_enabled", True) for v in variants)
        assert has_disabled

    def test_plasticity_rate_variant_exists(self):
        config_path = Path("configs/milestone_18_neural_controller_variant_sensitivity.toml")
        if not config_path.exists():
            pytest.skip("M18 config not found")
        import tomllib
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        variants = data.get("m18_variants", [])
        has_rate_diff = any(v.get("neural_plasticity_rate", 0.01) != 0.01 for v in variants)
        assert has_rate_diff


class TestHiddenSizeVariant:
    def test_changes_dimensions(self):
        cfg_small = NeuralProcessingConfig(hidden_size=8)
        nc_small = NeuralController(config=cfg_small, unit_id="u-0", seed=42)
        assert len(nc_small.state.hidden_state) == 8
        assert len(nc_small.state.W_in) == 8

    def test_default_unchanged(self):
        cfg = NeuralProcessingConfig()
        nc = NeuralController(config=cfg, unit_id="u-0", seed=42)
        assert len(nc.state.hidden_state) == 16


class TestPlasticityRateVariant:
    def test_changes_rate(self):
        cfg = NeuralProcessingConfig(plasticity_rate=0.05)
        assert cfg.plasticity_rate == 0.05

    def test_disabled_no_change(self):
        cfg = NeuralProcessingConfig(plasticity_enabled=False, plasticity_rate=0.0)
        nc = NeuralController(config=cfg, unit_id="u-0", seed=42)
        inp = [0.5] * SENSOR_INPUT_SIZE
        import random
        rng = random.Random(42)
        pre_w = [list(row) for row in nc.state.W_out]
        nc.update_from_feedback(inp, "MOVE", {"power_delta": 1.0}, rng)
        post_w = nc.state.W_out
        assert pre_w == post_w


class TestSimilarityMatrix:
    def test_square_and_numeric(self):
        ids = ["a", "b", "c"]
        summaries = {
            "a": {"neural_state_trace_count": 10, "neural_action_trace_count": 100, "neural_plasticity_trace_count": 5, "neural_successor_transfer_count": 2, "final_active_count": 6},
            "b": {"neural_state_trace_count": 8, "neural_action_trace_count": 80, "neural_plasticity_trace_count": 3, "neural_successor_transfer_count": 1, "final_active_count": 5},
            "c": {"neural_state_trace_count": 10, "neural_action_trace_count": 100, "neural_plasticity_trace_count": 5, "neural_successor_transfer_count": 2, "final_active_count": 6},
        }
        dists = {
            "a": {"MOVE": 50, "SCAN": 30, "HARVEST": 20},
            "b": {"MOVE": 20, "SCAN": 50, "HARVEST": 30},
            "c": {"MOVE": 50, "SCAN": 30, "HARVEST": 20},
        }
        result = build_similarity_matrix(ids, summaries, dists)
        assert len(result["similarity_matrix"]["action_distribution"]) == 3
        assert len(result["similarity_matrix"]["action_distribution"][0]) == 3
        # Diagonal should be ~1.0
        for i in range(3):
            assert abs(result["similarity_matrix"]["action_distribution"][i][i] - 1.0) < 0.01
            assert abs(result["similarity_matrix"]["neural_state"][i][i] - 1.0) < 0.01

    def test_nontrivial_difference_detected(self):
        ids = ["a", "b"]
        summaries = {
            "a": {"neural_state_trace_count": 10, "final_active_count": 6},
            "b": {"neural_state_trace_count": 2, "final_active_count": 2},
        }
        dists = {
            "a": {"MOVE": 100},
            "b": {"SCAN": 100},
        }
        result = build_similarity_matrix(ids, summaries, dists)
        assert result["nontrivial_off_diagonal_difference_detected"] is True


class TestSensitivitySummary:
    def test_numeric_bounded_scores(self):
        ids = ["baseline", "h8"]
        defs = [
            {"id": "baseline", "neural_hidden_size": 16, "neural_plasticity_rate": 0.01, "neural_plasticity_enabled": True},
            {"id": "h8", "neural_hidden_size": 8, "neural_plasticity_rate": 0.01, "neural_plasticity_enabled": True},
        ]
        summaries = {
            "baseline": {"neural_state_trace_count": 10, "final_active_count": 6, "neural_plasticity_trace_count": 5},
            "h8": {"neural_state_trace_count": 8, "final_active_count": 4, "neural_plasticity_trace_count": 3},
        }
        dists = {
            "baseline": {"MOVE": 50, "SCAN": 30},
            "h8": {"MOVE": 30, "SCAN": 50},
        }
        result = compute_sensitivity_summary(ids, defs, summaries, dists)
        assert "sensitivity_score_by_parameter" in result
        for v in result["sensitivity_score_by_parameter"].values():
            assert isinstance(v, (int, float))
            assert 0.0 <= v <= 1.0


class TestM18Judge:
    def test_judge_fails_variant_count_too_small(self):
        from machine_sim.verification.milestone_18_judge import judge
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "neural_variant_sweep_summary.json").write_text(json.dumps({
                "variant_definitions": [],
                "strict_regression_summary": {},
            }))
            (Path(tmpdir) / "neural_variant_similarity_matrix.json").write_text(json.dumps({
                "variant_ids": [],
                "similarity_matrix": {"action_distribution": [], "neural_state": [], "runtime_metric": []},
                "nontrivial_off_diagonal_difference_detected": False,
            }))
            (Path(tmpdir) / "neural_controller_sensitivity_summary.json").write_text(json.dumps({
                "sensitivity_score_by_parameter": {},
            }))
            (Path(tmpdir) / "per_variant_runtime_summary.jsonl").write_text("")
            result = judge(tmpdir)
            assert result["M18_JUDGE_STATUS"] == "FAIL"
            assert "variant_count_check" in result["failed_checks"]

    def test_judge_fails_missing_artifacts(self):
        from machine_sim.verification.milestone_18_judge import judge
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "neural_variant_sweep_summary.json").write_text(json.dumps({
                "variant_definitions": [
                    {"id": "v1"}, {"id": "v2"}, {"id": "v3"}, {"id": "v4"}, {"id": "v5"},
                ],
                "strict_regression_summary": {},
            }))
            (Path(tmpdir) / "neural_variant_similarity_matrix.json").write_text(json.dumps({
                "variant_ids": ["v1", "v2", "v3", "v4", "v5"],
                "similarity_matrix": {
                    "action_distribution": [[1.0]*5]*5,
                    "neural_state": [[1.0]*5]*5,
                    "runtime_metric": [[1.0]*5]*5,
                },
                "nontrivial_off_diagonal_difference_detected": True,
            }))
            (Path(tmpdir) / "neural_controller_sensitivity_summary.json").write_text(json.dumps({
                "sensitivity_score_by_parameter": {"hidden_size": 0.5},
            }))
            (Path(tmpdir) / "per_variant_runtime_summary.jsonl").write_text(
                json.dumps({"variant_id": "v1", "run_ticks": 20000, "neural_hidden_size": 16, "neural_plasticity_rate": 0.01}) + "\n"
            )
            result = judge(tmpdir)
            assert result["M18_JUDGE_STATUS"] == "FAIL"
            assert "per_variant_artifact_check" in result["failed_checks"]

    def test_judge_fails_non_pass_check_values(self):
        """Verify that non-PASS check values fail overall."""
        from machine_sim.verification.milestone_18_judge import judge
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create valid structure but missing m17 regression
            (Path(tmpdir) / "neural_variant_sweep_summary.json").write_text(json.dumps({
                "variant_definitions": [
                    {"id": "v1", "neural_hidden_size": 16, "neural_plasticity_rate": 0.01, "neural_plasticity_enabled": True},
                    {"id": "v2", "neural_hidden_size": 8, "neural_plasticity_rate": 0.01, "neural_plasticity_enabled": True},
                    {"id": "v3", "neural_hidden_size": 32, "neural_plasticity_rate": 0.01, "neural_plasticity_enabled": True},
                    {"id": "v4", "neural_hidden_size": 16, "neural_plasticity_rate": 0.0, "neural_plasticity_enabled": False},
                    {"id": "v5", "neural_hidden_size": 16, "neural_plasticity_rate": 0.05, "neural_plasticity_enabled": True},
                ],
                "strict_regression_summary": {},
            }))
            (Path(tmpdir) / "neural_variant_similarity_matrix.json").write_text(json.dumps({
                "variant_ids": ["v1", "v2", "v3", "v4", "v5"],
                "similarity_matrix": {
                    "action_distribution": [[1.0, 0.5, 0.5, 0.5, 0.5]]*5,
                    "neural_state": [[1.0, 0.8, 0.8, 0.8, 0.8]]*5,
                    "runtime_metric": [[1.0, 0.9, 0.9, 0.9, 0.9]]*5,
                },
                "nontrivial_off_diagonal_difference_detected": True,
            }))
            (Path(tmpdir) / "neural_controller_sensitivity_summary.json").write_text(json.dumps({
                "sensitivity_score_by_parameter": {"hidden_size": 0.3, "plasticity_rate": 0.5},
            }))
            (Path(tmpdir) / "per_variant_runtime_summary.jsonl").write_text(
                json.dumps({"variant_id": "v1", "run_ticks": 20000, "neural_hidden_size": 16, "neural_plasticity_rate": 0.01}) + "\n"
                + json.dumps({"variant_id": "v2", "run_ticks": 10000, "neural_hidden_size": 8, "neural_plasticity_rate": 0.01}) + "\n"
                + json.dumps({"variant_id": "v3", "run_ticks": 10000, "neural_hidden_size": 32, "neural_plasticity_rate": 0.01}) + "\n"
                + json.dumps({"variant_id": "v4", "run_ticks": 10000, "neural_hidden_size": 16, "neural_plasticity_rate": 0.0}) + "\n"
                + json.dumps({"variant_id": "v5", "run_ticks": 10000, "neural_hidden_size": 16, "neural_plasticity_rate": 0.05}) + "\n"
            )
            # Create variant dirs with artifacts
            for vid in ["v1", "v2", "v3", "v4", "v5"]:
                vdir = Path(tmpdir) / "variants" / vid
                vdir.mkdir(parents=True)
                (vdir / "neural_processing_summary.json").write_text(json.dumps({"run_ticks": 10000}))
            result = judge(tmpdir)
            # Should fail because m17_regression_check is FAIL (no evidence)
            assert result["M18_JUDGE_STATUS"] == "FAIL"
            assert "m17_regression_check" in result["failed_checks"]

    def test_judge_passes_valid_fixture(self):
        from machine_sim.verification.milestone_18_judge import judge
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "neural_variant_sweep_summary.json").write_text(json.dumps({
                "variant_definitions": [
                    {"id": "v1", "neural_hidden_size": 16, "neural_plasticity_rate": 0.01, "neural_plasticity_enabled": True},
                    {"id": "v2", "neural_hidden_size": 8, "neural_plasticity_rate": 0.01, "neural_plasticity_enabled": True},
                    {"id": "v3", "neural_hidden_size": 32, "neural_plasticity_rate": 0.01, "neural_plasticity_enabled": True},
                    {"id": "v4", "neural_hidden_size": 16, "neural_plasticity_rate": 0.0, "neural_plasticity_enabled": False},
                    {"id": "v5", "neural_hidden_size": 16, "neural_plasticity_rate": 0.05, "neural_plasticity_enabled": True},
                ],
                "strict_regression_summary": {"m17_regression": "PASS", "m14_m15_m16_regression": "PASS"},
            }))
            (Path(tmpdir) / "neural_variant_similarity_matrix.json").write_text(json.dumps({
                "variant_ids": ["v1", "v2", "v3", "v4", "v5"],
                "similarity_matrix": {
                    "action_distribution": [
                        [1.0, 0.8, 0.8, 0.7, 0.9],
                        [0.8, 1.0, 0.8, 0.7, 0.8],
                        [0.8, 0.8, 1.0, 0.7, 0.8],
                        [0.7, 0.7, 0.7, 1.0, 0.7],
                        [0.9, 0.8, 0.8, 0.7, 1.0],
                    ],
                    "neural_state": [
                        [1.0, 0.9, 0.9, 0.8, 0.9],
                        [0.9, 1.0, 0.9, 0.8, 0.9],
                        [0.9, 0.9, 1.0, 0.8, 0.9],
                        [0.8, 0.8, 0.8, 1.0, 0.8],
                        [0.9, 0.9, 0.9, 0.8, 1.0],
                    ],
                    "runtime_metric": [
                        [1.0, 0.95, 0.95, 0.9, 0.95],
                        [0.95, 1.0, 0.95, 0.9, 0.95],
                        [0.95, 0.95, 1.0, 0.9, 0.95],
                        [0.9, 0.9, 0.9, 1.0, 0.9],
                        [0.95, 0.95, 0.95, 0.9, 1.0],
                    ],
                },
                "nontrivial_off_diagonal_difference_detected": True,
            }))
            (Path(tmpdir) / "neural_controller_sensitivity_summary.json").write_text(json.dumps({
                "sensitivity_score_by_parameter": {"hidden_size": 0.3, "plasticity_rate": 0.5},
            }))
            (Path(tmpdir) / "per_variant_runtime_summary.jsonl").write_text(
                json.dumps({"variant_id": "v1", "run_ticks": 20000, "neural_hidden_size": 16, "neural_plasticity_rate": 0.01}) + "\n"
                + json.dumps({"variant_id": "v2", "run_ticks": 10000, "neural_hidden_size": 8, "neural_plasticity_rate": 0.01}) + "\n"
                + json.dumps({"variant_id": "v3", "run_ticks": 10000, "neural_hidden_size": 32, "neural_plasticity_rate": 0.01}) + "\n"
                + json.dumps({"variant_id": "v4", "run_ticks": 10000, "neural_hidden_size": 16, "neural_plasticity_rate": 0.0}) + "\n"
                + json.dumps({"variant_id": "v5", "run_ticks": 10000, "neural_hidden_size": 16, "neural_plasticity_rate": 0.05}) + "\n"
            )
            for vid in ["v1", "v2", "v3", "v4", "v5"]:
                vdir = Path(tmpdir) / "variants" / vid
                vdir.mkdir(parents=True)
                (vdir / "neural_processing_summary.json").write_text(json.dumps({"run_ticks": 10000}))
            result = judge(tmpdir)
            assert result["M18_JUDGE_STATUS"] == "PASS"
            assert len(result["failed_checks"]) == 0


class TestExistingTestsStillPass:
    def test_import_existing_modules(self):
        from machine_sim.sim.config import SimConfig
        cfg = SimConfig(
            neural_controller_enabled=True, neural_hidden_size=8,
            neural_plasticity_rate=0.05, neural_plasticity_enabled=True,
        )
        assert cfg.neural_hidden_size == 8
        assert cfg.neural_plasticity_rate == 0.05

    def test_unit_with_custom_neural_params(self):
        unit = MachineUnitImpl(
            "test-unit", adaptive_enabled=True,
            neural_controller_enabled=True, neural_hidden_size=8,
            neural_plasticity_rate=0.05, neural_seed=42,
        )
        assert unit._neural_controller is not None
        assert unit._neural_controller.config.hidden_size == 8
        assert unit._neural_controller.config.plasticity_rate == 0.05

    def test_unit_default_neural_params(self):
        unit = MachineUnitImpl(
            "test-unit", adaptive_enabled=True,
            neural_controller_enabled=True, neural_seed=42,
        )
        assert unit._neural_controller.config.hidden_size == 16
        assert unit._neural_controller.config.plasticity_rate == 0.01
