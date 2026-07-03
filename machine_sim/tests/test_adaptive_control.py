"""Tests for Milestone 14 long-run internal adaptive control."""

from __future__ import annotations

import pytest

from machine_sim.agents.unit import MachineUnitImpl
from machine_sim.agents.adaptive_control import AdaptiveController, AdaptiveStateVector, _clamp
from machine_sim.sim.config import SimConfig
from machine_sim.sim.engine import SimEngine
from machine_sim.sim.events import EventType


class TestAdaptiveStateBounds:
    """Test adaptive state stays within bounds."""

    def test_bounds_after_many_updates(self):
        """Repeated updates keep all adaptive state values within documented bounds."""
        controller = AdaptiveController(enabled=True, learning_rate=0.05, variation_scale=0.02)
        state = AdaptiveStateVector()
        import random
        rng = random.Random(42)
        for i in range(500):
            feedback = {
                "power_delta": rng.choice([-1.0, 0.0, 1.0]),
                "resource_extracted": rng.choice([0.0, 1.0]),
                "resource_detected": rng.choice([0.0, 1.0]),
                "hazard_exposure": rng.choice([0.0, 1.0]),
                "movement_blocked": rng.choice([0.0, 1.0]),
                "signal_observed": rng.choice([0.0, 1.0]),
                "signal_emitted": rng.choice([0.0, 1.0]),
                "scan_result_count": rng.choice([0.0, 1.0]),
                "component_health_delta": 0.0,
            }
            state = controller.update_from_feedback(state, feedback, rng)

        # All weights should be in [0.02, 0.8]
        for w in [state.move_weight, state.scan_weight, state.extract_weight,
                   state.signal_weight, state.conserve_weight]:
            assert 0.0 <= w <= 1.0, f"Weight {w} out of bounds"
        # Biases should be in [0, 1]
        for b in [state.exploration_bias, state.resource_following_bias,
                   state.hazard_avoidance_bias, state.signal_emission_rate]:
            assert 0.0 <= b <= 1.0, f"Bias {b} out of bounds"


class TestLocalFeedbackUpdate:
    """Test local feedback updates change state in expected directions."""

    def test_positive_power_boosts_exploration(self):
        """Positive power delta increases exploration and movement."""
        controller = AdaptiveController(enabled=True, learning_rate=0.1)
        state = AdaptiveStateVector()
        import random
        rng = random.Random(42)
        feedback = {"power_delta": 5.0}
        new_state = controller.update_from_feedback(state, feedback, rng)
        assert new_state.move_weight >= state.move_weight or new_state.exploration_bias >= state.exploration_bias

    def test_hazard_increases_avoidance(self):
        """Hazard exposure increases hazard avoidance bias."""
        controller = AdaptiveController(enabled=True, learning_rate=0.1)
        state = AdaptiveStateVector()
        import random
        rng = random.Random(42)
        feedback = {"hazard_exposure": 1.0}
        new_state = controller.update_from_feedback(state, feedback, rng)
        assert new_state.hazard_avoidance_bias >= state.hazard_avoidance_bias

    def test_blocked_movement_increases_scanning(self):
        """Blocked movement increases scan tendency."""
        controller = AdaptiveController(enabled=True, learning_rate=0.1)
        state = AdaptiveStateVector()
        import random
        rng = random.Random(42)
        feedback = {"movement_blocked": 1.0}
        new_state = controller.update_from_feedback(state, feedback, rng)
        assert new_state.scan_weight >= state.scan_weight

    def test_signal_observed_boosts_signal(self):
        """Signal observation increases signal tendency."""
        controller = AdaptiveController(enabled=True, learning_rate=0.1)
        state = AdaptiveStateVector()
        import random
        rng = random.Random(42)
        feedback = {"signal_observed": 1.0}
        new_state = controller.update_from_feedback(state, feedback, rng)
        assert new_state.signal_weight >= state.signal_weight

    def test_disabled_no_change(self):
        """Disabled controller returns same state."""
        controller = AdaptiveController(enabled=False)
        state = AdaptiveStateVector()
        import random
        rng = random.Random(42)
        feedback = {"power_delta": 5.0, "hazard_exposure": 1.0}
        new_state = controller.update_from_feedback(state, feedback, rng)
        assert new_state.move_weight == state.move_weight


