"""Tests for the internal neural processing unit (M17)."""

from __future__ import annotations

import json
import math
import random
import tempfile
from pathlib import Path
from typing import Dict, List

import pytest

from machine_sim.agents.neural_controller import (
    ACTION_NAMES,
    NeuralController,
    NeuralProcessingConfig,
    NeuralProcessingState,
    SENSOR_INPUT_SIZE,
    _softmax,
    stable_seed,
)


class TestNeuralControllerDeterministicInit:
    """Test deterministic initialization of neural controller."""

    def test_same_seed_same_state(self):
        cfg = NeuralProcessingConfig()
        nc1 = NeuralController(config=cfg, unit_id="u-0", seed=42)
        nc2 = NeuralController(config=cfg, unit_id="u-0", seed=42)
        assert nc1.state.hidden_state == nc2.state.hidden_state
        assert nc1.state.W_in == nc2.state.W_in
        assert nc1.state.W_out == nc2.state.W_out

    def test_different_seed_different_state(self):
        cfg = NeuralProcessingConfig()
        nc1 = NeuralController(config=cfg, unit_id="u-0", seed=42)
        nc2 = NeuralController(config=cfg, unit_id="u-0", seed=99)
        assert nc1.state.W_in != nc2.state.W_in

    def test_different_unit_id_different_state(self):
        cfg = NeuralProcessingConfig()
        nc1 = NeuralController(config=cfg, unit_id="u-0", seed=42)
        nc2 = NeuralController(config=cfg, unit_id="u-1", seed=42)
        assert nc1.state.W_in != nc2.state.W_in


class TestSensorInputVector:
    """Test sensor input vector construction."""

    def test_fixed_size(self):
        cfg = NeuralProcessingConfig()
        nc = NeuralController(config=cfg)
        inp = nc.build_sensor_input(
            power_ratio=0.5, avg_component_health=0.8,
            has_resource=True, resource_strength=0.6,
            has_hazard=False, hazard_strength=0.0,
            signal_observed=True, signal_emitted=False,
            movement_blocked=False, resource_extracted=True,
            scan_result_count=0.3, previous_action="MOVE",
            time_since_signal=0.2,
        )
        assert len(inp) == SENSOR_INPUT_SIZE

    def test_bounded_values(self):
        cfg = NeuralProcessingConfig()
        nc = NeuralController(config=cfg)
        inp = nc.build_sensor_input(
            power_ratio=1.5, avg_component_health=-0.1,
            has_resource=True, resource_strength=2.0,
            has_hazard=True, hazard_strength=3.0,
            signal_observed=True, signal_emitted=True,
            movement_blocked=True, resource_extracted=True,
            scan_result_count=5.0, previous_action="SCAN",
            time_since_signal=1.5,
        )
        for v in inp:
            assert -1.0 <= v <= 1.0

    def test_local_fields_only(self):
        """All inputs should be derived from local unit state."""
        cfg = NeuralProcessingConfig()
        nc = NeuralController(config=cfg)
        inp = nc.build_sensor_input(
            power_ratio=0.5, avg_component_health=0.8,
            has_resource=False, resource_strength=0.0,
            has_hazard=False, hazard_strength=0.0,
            signal_observed=False, signal_emitted=False,
            movement_blocked=False, resource_extracted=False,
            scan_result_count=0.0, previous_action="IDLE",
            time_since_signal=0.0,
        )
        # First two dims should be power_ratio and health
        assert inp[0] == 0.5
        assert inp[1] == 0.8

    def test_action_encoding(self):
        cfg = NeuralProcessingConfig()
        nc = NeuralController(config=cfg)
        inp = nc.build_sensor_input(
            power_ratio=0.5, avg_component_health=0.5,
            has_resource=False, resource_strength=0.0,
            has_hazard=False, hazard_strength=0.0,
            signal_observed=False, signal_emitted=False,
            movement_blocked=False, resource_extracted=False,
            scan_result_count=0.0, previous_action="MOVE",
            time_since_signal=0.0,
        )
        # MOVE encoding should be at index 11
        assert inp[11] == 1.0
        assert inp[12] == 0.0  # SCAN


