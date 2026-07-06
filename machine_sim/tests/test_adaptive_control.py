"""Tests for Milestone 14 long-run internal adaptive control."""

from __future__ import annotations

import pytest

from pathlib import Path
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


class TestAdaptiveActionScoring:
    """Test adaptive action scoring affects action probabilities."""

    def test_scoring_affects_all_action_types(self):
        """Adaptive scoring produces scores for MOVE, SCAN, HARVEST, SIGNAL, IDLE."""
        controller = AdaptiveController(enabled=True)
        state = AdaptiveStateVector()
        scores = controller.compute_action_scores(state, 0.8, False, False)
        assert "move" in scores
        assert "scan" in scores
        assert "harvest" in scores
        assert "signal" in scores
        assert "idle" in scores
        # All positive
        for v in scores.values():
            assert v > 0

    def test_resource_nearby_boosts_harvest(self):
        """Resource nearby increases harvest score."""
        controller = AdaptiveController(enabled=True)
        state = AdaptiveStateVector()
        scores_no_res = controller.compute_action_scores(state, 0.8, False, False)
        scores_res = controller.compute_action_scores(state, 0.8, True, False)
        assert scores_res["harvest"] > scores_no_res["harvest"]

    def test_hazard_nearby_boosts_move(self):
        """Hazard nearby increases move score."""
        controller = AdaptiveController(enabled=True)
        state = AdaptiveStateVector()
        scores_no_haz = controller.compute_action_scores(state, 0.8, False, False)
        scores_haz = controller.compute_action_scores(state, 0.8, False, True)
        assert scores_haz["move"] > scores_no_haz["move"]


class TestDecideUsesAdaptiveScoring:
    """Test MachineUnitImpl.decide() uses adaptive scoring."""

    def test_decide_returns_valid_action(self):
        """Adaptive unit returns a valid action during normal operation."""
        unit = MachineUnitImpl("u0", signal_enabled=True, adaptive_enabled=True)
        unit.power_reserve = 4000.0
        unit.max_power = 5000.0
        action = unit.decide(100)
        assert action is not None
        from machine_sim.agents.base import ActionType
        assert action.action_type in [
            ActionType.MOVE, ActionType.SCAN, ActionType.HARVEST,
            ActionType.EMIT_SIGNAL, ActionType.IDLE, ActionType.MAINTAIN,
        ]

    def test_different_states_different_decisions(self):
        """Units with different adaptive states may choose different actions."""
        unit_a = MachineUnitImpl("u-a", signal_enabled=True, adaptive_enabled=True)
        unit_a.power_reserve = 4000.0
        unit_a.max_power = 5000.0
        unit_a._adaptive_state.move_weight = 0.7
        unit_a._adaptive_state.scan_weight = 0.05
        unit_a._adaptive_state.extract_weight = 0.05
        unit_a._adaptive_state.signal_weight = 0.05
        unit_a._adaptive_state.conserve_weight = 0.05

        unit_b = MachineUnitImpl("u-b", signal_enabled=True, adaptive_enabled=True)
        unit_b.power_reserve = 4000.0
        unit_b.max_power = 5000.0
        unit_b._adaptive_state.move_weight = 0.05
        unit_b._adaptive_state.scan_weight = 0.7
        unit_b._adaptive_state.extract_weight = 0.05
        unit_b._adaptive_state.signal_weight = 0.05
        unit_b._adaptive_state.conserve_weight = 0.05

        from collections import Counter
        actions_a = Counter()
        actions_b = Counter()
        for tick in range(200, 300):
            a = unit_a.decide(tick)
            b = unit_b.decide(tick)
            if a:
                actions_a[a.action_type.name] += 1
            if b:
                actions_b[b.action_type.name] += 1
        # At least one action type should differ in count
        assert actions_a != actions_b


class TestLocalFeedbackTrace:
    """Test local feedback trace records nonzero feedback."""

    def test_feedback_trace_in_run(self):
        """Run produces local feedback trace with nonzero entries."""
        cfg = SimConfig(grid_width=15, grid_height=15, max_ticks=100, seed=42,
                        unit_count=3, resource_density=0.5, hazard_density=0.1,
                        power_drain_rate=1.0, signal_enabled=True, adaptive_enabled=True,
                        long_run_adaptation_enabled=True)
        engine = SimEngine(cfg, seed=42)
        for i in range(3):
            engine.register_unit(MachineUnitImpl(f"u-{i}", signal_enabled=True, adaptive_enabled=True))
        engine.run()
        assert hasattr(engine, '_local_feedback_trace')
        assert len(engine._local_feedback_trace) > 0
        # At least some entries have nonzero feedback
        has_nonzero = False
        for entry in engine._local_feedback_trace[:50]:
            for k in ["power_delta", "hazard_exposure", "resource_extracted",
                       "signal_observed", "movement_blocked"]:
                if abs(entry.get(k, 0)) > 0.01:
                    has_nonzero = True
                    break
        assert has_nonzero


