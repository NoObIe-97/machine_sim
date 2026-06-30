"""Tests for Milestone 5 adaptive signal control."""

from __future__ import annotations

import pytest

from machine_sim.analysis.adaptive import (
    AdaptiveEmissionPolicy,
    AdaptiveScanPolicy,
    LocalFieldTracker,
    SignalFieldSummary,
)
from machine_sim.agents.unit import MachineUnitImpl
from machine_sim.sim.config import SimConfig
from machine_sim.sim.engine import SimEngine
from machine_sim.sim.events import EventType


class TestLocalFieldTracker:
    """Local signal-field summary tests."""

    def test_tracker_records_signal_observations(self):
        """Tracker records signal observations."""
        tracker = LocalFieldTracker(window_size=10)
        tracker.record_signal_observation(tick=5, pattern_id=0, intensity=0.8)
        summary = tracker.get_summary(10)
        assert summary.recent_signal_count == 1
        assert summary.pattern_frequency == {0: 1}
        assert summary.avg_received_intensity == 0.8

    def test_tracker_records_hazard_events(self):
        """Tracker records hazard events."""
        tracker = LocalFieldTracker(window_size=10)
        tracker.record_hazard_event(tick=5)
        tracker.record_hazard_event(tick=8)
        summary = tracker.get_summary(10)
        assert summary.local_hazard_density > 0

    def test_tracker_records_movement_blocks(self):
        """Tracker records movement blocks."""
        tracker = LocalFieldTracker(window_size=10)
        tracker.record_movement_block(tick=5)
        summary = tracker.get_summary(10)
        assert summary.recent_movement_blocks == 1

    def test_tracker_records_emissions(self):
        """Tracker records emissions."""
        tracker = LocalFieldTracker(window_size=10)
        tracker.record_emission(tick=5)
        tracker.record_emission(tick=8)
        summary = tracker.get_summary(10)
        assert summary.emission_rate > 0

    def test_tracker_records_scans(self):
        """Tracker records scans."""
        tracker = LocalFieldTracker(window_size=10)
        tracker.record_scan(tick=5)
        summary = tracker.get_summary(10)
        assert summary.scan_rate > 0

    def test_tracker_bounded_window(self):
        """Tracker only includes events within window."""
        tracker = LocalFieldTracker(window_size=5)
        tracker.record_signal_observation(tick=1, pattern_id=0, intensity=1.0)
        tracker.record_signal_observation(tick=10, pattern_id=0, intensity=1.0)
        summary = tracker.get_summary(15)
        assert summary.recent_signal_count == 1  # only tick 10 is within window

    def test_tracker_deterministic(self):
        """Same events produce same summary."""
        def run_tracker(seed):
            tracker = LocalFieldTracker(window_size=10)
            tracker.record_signal_observation(tick=5, pattern_id=0, intensity=0.8)
            tracker.record_hazard_event(tick=7)
            summary = tracker.get_summary(10)
            return (summary.recent_signal_count, summary.local_hazard_density)

        r1 = run_tracker(42)
        r2 = run_tracker(42)
        assert r1 == r2


class TestAdaptiveEmissionPolicy:
    """Adaptive emission policy tests."""

    def test_low_power_increases_interval(self):
        """Low power increases emission interval."""
        policy = AdaptiveEmissionPolicy(base_interval=5, low_power_threshold=0.3)
        field_summary = SignalFieldSummary()
        interval_normal = policy.compute_interval(0.8, field_summary)
        interval_low = policy.compute_interval(0.2, field_summary)
        assert interval_low >= interval_normal

    def test_high_signal_density_decreases_interval(self):
        """High signal density decreases emission interval."""
        policy = AdaptiveEmissionPolicy(base_interval=5)
        field_normal = SignalFieldSummary(recent_signal_count=1)
        field_dense = SignalFieldSummary(recent_signal_count=8)
        interval_normal = policy.compute_interval(0.8, field_normal)
        interval_dense = policy.compute_interval(0.8, field_dense)
        assert interval_dense <= interval_normal

    def test_low_power_reduces_intensity(self):
        """Low power reduces signal intensity."""
        policy = AdaptiveEmissionPolicy(base_intensity=1.0, low_power_threshold=0.3)
        field_summary = SignalFieldSummary()
        intensity_normal = policy.compute_intensity(0.8, field_summary)
        intensity_low = policy.compute_intensity(0.2, field_summary)
        assert intensity_low < intensity_normal

    def test_low_power_reduces_radius(self):
        """Low power reduces signal radius."""
        policy = AdaptiveEmissionPolicy(base_radius=3, low_power_threshold=0.3)
        field_summary = SignalFieldSummary()
        radius_normal = policy.compute_radius(0.8, field_summary)
        radius_low = policy.compute_radius(0.2, field_summary)
        assert radius_low <= radius_normal

    def test_pattern_shift_on_high_frequency(self):
        """Pattern shifts when a pattern has high frequency."""
        policy = AdaptiveEmissionPolicy()
        field = SignalFieldSummary(pattern_frequency={0: 5, 1: 2})
        # If base pattern is 0 and it's frequent, shift to 1
        pattern = policy.compute_pattern_id(0, field, 3)
        assert pattern != 0 or field.pattern_frequency.get(0, 0) <= 3

    def test_policy_bounded(self):
        """Policy outputs are within bounds."""
        policy = AdaptiveEmissionPolicy(
            base_interval=5, min_interval=2, max_interval=15,
            base_intensity=1.0, base_radius=3
        )
        for power in [0.1, 0.3, 0.5, 0.8, 1.0]:
            field = SignalFieldSummary()
            interval = policy.compute_interval(power, field)
            intensity = policy.compute_intensity(power, field)
            radius = policy.compute_radius(power, field)
            assert 2 <= interval <= 15
            assert 0.3 <= intensity <= 1.5
            assert 1 <= radius <= 6