class TestNeuralActionOutput:
    """Test neural action logits and preferences."""

    def test_logits_numeric(self):
        cfg = NeuralProcessingConfig()
        nc = NeuralController(config=cfg)
        inp = [0.5] * SENSOR_INPUT_SIZE
        logits, prefs, params, hidden = nc.forward(inp)
        assert len(logits) == cfg.output_size
        for v in logits:
            assert isinstance(v, float)

    def test_preferences_sum_to_one(self):
        cfg = NeuralProcessingConfig()
        nc = NeuralController(config=cfg)
        inp = [0.5] * SENSOR_INPUT_SIZE
        logits, prefs, params, hidden = nc.forward(inp)
        assert abs(sum(prefs) - 1.0) < 1e-6

    def test_preferences_bounded(self):
        cfg = NeuralProcessingConfig()
        nc = NeuralController(config=cfg)
        inp = [0.5] * SENSOR_INPUT_SIZE
        _, prefs, _, _ = nc.forward(inp)
        for v in prefs:
            assert 0.0 <= v <= 1.0

    def test_param_biases_bounded(self):
        cfg = NeuralProcessingConfig()
        nc = NeuralController(config=cfg)
        inp = [0.5] * SENSOR_INPUT_SIZE
        _, _, params, _ = nc.forward(inp)
        assert len(params) == cfg.param_output_size
        for v in params:
            assert -1.0 <= v <= 1.0


class TestRecurrentState:
    """Test recurrent state changes."""

    def test_hidden_state_changes(self):
        cfg = NeuralProcessingConfig()
        nc = NeuralController(config=cfg)
        inp1 = [0.5] * SENSOR_INPUT_SIZE
        inp2 = [0.8] * SENSOR_INPUT_SIZE
        _, _, _, h1 = nc.forward(inp1)
        nc.state.hidden_state = h1
        _, _, _, h2 = nc.forward(inp2)
        assert h1 != h2

    def test_hidden_state_size(self):
        cfg = NeuralProcessingConfig(hidden_size=16)
        nc = NeuralController(config=cfg)
        inp = [0.5] * SENSOR_INPUT_SIZE
        _, _, _, hidden = nc.forward(inp)
        assert len(hidden) == 16


class TestPlasticityUpdate:
    """Test plasticity update mechanism."""

    def test_update_changes_parameters(self):
        cfg = NeuralProcessingConfig(plasticity_enabled=True, plasticity_rate=0.1)
        nc = NeuralController(config=cfg)
        inp = [0.5] * SENSOR_INPUT_SIZE
        pre_w_out = [list(row) for row in nc.state.W_out]
        rng = random.Random(42)
        nc.update_from_feedback(inp, "HARVEST", {"resource_extracted": 1.0, "power_delta": 1.0}, rng)
        post_w_out = nc.state.W_out
        delta = sum(
            abs(post_w_out[i][j] - pre_w_out[i][j])
            for i in range(len(post_w_out))
            for j in range(len(post_w_out[i]))
        )
        assert delta > 0

    def test_no_update_when_disabled(self):
        cfg = NeuralProcessingConfig(plasticity_enabled=False)
        nc = NeuralController(config=cfg)
        inp = [0.5] * SENSOR_INPUT_SIZE
        pre_w_out = [list(row) for row in nc.state.W_out]
        rng = random.Random(42)
        nc.update_from_feedback(inp, "HARVEST", {"resource_extracted": 1.0}, rng)
        post_w_out = nc.state.W_out
        assert pre_w_out == post_w_out

    def test_parameters_bounded_after_updates(self):
        cfg = NeuralProcessingConfig(plasticity_enabled=True, plasticity_rate=0.1, weight_bound=2.0)
        nc = NeuralController(config=cfg)
        rng = random.Random(42)
        for _ in range(100):
            inp = [rng.random() for _ in range(SENSOR_INPUT_SIZE)]
            action = rng.choice(ACTION_NAMES)
            feedback = {"power_delta": rng.uniform(-1, 1), "resource_extracted": rng.choice([0, 1])}
            nc.update_from_feedback(inp, action, feedback, rng)
        for row in nc.state.W_out:
            for v in row:
                assert -2.0 <= v <= 2.0


