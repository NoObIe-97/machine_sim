"""Tests for Milestone 2 interaction substrate."""

from __future__ import annotations

import pytest

from machine_sim.agents.unit import MachineUnitImpl
from machine_sim.environment.world import World
from machine_sim.guardrails.config import ALLOWED_EVENT_LABELS
from machine_sim.guardrails.runtime import StateViolation, validate_event_label
from machine_sim.sim.config import SimConfig
from machine_sim.sim.engine import SimEngine
from machine_sim.sim.events import EventType


class TestProximityDetection:
    """Unit proximity detection tests."""

    def test_nearby_units_detected_within_range(self):
        """Units within sensor range are detected in sensor readings."""
        import random
        rng = random.Random(42)
        world = World(10, 10, rng)
        u1 = MachineUnitImpl("u1", position=(5, 5))
        u2 = MachineUnitImpl("u2", position=(6, 5))
        world.grid[(5, 5)].unit_id = "u1"
        world.grid[(6, 5)].unit_id = "u2"

        readings = world.sense(u1.position, 2)
        nearby = [r for r in readings if r.nearby_units and "u2" in r.nearby_units]
        assert len(nearby) > 0, "Unit within range should be detected"

    def test_units_outside_range_not_detected(self):
        """Units outside sensor range are not detected."""
        import random
        rng = random.Random(42)
        world = World(10, 10, rng)
        u1 = MachineUnitImpl("u1", position=(5, 5))
        u2 = MachineUnitImpl("u2", position=(9, 9))
        world.grid[(5, 5)].unit_id = "u1"
        world.grid[(9, 9)].unit_id = "u2"

        readings = world.sense(u1.position, 1)
        nearby = [r for r in readings if r.nearby_units and "u2" in r.nearby_units]
        assert len(nearby) == 0, "Unit outside range should not be detected"

    def test_proximity_detection_deterministic(self):
        """Same seed produces same proximity detection."""
        def run_proximity(seed):
            cfg = SimConfig(grid_width=10, grid_height=10, max_ticks=5,
                            seed=seed, unit_count=3, resource_density=0.2)
            engine = SimEngine(cfg, seed=seed)
            for i in range(3):
                engine.register_unit(MachineUnitImpl(f"u-{i}", position=(i, i)))
            engine.initialize()
            engine.tick()
            events = [e for e in engine.event_log.all_events()
                      if e.event_type == EventType.UNIT_PROXIMITY]
            return tuple((e.unit_id, e.data.get("nearby_count")) for e in events)

        p1 = run_proximity(42)
        p2 = run_proximity(42)
        assert p1 == p2, "Same seed must produce same proximity events"


class TestOccupancyAwareMovement:
    """Occupancy-aware movement tests."""

    def test_move_into_empty_cell_succeeds(self):
        """Move into empty adjacent cell succeeds."""
        import random
        rng = random.Random(42)
        world = World(10, 10, rng)
        unit = MachineUnitImpl("u0", position=(5, 5))
        world.grid[(5, 5)].unit_id = "u0"

        from machine_sim.agents.base import Action, ActionType
        action = Action(ActionType.MOVE, target_position=(6, 5))
        result = world.execute_action(action, unit)

        assert result.success is True
        assert unit.position == (6, 5)
        assert world.grid[(6, 5)].unit_id == "u0"
        assert world.grid[(5, 5)].unit_id is None

    def test_move_into_occupied_cell_fails(self):
        """Move into occupied adjacent cell fails."""
        import random
        rng = random.Random(42)
        world = World(10, 10, rng)
        u0 = MachineUnitImpl("u0", position=(5, 5))
        u1 = MachineUnitImpl("u1", position=(6, 5))
        world.grid[(5, 5)].unit_id = "u0"
        world.grid[(6, 5)].unit_id = "u1"

        from machine_sim.agents.base import Action, ActionType
        action = Action(ActionType.MOVE, target_position=(6, 5))
        result = world.execute_action(action, u0)

        assert result.success is False
        assert result.event_type == "movement_blocked"
        assert u0.position == (5, 5), "Unit should remain in original position"
        assert u1.position == (6, 5), "Occupying unit should remain"
        assert world.grid[(5, 5)].unit_id == "u0"
        assert world.grid[(6, 5)].unit_id == "u1"

    def test_both_positions_valid_after_failed_move(self):
        """Both unit positions remain valid after failed movement."""
        import random
        rng = random.Random(42)
        world = World(10, 10, rng)
        u0 = MachineUnitImpl("u0", position=(3, 3))
        u1 = MachineUnitImpl("u1", position=(4, 3))
        world.grid[(3, 3)].unit_id = "u0"
        world.grid[(4, 3)].unit_id = "u1"

        from machine_sim.agents.base import Action, ActionType
        action = Action(ActionType.MOVE, target_position=(4, 3))
        world.execute_action(action, u0)

        assert world.grid[(3, 3)].unit_id == "u0"
        assert world.grid[(4, 3)].unit_id == "u1"
        assert u0.position == (3, 3)
        assert u1.position == (4, 3)

    def test_world_occupancy_consistent_after_move(self):
        """World grid occupancy remains consistent after successful move."""
        import random
        rng = random.Random(42)
        world = World(10, 10, rng)
        unit = MachineUnitImpl("u0", position=(2, 2))
        world.grid[(2, 2)].unit_id = "u0"

        from machine_sim.agents.base import Action, ActionType
        action = Action(ActionType.MOVE, target_position=(3, 2))
        world.execute_action(action, unit)

        occupied = [pos for pos, c in world.grid.items() if c.unit_id is not None]
        assert len(occupied) == 1
        assert occupied[0] == (3, 2)