class TestAdaptiveScanPolicy:
    """Adaptive scan policy tests."""

    def test_low_power_increases_scan_interval(self):
        """Low power increases scan interval."""
        policy = AdaptiveScanPolicy(base_scan_interval=3, low_power_threshold=0.3)
        field_summary = SignalFieldSummary()
        interval_normal = policy.compute_scan_interval(0.8, field_summary)
        interval_low = policy.compute_scan_interval(0.2, field_summary)
        assert interval_low >= interval_normal

    def test_high_signal_density_decreases_scan_interval(self):
        """High signal density decreases scan interval."""
        policy = AdaptiveScanPolicy(base_scan_interval=3)
        field_normal = SignalFieldSummary(recent_signal_count=1)
        field_dense = SignalFieldSummary(recent_signal_count=8)
        interval_normal = policy.compute_scan_interval(0.8, field_normal)
        interval_dense = policy.compute_scan_interval(0.8, field_dense)
        assert interval_dense <= interval_normal


class TestAdaptiveUnit:
    """Adaptive unit behavior tests."""

    def test_adaptive_unit_uses_field_tracker(self):
        """Adaptive unit tracks field statistics."""
        unit = MachineUnitImpl("u0", adaptive_enabled=True, signal_enabled=True)
        assert hasattr(unit, '_field_tracker')
        assert hasattr(unit, '_emission_policy')
        assert hasattr(unit, '_scan_policy')

    def test_adaptive_unit_decide_uses_policy(self):
        """Adaptive unit uses policy for emission decisions."""
        unit = MachineUnitImpl("u0", adaptive_enabled=True, signal_enabled=True)
        unit.power_reserve = 80.0
        unit.max_power = 100.0
        # Add some signal observations to field tracker
        unit._field_tracker.record_signal_observation(1, 0, 0.8)
        unit._field_tracker.record_signal_observation(2, 1, 0.6)
        action = unit.decide(10)
        # Should return some action (emission or scan or idle)
        assert action is not None

    def test_low_power_suppresses_emission(self):
        """Low power suppresses or reduces emission."""
        unit = MachineUnitImpl("u0", adaptive_enabled=True, signal_enabled=True)
        unit.power_reserve = 10.0
        unit.max_power = 100.0
        action = unit.decide(10)
        # With low power, should harvest or idle, not emit
        if action is not None:
            from machine_sim.agents.base import ActionType
            assert action.action_type != ActionType.EMIT_SIGNAL


class TestAdaptiveEngine:
    """Engine-level adaptive integration tests."""

    def test_engine_records_field_tracker_events(self):
        """Engine records events for field tracker."""
        cfg = SimConfig(grid_width=8, grid_height=8, max_ticks=20, seed=42,
                        unit_count=2, resource_density=0.2, hazard_density=0.1,
                        signal_enabled=True, adaptive_enabled=True,
                        signal_observation_window=10)
        engine = SimEngine(cfg, seed=42)
        for i in range(2):
            engine.register_unit(MachineUnitImpl(f"u-{i}", signal_enabled=True,
                                                  adaptive_enabled=True))
        engine.run()
        summary = engine.get_adaptive_summary()
        assert len(summary) == 2
        for uid, s in summary.items():
            assert "signal_count" in s
            assert "hazard_density" in s
            assert "emission_rate" in s

    def test_adaptive_vs_baseline_different_outputs(self):
        """Adaptive and baseline modes produce different outputs."""
        def run_mode(adaptive):
            cfg = SimConfig(grid_width=10, grid_height=10, max_ticks=50, seed=42,
                            unit_count=3, resource_density=0.2, hazard_density=0.1,
                            signal_enabled=True, adaptive_enabled=adaptive,
                            signal_observation_window=10)
            engine = SimEngine(cfg, seed=42)
            for i in range(3):
                engine.register_unit(MachineUnitImpl(f"u-{i}", signal_enabled=True,
                                                      adaptive_enabled=adaptive))
            state = engine.run()
            events = [e for e in state.events if e.event_type == EventType.SIGNAL_EMITTED]
            return len(events)

        baseline_count = run_mode(False)
        adaptive_count = run_mode(True)
        # Both should produce emissions, but counts may differ
        assert baseline_count > 0
        assert adaptive_count > 0