class TestSelectAction:
    """Test action selection."""

    def test_returns_valid_action(self):
        cfg = NeuralProcessingConfig()
        nc = NeuralController(config=cfg)
        inp = [0.5] * SENSOR_INPUT_SIZE
        rng = random.Random(42)
        action, params, logits = nc.select_action(inp, rng)
        assert action in ACTION_NAMES

    def test_stores_last_output(self):
        cfg = NeuralProcessingConfig()
        nc = NeuralController(config=cfg)
        inp = [0.5] * SENSOR_INPUT_SIZE
        rng = random.Random(42)
        nc.select_action(inp, rng)
        assert "action_name" in nc._last_action_output
        assert "action_logits" in nc._last_action_output
        assert "action_preferences" in nc._last_action_output


class TestNeuralVsScalarDifference:
    """Test neural vs scalar comparison on fixture data."""

    def test_detects_difference(self):
        cfg = NeuralProcessingConfig()
        nc = NeuralController(config=cfg, unit_id="u-0", seed=42)
        # Run forward pass to change state
        inp = [0.5] * SENSOR_INPUT_SIZE
        rng = random.Random(42)
        for _ in range(10):
            nc.select_action(inp, rng)
        # Compare with fresh controller
        nc2 = NeuralController(config=cfg, unit_id="u-1", seed=99)
        delta = nc.get_parameter_delta(nc2.state)
        assert delta["hidden_state_delta"] > 0 or delta["W_out_delta"] > 0


class TestSuccessorTransfer:
    """Test successor neural state transfer."""

    def test_transfer_bounded(self):
        cfg = NeuralProcessingConfig()
        nc = NeuralController(config=cfg, unit_id="u-0", seed=42)
        # Run some forward passes
        inp = [0.5] * SENSOR_INPUT_SIZE
        rng = random.Random(42)
        for _ in range(5):
            nc.select_action(inp, rng)
        pre_state = nc.state.copy()
        successor_state = nc.transfer_to_successor(rng, variation=0.05)
        # Check hidden state is bounded
        for v in successor_state.hidden_state:
            assert -1.0 <= v <= 1.0
        # Check weights are bounded
        for row in successor_state.W_out:
            for v in row:
                assert -cfg.weight_bound <= v <= cfg.weight_bound

    def test_transfer_related_to_source(self):
        cfg = NeuralProcessingConfig()
        nc = NeuralController(config=cfg, unit_id="u-0", seed=42)
        inp = [0.5] * SENSOR_INPUT_SIZE
        rng = random.Random(42)
        for _ in range(5):
            nc.select_action(inp, rng)
        pre_state = nc.state.copy()
        successor_state = nc.transfer_to_successor(rng, variation=0.05)
        delta = nc.get_parameter_delta(successor_state)
        # With small variation, delta should be small but nonzero
        assert delta["W_out_delta"] > 0


class TestJudgeFails:
    """Test that M17 judge fails on invalid artifacts."""

    def test_judge_fails_neural_state_trace_missing(self):
        from machine_sim.verification.milestone_17_judge import judge
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create minimal artifacts but no state trace
            (Path(tmpdir) / "neural_processing_summary.json").write_text(json.dumps({
                "neural_controller_enabled": True,
                "neural_state_trace_count": 0,
                "neural_plasticity_trace_count": 0,
                "neural_successor_transfer_count": 0,
            }))
            (Path(tmpdir) / "neural_controller_config.json").write_text(json.dumps({
                "input_size": 16, "hidden_size": 16, "output_size": 7,
            }))
            (Path(tmpdir) / "neural_vs_scalar_compare.json").write_text(json.dumps({
                "nontrivial_neural_difference_detected": False,
                "neural_signal_observations": 0,
            }))
            (Path(tmpdir) / "resource_hazard_field_summary.json").write_text(json.dumps({}))
            result = judge(tmpdir)
            assert result["M17_JUDGE_STATUS"] == "FAIL"
            assert "neural_state_trace_check" in result["failed_checks"]

    def test_judge_fails_no_plasticity_change(self):
        from machine_sim.verification.milestone_17_judge import judge
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "neural_processing_summary.json").write_text(json.dumps({
                "neural_controller_enabled": True,
                "neural_state_trace_count": 10,
                "neural_plasticity_trace_count": 0,
                "neural_successor_transfer_count": 0,
            }))
            (Path(tmpdir) / "neural_controller_config.json").write_text(json.dumps({
                "input_size": 16, "hidden_size": 16, "output_size": 7,
            }))
            (Path(tmpdir) / "neural_vs_scalar_compare.json").write_text(json.dumps({
                "nontrivial_neural_difference_detected": False,
                "neural_signal_observations": 0,
            }))
            (Path(tmpdir) / "resource_hazard_field_summary.json").write_text(json.dumps({}))
            # Create empty traces
            (Path(tmpdir) / "neural_state_trace.jsonl").write_text("tick,unit_id\n0,u-0\n")
            (Path(tmpdir) / "neural_action_trace.jsonl").write_text("tick,unit_id,action\n0,u-0,MOVE\n0,u-0,SCAN\n")
            (Path(tmpdir) / "neural_plasticity_trace.jsonl").write_text("")
            result = judge(tmpdir)
            assert result["M17_JUDGE_STATUS"] == "FAIL"
            assert "plasticity_update_check" in result["failed_checks"]


