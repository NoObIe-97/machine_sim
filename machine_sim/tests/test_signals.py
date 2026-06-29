"""Tests for Milestone 3 non-semantic signaling substrate."""

from __future__ import annotations

import pytest

from machine_sim.agents.base import Action, ActionType
from machine_sim.agents.unit import MachineUnitImpl
from machine_sim.environment.world import World, Signal
from machine_sim.guardrails.runtime import StateViolation, validate_action_name, validate_event_label
from machine_sim.sim.config import SimConfig
from machine_sim.sim.engine import SimEngine
from machine_sim.sim.events import EventType


class TestSignalEmission:
    """Signal emission tests."""

    def test_signal_emission_consumes_power(self):
        """Emitting a signal consumes power."""
        import random
        rng = random.Random(42)
        world = World(10, 10, rng)
        unit = MachineUnitImpl("u0", position=(5, 5))
        world.grid[(5, 5)].unit_id = "u0"

        action = Action(
            ActionType.EMIT_SIGNAL,
            parameters={"pattern_id": 0, "intensity": 1.0, "radius": 3, "decay_rate": 0.1, "duration": 10},
        )
        result = world.execute_action(action, unit)

        assert result.success is True
        assert result.power_delta < 0, "Signal emission should consume power"

    def test_emitted_signal_appears_in_world(self):
        """Emitted signals appear in world signal list."""
        import random
        rng = random.Random(42)
        world = World(10, 10, rng)
        unit = MachineUnitImpl("u0", position=(5, 5))
        world.grid[(5, 5)].unit_id = "u0"

        action = Action(
            ActionType.EMIT_SIGNAL,
            parameters={"pattern_id": 0, "intensity": 1.0, "radius": 3, "decay_rate": 0.1, "duration": 10},
        )
        world.execute_action(action, unit)

        assert len(world.signals) == 1
        assert world.signals[0].source_unit_id == "u0"
        assert world.signals[0].position == (5, 5)

    def test_signal_has_correct_parameters(self):
        """Emitted signal has correct parameters."""
        import random
        rng = random.Random(42)
        world = World(10, 10, rng)
        unit = MachineUnitImpl("u0", position=(5, 5))
        world.grid[(5, 5)].unit_id = "u0"

        action = Action(
            ActionType.EMIT_SIGNAL,
            parameters={"pattern_id": 2, "intensity": 0.8, "radius": 5, "decay_rate": 0.2, "duration": 15},
        )
        world.execute_action(action, unit)

        sig = world.signals[0]
        assert sig.pattern_id == 2
        assert sig.intensity == 0.8
        assert sig.radius == 5
        assert sig.decay_rate == 0.2
        assert sig.duration == 15


class TestSignalDecay:
    """Signal decay and expiration tests."""

    def test_signal_decays_over_ticks(self):
        """Signal intensity decays over ticks."""
        import random
        rng = random.Random(42)
        world = World(10, 10, rng)
        unit = MachineUnitImpl("u0", position=(5, 5))
        world.grid[(5, 5)].unit_id = "u0"

        action = Action(
            ActionType.EMIT_SIGNAL,
            parameters={"pattern_id": 0, "intensity": 1.0, "radius": 3, "decay_rate": 0.2, "duration": 10},
        )
        world.execute_action(action, unit)

        initial_intensity = world.signals[0].intensity
        world.update(1)
        assert world.signals[0].intensity < initial_intensity

    def test_signal_expires_after_duration(self):
        """Signal is removed after duration expires."""
        import random
        rng = random.Random(42)
        world = World(10, 10, rng)
        unit = MachineUnitImpl("u0", position=(5, 5))
        world.grid[(5, 5)].unit_id = "u0"

        action = Action(
            ActionType.EMIT_SIGNAL,
            parameters={"pattern_id": 0, "intensity": 1.0, "radius": 3, "decay_rate": 0.1, "duration": 5},
        )
        world.execute_action(action, unit)

        # Tick 0: emitted
        world.update(1)  # tick 1
        world.update(2)  # tick 2
        world.update(3)  # tick 3
        world.update(4)  # tick 4
        assert len(world.signals) == 1  # still alive

        world.update(5)  # tick 5: duration expired
        assert len(world.signals) == 0

    def test_signal_decay_deterministic(self):
        """Same seed produces same signal decay pattern."""
        def run_signal_decay(seed):
            cfg = SimConfig(grid_width=5, grid_height=5, max_ticks=10, seed=seed,
                            unit_count=1, resource_density=0.0, hazard_density=0.0,
                            signal_enabled=True)
            engine = SimEngine(cfg, seed=seed)
            unit = MachineUnitImpl("u0", signal_enabled=True)
            engine.register_unit(unit)
            engine.initialize()
            engine.run()
            events = [e for e in engine.event_log.all_events()
                      if e.event_type == EventType.SIGNAL_EMITTED]
            return len(events)

        r1 = run_signal_decay(42)
        r2 = run_signal_decay(42)
        assert r1 == r2