class TestCollisionEventLogging:
    """Collision/contact event logging tests."""

    def test_movement_blocked_event_emitted(self):
        """Movement blocked event is emitted when move fails due to occupancy."""
        cfg = SimConfig(grid_width=5, grid_height=5, max_ticks=1, seed=42,
                        unit_count=2, resource_density=0.0, hazard_density=0.0)
        engine = SimEngine(cfg, seed=42)
        u0 = MachineUnitImpl("u0", position=(2, 2))
        u1 = MachineUnitImpl("u1", position=(3, 2))
        engine.register_unit(u0)
        engine.register_unit(u1)
        engine.world.grid[(2, 2)].unit_id = "u0"
        engine.world.grid[(3, 2)].unit_id = "u1"

        # Force u0 to try moving into u1's cell
        from machine_sim.agents.base import Action, ActionType
        original_decide = u0.decide
        u0.decide = lambda tick: Action(ActionType.MOVE, target_position=(3, 2))

        engine.tick()
        blocked_events = [e for e in engine.event_log.all_events()
                          if e.event_type == EventType.MOVEMENT_BLOCKED]
        assert len(blocked_events) >= 1, "Expected MOVEMENT_BLOCKED event"

    def test_new_event_labels_allowed(self):
        """New interaction event labels pass guardrail validation."""
        for label in ["movement_blocked", "occupancy_constraint",
                      "unit_proximity", "contact_event"]:
            validate_event_label(label)

    def test_forbidden_labels_still_rejected(self):
        """Forbidden social/emotional labels are still rejected."""
        with pytest.raises(StateViolation, match="Forbidden event label"):
            validate_event_label("fight")
        with pytest.raises(StateViolation, match="Forbidden event label"):
            validate_event_label("cooperate")
        with pytest.raises(StateViolation, match="Forbidden event label"):
            validate_event_label("hostile")


class TestSpatialPressure:
    """Local spatial pressure metric tests."""

    def test_spatial_pressure_bounded(self):
        """Spatial pressure is bounded between 0.0 and 1.0."""
        import random
        rng = random.Random(42)
        world = World(10, 10, rng)

        # Empty grid
        p_empty = world.compute_spatial_pressure((5, 5), 2)
        assert 0.0 <= p_empty <= 1.0

        # Fill some cells
        world.grid[(5, 5)].unit_id = "u0"
        world.grid[(5, 6)].unit_id = "u1"
        world.grid[(6, 5)].unit_id = "u2"
        p_partial = world.compute_spatial_pressure((5, 5), 2)
        assert 0.0 <= p_partial <= 1.0

    def test_spatial_pressure_deterministic(self):
        """Same configuration produces same spatial pressure."""
        import random
        rng1 = random.Random(42)
        rng2 = random.Random(42)
        w1 = World(10, 10, rng1)
        w2 = World(10, 10, rng2)
        w1.grid[(5, 5)].unit_id = "u0"
        w1.grid[(5, 6)].unit_id = "u1"
        w2.grid[(5, 5)].unit_id = "u0"
        w2.grid[(5, 6)].unit_id = "u1"

        p1 = w1.compute_spatial_pressure((5, 5), 2)
        p2 = w2.compute_spatial_pressure((5, 5), 2)
        assert p1 == p2

    def test_spatial_pressure_zero_when_empty(self):
        """Spatial pressure is 0.0 when no nearby units."""
        import random
        rng = random.Random(42)
        world = World(10, 10, rng)
        p = world.compute_spatial_pressure((5, 5), 2)
        assert p == 0.0

    def test_spatial_pressure_increases_with_density(self):
        """Spatial pressure increases as more cells are occupied."""
        import random
        rng = random.Random(42)
        world = World(10, 10, rng)
        p0 = world.compute_spatial_pressure((5, 5), 1)

        world.grid[(5, 5)].unit_id = "u0"
        p1 = world.compute_spatial_pressure((5, 5), 1)

        world.grid[(5, 6)].unit_id = "u1"
        world.grid[(6, 5)].unit_id = "u2"
        p2 = world.compute_spatial_pressure((5, 5), 1)

        assert p0 < p1 < p2, "Pressure should increase with density"


class TestCrowdedScenario:
    """Crowded scenario determinism tests."""

    def test_crowded_scenario_deterministic(self):
        """Crowded scenario produces identical results with same seed."""
        def run_crowded(seed):
            cfg = SimConfig(grid_width=8, grid_height=8, max_ticks=20,
                            seed=seed, unit_count=6, resource_density=0.15)
            engine = SimEngine(cfg, seed=seed)
            for i in range(6):
                engine.register_unit(MachineUnitImpl(f"u-{i}"))
            state = engine.run()
            proximity = [e for e in state.events if e.event_type == EventType.UNIT_PROXIMITY]
            blocked = [e for e in state.events if e.event_type == EventType.MOVEMENT_BLOCKED]
            return (len(proximity), len(blocked), state.tick)

        r1 = run_crowded(42)
        r2 = run_crowded(42)
        assert r1 == r2, "Same seed must produce identical crowded scenario results"

    def test_crowded_scenario_generates_interactions(self):
        """Crowded scenario generates proximity and/or blocked events."""
        cfg = SimConfig(grid_width=8, grid_height=8, max_ticks=50,
                        seed=42, unit_count=6, resource_density=0.15)
        engine = SimEngine(cfg, seed=42)
        for i in range(6):
            engine.register_unit(MachineUnitImpl(f"u-{i}"))
        engine.run()
        events = engine.event_log.all_events()
        proximity = [e for e in events if e.event_type == EventType.UNIT_PROXIMITY]
        assert len(proximity) > 0, "Crowded scenario should generate proximity events"
