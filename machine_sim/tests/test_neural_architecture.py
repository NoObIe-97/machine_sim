"""Tests for M19 successor-transferred neural architecture variation."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
import random

import pytest

from machine_sim.agents.neural_architecture import (
    NeuralArchitectureConfig,
    NeuralArchitectureDescriptor,
    vary_architecture,
    compute_recurrence_mask,
    compute_processing_cost,
    compute_fabrication_cost,
    resize_state_for_successor,
    stable_seed,
)


class TestArchitectureDescriptorValidation:
    def test_valid_descriptor_passes(self):
        d = NeuralArchitectureDescriptor(hidden_size=16, recurrent_density=1.0, plasticity_rate=0.01)
        d.validate()

    def test_rejects_hidden_size_below_minimum(self):
        d = NeuralArchitectureDescriptor(hidden_size=4)
        with pytest.raises(AssertionError):
            d.validate()

    def test_rejects_density_out_of_range(self):
        d = NeuralArchitectureDescriptor(hidden_size=16, recurrent_density=1.5)
        with pytest.raises(AssertionError):
            d.validate()

    def test_rejects_plasticity_rate_out_of_range(self):
        d = NeuralArchitectureDescriptor(hidden_size=16, plasticity_rate=-0.01)
        with pytest.raises(AssertionError):
            d.validate()

    def test_active_recurrent_connections(self):
        d = NeuralArchitectureDescriptor(hidden_size=10, recurrent_density=0.5)
        assert d.active_recurrent_connections() == 50

    def test_to_dict_roundtrip(self):
        d = NeuralArchitectureDescriptor(
            architecture_id="test-1", hidden_size=16, recurrent_density=0.8, plasticity_rate=0.02)
        d2 = NeuralArchitectureDescriptor.from_dict(d.to_dict())
        assert d.hidden_size == d2.hidden_size
        assert d.recurrent_density == d2.recurrent_density
        assert d.architecture_id == d2.architecture_id


class TestArchitectureVariation:
    def test_same_seed_same_result(self):
        bounds = NeuralArchitectureConfig()
        src = NeuralArchitectureDescriptor(hidden_size=16, recurrent_density=1.0, plasticity_rate=0.01)
        rng1 = random.Random(stable_seed("test", 42))
        rng2 = random.Random(stable_seed("test", 42))
        r1 = vary_architecture(src, bounds, rng1, tick=100)
        r2 = vary_architecture(src, bounds, rng2, tick=100)
        assert r1.hidden_size == r2.hidden_size
        assert r1.recurrent_density == r2.recurrent_density

    def test_different_seeds_can_differ(self):
        bounds = NeuralArchitectureConfig()
        src = NeuralArchitectureDescriptor(hidden_size=16, recurrent_density=1.0, plasticity_rate=0.01)
        results = set()
        for i in range(20):
            rng = random.Random(stable_seed("var", i))
            r = vary_architecture(src, bounds, rng, tick=100, index=i)
            results.add(r.hidden_size)
        assert len(results) > 1

    def test_disabled_preserves_source(self):
        bounds = NeuralArchitectureConfig(architecture_variation_enabled=False)
        src = NeuralArchitectureDescriptor(hidden_size=16)
        rng = random.Random(42)
        r = vary_architecture(src, bounds, rng, tick=0)
        assert r.hidden_size == src.hidden_size

    def test_respects_bounds(self):
        bounds = NeuralArchitectureConfig(minimum_hidden_size=8, maximum_hidden_size=24)
        src = NeuralArchitectureDescriptor(hidden_size=8)
        for i in range(50):
            rng = random.Random(stable_seed("bound", i))
            r = vary_architecture(src, bounds, rng, tick=100, index=i)
            assert bounds.minimum_hidden_size <= r.hidden_size <= bounds.maximum_hidden_size


class TestRecurrentMask:
    def test_mask_dimensions_match(self):
        mask = compute_recurrence_mask(10, 0.5, random.Random(42))
        assert len(mask) == 10
        assert all(len(row) == 10 for row in mask)

    def test_density_approximate(self):
        mask = compute_recurrence_mask(100, 0.3, random.Random(42))
        active = sum(int(v) for row in mask for v in row)
        total = 100 * 100
        density = active / total
        assert abs(density - 0.3) < 0.05

    def test_mask_values_are_binary(self):
        mask = compute_recurrence_mask(10, 0.5, random.Random(42))
        for row in mask:
            for v in row:
                assert v in (0.0, 1.0)


class TestProcessingCost:
    def test_positive_for_enabled(self):
        desc = NeuralArchitectureDescriptor(hidden_size=16, recurrent_density=1.0)
        bounds = NeuralArchitectureConfig()
        cost = compute_processing_cost(desc, bounds)
        assert cost > 0

    def test_higher_hidden_not_lower_cost(self):
        bounds = NeuralArchitectureConfig()
        c8 = compute_processing_cost(NeuralArchitectureDescriptor(hidden_size=8), bounds)
        c16 = compute_processing_cost(NeuralArchitectureDescriptor(hidden_size=16), bounds)
        c32 = compute_processing_cost(NeuralArchitectureDescriptor(hidden_size=32), bounds)
        assert c8 <= c16 <= c32

    def test_higher_connections_not_lower_cost(self):
        bounds = NeuralArchitectureConfig()
        c_low = compute_processing_cost(NeuralArchitectureDescriptor(hidden_size=16, recurrent_density=0.3), bounds)
        c_high = compute_processing_cost(NeuralArchitectureDescriptor(hidden_size=16, recurrent_density=1.0), bounds)
        assert c_low <= c_high


class TestFabricationCost:
    def test_positive(self):
        desc = NeuralArchitectureDescriptor(hidden_size=16)
        bounds = NeuralArchitectureConfig()
        cost = compute_fabrication_cost(desc, bounds)
        assert cost > 0

    def test_higher_complexity_higher_cost(self):
        bounds = NeuralArchitectureConfig()
        c8 = compute_fabrication_cost(NeuralArchitectureDescriptor(hidden_size=8), bounds)
        c32 = compute_fabrication_cost(NeuralArchitectureDescriptor(hidden_size=32), bounds)
        assert c8 < c32


class TestDimensionChangingTransfer:
    def test_expansion_preserves_old_state(self):
        src = NeuralArchitectureDescriptor(hidden_size=4)
        dst = NeuralArchitectureDescriptor(hidden_size=6)
        rng = random.Random(42)
        hidden = [0.1, 0.2, 0.3, 0.4]
        W_in = [[1.0, 2.0, 3.0, 4.0]] * 4
        W_rec = [[0.1] * 4] * 4
        W_out = [[0.5] * 4] * 7
        W_param = [[0.3] * 4] * 3
        b_hidden = [0.01] * 4
        mask = [[1.0] * 4] * 4

        new_h, new_W_in, new_W_rec, new_W_out, new_W_param, new_b_h, new_mask, retained = \
            resize_state_for_successor(hidden, W_in, W_rec, W_out, W_param, b_hidden, mask, dst, src, rng)

        assert len(new_h) == 6
        assert len(new_W_in) == 6
        assert len(new_W_rec) == 6
        assert all(len(row) == 6 for row in new_W_rec)
        assert len(new_W_out[0]) == 6
        assert len(new_W_param[0]) == 6
        # First 4 hidden values preserved
        for i in range(4):
            assert new_h[i] == hidden[i]

    def test_contraction_preserves_retained(self):
        src = NeuralArchitectureDescriptor(hidden_size=6)
        dst = NeuralArchitectureDescriptor(hidden_size=4)
        rng = random.Random(42)
        hidden = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
        W_in = [[float(i)] * 6 for i in range(6)]
        W_rec = [[0.1] * 6] * 6
        W_out = [[0.5] * 6] * 7
        W_param = [[0.3] * 6] * 3
        b_hidden = [0.01] * 6
        mask = [[1.0] * 6] * 6

        new_h, new_W_in, new_W_rec, new_W_out, new_W_param, new_b_h, new_mask, retained = \
            resize_state_for_successor(hidden, W_in, W_rec, W_out, W_param, b_hidden, mask, dst, src, rng)

        assert len(new_h) == 4
        assert len(retained) == 4
        # Retained values come from source
        for idx in retained:
            assert hidden[idx] in new_h

    def test_same_size_preserves_all(self):
        src = NeuralArchitectureDescriptor(hidden_size=4)
        dst = NeuralArchitectureDescriptor(hidden_size=4)
        rng = random.Random(42)
        hidden = [0.1, 0.2, 0.3, 0.4]
        W_in = [[1.0] * 4] * 4
        W_rec = [[0.1] * 4] * 4
        W_out = [[0.5] * 4] * 7
        W_param = [[0.3] * 4] * 3
        b_hidden = [0.01] * 4
        mask = [[1.0] * 4] * 4

        new_h, _, _, _, _, _, _, retained = \
            resize_state_for_successor(hidden, W_in, W_rec, W_out, W_param, b_hidden, mask, dst, src, rng)
        assert new_h == hidden
        assert retained == list(range(4))


class TestM19Judge:
    def _make_valid_fixture(self, tmpdir, arch_cfg=None):
        if arch_cfg is None:
            arch_cfg = NeuralArchitectureConfig()
        (Path(tmpdir) / "neural_architecture_run_summary.json").write_text(json.dumps({
            "run_ticks": 40000,
            "architecture_variation_enabled": True,
            "architecture_transfer_count": 10,
            "increase_transition_count": 5,
            "decrease_transition_count": 3,
            "unchanged_transition_count": 2,
            "distinct_architecture_count": 4,
            "total_processing_cost": 12.5,
            "total_fabrication_cost": 8.3,
            "architecture_bounds": {
                "minimum_hidden_size": arch_cfg.minimum_hidden_size,
                "maximum_hidden_size": arch_cfg.maximum_hidden_size,
                "minimum_recurrent_density": arch_cfg.minimum_recurrent_density,
                "maximum_recurrent_density": arch_cfg.maximum_recurrent_density,
            },
            "strict_regression_summary": {
                "m17_regression": "PASS",
                "m14_m15_m16_regression": "PASS",
                "m18_regression": "PASS",
            },
        }))
        # Initial descriptors
        with open(Path(tmpdir) / "neural_architecture_initial_descriptors.jsonl", "w") as f:
            for i in range(8):
                f.write(json.dumps({"architecture_id": f"arch-{i}", "hidden_size": 16, "recurrent_density": 1.0, "plasticity_rate": 0.01}) + "\n")
        # Transfer trace
        with open(Path(tmpdir) / "neural_architecture_transfer_trace.jsonl", "w") as f:
            for i in range(10):
                delta = 2 if i < 5 else (-2 if i < 8 else 0)
                f.write(json.dumps({
                    "tick": (i + 1) * 1000, "source_unit_id": f"u-{i}", "successor_unit_id": f"u-{i+8}",
                    "source_hidden_size": 16, "successor_hidden_size": 16 + delta,
                    "hidden_size_delta": delta,
                    "source_recurrent_density": 1.0, "successor_recurrent_density": 1.0,
                    "recurrent_density_delta": 0.0,
                    "source_plasticity_rate": 0.01, "successor_plasticity_rate": 0.01,
                    "plasticity_rate_delta": 0.0,
                    "retained_hidden_count": 16 + min(0, delta), "added_hidden_count": max(0, delta), "removed_hidden_count": max(0, -delta),
                    "active_recurrent_connection_delta": 0,
                    "processing_cost_estimate": 0.1, "fabrication_complexity_cost": 0.5,
                    "variation_applied": True,
                }) + "\n")
        # Distribution trace
        with open(Path(tmpdir) / "neural_architecture_distribution_trace.jsonl", "w") as f:
            for i in range(5):
                f.write(json.dumps({
                    "tick": i * 5000, "active_unit_count": 8, "distinct_architecture_count": 3,
                    "hidden_size_histogram": {16: 5, 18: 2, 14: 1},
                    "mean_hidden_size": 16.0,
                }) + "\n")
        # Cost trace
        with open(Path(tmpdir) / "neural_architecture_cost_trace.jsonl", "w") as f:
            for i in range(5):
                f.write(json.dumps({"tick": i * 1000, "unit_id": "u-0", "processing_cost": 0.1, "hidden_size": 16, "recurrent_density": 1.0}) + "\n")
        # Comparison
        (Path(tmpdir) / "fixed_vs_variable_architecture_compare.json").write_text(json.dumps({
            "fixed_run_ticks": 40000, "variable_run_ticks": 40000,
            "fixed_final_active_count": 6, "variable_final_active_count": 7,
            "nontrivial_architecture_variation_detected": True,
        }))
        # Lineage
        (Path(tmpdir) / "neural_architecture_lineage_summary.json").write_text(json.dumps({
            "total_transitions": 10, "increase_transition_count": 5,
            "decrease_transition_count": 3, "distinct_architecture_count": 4,
        }))

    def test_judge_passes_valid_fixture(self):
        from machine_sim.verification.milestone_19_judge import judge
        with tempfile.TemporaryDirectory() as tmpdir:
            self._make_valid_fixture(tmpdir)
            result = judge(tmpdir)
            assert result["M19_JUDGE_STATUS"] == "PASS"
            assert len(result["failed_checks"]) == 0

    def test_judge_fails_no_transfers(self):
        from machine_sim.verification.milestone_19_judge import judge
        with tempfile.TemporaryDirectory() as tmpdir:
            self._make_valid_fixture(tmpdir)
            # Override: no transfers
            (Path(tmpdir) / "neural_architecture_run_summary.json").write_text(json.dumps({
                "run_ticks": 40000, "architecture_variation_enabled": True,
                "architecture_transfer_count": 0, "increase_transition_count": 0,
                "decrease_transition_count": 0, "distinct_architecture_count": 1,
                "total_processing_cost": 1.0, "total_fabrication_cost": 0.0,
                "architecture_bounds": {"minimum_hidden_size": 8, "maximum_hidden_size": 64,
                                        "minimum_recurrent_density": 0.15, "maximum_recurrent_density": 1.0},
                "strict_regression_summary": {"m17_regression": "PASS", "m14_m15_m16_regression": "PASS", "m18_regression": "PASS"},
            }))
            result = judge(tmpdir)
            assert result["M19_JUDGE_STATUS"] == "FAIL"
            assert "successor_architecture_transfer_check" in result["failed_checks"]

    def test_judge_fails_no_increase(self):
        from machine_sim.verification.milestone_19_judge import judge
        with tempfile.TemporaryDirectory() as tmpdir:
            self._make_valid_fixture(tmpdir)
            (Path(tmpdir) / "neural_architecture_run_summary.json").write_text(json.dumps({
                "run_ticks": 40000, "architecture_variation_enabled": True,
                "architecture_transfer_count": 5, "increase_transition_count": 0,
                "decrease_transition_count": 5, "unchanged_transition_count": 0,
                "distinct_architecture_count": 2, "total_processing_cost": 1.0,
                "total_fabrication_cost": 1.0,
                "architecture_bounds": {"minimum_hidden_size": 8, "maximum_hidden_size": 64,
                                        "minimum_recurrent_density": 0.15, "maximum_recurrent_density": 1.0},
                "strict_regression_summary": {"m17_regression": "PASS", "m14_m15_m16_regression": "PASS", "m18_regression": "PASS"},
            }))
            result = judge(tmpdir)
            assert result["M19_JUDGE_STATUS"] == "FAIL"
            assert "increase_transition_check" in result["failed_checks"]

    def test_judge_fails_zero_cost(self):
        from machine_sim.verification.milestone_19_judge import judge
        with tempfile.TemporaryDirectory() as tmpdir:
            self._make_valid_fixture(tmpdir)
            (Path(tmpdir) / "neural_architecture_run_summary.json").write_text(json.dumps({
                "run_ticks": 40000, "architecture_variation_enabled": True,
                "architecture_transfer_count": 5, "increase_transition_count": 3,
                "decrease_transition_count": 2, "distinct_architecture_count": 2,
                "total_processing_cost": 0.0, "total_fabrication_cost": 0.0,
                "architecture_bounds": {"minimum_hidden_size": 8, "maximum_hidden_size": 64,
                                        "minimum_recurrent_density": 0.15, "maximum_recurrent_density": 1.0},
                "strict_regression_summary": {"m17_regression": "PASS", "m14_m15_m16_regression": "PASS", "m18_regression": "PASS"},
            }))
            result = judge(tmpdir)
            assert result["M19_JUDGE_STATUS"] == "FAIL"
            assert "processing_cost_nonzero_check" in result["failed_checks"]

    def test_judge_fails_missing_regression(self):
        from machine_sim.verification.milestone_19_judge import judge
        with tempfile.TemporaryDirectory() as tmpdir:
            self._make_valid_fixture(tmpdir)
            (Path(tmpdir) / "neural_architecture_run_summary.json").write_text(json.dumps({
                "run_ticks": 40000, "architecture_variation_enabled": True,
                "architecture_transfer_count": 5, "increase_transition_count": 3,
                "decrease_transition_count": 2, "distinct_architecture_count": 2,
                "total_processing_cost": 1.0, "total_fabrication_cost": 1.0,
                "architecture_bounds": {"minimum_hidden_size": 8, "maximum_hidden_size": 64,
                                        "minimum_recurrent_density": 0.15, "maximum_recurrent_density": 1.0},
                "strict_regression_summary": {},
            }))
            # Remove demo dirs
            result = judge(tmpdir)
            assert result["M19_JUDGE_STATUS"] == "FAIL"
            assert "m14_m15_m16_m17_m18_regression_check" in result["failed_checks"]


class TestExistingTestsStillPass:
    def test_import_existing_modules(self):
        from machine_sim.sim.config import SimConfig
        cfg = SimConfig(
            neural_controller_enabled=True, neural_hidden_size=8,
            neural_plasticity_rate=0.05, neural_plasticity_enabled=True,
            neural_architecture_variation_enabled=True,
        )
        assert cfg.neural_hidden_size == 8
        assert cfg.neural_architecture_variation_enabled is True