class TestSignalSensing:
    """Signal sensing by nearby units tests."""

    def test_nearby_unit_senses_signal(self):
        """Unit within signal range can sense the signal."""
        import random
        rng = random.Random(42)
        world = World(10, 10, rng)
        u0 = MachineUnitImpl("u0", position=(5, 5))
        u1 = MachineUnitImpl("u1", position=(6, 5))
        world.grid[(5, 5)].unit_id = "u0"
        world.grid[(6, 5)].unit_id = "u1"

        # Emit signal from u0
        action = Action(
            ActionType.EMIT_SIGNAL,
            parameters={"pattern_id": 0, "intensity": 1.0, "radius": 3, "decay_rate": 0.1, "duration": 10},
        )
        world.execute_action(action, u0)

        # u1 senses signals
        observations = world.sense_signals(u1.position, u1.sensor_range)
        assert len(observations) >= 1
        assert observations[0]["source_unit_id"] == "u0"

    def test_unit_outside_range_does_not_sense(self):
        """Unit outside signal range does not sense the signal."""
        import random
        rng = random.Random(42)
        world = World(10, 10, rng)
        u0 = MachineUnitImpl("u0", position=(5, 5))
        u1 = MachineUnitImpl("u1", position=(9, 9))
        world.grid[(5, 5)].unit_id = "u0"
        world.grid[(9, 9)].unit_id = "u1"

        action = Action(
            ActionType.EMIT_SIGNAL,
            parameters={"pattern_id": 0, "intensity": 1.0, "radius": 2, "decay_rate": 0.1, "duration": 10},
        )
        world.execute_action(action, u0)

        observations = world.sense_signals(u1.position, 1)
        assert len(observations) == 0

    def test_signal_sensing_deterministic(self):
        """Same seed produces same signal observations."""
        def run_signal_sense(seed):
            cfg = SimConfig(grid_width=10, grid_height=10, max_ticks=5, seed=seed,
                            unit_count=2, resource_density=0.0, hazard_density=0.0,
                            signal_enabled=True)
            engine = SimEngine(cfg, seed=seed)
            for i in range(2):
                engine.register_unit(MachineUnitImpl(f"u-{i}", signal_enabled=True))
            engine.initialize()
            engine.run()
            events = [e for e in engine.event_log.all_events()
                      if e.event_type == EventType.SIGNAL_RECEIVED]
            return len(events)

        r1 = run_signal_sense(42)
        r2 = run_signal_sense(42)
        assert r1 == r2

    def test_source_unit_excluded_from_own_signal(self):
        """Source unit does not receive its own signal."""
        import random
        rng = random.Random(42)
        world = World(10, 10, rng)
        u0 = MachineUnitImpl("u0", position=(5, 5))
        world.grid[(5, 5)].unit_id = "u0"

        action = Action(
            ActionType.EMIT_SIGNAL,
            parameters={"pattern_id": 0, "intensity": 1.0, "radius": 3, "decay_rate": 0.1, "duration": 10},
        )
        world.execute_action(action, u0)

        # u0 should NOT sense its own signal
        observations = world.sense_signals(u0.position, u0.sensor_range, exclude_unit_id="u0")
        assert len(observations) == 0, "Source unit should not receive its own signal"

    def test_other_units_still_receive_signal(self):
        """Other units still receive signals from the source."""
        import random
        rng = random.Random(42)
        world = World(10, 10, rng)
        u0 = MachineUnitImpl("u0", position=(5, 5))
        u1 = MachineUnitImpl("u1", position=(5, 6))
        world.grid[(5, 5)].unit_id = "u0"
        world.grid[(5, 6)].unit_id = "u1"

        action = Action(
            ActionType.EMIT_SIGNAL,
            parameters={"pattern_id": 0, "intensity": 1.0, "radius": 3, "decay_rate": 0.1, "duration": 10},
        )
        world.execute_action(action, u0)

        # u1 should receive the signal
        observations = world.sense_signals(u1.position, u1.sensor_range, exclude_unit_id="u1")
        assert len(observations) >= 1, "Other unit should receive signal"
        assert observations[0]["source_unit_id"] == "u0"


