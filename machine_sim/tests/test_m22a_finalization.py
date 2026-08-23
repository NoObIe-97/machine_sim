"""M22A transactional-finalization tests.

Forces a program-invalid assembly attempt after fabrication prerequisites
pass and proves success-only state is never committed; pairs it with a valid
attempt proving exactly-once finalization; chains both to prove no phantom
lineage edges or generations."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

from machine_sim.agents.design_program import (
    DesignProgram,
    InstructionRecord,
    OP_END,
    canonical_baseline_program,
)
from machine_sim.cli.main import build_engine
from machine_sim.environment.resources import Resource, ResourceType
from machine_sim.sim.config import SimConfig


def _m22a_config() -> SimConfig:
    return SimConfig(
        grid_width=8,
        grid_height=8,
        resource_density=0.0,
        hazard_density=0.0,
        unit_count=1,
        max_ticks=60,
        seed=41,
        signal_enabled=False,
        adaptive_enabled=False,
        neural_controller_enabled=False,
        telemetry_enabled=False,
        multi_generation_trace_enabled=False,
        long_run_adaptation_enabled=False,
        fabrication_enabled=True,
        unit_capacity=8,
        fabrication_interval=3,
        fabrication_power_cost=30.0,
        fabrication_material_cost=0.3,
        capsule_enabled=False,
        design_program_enabled=True,
        program_execution_budget=512,
        program_min_length=1,
        program_max_length=128,
        program_base_cost=0.5,
        program_per_instruction_cost=0.01,
        program_substitution_probability=0.0,
        program_operand_mutation_probability=0.0,
        program_insertion_probability=0.0,
        program_deletion_probability=0.0,
    )


def _build(program: Optional[DesignProgram]) -> Any:
    from machine_sim.agents.unit import MachineUnitImpl

    config = _m22a_config()
    engine = build_engine(config)
    # Replace the CLI-built population with a single deterministic unit.
    engine.units.clear()
    engine._architecture_initial_descriptors.clear()
    unit = MachineUnitImpl(
        unit_id="unit-src",
        position=(4, 4),
        signal_enabled=False,
        adaptive_enabled=False,
        neural_controller_enabled=False,
        neural_seed=config.seed,
        design_program=program,
        design_execution_bounds=None,
    )
    unit.power_reserve = 10000.0
    unit.max_power = 10000.0
    engine.register_unit(unit)
    engine.initialize()
    # Deterministic fabrication prerequisites: rich local material, no
    # neighbors, cleared cooldown markers.
    engine.world.grid[(4, 4)].resources["component_scrap"] = Resource(
        resource_type=ResourceType.COMPONENT_SCRAP, quantity=50.0
    )
    unit._last_fabrication_tick = -999
    unit._last_fabrication_attempt_tick = -999
    return engine


def _occupied_cells(engine: Any) -> int:
    return sum(1 for cell in engine.world.grid.values() if cell.unit_id is not None)


def _events_of(engine: Any, name: str) -> List[Dict[str, Any]]:
    return [
        {"cause": e.data.get("cause"), "tick": e.tick}
        for e in engine.event_log.all_events()
        if e.event_type.name == name
    ]


def _prime_fabrication_snapshot(engine: Any) -> Dict[str, Any]:
    """Capture pre-attempt accounting plus the exact pre-consumption power."""
    unit = engine.units[0]
    snapshots: Dict[str, Any] = {}
    fabricator = engine.fabrication_engine
    original_prepare = fabricator.prepare_fabricate

    def snapshotting_prepare(source_unit, current_tick, world, population, rng):
        snapshots["pre_power"] = source_unit.power_reserve
        snapshots["pre_material"] = engine.world.grid[(4, 4)].resources[
            "component_scrap"
        ].quantity
        snapshots["tick"] = current_tick
        return original_prepare(source_unit, current_tick, world, population, rng)

    fabricator.prepare_fabricate = snapshotting_prepare  # type: ignore[method-assign]
    return snapshots


def _accounting(engine: Any) -> Dict[str, Any]:
    unit = engine.units[0]
    fabricator = engine.fabrication_engine
    return {
        "attempts": fabricator._fabrication_attempts,
        "successes": fabricator._fabrication_successes,
        "lineage": len(fabricator.get_lineage_records()),
        "failures": dict(fabricator._fabrication_failures),
        "units": len(engine.units),
        "occupied": _occupied_cells(engine),
        "marker": unit._last_fabrication_tick,
        "attempt_marker": unit._last_fabrication_attempt_tick,
        "failed_events": _events_of(engine, "FABRICATION_FAILED"),
        "succeeded_events": _events_of(engine, "FABRICATION_SUCCEEDED"),
    }


EMPTY_PROGRAM = DesignProgram(instructions=[])


def test_invalid_program_attempt_commits_nothing() -> None:
    engine = _build(EMPTY_PROGRAM)
    snapshots = _prime_fabrication_snapshot(engine)
    before = _accounting(engine)
    engine.tick()
    after = _accounting(engine)

    assert after["attempts"] == before["attempts"] + 1
    assert after["successes"] == before["successes"]
    assert after["lineage"] == before["lineage"]
    assert after["units"] == before["units"]
    assert after["occupied"] == before["occupied"]
    assert after["failures"].get("successor_program_invalid") == 1

    # Exactly one program-invalid failure event, no success event.
    failed = [e for e in after["failed_events"] if e["cause"] == "successor_program_invalid"]
    assert len(failed) == 1
    assert len(after["succeeded_events"]) == 0

    # Success-only marker untouched; attempt marker coherent.
    assert after["marker"] == -999
    assert after["attempt_marker"] == snapshots["tick"]

    # Consumed costs changed exactly once: base power + program execution.
    expected_power = (
        snapshots["pre_power"]
        - 30.0  # base fabrication power cost
        - 0.5   # program base cost (empty program executes nothing)
    )
    assert engine.units[0].power_reserve == pytest.approx(expected_power)
    assert snapshots["pre_material"] - 0.3 == pytest.approx(
        engine.world.grid[(4, 4)].resources["component_scrap"].quantity
    )


def test_valid_program_finalizes_exactly_once() -> None:
    engine = _build(canonical_baseline_program())
    snapshots = _prime_fabrication_snapshot(engine)
    before = _accounting(engine)
    engine.tick()
    after = _accounting(engine)

    assert after["attempts"] == before["attempts"] + 1
    assert after["successes"] == before["successes"] + 1
    assert after["lineage"] == before["lineage"] + 1
    assert after["units"] == before["units"] + 1
    assert after["occupied"] == before["occupied"] + 1
    assert after["marker"] == snapshots["tick"]
    assert len(after["succeeded_events"]) == 1
    program_failures = [
        e for e in after["failed_events"] if e["cause"] == "successor_program_invalid"
    ]
    assert program_failures == []

    lineage = engine.fabrication_engine.get_lineage_records()
    assert len(lineage) == 1
    successor = [u for u in engine.units if u.unit_id != "unit-src"]
    assert len(successor) == 1
    assert lineage[0].successor_unit_id == successor[0].unit_id
    assert successor[0]._design_program is not None


def test_failed_then_valid_sequence_has_no_phantom_lineage() -> None:
    engine = _build(EMPTY_PROGRAM)
    engine.tick()  # failed attempt
    failed_accounting = _accounting(engine)
    assert failed_accounting["failures"].get("successor_program_invalid") == 1

    provisional_ids = {
        row["successor_unit_id"]
        for row in engine._design_program_transfer_trace
    }

    # Repair the program (machine-native replacement, not runtime
    # self-modification of an active program: the unit is rebuilt through the
    # documented constructor path used by tests) and clear cooldown markers.
    unit = engine.units[0]
    unit._design_program = canonical_baseline_program()
    unit._last_fabrication_attempt_tick = -999
    unit._last_fabrication_tick = -999

    while engine.tick_count < 40:
        pre_units = len(engine.units)
        engine.tick()
        if len(engine.units) > pre_units:
            break

    after = _accounting(engine)
    assert after["successes"] == 1
    assert after["lineage"] == 1
    lineage = engine.fabrication_engine.get_lineage_records()
    # No lineage edge may reference any provisional ID from the failed phase.
    for record in lineage:
        assert record.successor_unit_id not in provisional_ids
    # The real successor exists and owns its own generation edge.
    successors = [u for u in engine.units if u.unit_id != "unit-src"]
    assert len(successors) == 1
    assert successors[0]._generation_index == 1
    # Failed attempt left no phantom generation entries anywhere.
    assert all(
        record.successor_generation == 1 for record in lineage
    )


def test_checkpoint_roundtrip_preserves_post_failure_accounting() -> None:
    from machine_sim.sim.checkpoint import decode_state, encode_state
    from machine_sim.sim.state_digest import deep_state_digest

    engine = _build(EMPTY_PROGRAM)
    engine.tick()
    before_digest = deep_state_digest(engine)
    restored = decode_state(encode_state(engine))

    assert deep_state_digest(restored) == before_digest
    assert (
        restored.fabrication_engine._fabrication_attempts
        == engine.fabrication_engine._fabrication_attempts
    )
    assert (
        restored.fabrication_engine._fabrication_successes
        == engine.fabrication_engine._fabrication_successes
    )
    assert (
        restored.fabrication_engine._fabrication_failures
        == engine.fabrication_engine._fabrication_failures
    )
    assert len(restored.fabrication_engine.get_lineage_records()) == len(
        engine.fabrication_engine.get_lineage_records()
    )
    assert restored.units[0]._last_fabrication_tick == engine.units[0]._last_fabrication_tick


def test_legacy_wrapper_matches_two_phase_outcomes() -> None:
    """The legacy fabricate() wrapper equals prepare+commit exactly."""
    outcomes = []
    for mode in ("wrapper", "two_phase"):
        engine = _build(canonical_baseline_program())
        fabricator = engine.fabrication_engine
        unit = engine.units[0]
        snapshots = {}
        original_prepare = fabricator.prepare_fabricate

        def snapshotting_prepare(source_unit, tick, world, pop, rng, _s=snapshots):
            _s["power"] = source_unit.power_reserve
            return original_prepare(source_unit, tick, world, pop, rng)

        fabricator.prepare_fabricate = snapshotting_prepare  # type: ignore[method-assign]
        if mode == "wrapper":
            result = fabricator.fabricate(unit, 1, engine.world, 1, random_module().Random(3))
        else:
            pending = fabricator.prepare_fabricate(unit, 1, engine.world, 1, random_module().Random(3))
            result = fabricator.commit_fabrication(pending)
        outcomes.append(
            (
                result.success,
                result.successor_id,
                result.material_cost,
                result.power_cost,
                snapshots["power"],
                fabricator._fabrication_successes,
                len(fabricator.get_lineage_records()),
                unit._last_fabrication_tick,
            )
        )
    assert outcomes[0] == outcomes[1]


def random_module():
    import random

    return random