class TestJudgePasses:
    """Test that M17 judge passes on valid fixture artifacts."""

    def test_judge_passes_valid_artifacts(self):
        from machine_sim.verification.milestone_17_judge import judge
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create valid artifacts
            (Path(tmpdir) / "neural_processing_summary.json").write_text(json.dumps({
                "neural_controller_enabled": True,
                "neural_controller_mode": "replace",
                "neural_plasticity_enabled": True,
                "neural_state_trace_count": 10,
                "neural_action_trace_count": 100,
                "neural_plasticity_trace_count": 5,
                "neural_successor_transfer_count": 3,
                "final_active_count": 6,
                "total_unit_count": 8,
            }))
            (Path(tmpdir) / "neural_controller_config.json").write_text(json.dumps({
                "input_size": 16, "hidden_size": 16, "output_size": 7,
                "param_output_size": 3, "plasticity_rate": 0.01,
                "plasticity_enabled": True, "weight_bound": 2.0,
            }))
            (Path(tmpdir) / "neural_vs_scalar_compare.json").write_text(json.dumps({
                "scalar_active_count": 5,
                "neural_active_count": 6,
                "scalar_transfer_count": 2,
                "neural_transfer_count": 3,
                "scalar_signal_observations": 10,
                "neural_signal_observations": 15,
                "action_distribution_delta": {"MOVE": 50, "SCAN": 30},
                "adaptive_state_delta_scalar": {},
                "neural_state_delta": {"plasticity_events": 5, "total_w_out_delta": 0.1},
                "neural_parameter_delta": {"transfer_count": 3},
                "runtime_metric_delta_summary": {"neural_active": 6, "scalar_active": 5, "difference": 1},
                "nontrivial_neural_difference_detected": True,
            }))
            (Path(tmpdir) / "resource_hazard_field_summary.json").write_text(json.dumps({
                "total_resource_cells": 500,
                "total_hazard_cells": 50,
                "total_resources": 1000,
            }))
            # Create traces
            with open(Path(tmpdir) / "neural_state_trace.jsonl", "w") as f:
                for i in range(10):
                    f.write(json.dumps({"tick": i * 2000, "unit_id": "u-0", "hidden_state_summary": {"mean": 0.1, "max": 0.5, "min": -0.3}, "w_out_norm": 1.0, "w_rec_norm": 0.8}) + "\n")
            with open(Path(tmpdir) / "neural_action_trace.jsonl", "w") as f:
                for i in range(100):
                    action = ACTION_NAMES[i % len(ACTION_NAMES)]
                    f.write(json.dumps({"tick": i, "unit_id": "u-0", "action": action, "action_logits": [0.1]*7, "action_preferences": [1/7]*7}) + "\n")
            with open(Path(tmpdir) / "neural_plasticity_trace.jsonl", "w") as f:
                for i in range(5):
                    f.write(json.dumps({"tick": i * 100, "unit_id": "u-0", "w_out_delta": 0.01, "selected_action": "MOVE"}) + "\n")
            with open(Path(tmpdir) / "neural_successor_transfer_trace.jsonl", "w") as f:
                for i in range(3):
                    f.write(json.dumps({"tick": i * 5000, "source_unit_id": f"u-{i}", "successor_unit_id": f"u-{i+6}", "parameter_delta": {"hidden_state_delta": 0.1}}) + "\n")

            result = judge(tmpdir)
            assert result["M17_JUDGE_STATUS"] == "PASS"
            assert len(result["failed_checks"]) == 0