class TestSignalGuardrails:
    """Signal-related guardrail tests."""

    def test_emit_signal_action_allowed(self):
        """EMIT_SIGNAL action name passes validation."""
        validate_action_name("EMIT_SIGNAL")

    def test_signal_event_labels_allowed(self):
        """Signal event labels pass validation."""
        for label in ["emit_signal", "signal_emitted", "signal_received"]:
            validate_event_label(label)

    def test_forbidden_labels_rejected(self):
        """Forbidden semantic labels are still rejected."""
        with pytest.raises(StateViolation, match="Forbidden event label"):
            validate_event_label("message")
        with pytest.raises(StateViolation, match="Forbidden event label"):
            validate_event_label("communicate")
        with pytest.raises(StateViolation, match="Forbidden event label"):
            validate_event_label("warning")


class TestSignalDemo:
    """Signal demo scenario tests."""

    def test_signal_demo_deterministic(self):
        """Signal demo produces identical results with same seed."""
        def run_demo(seed):
            cfg = SimConfig(grid_width=10, grid_height=10, max_ticks=30, seed=seed,
                            unit_count=4, resource_density=0.2, hazard_density=0.05,
                            signal_enabled=True, signal_default_radius=4,
                            signal_default_decay=0.15, signal_default_duration=8)
            engine = SimEngine(cfg, seed=seed)
            for i in range(4):
                engine.register_unit(MachineUnitImpl(f"u-{i}", signal_enabled=True))
            state = engine.run()
            emitted = [e for e in state.events if e.event_type == EventType.SIGNAL_EMITTED]
            received = [e for e in state.events if e.event_type == EventType.SIGNAL_RECEIVED]
            return (len(emitted), len(received), state.tick)

        r1 = run_demo(42)
        r2 = run_demo(42)
        assert r1 == r2

    def test_signal_demo_generates_signal_events(self):
        """Signal demo generates emitted and received events."""
        cfg = SimConfig(grid_width=10, grid_height=10, max_ticks=50, seed=42,
                        unit_count=4, resource_density=0.2, hazard_density=0.05,
                        signal_enabled=True, signal_default_radius=4,
                        signal_default_decay=0.15, signal_default_duration=8)
        engine = SimEngine(cfg, seed=42)
        for i in range(4):
            engine.register_unit(MachineUnitImpl(f"u-{i}", signal_enabled=True))
        engine.run()
        events = engine.event_log.all_events()
        emitted = [e for e in events if e.event_type == EventType.SIGNAL_EMITTED]
        received = [e for e in events if e.event_type == EventType.SIGNAL_RECEIVED]
        assert len(emitted) > 0, "Signal demo should generate emitted events"
        assert len(received) > 0, "Signal demo should generate received events"
