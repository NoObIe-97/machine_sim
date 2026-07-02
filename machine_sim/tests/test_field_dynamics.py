"""Tests for Milestone 10 signal pattern field dynamics."""

from __future__ import annotations

import pytest

from machine_sim.agents.unit import MachineUnitImpl
from machine_sim.analysis.field_dynamics import SignalFieldDynamics
from machine_sim.environment.world import World
from machine_sim.sim.config import SimConfig
from machine_sim.sim.engine import SimEngine
from machine_sim.sim.events import EventType


class TestSignalFieldDynamics:
    """Signal field dynamics tests."""

    def test_pattern_frequency_nonzero(self):
        """Pattern frequency is nonzero with signal mode enabled."""
        import random as _random
        rng = _random.Random(42)
        world = World(10, 10, rng)

        dynamics = SignalFieldDynamics(enabled=True)
        dynamics.record_signal(1, "u0", 0, {})
        dynamics.record_signal(5, "u0", 1, {})
        dynamics.record_signal(10, "u0", 0, {})

        patterns = dynamics.compute_pattern_frequency()
        assert len(patterns) > 0
        assert patterns[0].total_count >= 1

    def test_density_clusters_deterministic(self):
        """Same inputs produce same density clusters."""
        import random as _random

        def run_clusters(seed):
            rng = _random.Random(seed)
            world = World(10, 10, rng)
            dynamics = SignalFieldDynamics(enabled=True)
            dynamics.record_signal(1, "u0", 0, {})
            dynamics.record_signal(2, "u0", 0, {})
            dynamics.record_signal(10, "u0", 1, {})
            return len(dynamics.compute_density_clusters())

        r1 = run_clusters(42)
        r2 = run_clusters(42)
        assert r1 == r2

    def test_signal_gradient_from_real_data(self):
        """Signal gradient metrics are generated from real signal data."""
        import random as _random
        rng = _random.Random(42)
        world = World(10, 10, rng)
        world.populate_resources(0.5, rng)

        # Place a unit so gradient has cells to measure
        unit = MachineUnitImpl("u0", position=(5, 5))
        world.grid[(5, 5)].unit_id = "u0"

        dynamics = SignalFieldDynamics(enabled=True)
        gradient = dynamics.compute_signal_gradient(world)
        assert gradient.cell_count > 0
        assert gradient.avg_gradient >= 0

    def test_pattern_correlation_present(self):
        """Pattern correlation score is present and numeric."""
        dynamics = SignalFieldDynamics(enabled=True)
        dynamics.record_signal(1, "u0", 0, {})
        dynamics.record_observation(3, "u0", "hazard", {})
        correlations = dynamics.compute_pattern_correlation()
        assert len(correlations) > 0
        assert correlations[0].avg_score >= 0

    def test_signal_disabled_safe(self):
        """Signal-disabled mode produces clean zero summaries."""
        dynamics = SignalFieldDynamics(enabled=False)
        summary = dynamics.get_summary()
        assert summary["total_signals"] == 0
        assert summary["total_observations"] == 0

    def test_field_deterministic(self):
        """Same inputs produce same field dynamics summary."""
        def run_dynamics(seed):
            cfg = SimConfig(grid_width=10, grid_height=10, max_ticks=20, seed=seed,
                            unit_count=2, resource_density=0.5, hazard_density=0.05,
                            signal_enabled=True, adaptive_enabled=True,
                            signal_dynamics_enabled=True)
            engine = SimEngine(cfg, seed=seed)
            for i in range(2):
                engine.register_unit(MachineUnitImpl(f"u-{i}", signal_enabled=True,
                                                      adaptive_enabled=True))
            engine.run()
            summary = engine.get_field_dynamics_summary()
            return (summary["total_signals"], summary["pattern_count"])

        r1 = run_dynamics(42)
        r2 = run_dynamics(42)
        assert r1 == r2

    def test_field_dynamics_generates_metrics(self):
        """Field dynamics demo generates nonzero metrics with gradient fields."""
        cfg = SimConfig(grid_width=12, grid_height=12, max_ticks=200, seed=42,
                        unit_count=4, resource_density=0.5, hazard_density=0.08,
                        power_drain_rate=0.5,
                        signal_enabled=True, adaptive_enabled=True,
                        signal_dynamics_enabled=True)
        engine = SimEngine(cfg, seed=42)
        for i in range(4):
            engine.register_unit(MachineUnitImpl(f"u-{i}", signal_enabled=True,
                                                  adaptive_enabled=True))
        engine.run()
        summary = engine.get_field_dynamics_summary()
        assert summary["total_signals"] > 0
        assert summary["pattern_count"] > 0
        assert summary["cluster_count"] > 0
        assert summary["peak_cluster_density"] > 0.0
        assert summary["correlation_count"] > 0
        assert summary["avg_correlation_score"] > 0.0
        assert summary["max_correlation_score"] > 0.0
        assert summary["signal_gradient_cells"] > 0
        assert summary["avg_signal_gradient"] > 0.0
        assert summary["max_signal_gradient"] > 0.0

    def test_field_dynamics_bounded_storage(self):
        """Field dynamics respects max_records bound."""
        dynamics = SignalFieldDynamics(enabled=True, max_records=5)
        for i in range(10):
            dynamics.record_signal(i, f"u-{i}", 0, {})
            dynamics.record_observation(i, f"u-{i}", "hazard", {})
        assert len(dynamics._signal_history) <= 5
        assert len(dynamics._observation_history) <= 5