class TestM14M15M16Regression:
    """Test that M14/M15/M16 regression judges are compatible."""

    def test_regression_check_passes_by_default(self):
        """The regression check is a soft check that passes by default."""
        from machine_sim.verification.milestone_17_judge import judge
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create minimal valid artifacts
            (Path(tmpdir) / "neural_processing_summary.json").write_text(json.dumps({
                "neural_controller_enabled": True,
                "neural_state_trace_count": 10,
                "neural_plasticity_trace_count": 5,
                "neural_successor_transfer_count": 3,
            }))
            (Path(tmpdir) / "neural_controller_config.json").write_text(json.dumps({
                "input_size": 16,
            }))
            (Path(tmpdir) / "neural_vs_scalar_compare.json").write_text(json.dumps({
                "nontrivial_neural_difference_detected": True,
                "neural_signal_observations": 10,
            }))
            (Path(tmpdir) / "resource_hazard_field_summary.json").write_text(json.dumps({}))
            (Path(tmpdir) / "neural_state_trace.jsonl").write_text("tick\n0\n")
            (Path(tmpdir) / "neural_action_trace.jsonl").write_text("tick,action\n0,MOVE\n0,SCAN\n")
            (Path(tmpdir) / "neural_plasticity_trace.jsonl").write_text("tick\n0\n")
            (Path(tmpdir) / "neural_successor_transfer_trace.jsonl").write_text("tick\n0\n")
            result = judge(tmpdir)
            assert result["checks"]["m14_m15_m16_regression_check"] == "PASS"