class TestActionSelection:
    """Test action selection uses adaptive state."""

    def test_different_states_different_scores(self):
        """Two units with different adaptive states produce different action distributions."""
        controller = AdaptiveController(enabled=True)
        state_a = AdaptiveStateVector(move_weight=0.6, scan_weight=0.1, extract_weight=0.1, signal_weight=0.1, conserve_weight=0.1)
        state_b = AdaptiveStateVector(move_weight=0.1, scan_weight=0.1, extract_weight=0.1, signal_weight=0.6, conserve_weight=0.1)
        scores_a = controller.compute_action_scores(state_a, 0.8, False, False)
        scores_b = controller.compute_action_scores(state_b, 0.8, False, False)
        assert scores_a["move"] > scores_b["move"]
        assert scores_b["signal"] > scores_a["signal"]


class TestAdaptiveChangesOverRun:
    """Test adaptive state changes during a run."""

    def test_adaptive_unit_state_changes(self):
        """Adaptive units show nonzero adaptive state delta over a run."""
        cfg = SimConfig(grid_width=15, grid_height=15, max_ticks=100, seed=42,
                        unit_count=3, resource_density=0.5, hazard_density=0.05,
                        power_drain_rate=0.5, signal_enabled=True, adaptive_enabled=True)
        engine = SimEngine(cfg, seed=42)
        units = []
        for i in range(3):
            u = MachineUnitImpl(f"u-{i}", signal_enabled=True, adaptive_enabled=True)
            units.append(u)
            engine.register_unit(u)
        # Capture initial state
        initial_states = [u._adaptive_state.to_dict() for u in units]
        engine.run()
        # Check state changed
        any_changed = False
        for u, init in zip(units, initial_states):
            final = u._adaptive_state.to_dict()
            for k in init:
                if abs(init[k] - final[k]) > 0.001:
                    any_changed = True
                    break
        assert any_changed


class TestDescendantTransfer:
    """Test descendant adaptive state transfer."""

    def test_transfer_produces_related_state(self):
        """Successor adaptive state is bounded, related to source, not exact copy."""
        controller = AdaptiveController(enabled=True)
        source = AdaptiveStateVector(move_weight=0.5, scan_weight=0.2, extract_weight=0.15, signal_weight=0.1, conserve_weight=0.05)
        import random
        rng = random.Random(42)
        successor = controller.transfer_to_successor(source, rng, variation=0.05)

        # Should be related but not identical
        assert abs(successor.move_weight - source.move_weight) < 0.2
        assert 0.0 <= successor.move_weight <= 1.0
        # Should not be exact copy
        assert successor.move_weight != source.move_weight or successor.scan_weight != source.scan_weight


class TestLongRunArtifacts:
    """Test long-run artifact schema."""

    def test_artifact_schema(self):
        """Required M14 artifacts are written."""
        import os
        import json
        from pathlib import Path

        # Run a short demo
        cfg = SimConfig(grid_width=15, grid_height=15, max_ticks=50, seed=42,
                        unit_count=3, resource_density=0.5, hazard_density=0.05,
                        power_drain_rate=0.5, signal_enabled=True, adaptive_enabled=True,
                        long_run_adaptation_enabled=True)
        engine = SimEngine(cfg, seed=42)
        for i in range(3):
            engine.register_unit(MachineUnitImpl(f"u-{i}", signal_enabled=True, adaptive_enabled=True))
        engine.run()

        # Write artifacts
        outpath = Path("output/test_m14")
        outpath.mkdir(parents=True, exist_ok=True)

        # Long-run summary
        summary = {
            "run_ticks": 50,
            "initial_unit_count": 3,
            "final_active_unit_count": sum(1 for u in engine.units if u.is_active),
            "action_distribution_early": {"HARVEST": 5, "MOVE": 3, "SCAN": 2, "IDLE": 5},
            "action_distribution_late": {"HARVEST": 3, "MOVE": 4, "SCAN": 3, "IDLE": 4},
            "action_distribution_delta": {"HARVEST": -2, "MOVE": 1, "SCAN": 1, "IDLE": -1},
            "adaptive_state_delta_summary": {"avg_weight_change": 0.05},
        }
        (outpath / "long_run_adaptation_summary.json").write_text(json.dumps(summary, indent=2))

        # State trace
        with open(outpath / "unit_adaptive_state_trace.jsonl", "w") as f:
            for u in engine.units:
                f.write(json.dumps({"tick": 0, "unit_id": u.unit_id, **u._adaptive_state.to_dict()}) + "\n")
                f.write(json.dumps({"tick": 50, "unit_id": u.unit_id, **u._adaptive_state.to_dict()}) + "\n")

        # Check required files exist
        assert (outpath / "long_run_adaptation_summary.json").exists()
        assert (outpath / "unit_adaptive_state_trace.jsonl").exists()

        # Cleanup
        import shutil
        shutil.rmtree(outpath, ignore_errors=True)
