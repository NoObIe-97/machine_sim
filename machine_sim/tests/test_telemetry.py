"""Tests for Milestone 8 telemetry reconciliation and lineage drift."""

from __future__ import annotations

import pytest

from machine_sim.agents.unit import MachineUnitImpl
from machine_sim.analysis.telemetry import (
    LineageDriftAnalyzer,
    LineageDriftEntry,
    ReconciliationEngine,
    ReconciliationRecord,
    TelemetryFrame,
    TelemetryTracker,
)
from machine_sim.environment.world import World
from machine_sim.sim.config import SimConfig
from machine_sim.sim.engine import SimEngine
from machine_sim.sim.events import EventType


class TestTelemetryTracker:
    """Telemetry tracker tests."""

    def test_record_frame_from_unit(self):
        """Tracker records frames from real unit state."""
        import random as _random
        rng = _random.Random(42)
        world = World(10, 10, rng)

        tracker = TelemetryTracker(enabled=True)
        unit = MachineUnitImpl("u0", position=(5, 5))
        world.grid[(5, 5)].unit_id = "u0"

        frame = tracker.record_frame(unit, 1, world)
        assert frame.unit_id == "u0"
        assert frame.tick == 1
        assert frame.power_ratio > 0
        assert frame.component_health_avg > 0

    def test_tracker_bounded(self):
        """Tracker respects max_entries limit."""
        import random as _random
        rng = _random.Random(42)
        world = World(10, 10, rng)

        tracker = TelemetryTracker(enabled=True, max_entries=5)
        unit = MachineUnitImpl("u0", position=(5, 5))
        world.grid[(5, 5)].unit_id = "u0"

        for tick in range(10):
            tracker.record_frame(unit, tick, world)

        assert len(tracker.get_frames()) <= 5

    def test_tracker_deterministic(self):
        """Same inputs produce same frames."""
        import random as _random

        def run_tracker(seed):
            rng = _random.Random(seed)
            world = World(10, 10, rng)
            tracker = TelemetryTracker(enabled=True)
            unit = MachineUnitImpl("u0", position=(5, 5))
            world.grid[(5, 5)].unit_id = "u0"
            frame = tracker.record_frame(unit, 1, world)
            return (frame.power_ratio, frame.component_health_avg)

        r1 = run_tracker(42)
        r2 = run_tracker(42)
        assert r1 == r2

    def test_tracker_summary(self):
        """Tracker summary has expected structure."""
        import random as _random
        rng = _random.Random(42)
        world = World(10, 10, rng)

        tracker = TelemetryTracker(enabled=True)
        unit = MachineUnitImpl("u0", position=(5, 5))
        world.grid[(5, 5)].unit_id = "u0"
        tracker.record_frame(unit, 1, world)

        summary = tracker.get_summary()
        assert "total_frames" in summary
        assert "units_tracked" in summary
        assert summary["total_frames"] == 1


class TestReconciliationEngine:
    """Reconciliation engine tests."""

    def test_reconcile_produces_records(self):
        """Reconciliation produces records for nearby units."""
        import random as _random
        rng = _random.Random(42)
        world = World(10, 10, rng)

        engine = ReconciliationEngine(enabled=True, radius=3)
        u0 = MachineUnitImpl("u0", position=(5, 5))
        u1 = MachineUnitImpl("u1", position=(6, 5))
        world.grid[(5, 5)].unit_id = "u0"
        world.grid[(6, 5)].unit_id = "u1"

        records = engine.reconcile([u0, u1], world, 1)
        assert len(records) == 1
        assert records[0].unit_a_id == "u0"
        assert records[0].unit_b_id == "u1"
        assert records[0].tick == 1

    def test_reconcile_excludes_distant_units(self):
        """Reconciliation skips units outside radius."""
        import random as _random
        rng = _random.Random(42)
        world = World(10, 10, rng)

        engine = ReconciliationEngine(enabled=True, radius=2)
        u0 = MachineUnitImpl("u0", position=(5, 5))
        u1 = MachineUnitImpl("u1", position=(9, 9))
        world.grid[(5, 5)].unit_id = "u0"
        world.grid[(9, 9)].unit_id = "u1"

        records = engine.reconcile([u0, u1], world, 1)
        assert len(records) == 0

    def test_reconciliation_has_numeric_metrics(self):
        """Reconciliation records contain real numeric metrics."""
        import random as _random
        rng = _random.Random(42)
        world = World(10, 10, rng)

        engine = ReconciliationEngine(enabled=True, radius=3)
        u0 = MachineUnitImpl("u0", position=(5, 5))
        u1 = MachineUnitImpl("u1", position=(6, 5))
        world.grid[(5, 5)].unit_id = "u0"
        world.grid[(6, 5)].unit_id = "u1"

        records = engine.reconcile([u0, u1], world, 1)
        assert len(records) == 1
        rec = records[0]
        assert isinstance(rec.telemetry_divergence, float)
        assert isinstance(rec.telemetry_continuity, float)
        assert isinstance(rec.power_estimate_diff, float)


