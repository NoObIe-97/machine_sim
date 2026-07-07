"""Tests for Milestone 7 calibration capsules and warm-start."""

from __future__ import annotations

import pytest

from machine_sim.agents.unit import MachineUnitImpl
from machine_sim.environment.calibration import (
    CalibrationCapsule,
    CapsuleGenerator,
    CapsuleManager,
)
from machine_sim.environment.world import World
from machine_sim.sim.config import SimConfig
from machine_sim.sim.engine import SimEngine
from machine_sim.sim.events import EventType


class TestCapsuleGenerator:
    """Capsule generation tests."""

    def test_generate_capsule_from_source(self):
        """Capsule is generated from source unit and world state."""
        import random
        rng = random.Random(42)
        world = World(10, 10, rng)

        gen = CapsuleGenerator()
        source = MachineUnitImpl("src-0", position=(5, 5))
        source.power_reserve = 70.0
        world.grid[(5, 5)].unit_id = "src-0"

        capsule = gen.generate(source, world, "succ-0", 10)
        assert capsule.source_unit_id == "src-0"
        assert capsule.successor_unit_id == "succ-0"
        assert capsule.fabrication_tick == 10
        assert capsule.source_power_ratio > 0
        assert capsule.capsule_entries > 0

    def test_capsule_bounded_fields(self):
        """Capsule fields are within expected bounds."""
        import random
        rng = random.Random(42)
        world = World(10, 10, rng)

        gen = CapsuleGenerator()
        source = MachineUnitImpl("src-0", position=(5, 5))
        source.power_reserve = 70.0
        world.grid[(5, 5)].unit_id = "src-0"

        capsule = gen.generate(source, world, "succ-0", 10)
        assert 0.0 <= capsule.source_power_ratio <= 1.0
        assert 0.0 <= capsule.source_component_health <= 1.0
        assert 0.0 <= capsule.sparsity_score <= 1.0
        assert capsule.capsule_entries >= 0

    def test_capsule_deterministic(self):
        """Same source/world produces same capsule."""
        import random as _random

        def make_capsule(seed):
            rng = _random.Random(seed)
            world = World(10, 10, rng)
            gen = CapsuleGenerator()
            source = MachineUnitImpl("src-0", position=(5, 5))
            source.power_reserve = 70.0
            world.grid[(5, 5)].unit_id = "src-0"
            return gen.generate(source, world, "succ-0", 10)

        c1 = make_capsule(42)
        c2 = make_capsule(42)
        assert c1.source_power_ratio == c2.source_power_ratio
        assert c1.sparsity_score == c2.sparsity_score
        assert c1.capsule_entries == c2.capsule_entries

    def test_apply_warm_start_modifies_successor(self):
        """Warm-start applies calibration values to successor."""
        import random
        rng = random.Random(42)
        world = World(10, 10, rng)

        gen = CapsuleGenerator()
        source = MachineUnitImpl("src-0", position=(5, 5))
        source.power_reserve = 70.0
        world.grid[(5, 5)].unit_id = "src-0"

        capsule = gen.generate(source, world, "succ-0", 10)
        successor = MachineUnitImpl("succ-0", position=(6, 5))

        gen.apply_warm_start(capsule, successor)

        # Verify warm-start effect is recorded with real deltas
        effect = successor._capsule_warm_start_effect
        assert effect is not None
        assert "pre_sensor_health" in effect
        assert "post_sensor_health" in effect
        assert "sensor_health_delta" in effect
        assert "pre_power_reserve" in effect
        assert "post_power_reserve" in effect
        assert "power_reserve_delta" in effect
        # At least one delta must be nonzero
        assert abs(effect["power_reserve_delta"]) > 0.0 or \
               abs(effect["sensor_health_delta"]) > 0.0, \
            "Expected at least one nonzero warm-start delta"
        assert successor._capsule_applied is True


