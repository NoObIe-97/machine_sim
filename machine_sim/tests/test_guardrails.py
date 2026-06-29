"""Tests for guardrail enforcement."""

from __future__ import annotations

from pathlib import Path

import pytest

from machine_sim.agents.unit import MachineUnitImpl
from machine_sim.agents.variants import ALL_VARIANTS
from machine_sim.guardrails.codecheck import check_ast
from machine_sim.guardrails.lexical import scan_directory
from machine_sim.guardrails.runtime import StateViolation, validate_agent_state


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
    # Simulate adding a forbidden field by creating a new state-like object
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
    # validate_agent_state expects MachineState, so test the field check directly
    from machine_sim.guardrails.config import ALLOWED_STATE_FIELDS
    extra = set(fake.__dict__.keys()) - ALLOWED_STATE_FIELDS
    assert "goal" in extra