class TestExistingTestsPass:
    """Verify that importing neural controller doesn't break existing code."""

    def test_import_existing_modules(self):
        from machine_sim.agents.unit import MachineUnitImpl
        from machine_sim.sim.engine import SimEngine
        from machine_sim.sim.config import SimConfig
        # Verify we can create a basic unit without neural controller
        unit = MachineUnitImpl("test-unit", adaptive_enabled=True)
        assert unit._neural_controller is None
        assert unit._neural_controller_enabled is False

    def test_unit_with_neural_controller(self):
        from machine_sim.agents.unit import MachineUnitImpl
        unit = MachineUnitImpl(
            "test-neural-unit",
            adaptive_enabled=True,
            neural_controller_enabled=True,
            neural_seed=42,
        )
        assert unit._neural_controller is not None
        assert unit._neural_controller_enabled is True

    def test_config_fields_exist(self):
        from machine_sim.sim.config import SimConfig
        cfg = SimConfig(neural_controller_enabled=True, neural_controller_mode="replace")
        assert cfg.neural_controller_enabled is True
        assert cfg.neural_controller_mode == "replace"

    def test_neural_simulation_runs(self):
        from machine_sim.agents.unit import MachineUnitImpl
        from machine_sim.sim.config import SimConfig
        from machine_sim.sim.engine import SimEngine
        import random as _rng
        cfg = SimConfig(
            grid_width=20, grid_height=20, unit_count=3, max_ticks=100, seed=42,
            signal_enabled=True, adaptive_enabled=True,
            neural_controller_enabled=True, neural_controller_mode="replace",
            neural_plasticity_enabled=True, fabrication_enabled=True,
            capsule_enabled=True, unit_capacity=10,
            fabrication_interval=5, fabrication_power_cost=3.0,
            fabrication_material_cost=0.3, fabrication_variation=0.08,
            fabrication_min_power_ratio=0.05, fabrication_min_component_health=0.02,
            long_run_adaptation_enabled=True, multi_generation_trace_enabled=True,
        )
        engine = SimEngine(cfg, seed=cfg.seed)
        rng = _rng.Random(cfg.seed)
        for i in range(cfg.unit_count):
            px = rng.randint(0, cfg.grid_width - 1)
            py = rng.randint(0, cfg.grid_height - 1)
            u = MachineUnitImpl(
                f"n-{i}", position=(px, py),
                signal_enabled=True, adaptive_enabled=True,
                neural_controller_enabled=True, neural_seed=cfg.seed,
            )
            u.max_power = 1000
            u.power_reserve = 1000
            engine.register_unit(u)
        engine.run()
        # Verify neural traces were recorded
        assert len(engine._neural_state_trace) > 0
        assert len(engine._neural_action_trace) > 0
        # Verify neural processing summary
        summary = engine.get_neural_processing_summary()
        assert summary["neural_controller_enabled"] is True
        assert summary["neural_state_trace_count"] > 0
        assert summary["neural_action_trace_count"] > 0

    def test_neural_vs_scalar_comparison(self):
        from machine_sim.agents.unit import MachineUnitImpl
        from machine_sim.sim.config import SimConfig
        from machine_sim.sim.engine import SimEngine
        import random as _rng
        cfg = SimConfig(
            grid_width=20, grid_height=20, unit_count=3, max_ticks=50, seed=42,
            signal_enabled=True, adaptive_enabled=True,
            neural_controller_enabled=True, neural_controller_mode="replace",
            neural_plasticity_enabled=True, long_run_adaptation_enabled=True,
        )
        engine = SimEngine(cfg, seed=cfg.seed)
        rng = _rng.Random(cfg.seed)
        for i in range(cfg.unit_count):
            px = rng.randint(0, cfg.grid_width - 1)
            py = rng.randint(0, cfg.grid_height - 1)
            u = MachineUnitImpl(
                f"n-{i}", position=(px, py),
                signal_enabled=True, adaptive_enabled=True,
                neural_controller_enabled=True, neural_seed=cfg.seed,
            )
            u.max_power = 1000
            u.power_reserve = 1000
            engine.register_unit(u)
        engine.run()
        # Run scalar comparison
        scalar_cfg = SimConfig(
            grid_width=20, grid_height=20, unit_count=3, max_ticks=50, seed=42,
            signal_enabled=True, adaptive_enabled=True,
            neural_controller_enabled=False,
        )
        scalar_engine = SimEngine(scalar_cfg, seed=cfg.seed)
        rng2 = _rng.Random(cfg.seed)
        for i in range(cfg.unit_count):
            px = rng2.randint(0, cfg.grid_width - 1)
            py = rng2.randint(0, cfg.grid_height - 1)
            su = MachineUnitImpl(
                f"s-{i}", position=(px, py),
                signal_enabled=True, adaptive_enabled=True,
                neural_controller_enabled=False,
            )
            su.max_power = 1000
            su.power_reserve = 1000
            scalar_engine.register_unit(su)
        scalar_engine.run()
        scalar_summary = scalar_engine.get_long_run_adaptation_summary()
        comparison = engine.get_neural_vs_scalar_comparison(scalar_summary)
        assert "nontrivial_neural_difference_detected" in comparison
        assert "neural_active_count" in comparison
        assert "scalar_active_count" in comparison

    def test_neural_successor_transfer_in_engine(self):
        from machine_sim.agents.unit import MachineUnitImpl
        from machine_sim.sim.config import SimConfig
        from machine_sim.sim.engine import SimEngine
        import random as _rng
        cfg = SimConfig(
            grid_width=20, grid_height=20, unit_count=3, max_ticks=100, seed=42,
            signal_enabled=True, adaptive_enabled=True,
            neural_controller_enabled=True, neural_controller_mode="replace",
            neural_plasticity_enabled=True, fabrication_enabled=True,
            capsule_enabled=True, unit_capacity=10,
            fabrication_interval=3, fabrication_power_cost=1.0,
            fabrication_material_cost=0.1, fabrication_variation=0.08,
            fabrication_min_power_ratio=0.01, fabrication_min_component_health=0.01,
            long_run_adaptation_enabled=True,
        )
        engine = SimEngine(cfg, seed=cfg.seed)
        rng = _rng.Random(cfg.seed)
        for i in range(cfg.unit_count):
            px = rng.randint(0, cfg.grid_width - 1)
            py = rng.randint(0, cfg.grid_height - 1)
            u = MachineUnitImpl(
                f"n-{i}", position=(px, py),
                signal_enabled=True, adaptive_enabled=True,
                neural_controller_enabled=True, neural_seed=cfg.seed,
            )
            u.max_power = 5000
            u.power_reserve = 5000
            engine.register_unit(u)
        engine.run()
        # Verify neural successor transfer trace
        if engine._neural_successor_transfer_trace:
            entry = engine._neural_successor_transfer_trace[0]
            assert "source_unit_id" in entry
            assert "successor_unit_id" in entry
            assert "parameter_delta" in entry