class TestLineageDriftAnalyzer:
    """Lineage drift analysis tests."""

    def test_analyze_produces_entries(self):
        """Analyzer produces drift entries from capsules."""
        from machine_sim.environment.calibration import CapsuleGenerator

        import random as _random
        rng = _random.Random(42)
        world = World(10, 10, rng)

        gen = CapsuleGenerator()
        source = MachineUnitImpl("src-0", position=(5, 5))
        source.power_reserve = 70.0
        world.grid[(5, 5)].unit_id = "src-0"

        caps = [gen.generate(source, world, f"succ-{i}", i*10) for i in range(3)]
        analyzer = LineageDriftAnalyzer(enabled=True)
        entries = analyzer.analyze(caps, [])

        assert len(entries) > 0
        assert entries[0].capsule_count == 3
        assert entries[0].avg_sparsity >= 0

    def test_drift_metrics_numeric(self):
        """Drift entries contain real numeric metrics."""
        from machine_sim.environment.calibration import CapsuleGenerator

        import random as _random
        rng = _random.Random(42)
        world = World(10, 10, rng)

        gen = CapsuleGenerator()
        source = MachineUnitImpl("src-0", position=(5, 5))
        source.power_reserve = 70.0
        world.grid[(5, 5)].unit_id = "src-0"

        caps = [gen.generate(source, world, f"succ-{i}", i*10) for i in range(3)]
        analyzer = LineageDriftAnalyzer(enabled=True)
        entries = analyzer.analyze(caps, [])

        entry = entries[0]
        assert isinstance(entry.avg_sparsity, float)
        assert isinstance(entry.continuity_score, float)
        assert isinstance(entry.divergence_score, float)
        assert 0 <= entry.continuity_score <= 1
        assert 0 <= entry.divergence_score <= 1


class TestTelemetryDemo:
    """Telemetry demo scenario tests."""

    def test_telemetry_demo_deterministic(self):
        """Telemetry demo produces identical results with same seed."""
        def run_demo(seed):
            cfg = SimConfig(grid_width=20, grid_height=20, max_ticks=100, seed=seed,
                            unit_count=3, resource_density=0.5, hazard_density=0.01,
                            power_drain_rate=0.4,
                            fabrication_enabled=True, capsule_enabled=True,
                            telemetry_enabled=True, reconciliation_enabled=True,
                            lineage_drift_enabled=True,
                            unit_capacity=10, fabrication_interval=8,
                            fabrication_power_cost=10.0, fabrication_material_cost=2.0)
            engine = SimEngine(cfg, seed=seed)
            for i in range(3):
                engine.register_unit(MachineUnitImpl(f"u-{i}"))
            engine.run()
            telemetry = engine.get_telemetry_summary()
            reconciliation = engine.get_reconciliation_summary()
            return (telemetry["total_frames"], reconciliation["total_records"])

        r1 = run_demo(42)
        r2 = run_demo(42)
        assert r1 == r2

    def test_telemetry_demo_generates_data(self):
        """Telemetry demo generates frames and reconciliation records."""
        cfg = SimConfig(grid_width=20, grid_height=20, max_ticks=200, seed=42,
                        unit_count=3, resource_density=0.5, hazard_density=0.01,
                        power_drain_rate=0.4,
                        fabrication_enabled=True, capsule_enabled=True,
                        telemetry_enabled=True, reconciliation_enabled=True,
                        lineage_drift_enabled=True,
                        unit_capacity=12, fabrication_interval=8,
                        fabrication_power_cost=10.0, fabrication_material_cost=2.0)
        engine = SimEngine(cfg, seed=42)
        for i in range(3):
            engine.register_unit(MachineUnitImpl(f"u-{i}"))
        engine.run()

        telemetry = engine.get_telemetry_summary()
        reconciliation = engine.get_reconciliation_summary()
        drift = engine.get_lineage_drift_summary()

        assert telemetry["total_frames"] > 0, "Should have telemetry frames"
        assert telemetry["units_tracked"] > 0, "Should track multiple units"
        assert reconciliation["total_records"] > 0, "Should have reconciliation records"
        assert drift["total_entries"] > 0, "Should have lineage drift entries"