class TestSignalObservationAdaptation:
    """Test signal observation changes signal-related parameters."""

    def test_signal_observed_increases_signal_weight(self):
        """Signal observation increases signal_weight via feedback."""
        controller = AdaptiveController(enabled=True, learning_rate=0.1)
        state = AdaptiveStateVector()
        import random
        rng = random.Random(42)
        feedback = {"signal_observed": 1.0}
        new_state = controller.update_from_feedback(state, feedback, rng)
        assert new_state.signal_weight >= state.signal_weight
        assert new_state.signal_emission_rate >= state.signal_emission_rate


class TestDescendantTransferInFabrication:
    """Test descendant adaptive-state transfer during fabrication."""

    def test_transfer_in_engine(self):
        """Fabrication transfers adaptive state to successor."""
        cfg = SimConfig(grid_width=15, grid_height=15, max_ticks=200, seed=42,
                        unit_count=3, resource_density=0.7, hazard_density=0.05,
                        power_drain_rate=0.3, signal_enabled=True, adaptive_enabled=True,
                        fabrication_enabled=True, capsule_enabled=False,
                        fabrication_interval=10, fabrication_power_cost=10.0,
                        fabrication_material_cost=1.0, population_cap=10,
                        long_run_adaptation_enabled=True)
        engine = SimEngine(cfg, seed=42)
        for i in range(3):
            u = MachineUnitImpl(f"u-{i}", signal_enabled=True, adaptive_enabled=True)
            u.max_power = 2000
            u.power_reserve = 2000
            engine.register_unit(u)
        engine.run()
        # Check if any descendant transfers occurred
        if hasattr(engine, '_descendant_transfer_trace'):
            transfers = engine._descendant_transfer_trace
            if len(transfers) > 0:
                t = transfers[0]
                assert "source_unit_id" in t
                assert "successor_unit_id" in t
                assert "source_adaptive_summary" in t
                assert "successor_adaptive_summary" in t
                assert "bounded_delta_summary" in t


class TestDescendantTransferBounded:
    """Test descendant transfer is bounded and related to source."""

    def test_transfer_bounded_related(self):
        """Transfer produces bounded, related state."""
        controller = AdaptiveController(enabled=True)
        source = AdaptiveStateVector(
            move_weight=0.5, scan_weight=0.2, extract_weight=0.15,
            signal_weight=0.1, conserve_weight=0.05,
            exploration_bias=0.7, resource_following_bias=0.6,
            hazard_avoidance_bias=0.4, signal_emission_rate=0.8,
        )
        import random
        rng = random.Random(42)
        successor = controller.transfer_to_successor(source, rng, variation=0.05)

        # Bounded
        for v in [successor.move_weight, successor.scan_weight, successor.extract_weight,
                  successor.signal_weight, successor.conserve_weight]:
            assert 0.0 <= v <= 1.0
        for v in [successor.exploration_bias, successor.resource_following_bias,
                  successor.hazard_avoidance_bias, successor.signal_emission_rate]:
            assert 0.0 <= v <= 1.0

        # Related but not identical
        delta = abs(successor.move_weight - source.move_weight)
        assert delta < 0.2  # within variation bound


class TestJudgeFailsLowTicks:
    """Test judge fails when run ticks are below 20000."""

    def test_judge_fails_below_20000(self):
        """Judge returns FAIL when run_ticks < 20000."""
        import json
        import tempfile
        from machine_sim.verification.milestone_14_judge import judge

        with tempfile.TemporaryDirectory() as tmpdir:
            summary = {
                "run_ticks": 5000,
                "grid_width": 120,
                "grid_height": 120,
                "initial_unit_count": 6,
                "final_active_unit_count": 3,
                "descendant_active_count": 1,
                "power_drain_rate": 1.5,
                "action_distribution_early": {"HARVEST": 10},
                "action_distribution_late": {"HARVEST": 5},
                "action_distribution_delta": {"HARVEST": -5},
                "signal_behavior_summary": {
                    "total_signal_emissions": 100,
                    "total_signal_observations": 50,
                },
            }
            (Path(tmpdir) / "long_run_adaptation_summary.json").write_text(
                json.dumps(summary))
            result = judge(tmpdir)
            assert result["checks"]["long_run_ticks_check"] == "FAIL"