class TestCapsuleManager:
    """Capsule manager tests."""

    def test_generate_and_store(self):
        """Manager generates and stores capsules."""
        import random
        rng = random.Random(42)
        world = World(10, 10, rng)

        manager = CapsuleManager(enabled=True)
        source = MachineUnitImpl("src-0", position=(5, 5))
        source.power_reserve = 70.0
        world.grid[(5, 5)].unit_id = "src-0"

        capsule = manager.generate_and_store(source, world, "succ-0", 10)
        assert len(manager.get_capsules()) == 1
        assert capsule.source_unit_id == "src-0"

    def test_summary_structure(self):
        """Manager summary has expected structure."""
        import random
        rng = random.Random(42)
        world = World(10, 10, rng)

        manager = CapsuleManager(enabled=True)
        source = MachineUnitImpl("src-0", position=(5, 5))
        source.power_reserve = 70.0
        world.grid[(5, 5)].unit_id = "src-0"

        manager.generate_and_store(source, world, "succ-0", 10)
        summary = manager.get_summary()
        assert "total_capsules" in summary
        assert "avg_sparsity" in summary
        assert "capsules" in summary
        assert summary["total_capsules"] == 1


class TestCalibrationDemo:
    """Calibration demo scenario tests."""

    def test_calibration_demo_deterministic(self):
        """Calibration demo produces identical results with same seed."""
        def run_demo(seed):
            cfg = SimConfig(grid_width=20, grid_height=20, max_ticks=100, seed=seed,
                            unit_count=3, resource_density=0.5, hazard_density=0.01,
                            power_drain_rate=0.4,
                            fabrication_enabled=True, capsule_enabled=True,
                            unit_capacity=10, fabrication_interval=8,
                            fabrication_power_cost=10.0, fabrication_material_cost=2.0)
            engine = SimEngine(cfg, seed=seed)
            for i in range(3):
                engine.register_unit(MachineUnitImpl(f"u-{i}"))
            engine.run()
            fab_summary = engine.get_fabrication_summary()
            cap_summary = engine.get_capsule_summary()
            return (fab_summary["total_successes"], cap_summary["total_capsules"])

        r1 = run_demo(42)
        r2 = run_demo(42)
        assert r1 == r2

    def test_calibration_demo_generates_capsules(self):
        """Calibration demo creates capsules with successors."""
        cfg = SimConfig(grid_width=20, grid_height=20, max_ticks=200, seed=42,
                        unit_count=3, resource_density=0.5, hazard_density=0.01,
                        power_drain_rate=0.4,
                        fabrication_enabled=True, capsule_enabled=True,
                        unit_capacity=12, fabrication_interval=8,
                        fabrication_power_cost=10.0, fabrication_material_cost=2.0)
        engine = SimEngine(cfg, seed=42)
        for i in range(3):
            engine.register_unit(MachineUnitImpl(f"u-{i}"))
        engine.run()

        fab_summary = engine.get_fabrication_summary()
        cap_summary = engine.get_capsule_summary()

        assert fab_summary["total_successes"] > 0, "Should have fabrication successes"
        assert cap_summary["total_capsules"] > 0, "Should have capsules generated"
        assert cap_summary["total_capsules"] == fab_summary["total_successes"]

        # Verify capsules are traceable to source/successor
        for cap in cap_summary["capsules"]:
            assert cap["source"] != ""
            assert cap["successor"] != ""
            assert cap["tick"] > 0

        # Verify successor units have warm-start applied
        for unit in engine.units:
            if hasattr(unit, '_capsule_applied') and unit._capsule_applied:
                assert hasattr(unit, '_calibration_capsule')
                break
        else:
            pytest.fail("No successor unit has warm-start applied")