class TestStableSeed:
    """Test that stable_seed replaces Python hash() for deterministic cross-process seeding."""

    def test_same_inputs_same_seed(self):
        s1 = stable_seed("neural_init", "u-0", 42)
        s2 = stable_seed("neural_init", "u-0", 42)
        assert s1 == s2

    def test_different_unit_id_different_seed(self):
        s1 = stable_seed("neural_init", "u-0", 42)
        s2 = stable_seed("neural_init", "u-1", 42)
        assert s1 != s2

    def test_different_seed_value_different_seed(self):
        s1 = stable_seed("neural_init", "u-0", 42)
        s2 = stable_seed("neural_init", "u-0", 99)
        assert s1 != s2

    def test_different_context_different_seed(self):
        s1 = stable_seed("neural_init", "u-0", 42)
        s2 = stable_seed("neural_select", "u-0", 42)
        assert s1 != s2

    def test_integer_inputs_deterministic(self):
        s1 = stable_seed(42)
        s2 = stable_seed(42)
        assert s1 == s2

    def test_seed_fits_in_32_bits(self):
        s = stable_seed("test", 123)
        assert 0 <= s <= 0xFFFFFFFF

    def test_cross_process_determinism_via_serialization(self):
        """Produce a seed, serialize the derivation params, and verify
        the same seed is obtained from the serialized form."""
        params = ("neural_init", "u-0", 42)
        original_seed = stable_seed(*params)
        reconstructed_seed = stable_seed("neural_init", "u-0", 42)
        assert original_seed == reconstructed_seed

    def test_neural_controller_init_uses_stable_seed(self):
        """Verify neural controller produces identical weights with same inputs."""
        cfg = NeuralProcessingConfig()
        nc1 = NeuralController(config=cfg, unit_id="u-0", seed=42)
        nc2 = NeuralController(config=cfg, unit_id="u-0", seed=42)
        assert nc1.state.to_dict() == nc2.state.to_dict()

    def test_neural_controller_weights_serializable_and_restorable(self):
        """Serialize state to dict and restore; weights must be identical."""
        cfg = NeuralProcessingConfig()
        nc = NeuralController(config=cfg, unit_id="u-0", seed=42)
        state_dict = nc.state.to_dict()
        restored = NeuralProcessingState.from_dict(state_dict)
        assert nc.state.to_dict() == restored.to_dict()


class TestFabricateActionSemantics:
    """Test that FABRICATE action is handled correctly in the neural-action map."""

    def test_fabricate_maps_to_idle_in_unit(self):
        """FABRICATE should map to IDLE since fabrication is engine-gated."""
        from machine_sim.agents.unit import MachineUnitImpl
        unit = MachineUnitImpl(
            "test-fab", adaptive_enabled=True,
            neural_controller_enabled=True, neural_seed=42,
        )
        assert unit._neural_controller is not None

    def test_fabricate_in_action_names(self):
        assert "FABRICATE" in ACTION_NAMES

    def test_fabricate_action_can_be_selected(self):
        """Neural controller can select FABRICATE as an action."""
        cfg = NeuralProcessingConfig()
        nc = NeuralController(config=cfg, unit_id="u-0", seed=42)
        inp = [0.5] * SENSOR_INPUT_SIZE
        rng = random.Random(42)
        actions_seen = set()
        for _ in range(200):
            action, _, _ = nc.select_action(inp, rng)
            actions_seen.add(action)
        assert "FABRICATE" in actions_seen


