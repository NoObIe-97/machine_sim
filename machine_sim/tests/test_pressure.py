"""Tests for Milestone 9 resource pressure and field perturbation."""

from __future__ import annotations

import pytest

from machine_sim.agents.unit import MachineUnitImpl
from machine_sim.analysis.pressure import PressureAnalyzer
from machine_sim.environment.world import World
from machine_sim.sim.config import SimConfig
from machine_sim.sim.engine import SimEngine
from machine_sim.sim.events import EventType


class TestPressureAnalyzer:
    """Pressure analyzer tests."""

    def test_record_tick_generates_pressure(self):
        """Pressure analyzer records pressure from real unit state."""
        import random as _random
        rng = _random.Random(42)
        world = World(10, 10, rng)
        world.populate_resources(0.5, rng)

        analyzer = PressureAnalyzer(enabled=True)
        unit = MachineUnitImpl("u0", position=(5, 5))
        world.grid[(5, 5)].unit_id = "u0"

        analyzer.record_tick(world, [unit], 1)
        summary = analyzer.get_summary()
        assert summary["total_samples"] > 0

    def test_pressure_summary_bounded(self):
        """Pressure summary metrics are bounded."""
        import random as _random
        rng = _random.Random(42)
        world = World(10, 10, rng)
        world.populate_resources(0.5, rng)

        analyzer = PressureAnalyzer(enabled=True)
        unit = MachineUnitImpl("u0", position=(5, 5))
        world.grid[(5, 5)].unit_id = "u0"

        analyzer.record_tick(world, [unit], 1)
        summary = analyzer.get_summary()
        assert 0.0 <= summary["avg_resource_pressure"] <= 1.0
        assert 0.0 <= summary["max_resource_pressure"] <= 1.0
        assert 0.0 <= summary["avg_proximity_pressure"] <= 1.0

    def test_pressure_deterministic(self):
        """Same inputs produce same pressure summary."""
        import random as _random

        def run_pressure(seed):
            rng = _random.Random(seed)
            world = World(10, 10, rng)
            world.populate_resources(0.5, rng)
            analyzer = PressureAnalyzer(enabled=True)
            unit = MachineUnitImpl("u0", position=(5, 5))
            world.grid[(5, 5)].unit_id = "u0"
            analyzer.record_tick(world, [unit], 1)
            return analyzer.get_summary()

        r1 = run_pressure(42)
        r2 = run_pressure(42)
        assert r1 == r2


class TestPressureDemo:
    """Pressure demo scenario tests."""

    def test_pressure_demo_deterministic(self):
        """Pressure demo produces identical results with same seed."""
        def run_demo(seed):
            cfg = SimConfig(grid_width=15, grid_height=15, max_ticks=100, seed=seed,
                            unit_count=5, resource_density=0.6, hazard_density=0.05,
                            power_drain_rate=0.5,
                            signal_enabled=True, adaptive_enabled=True,
                            fabrication_enabled=True, capsule_enabled=True,
                            telemetry_enabled=True, reconciliation_enabled=True,
                            lineage_drift_enabled=True, pressure_analysis_enabled=True,
                            population_cap=10, fabrication_interval=10,
                            fabrication_power_cost=10.0, fabrication_material_cost=2.0)
            engine = SimEngine(cfg, seed=seed)
            for i in range(5):
                engine.register_unit(MachineUnitImpl(f"u-{i}"))
            engine.run()
            pressure = engine.get_pressure_summary()
            return (pressure["total_samples"], pressure["total_extraction_records"])

        r1 = run_demo(42)
        r2 = run_demo(42)
        assert r1 == r2

    def test_pressure_demo_generates_metrics(self):
        """Pressure demo generates nonzero pressure metrics."""
        cfg = SimConfig(grid_width=15, grid_height=15, max_ticks=200, seed=42,
                        unit_count=5, resource_density=0.6, hazard_density=0.05,
                        power_drain_rate=0.5,
                        signal_enabled=True, adaptive_enabled=True,
                        fabrication_enabled=True, capsule_enabled=True,
                        telemetry_enabled=True, reconciliation_enabled=True,
                        lineage_drift_enabled=True, pressure_analysis_enabled=True,
                        population_cap=10, fabrication_interval=10,
                        fabrication_power_cost=10.0, fabrication_material_cost=2.0)
        engine = SimEngine(cfg, seed=42)
        for i in range(5):
            engine.register_unit(MachineUnitImpl(f"u-{i}"))
        engine.run()
        pressure = engine.get_pressure_summary()
        assert pressure["total_samples"] > 0, "Should have pressure samples"
        assert pressure["total_extraction_records"] >= 0
        assert pressure["avg_resource_pressure"] >= 0

    def test_dense_layout_higher_pressure(self):
        """Dense unit layout produces higher pressure than sparse."""
        def run_pressure(unit_count):
            cfg = SimConfig(grid_width=10, grid_height=10, max_ticks=10, seed=42,
                            unit_count=unit_count, resource_density=0.5,
                            hazard_density=0.0, power_drain_rate=0.5,
                            pressure_analysis_enabled=True)
            engine = SimEngine(cfg, seed=42)
            for i in range(unit_count):
                engine.register_unit(MachineUnitImpl(f"u-{i}"))
            engine.run()
            return engine.get_pressure_summary()

        sparse = run_pressure(2)
        dense = run_pressure(8)
        assert dense["avg_proximity_pressure"] >= sparse["avg_proximity_pressure"]