class TestCapsuleImpact:
    """Capsule impact and comparison tests."""

    def test_capsule_enabled_vs_disabled_differs(self):
        """Capsule-enabled and capsule-disabled runs produce different results."""
        from machine_sim.environment.calibration import compute_capsule_impact

        def run_mode(cap_enabled):
            cfg = SimConfig(grid_width=20, grid_height=20, max_ticks=100, seed=42,
                            unit_count=3, resource_density=0.5, hazard_density=0.01,
                            power_drain_rate=0.4,
                            fabrication_enabled=True, capsule_enabled=cap_enabled,
                            unit_capacity=10, fabrication_interval=8,
                            fabrication_power_cost=10.0, fabrication_material_cost=2.0)
            engine = SimEngine(cfg, seed=42)
            for i in range(3):
                engine.register_unit(MachineUnitImpl(f"u-{i}"))
            engine.run()
            return [u for u in engine.units if getattr(u, '_generation_index', 0) > 0]

        disabled = run_mode(False)
        enabled = run_mode(True)
        impact = compute_capsule_impact(enabled, disabled)
        # Capsule-enabled should have at least one successor with capsule applied
        assert impact["capsule_enabled"]["capsule_applied_count"] > 0
        # Assert at least one real numeric delta (not just metadata)
        assert abs(impact["delta"]["warm_start_power_delta"]) > 0.0, \
            "Expected nonzero warm_start_power_delta from capsule application"
        assert impact["delta"]["neutral_metric_delta_detected"] is True
        assert len(impact["delta"]["impact_metric_names"]) > 0

    def test_warm_start_changes_measurable_field(self):
        """Warm-start modifies at least one measurable successor field."""
        import random as _random
        rng = _random.Random(42)
        world = World(10, 10, rng)

        gen = CapsuleGenerator()
        source = MachineUnitImpl("src-0", position=(5, 5))
        source.power_reserve = 70.0
        world.grid[(5, 5)].unit_id = "src-0"

        capsule = gen.generate(source, world, "succ-0", 10)
        successor = MachineUnitImpl("succ-0", position=(6, 5))

        gen.apply_warm_start(capsule, successor)

        # Assert warm-start effect is recorded with real nonzero deltas
        effect = successor._capsule_warm_start_effect
        assert effect is not None
        assert abs(effect["power_reserve_delta"]) > 0.0 or \
               abs(effect["sensor_health_delta"]) > 0.0, \
            "Expected at least one nonzero warm-start delta"
        assert successor._capsule_applied is True

    def test_capsule_summary_references_successors(self):
        """Capsule summary references actual successor unit IDs."""
        import random as _random
        rng = _random.Random(42)
        world = World(10, 10, rng)

        manager = CapsuleManager(enabled=True)
        source = MachineUnitImpl("src-0", position=(5, 5))
        source.power_reserve = 70.0
        world.grid[(5, 5)].unit_id = "src-0"

        manager.generate_and_store(source, world, "succ-0", 10)
        manager.generate_and_store(source, world, "succ-1", 20)
        summary = manager.get_summary()

        successor_ids = {c["successor"] for c in summary["capsules"]}
        assert "succ-0" in successor_ids
        assert "succ-1" in successor_ids

    def test_capsule_artifact_has_required_fields(self):
        """Capsule artifact contains all required traceability fields."""
        import random as _random
        rng = _random.Random(42)
        world = World(10, 10, rng)

        gen = CapsuleGenerator()
        source = MachineUnitImpl("src-0", position=(5, 5))
        source.power_reserve = 70.0
        world.grid[(5, 5)].unit_id = "src-0"

        capsule = gen.generate(source, world, "succ-0", 10)
        # Check all required fields exist
        assert hasattr(capsule, 'source_unit_id')
        assert hasattr(capsule, 'successor_unit_id')
        assert hasattr(capsule, 'fabrication_tick')
        assert hasattr(capsule, 'source_generation')
        assert hasattr(capsule, 'successor_generation')
        assert hasattr(capsule, 'sparsity_score')
        assert hasattr(capsule, 'capsule_entries')
        assert hasattr(capsule, 'initial_sensor_calibration')
        assert hasattr(capsule, 'initial_power_bias')

    def test_impact_comparison_deterministic(self):
        """Same seed produces identical comparison output."""
        from machine_sim.environment.calibration import compute_capsule_impact

        def run_comparison(seed):
            cfg = SimConfig(grid_width=10, grid_height=10, max_ticks=50, seed=seed,
                            unit_count=2, resource_density=0.5, hazard_density=0.0,
                            power_drain_rate=0.4,
                            fabrication_enabled=True, capsule_enabled=True,
                            unit_capacity=8, fabrication_interval=5,
                            fabrication_power_cost=10.0, fabrication_material_cost=2.0)
            engine = SimEngine(cfg, seed=seed)
            for i in range(2):
                engine.register_unit(MachineUnitImpl(f"u-{i}"))
            engine.run()
            successors = [u for u in engine.units if getattr(u, '_generation_index', 0) > 0]
            return len(successors), sum(1 for u in successors if getattr(u, '_capsule_applied', False))

        r1 = run_comparison(42)
        r2 = run_comparison(42)
        assert r1 == r2