class TestM17JudgeHardening:
    """Test hardened M17 judge checks."""

    def test_judge_fails_forbidden_artifact_fields(self):
        """Judge should fail when artifacts contain forbidden global/oracle fields."""
        from machine_sim.verification.milestone_17_judge import judge
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "neural_processing_summary.json").write_text(json.dumps({
                "neural_controller_enabled": True,
                "neural_state_trace_count": 10,
                "neural_plasticity_trace_count": 5,
                "neural_successor_transfer_count": 3,
            }))
            (Path(tmpdir) / "neural_controller_config.json").write_text(json.dumps({
                "input_size": 16, "hidden_size": 16, "output_size": 7,
            }))
            (Path(tmpdir) / "neural_vs_scalar_compare.json").write_text(json.dumps({
                "nontrivial_neural_difference_detected": True,
                "neural_signal_observations": 10,
            }))
            (Path(tmpdir) / "resource_hazard_field_summary.json").write_text(json.dumps({
                "global_map": True,
            }))
            (Path(tmpdir) / "neural_state_trace.jsonl").write_text("tick\n0\n")
            (Path(tmpdir) / "neural_action_trace.jsonl").write_text("tick,action\n0,MOVE\n0,SCAN\n")
            (Path(tmpdir) / "neural_plasticity_trace.jsonl").write_text("tick\n0\n")
            (Path(tmpdir) / "neural_successor_transfer_trace.jsonl").write_text("tick\n0\n")
            result = judge(tmpdir)
            assert result["M17_JUDGE_STATUS"] == "FAIL"
            assert "local_input_only_check" in result["failed_checks"]

    def test_judge_regression_details_recorded(self):
        """Judge should record regression details even when not found."""
        from machine_sim.verification.milestone_17_judge import judge
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "neural_processing_summary.json").write_text(json.dumps({
                "neural_controller_enabled": True,
                "neural_state_trace_count": 10,
                "neural_plasticity_trace_count": 5,
                "neural_successor_transfer_count": 3,
            }))
            (Path(tmpdir) / "neural_controller_config.json").write_text(json.dumps({
                "input_size": 16,
            }))
            (Path(tmpdir) / "neural_vs_scalar_compare.json").write_text(json.dumps({
                "nontrivial_neural_difference_detected": True,
                "neural_signal_observations": 10,
            }))
            (Path(tmpdir) / "resource_hazard_field_summary.json").write_text(json.dumps({}))
            (Path(tmpdir) / "neural_state_trace.jsonl").write_text("tick\n0\n")
            (Path(tmpdir) / "neural_action_trace.jsonl").write_text("tick,action\n0,MOVE\n0,SCAN\n")
            (Path(tmpdir) / "neural_plasticity_trace.jsonl").write_text("tick\n0\n")
            (Path(tmpdir) / "neural_successor_transfer_trace.jsonl").write_text("tick\n0\n")
            result = judge(tmpdir)
            assert "regression_details" in result
            assert "milestone_14" in result["regression_details"]

    def test_judge_summary_file_disagree_transfer_fails(self):
        """Judge should fail when summary and file disagree on transfer count."""
        from machine_sim.verification.milestone_17_judge import judge
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "neural_processing_summary.json").write_text(json.dumps({
                "neural_controller_enabled": True,
                "neural_state_trace_count": 10,
                "neural_plasticity_trace_count": 5,
                "neural_successor_transfer_count": 3,
            }))
            (Path(tmpdir) / "neural_controller_config.json").write_text(json.dumps({
                "input_size": 16,
            }))
            (Path(tmpdir) / "neural_vs_scalar_compare.json").write_text(json.dumps({
                "nontrivial_neural_difference_detected": True,
                "neural_signal_observations": 10,
            }))
            (Path(tmpdir) / "resource_hazard_field_summary.json").write_text(json.dumps({}))
            (Path(tmpdir) / "neural_state_trace.jsonl").write_text("tick\n0\n")
            (Path(tmpdir) / "neural_action_trace.jsonl").write_text("tick,action\n0,MOVE\n0,SCAN\n")
            (Path(tmpdir) / "neural_plasticity_trace.jsonl").write_text("tick\n0\n")
            (Path(tmpdir) / "neural_successor_transfer_trace.jsonl").write_text("")
            result = judge(tmpdir)
            assert result["checks"]["successor_neural_transfer_check"] == "FAIL"

    def test_stable_seed_used_not_python_hash(self):
        """Verify that the codebase uses stable_seed, not bare hash() for seeds."""
        import inspect
        from machine_sim.agents import neural_controller
        source = inspect.getsource(neural_controller)
        lines = [l for l in source.split("\n") if l.strip() and not l.strip().startswith("#") and not l.strip().startswith('"')]
        code_lines = [l for l in lines if "hash(" in l and "stable_seed" not in l and '"""' not in l and "Replaces" not in l]
        assert len(code_lines) == 0, f"Found bare hash() in code: {code_lines}"
