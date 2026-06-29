"""Runtime state and label validation."""

from __future__ import annotations

from machine_sim.agents.base import MachineState
from machine_sim.guardrails.config import (
    ALLOWED_ACTION_NAMES,
    ALLOWED_COMPONENT_NAMES,
    ALLOWED_CONFIG_KEYS,
    ALLOWED_EVENT_LABELS,
    ALLOWED_MEMORY_LABELS,
    ALLOWED_STATE_FIELDS,
)


class StateViolation(Exception):
    """Raised when unit state contains non-machine-native fields."""


def validate_agent_state(state: MachineState) -> None:
    """Assert that unit state contains only machine-native fields."""
    state_dict = state.__dict__
    extra_keys = set(state_dict.keys()) - ALLOWED_STATE_FIELDS
    if extra_keys:
        raise StateViolation(
            f"Unit {state.unit_id} has non-machine-native state fields: {extra_keys}"
        )
    if not (0.0 <= state.power_reserve <= state.max_power):
        raise StateViolation(
            f"Unit {state.unit_id} power_reserve out of bounds: {state.power_reserve}"
        )
    for comp_name in state.components:
        if comp_name not in ALLOWED_COMPONENT_NAMES:
            raise StateViolation(
                f"Unit {state.unit_id} has forbidden component: {comp_name}"
            )
    for entry in state.local_memory:
        if entry.event_type not in ALLOWED_MEMORY_LABELS:
            raise StateViolation(
                f"Unit {state.unit_id} memory has forbidden label: {entry.event_type}"
            )


def validate_action_name(action_name: str) -> None:
    """Assert action name is in allowed set."""
    if action_name not in ALLOWED_ACTION_NAMES:
        raise StateViolation(f"Forbidden action name: {action_name}")


def validate_event_label(label: str) -> None:
    """Assert event label is in allowed set."""
    if label not in ALLOWED_EVENT_LABELS:
        raise StateViolation(f"Forbidden event label: {label}")


def validate_config_keys(keys: set) -> None:
    """Assert config keys are in allowed set."""
    extra = keys - ALLOWED_CONFIG_KEYS
    if extra:
        raise StateViolation(f"Forbidden config keys: {extra}")
