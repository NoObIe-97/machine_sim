"""Tests for guardrail enforcement."""

from __future__ import annotations

from pathlib import Path

import pytest

from machine_sim.agents.unit import MachineUnitImpl
from machine_sim.agents.variants import ALL_VARIANTS
from machine_sim.guardrails.codecheck import check_ast
from machine_sim.guardrails.lexical import scan_directory
from machine_sim.guardrails.runtime import (
    StateViolation,
    validate_action_name,
    validate_agent_state,
    validate_config_keys,
    validate_event_label,
)


@pytest.fixture
def source_dir():
    return Path(__file__).parent.parent


def test_no_forbidden_terms_in_agents(source_dir):
    agent_dir = source_dir / "agents"
    violations = scan_directory(agent_dir)
    assert not violations, f"Forbidden terms found in agent code: {violations}"


def test_no_forbidden_terms_in_environment(source_dir):
    env_dir = source_dir / "environment"
    violations = scan_directory(env_dir)
    assert not violations, f"Forbidden terms found in environment code: {violations}"


def test_no_forbidden_terms_in_sim(source_dir):
    sim_dir = source_dir / "sim"
    violations = scan_directory(sim_dir)
    assert not violations, f"Forbidden terms found in sim code: {violations}"


def test_no_forbidden_ast_patterns_agents(source_dir):
    agent_dir = source_dir / "agents"
    for py_file in agent_dir.rglob("*.py"):
        violations = check_ast(py_file)
        assert not violations, f"AST violations in {py_file}: {violations}"


def test_no_forbidden_ast_patterns_environment(source_dir):
    env_dir = source_dir / "environment"
    for py_file in env_dir.rglob("*.py"):
        violations = check_ast(py_file)
        assert not violations, f"AST violations in {py_file}: {violations}"


def test_agent_state_validation_all_variants():
    for variant in ALL_VARIANTS:
        unit = MachineUnitImpl(f"test-{variant.name}", variant=variant)
        state = unit.state_copy()
        validate_agent_state(state)


def test_agent_state_rejects_extra_fields():
    unit = MachineUnitImpl("test")
    state = unit.state_copy()
    class FakeState:
        pass
    fake = FakeState()
    fake.unit_id = "x"
    fake.position = (0, 0)
    fake.power_reserve = 50.0
    fake.max_power = 100.0
    fake.components = {}
    fake.sensor_readings = ()
    fake.local_memory = ()
    fake.action_budget = 2
    fake.is_active = True
    fake.unit_class = "test"
    fake.goal = "test_forbidden"
    from machine_sim.guardrails.config import ALLOWED_STATE_FIELDS
    extra = set(fake.__dict__.keys()) - ALLOWED_STATE_FIELDS
    assert "goal" in extra


def test_validate_action_name_accepts_allowed():
    for name in ["MOVE", "SCAN", "HARVEST", "COLLECT", "MAINTAIN", "IDLE"]:
        validate_action_name(name)


def test_validate_action_name_rejects_forbidden():
    with pytest.raises(StateViolation, match="Forbidden action name"):
        validate_action_name("FIGHT")
    with pytest.raises(StateViolation, match="Forbidden action name"):
        validate_action_name("ATTACK")
    with pytest.raises(StateViolation, match="Forbidden action name"):
        validate_action_name("TRADE")


def test_validate_event_label_accepts_allowed():
    for label in ["tick_begin", "tick_end", "unit_action", "hazard_encounter",
                  "unit_deactivated", "move", "harvest", "scan", "idle"]:
        validate_event_label(label)


def test_validate_event_label_rejects_forbidden():
    with pytest.raises(StateViolation, match="Forbidden event label"):
        validate_event_label("fight")
    with pytest.raises(StateViolation, match="Forbidden event label"):
        validate_event_label("trade")
    with pytest.raises(StateViolation, match="Forbidden event label"):
        validate_event_label("emotion")


def test_validate_config_keys_accepts_allowed():
    validate_config_keys({"grid_width", "grid_height", "seed", "max_ticks"})


def test_validate_config_keys_rejects_forbidden():
    with pytest.raises(StateViolation, match="Forbidden config keys"):
        validate_config_keys({"grid_width", "morale_level"})
    with pytest.raises(StateViolation, match="Forbidden config keys"):
        validate_config_keys({"social_graph"})


def test_forbidden_action_rejected_during_simulation():
    """Engine rejects actions with forbidden names at runtime."""
    from machine_sim.sim.config import SimConfig
    from machine_sim.sim.engine import SimEngine
    cfg = SimConfig(grid_width=5, grid_height=5, max_ticks=1, seed=42, unit_count=1)
    engine = SimEngine(cfg, seed=42)
    unit = MachineUnitImpl("u0")
    engine.register_unit(unit)
    engine.initialize()
    engine.tick()
    events = engine.event_log.all_events()
    action_events = [e for e in events if e.data and "action" in e.data]
    for e in action_events:
        validate_action_name(e.data["action"])