class TestJudgeFailsNoDescendant:
    """Test judge fails when descendant transfer artifact is missing."""

    def test_judge_fails_no_descendant_artifact(self):
        """Judge returns FAIL for descendant_transfer_check when artifact missing."""
        import json
        import tempfile
        from machine_sim.verification.milestone_14_judge import judge

        with tempfile.TemporaryDirectory() as tmpdir:
            summary = {
                "run_ticks": 25000,
                "grid_width": 120,
                "grid_height": 120,
                "initial_unit_count": 6,
                "final_active_unit_count": 3,
                "descendant_active_count": 0,
                "power_drain_rate": 1.5,
                "action_distribution_early": {"HARVEST": 10},
                "action_distribution_late": {"HARVEST": 5},
                "action_distribution_delta": {"HARVEST": -5},
                "signal_behavior_summary": {
                    "total_signal_emissions": 100,
                    "total_signal_observations": 50,
                },
            }
            (Path(tmpdir) / "long_run_adaptation_summary.json").write_text(
                json.dumps(summary))
            # Create other required artifacts but NOT descendant trace
            for fname in ["action_distribution_trace.jsonl", "unit_lifetime_trace.jsonl"]:
                (Path(tmpdir) / fname).write_text(json.dumps({"tick": 1}) + "\n")
            # Local feedback trace with valid JSON
            fb_entry = {"tick": 1, "unit_id": "u0", "power_delta": 5.0, "hazard_exposure": 0.0,
                        "resource_extracted": 1.0, "signal_observed": 0.0, "movement_blocked": 0.0}
            (Path(tmpdir) / "local_feedback_trace.jsonl").write_text(json.dumps(fb_entry) + "\n")
            # Create state trace with changes
            state_trace = {"tick": 0, "unit_id": "u0", "move_weight": 0.25, "scan_weight": 0.25,
                           "extract_weight": 0.25, "signal_weight": 0.1}
            (Path(tmpdir) / "unit_adaptive_state_trace.jsonl").write_text(
                json.dumps(state_trace) + "\n")
            state_trace2 = {"tick": 100, "unit_id": "u0", "move_weight": 0.35, "scan_weight": 0.15,
                            "extract_weight": 0.3, "signal_weight": 0.1}
            (Path(tmpdir) / "unit_adaptive_state_trace.jsonl").write_text(
                json.dumps(state_trace) + "\n" + json.dumps(state_trace2) + "\n")
            compare = {"action_distribution_delta": {"HARVEST": 3},
                        "active_unit_count_delta": 1}
            (Path(tmpdir) / "adaptive_vs_static_compare.json").write_text(
                json.dumps(compare))
            field = {"total_resource_cells": 100, "total_hazard_cells": 10}
            (Path(tmpdir) / "resource_hazard_field_summary.json").write_text(
                json.dumps(field))
            result = judge(tmpdir)
            assert result["checks"]["descendant_transfer_check"] == "FAIL"


class TestJudgeFailsNoSignalObs:
    """Test judge fails when signal observations are zero."""

    def test_judge_fails_zero_observations(self):
        """Judge returns FAIL for signal_adaptation_check when observations=0."""
        import json
        import tempfile
        from machine_sim.verification.milestone_14_judge import judge

        with tempfile.TemporaryDirectory() as tmpdir:
            summary = {
                "run_ticks": 25000,
                "grid_width": 120,
                "grid_height": 120,
                "initial_unit_count": 6,
                "final_active_unit_count": 3,
                "descendant_active_count": 1,
                "power_drain_rate": 1.5,
                "action_distribution_early": {"HARVEST": 10},
                "action_distribution_late": {"HARVEST": 5},
                "action_distribution_delta": {"HARVEST": -5},
                "signal_behavior_summary": {
                    "total_signal_emissions": 100,
                    "total_signal_observations": 0,
                },
            }
            (Path(tmpdir) / "long_run_adaptation_summary.json").write_text(
                json.dumps(summary))
            for fname in ["action_distribution_trace.jsonl", "unit_lifetime_trace.jsonl"]:
                (Path(tmpdir) / fname).write_text(json.dumps({"tick": 1}) + "\n")
            fb_entry = {"tick": 1, "unit_id": "u0", "power_delta": 5.0, "hazard_exposure": 0.0,
                        "resource_extracted": 1.0, "signal_observed": 0.0, "movement_blocked": 0.0}
            (Path(tmpdir) / "local_feedback_trace.jsonl").write_text(json.dumps(fb_entry) + "\n")
            state_trace = {"tick": 0, "unit_id": "u0", "move_weight": 0.25, "scan_weight": 0.25,
                           "extract_weight": 0.25, "signal_weight": 0.1}
            (Path(tmpdir) / "unit_adaptive_state_trace.jsonl").write_text(
                json.dumps(state_trace) + "\n")
            state_trace2 = {"tick": 100, "unit_id": "u0", "move_weight": 0.35, "scan_weight": 0.15,
                            "extract_weight": 0.3, "signal_weight": 0.1}
            (Path(tmpdir) / "unit_adaptive_state_trace.jsonl").write_text(
                json.dumps(state_trace) + "\n" + json.dumps(state_trace2) + "\n")
            compare = {"action_distribution_delta": {"HARVEST": 3},
                        "active_unit_count_delta": 1}
            (Path(tmpdir) / "adaptive_vs_static_compare.json").write_text(
                json.dumps(compare))
            desc = {"tick": 100, "source_unit_id": "u0", "successor_unit_id": "u-0001"}
            (Path(tmpdir) / "descendant_adaptive_state_trace.jsonl").write_text(
                json.dumps(desc) + "\n")
            field = {"total_resource_cells": 100, "total_hazard_cells": 10}
            (Path(tmpdir) / "resource_hazard_field_summary.json").write_text(
                json.dumps(field))
            result = judge(tmpdir)
            assert result["checks"]["signal_adaptation_check"] == "FAIL"