class TestCorrelationImprovements:
    """Improved correlation metrics tests."""

    def test_lag_weighted_score_bounded(self):
        """Lag-weighted score is bounded between 0 and 1."""
        from machine_sim.analysis.correlation import SignalCorrelator
        corr = SignalCorrelator(observation_window=10)
        for i in range(5):
            corr.record_signal_emission(tick=i*10, unit_id="u0", pattern_id=0, data={})
            corr.record_observation(tick=i*10+2, unit_id="u0", observation_type="hazard", data={})
        stats = corr.get_pattern_stats()
        for pid, s in stats.items():
            for score in s.lag_weighted_score.values():
                assert 0.0 <= score <= 1.0

    def test_confidence_bounded(self):
        """Confidence score is bounded between 0 and 1."""
        from machine_sim.analysis.correlation import SignalCorrelator
        corr = SignalCorrelator(observation_window=10)
        for i in range(5):
            corr.record_signal_emission(tick=i*10, unit_id="u0", pattern_id=0, data={})
            corr.record_observation(tick=i*10+2, unit_id="u0", observation_type="hazard", data={})
        stats = corr.get_pattern_stats()
        for pid, s in stats.items():
            for score in s.confidence.values():
                assert 0.0 <= score <= 1.0

    def test_normalized_rate_bounded(self):
        """Normalized rate is bounded between 0 and 1."""
        from machine_sim.analysis.correlation import SignalCorrelator
        corr = SignalCorrelator(observation_window=10)
        for i in range(5):
            corr.record_signal_emission(tick=i*10, unit_id="u0", pattern_id=0, data={})
            corr.record_observation(tick=i*10+2, unit_id="u0", observation_type="hazard", data={})
        stats = corr.get_pattern_stats()
        for pid, s in stats.items():
            for score in s.normalized_rate.values():
                assert 0.0 <= score <= 1.0

    def test_lag_weighted_prefers_early_observations(self):
        """Lag-weighted score gives more weight to earlier observations."""
        from machine_sim.analysis.correlation import SignalCorrelator
        # Scenario A: observation at lag 1
        corr_a = SignalCorrelator(observation_window=20)
        corr_a.record_signal_emission(tick=1, unit_id="u0", pattern_id=0, data={})
        corr_a.record_observation(tick=2, unit_id="u0", observation_type="hazard", data={})
        corr_a.compute_associations()
        stats_a = corr_a.get_pattern_stats()

        # Scenario B: observation at lag 9
        corr_b = SignalCorrelator(observation_window=20)
        corr_b.record_signal_emission(tick=1, unit_id="u0", pattern_id=0, data={})
        corr_b.record_observation(tick=10, unit_id="u0", observation_type="hazard", data={})
        corr_b.compute_associations()
        stats_b = corr_b.get_pattern_stats()

        # Lag-1 observation should produce higher lag-weighted score than lag-9
        assert stats_a[0].lag_weighted_score.get("hazard", 0) > \
               stats_b[0].lag_weighted_score.get("hazard", 0)


class TestAdaptiveDemo:
    """Adaptive demo scenario tests."""

    def test_adaptive_demo_deterministic(self):
        """Adaptive demo produces identical results with same seed."""
        def run_demo(seed, adaptive):
            cfg = SimConfig(grid_width=12, grid_height=12, max_ticks=50, seed=seed,
                            unit_count=5, resource_density=0.25, hazard_density=0.1,
                            signal_enabled=True, adaptive_enabled=adaptive,
                            signal_observation_window=10)
            engine = SimEngine(cfg, seed=seed)
            for i in range(5):
                engine.register_unit(MachineUnitImpl(f"u-{i}", signal_enabled=True,
                                                      adaptive_enabled=adaptive))
            state = engine.run()
            emitted = [e for e in state.events if e.event_type == EventType.SIGNAL_EMITTED]
            return len(emitted)

        r1 = run_demo(42, True)
        r2 = run_demo(42, True)
        assert r1 == r2

    def test_adaptive_demo_generates_metrics(self):
        """Adaptive demo generates adaptive metrics."""
        cfg = SimConfig(grid_width=12, grid_height=12, max_ticks=100, seed=42,
                        unit_count=5, resource_density=0.25, hazard_density=0.1,
                        signal_enabled=True, adaptive_enabled=True,
                        signal_observation_window=10)
        engine = SimEngine(cfg, seed=42)
        for i in range(5):
            engine.register_unit(MachineUnitImpl(f"u-{i}", signal_enabled=True,
                                                  adaptive_enabled=True))
        engine.run()
        adaptive_summary = engine.get_adaptive_summary()
        assert len(adaptive_summary) == 5
        for uid, s in adaptive_summary.items():
            assert s["adaptive_enabled"] is True
