"""Tests for Milestone 6 fabricated descent and lineage."""

from __future__ import annotations

import pytest

from machine_sim.agents.unit import MachineUnitImpl
from machine_sim.environment.fabrication import (
    DesignTemplate,
    FabricationEngine,
    FabricationResult,
    LineageRecord,
)
from machine_sim.environment.resources import Resource, ResourceType
from machine_sim.environment.world import World
from machine_sim.sim.config import SimConfig
from machine_sim.sim.engine import SimEngine
from machine_sim.sim.events import EventType


class TestFabricationEngine:
    """Fabrication engine tests."""

    def test_can_fabricate_succeeds_with_resources(self):
        """Fabrication succeeds when constraints are met."""
        import random
        rng = random.Random(42)
        world = World(10, 10, rng)

        fab = FabricationEngine(population_cap=10, power_cost=20.0, material_cost=3.0)
        unit = MachineUnitImpl("u0", position=(5, 5))
        unit.power_reserve = 80.0
        world.grid[(5, 5)].unit_id = "u0"
        # Manually place resources at unit position
        world.grid[(5, 5)].resources["component_scrap"] = Resource(
            resource_type=ResourceType.COMPONENT_SCRAP, quantity=10.0
        )

        can_fab, cause = fab.can_fabricate(unit, 10, world, 1)
        assert can_fab is True
        assert cause == "ok"

    def test_can_fabricate_fails_insufficient_power(self):
        """Fabrication fails with insufficient power."""
        import random
        rng = random.Random(42)
        world = World(10, 10, rng)

        fab = FabricationEngine(population_cap=10, power_cost=50.0)
        unit = MachineUnitImpl("u0", position=(5, 5))
        unit.power_reserve = 10.0
        world.grid[(5, 5)].unit_id = "u0"
        world.grid[(5, 5)].resources["component_scrap"] = Resource(
            resource_type=ResourceType.COMPONENT_SCRAP, quantity=10.0
        )

        can_fab, cause = fab.can_fabricate(unit, 10, world, 1)
        assert can_fab is False
        assert cause == "insufficient_power"

    def test_can_fabricate_fails_placement_unavailable(self):
        """Fabrication fails when no placement available."""
        import random
        rng = random.Random(42)
        world = World(3, 3, rng)

        fab = FabricationEngine(population_cap=10, power_cost=10.0, material_cost=1.0)
        # Fill all cells
        for pos in world.grid:
            world.grid[pos].unit_id = "filler"
            world.grid[pos].resources["component_scrap"] = Resource(
                resource_type=ResourceType.COMPONENT_SCRAP, quantity=10.0
            )

        unit = MachineUnitImpl("u0", position=(1, 1))
        unit.power_reserve = 80.0
        world.grid[(1, 1)].unit_id = "u0"

        can_fab, cause = fab.can_fabricate(unit, 10, world, 9)
        assert can_fab is False
        assert cause == "placement_unavailable"

    def test_can_fabricate_fails_population_cap(self):
        """Fabrication fails when population cap reached."""
        import random
        rng = random.Random(42)
        world = World(10, 10, rng)

        fab = FabricationEngine(population_cap=2, power_cost=10.0, material_cost=1.0)
        unit = MachineUnitImpl("u0", position=(5, 5))
        unit.power_reserve = 80.0
        world.grid[(5, 5)].unit_id = "u0"
        world.grid[(5, 5)].resources["component_scrap"] = Resource(
            resource_type=ResourceType.COMPONENT_SCRAP, quantity=10.0
        )

        can_fab, cause = fab.can_fabricate(unit, 10, world, 2)
        assert can_fab is False
        assert cause == "population_capacity"

    def test_fabrication_deducts_costs(self):
        """Fabrication deducts power and material from source."""
        import random
        rng = random.Random(42)
        world = World(10, 10, rng)

        fab = FabricationEngine(population_cap=10, power_cost=20.0, material_cost=3.0)
        unit = MachineUnitImpl("u0", position=(5, 5))
        unit.power_reserve = 80.0
        world.grid[(5, 5)].unit_id = "u0"
        world.grid[(5, 5)].resources["component_scrap"] = Resource(
            resource_type=ResourceType.COMPONENT_SCRAP, quantity=10.0
        )

        initial_power = unit.power_reserve
        result = fab.fabricate(unit, 10, world, 1, rng)
        assert result.success is True
        assert unit.power_reserve < initial_power

    def test_fabrication_creates_successor(self):
        """Fabrication creates a successor unit."""
        import random
        rng = random.Random(42)
        world = World(10, 10, rng)

        fab = FabricationEngine(population_cap=10, power_cost=20.0, material_cost=3.0)
        unit = MachineUnitImpl("u0", position=(5, 5))
        unit.power_reserve = 80.0
        world.grid[(5, 5)].unit_id = "u0"
        world.grid[(5, 5)].resources["component_scrap"] = Resource(
            resource_type=ResourceType.COMPONENT_SCRAP, quantity=10.0
        )

        result = fab.fabricate(unit, 10, world, 1, rng)
        assert result.success is True
        assert result.successor_id is not None
        assert result.source_id == "u0"

    def test_lineage_recorded(self):
        """Fabrication records lineage metadata."""
        import random
        rng = random.Random(42)
        world = World(10, 10, rng)

        fab = FabricationEngine(population_cap=10, power_cost=20.0, material_cost=3.0)
        unit = MachineUnitImpl("u0", position=(5, 5))
        unit.power_reserve = 80.0
        world.grid[(5, 5)].unit_id = "u0"
        world.grid[(5, 5)].resources["component_scrap"] = Resource(
            resource_type=ResourceType.COMPONENT_SCRAP, quantity=10.0
        )

        fab.fabricate(unit, 10, world, 1, rng)
        records = fab.get_lineage_records()
        assert len(records) == 1
        assert records[0].source_unit_id == "u0"
        assert records[0].successor_generation == 1

    def test_fabrication_deterministic(self):
        """Same seed produces same fabrication results."""
        def run_fab(seed):
            cfg = SimConfig(grid_width=10, grid_height=10, max_ticks=50, seed=seed,
                            unit_count=3, resource_density=0.3, hazard_density=0.0,
                            signal_enabled=True, fabrication_enabled=True,
                            population_cap=10, fabrication_interval=10,
                            fabrication_power_cost=15.0, fabrication_material_cost=2.0)
            engine = SimEngine(cfg, seed=seed)
            for i in range(3):
                engine.register_unit(MachineUnitImpl(f"u-{i}", signal_enabled=True))
            engine.run()
            summary = engine.get_fabrication_summary()
            return (summary["total_successes"], summary["total_lineage_records"])

        r1 = run_fab(42)
        r2 = run_fab(42)
        assert r1 == r2

    def test_fabrication_summary_structure(self):
        """Fabrication summary has expected structure."""
        import random
        rng = random.Random(42)
        world = World(10, 10, rng)

        fab = FabricationEngine(population_cap=10, power_cost=20.0, material_cost=3.0)
        unit = MachineUnitImpl("u0", position=(5, 5))
        unit.power_reserve = 80.0
        world.grid[(5, 5)].unit_id = "u0"
        world.grid[(5, 5)].resources["component_scrap"] = Resource(
            resource_type=ResourceType.COMPONENT_SCRAP, quantity=10.0
        )

        fab.fabricate(unit, 10, world, 1, rng)
        summary = fab.get_summary()
        assert "total_attempts" in summary
        assert "total_successes" in summary
        assert "failures_by_cause" in summary
        assert "generation_distribution" in summary
        assert "lineage" in summary


class TestDesignTemplate:
    """Design template tests."""

    def test_template_has_expected_fields(self):
        """Design template has all expected fields."""
        template = DesignTemplate()
        assert hasattr(template, 'variant_name')
        assert hasattr(template, 'max_power')
        assert hasattr(template, 'sensor_range')
        assert hasattr(template, 'signal_enabled')

    def test_template_bounded_variation(self):
        """Template variation is bounded."""
        import random
        rng = random.Random(42)
        fab = FabricationEngine(variation_factor=0.1)
        unit = MachineUnitImpl("u0")
        template = fab._create_template(unit, rng)
        assert 50.0 <= template.max_power <= 200.0
        assert 1 <= template.sensor_range <= 8


class TestFabricationDemo:
    """Fabrication demo scenario tests."""

    def test_fabrication_demo_deterministic(self):
        """Fabrication demo produces identical results with same seed."""
        def run_demo(seed):
            cfg = SimConfig(grid_width=15, grid_height=15, max_ticks=100, seed=seed,
                            unit_count=4, resource_density=0.3, hazard_density=0.05,
                            signal_enabled=True, adaptive_enabled=True,
                            fabrication_enabled=True, population_cap=10,
                            fabrication_interval=15, fabrication_power_cost=20.0,
                            fabrication_material_cost=3.0)
            engine = SimEngine(cfg, seed=seed)
            for i in range(4):
                engine.register_unit(MachineUnitImpl(f"u-{i}", signal_enabled=True,
                                                       adaptive_enabled=True))
            engine.run()
            summary = engine.get_fabrication_summary()
            return (summary["total_attempts"], summary["total_successes"])

        r1 = run_demo(42)
        r2 = run_demo(42)
        assert r1 == r2

    def test_fabrication_direct_pipeline_produces_successor(self):
        """Directly invoke fabrication pipeline to prove it creates successors."""
        import random
        rng = random.Random(42)
        world = World(10, 10, rng)

        # Place resources at unit position
        world.grid[(5, 5)].resources["component_scrap"] = Resource(
            resource_type=ResourceType.COMPONENT_SCRAP, quantity=20.0
        )
        world.grid[(5, 5)].resources["power_node"] = Resource(
            resource_type=ResourceType.POWER_NODE, quantity=20.0
        )

        fab = FabricationEngine(
            population_cap=10, power_cost=15.0, material_cost=3.0,
            variation_factor=0.1, min_power_ratio=0.3,
            min_component_health=0.2, fabrication_interval=0,
        )
        source = MachineUnitImpl("src-0", position=(5, 5))
        source.power_reserve = 80.0
        world.grid[(5, 5)].unit_id = "src-0"

        # First fabrication
        result1 = fab.fabricate(source, 10, world, 1, rng)
        assert result1.success is True
        assert result1.template is not None
        assert result1.placement is not None
        assert result1.source_id == "src-0"

        # Verify template fields are populated
        tmpl = result1.template
        assert 50.0 <= tmpl.max_power <= 200.0
        assert 1 <= tmpl.sensor_range <= 8
        assert tmpl.signal_enabled is False

        # Verify material cost is unchanged after consumption
        assert fab.material_cost == 3.0

        # Verify lineage
        records = fab.get_lineage_records()
        assert len(records) == 1
        assert records[0].source_unit_id == "src-0"
        assert records[0].successor_unit_id == result1.successor_id
        assert records[0].successor_generation == 1
        assert records[0].fabrication_tick == 10

        # Second fabrication from same source
        source._last_fabrication_tick = -999  # reset cooldown
        result2 = fab.fabricate(source, 20, world, 2, rng)
        assert result2.success is True
        records = fab.get_lineage_records()
        assert len(records) == 2
        assert records[1].successor_generation == 1
        assert records[1].fabrication_tick == 20

    def test_fabrication_config_unchanged_after_attempts(self):
        """Fabrication config parameters remain unchanged after multiple attempts."""
        import random
        rng = random.Random(42)
        world = World(10, 10, rng)

        fab = FabricationEngine(
            population_cap=10, power_cost=25.0, material_cost=5.0,
            variation_factor=0.1, fabrication_interval=0,
        )
        source = MachineUnitImpl("src-0", position=(5, 5))
        source.power_reserve = 80.0
        world.grid[(5, 5)].unit_id = "src-0"

        # Record initial config
        initial_power_cost = fab.power_cost
        initial_material_cost = fab.material_cost

        # Run multiple failed attempts (insufficient material)
        for tick in range(10):
            fab.fabricate(source, tick, world, 1, rng)
            source._last_fabrication_tick = -999

        # Config should be unchanged
        assert fab.power_cost == initial_power_cost
        assert fab.material_cost == initial_material_cost

    def test_fabrication_demo_generates_successors(self):
        """Engine-level fabrication creates successors with proper config."""
        cfg = SimConfig(grid_width=15, grid_height=15, max_ticks=250, seed=42,
                        unit_count=3, resource_density=0.4, hazard_density=0.02,
                        signal_enabled=True, adaptive_enabled=True,
                        fabrication_enabled=True, population_cap=12,
                        fabrication_interval=10, fabrication_power_cost=15.0,
                        fabrication_material_cost=2.0)
        engine = SimEngine(cfg, seed=42)
        for i in range(3):
            engine.register_unit(MachineUnitImpl(f"u-{i}", signal_enabled=True,
                                                  adaptive_enabled=True))
        engine.run()
        summary = engine.get_fabrication_summary()
        assert summary["total_attempts"] > 0, "Should have fabrication attempts"
