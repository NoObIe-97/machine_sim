"""M23 unit-executed construction integration tests."""

from __future__ import annotations

from typing import Any, Dict, Optional

import pytest

from machine_sim.agents.design_program import (
    DesignProgram,
    InstructionRecord,
    OP_CONSTRUCTION_BEGIN,
    OP_CONSTRUCTION_COMMIT,
    OP_COPY_RECORD,
    OP_END,
    OP_NO_OP,
    OP_SET_HIDDEN,
    canonical_baseline_program,
)
from machine_sim.agents.program_construction import (
    ConstructionExecutionBounds,
    build_canonical_copy_capable_program,
    build_long_developmental_program,
    build_padded_runtime_program,
    init_construction_state,
    runtime_section_bounds,
    _apply_copy_error,
)
from machine_sim.cli.main import build_engine
from machine_sim.environment.resources import Resource, ResourceType
from machine_sim.sim.checkpoint import decode_state, encode_state
from machine_sim.sim.config import SimConfig
from machine_sim.sim.state_digest import deep_state_digest


def _config(**overrides) -> SimConfig:
    values = dict(
        grid_width=10,
        grid_height=10,
        resource_density=0.0,
        hazard_density=0.0,
        unit_count=1,
        max_ticks=120,
        seed=97,
        signal_enabled=False,
        adaptive_enabled=False,
        telemetry_enabled=False,
        multi_generation_trace_enabled=False,
        long_run_adaptation_enabled=False,
        fabrication_enabled=True,
        unit_capacity=8,
        capsule_enabled=False,
        design_program_enabled=True,
        program_substitution_probability=0.0,
        program_operand_mutation_probability=0.0,
        program_insertion_probability=0.0,
        program_deletion_probability=0.0,
        unit_executed_construction_enabled=True,
        runtime_construction_steps_per_tick=1,
        copy_records_per_copy_instruction=1,
        copy_error_probability=0.0,
    )
    values.update(overrides)
    return SimConfig(**values)


def _engine(program: Optional[DesignProgram], **overrides) -> Any:
    from machine_sim.agents.unit import MachineUnitImpl

    config = _config(**overrides)
    engine = build_engine(config)
    engine.units.clear()
    unit = MachineUnitImpl(
        unit_id="unit-a",
        position=(4, 4),
        signal_enabled=False,
        adaptive_enabled=False,
        neural_controller_enabled=False,
        neural_seed=config.seed,
        design_program=program,
        unit_executed_construction_enabled=config.unit_executed_construction_enabled,
    )
    unit.power_reserve = 10000.0
    unit.max_power = 10000.0
    engine.register_unit(unit)
    engine.initialize()
    engine.world.grid[(4, 4)].resources["component_scrap"] = Resource(
        resource_type=ResourceType.COMPONENT_SCRAP, quantity=500.0
    )
    return engine


def _succeeded(engine: Any):
    return [
        e for e in engine.event_log.all_events()
        if e.event_type.name == "CONSTRUCTION_SUCCEEDED"
    ]


def _failed(engine: Any, cause_prefix: str = ""):
    return [
        e for e in engine.event_log.all_events()
        if e.event_type.name == "CONSTRUCTION_FAILED"
        and str(e.data.get("cause", "")).startswith(cause_prefix)
    ]


# --- demonstration A: engine scheduler removal -------------------------------


def test_no_construction_section_produces_zero_successors() -> None:
    """Abundant resources/space but no runtime construction section: the
    engine must never initiate construction on eligibility."""
    engine = _engine(canonical_baseline_program())  # dev-only, ends at END
    state = engine.units[0]._construction_state
    assert state.construction_enabled is False
    for _ in range(60):
        engine.tick()
    assert len(_succeeded(engine)) == 0
    assert len(engine.fabrication_engine._lineage_records) == 0
    assert engine.fabrication_engine._fabrication_successes == 0
    assert len(engine.units) == 1


def test_m23_mode_flag_gates_executor() -> None:
    """M23-disabled configs keep the legacy path and gain no executor."""
    program = build_canonical_copy_capable_program()
    engine = _engine(program, unit_executed_construction_enabled=False)
    state = engine.units[0]._construction_state
    assert state.construction_enabled is False
    for _ in range(30):
        engine.tick()
    # Legacy periodic path owns construction; no runtime stepping happened.
    assert state.executed_runtime_instruction_count == 0


# --- demonstration B: canonical copy-capable program -------------------------


def test_canonical_copy_capable_program_copies_whole_source() -> None:
    program = build_canonical_copy_capable_program()
    engine = _engine(program)
    unit = engine.units[0]
    deadline = 60
    while engine.tick_count < deadline and not _succeeded(engine):
        engine.tick()

    events = _succeeded(engine)
    assert len(events) == 1
    event = events[0]

    # Whole source program copied record-for-record: digests equal.
    successor = [u for u in engine.units if u.unit_id != "unit-a"]
    assert len(successor) == 1
    assert event.data["copied_program_digest"] == program.program_digest()
    assert successor[0]._design_program.program_digest() == program.program_digest()

    # Copied runtime construction instructions present in the successor.
    opcodes = {r.opcode for r in successor[0]._design_program.instructions}
    assert {OP_CONSTRUCTION_BEGIN, OP_COPY_RECORD, OP_CONSTRUCTION_COMMIT} <= opcodes

    # Transactional accounting exactly once.
    assert engine.fabrication_engine._fabrication_successes == 1
    assert len(engine.fabrication_engine.get_lineage_records()) == 1
    lineage = engine.fabrication_engine.get_lineage_records()[0]
    assert lineage.successor_unit_id == successor[0].unit_id

    # Copy cursor completed across ticks.
    state = unit._construction_state
    assert state.copied_record_count == len(program.instructions)
    assert state.construction_cycle_index == 1


# --- demonstration D: broken copy programs -----------------------------------


@pytest.mark.parametrize("remove", ["copy", "commit"])
def test_broken_runtime_programs_never_complete(remove: str) -> None:
    engine = _engine(build_broken_fixture(remove))
    for _ in range(90):
        engine.tick()
    assert len(_succeeded(engine)) == 0
    assert engine.fabrication_engine._fabrication_successes == 0
    assert len(engine.fabrication_engine.get_lineage_records()) == 0
    assert len(engine.units) == 1


def build_broken_fixture(remove: str) -> DesignProgram:
    base = build_canonical_copy_capable_program()
    drop = {
        "copy": OP_COPY_RECORD,
        "commit": OP_CONSTRUCTION_COMMIT,
    }[remove]
    keep_begin = remove != "begin"
    instructions = []
    for record in base.instructions:
        if record.opcode == drop:
            continue
        instructions.append(record)
    assert keep_begin  # begin-only removal covered by no-section fixture
    return DesignProgram(instructions=instructions)


def test_missing_commit_leaves_no_lineage_edge() -> None:
    program_instructions = [
        r for r in build_canonical_copy_capable_program().instructions
        if r.opcode != OP_CONSTRUCTION_COMMIT
    ]
    program = DesignProgram(instructions=program_instructions)
    engine = _engine(program)
    for _ in range(40):
        engine.tick()
    # Copy buffer may have completed, but nothing was finalized.
    assert len(engine.fabrication_engine.get_lineage_records()) == 0
    state = engine.units[0]._construction_state
    assert state.source_cursor >= len(program.instructions)


# --- demonstration F: program length increases copy work ---------------------


def test_longer_program_costs_more_copy_work() -> None:
    short = build_canonical_copy_capable_program()
    long_program = build_long_developmental_program(extra_neutral_records=6)

    def run(program: DesignProgram) -> Any:
        engine = _engine(program)
        while engine.tick_count < 80 and not _succeeded(engine):
            engine.tick()
        return engine

    short_engine = run(short)
    long_engine = run(long_program)
    short_state = short_engine.units[0]._construction_state
    long_state = long_engine.units[0]._construction_state

    # More source records copied, more copy energy, and no shorter cycle
    # duration in one-record-per-step mode.
    assert long_state.copied_record_count > short_state.copied_record_count
    assert long_state.accumulated_copy_cost > short_state.accumulated_copy_cost

    def duration(engine: Any) -> int:
        rows = [
            row for row in engine._construction_cycle_trace
            if row["status"] == "complete"
        ]
        assert rows
        return rows[-1]["cycle_end_tick"] - rows[-1]["cycle_start_tick"]

    assert duration(long_engine) >= duration(short_engine)
    assert duration(long_engine) == duration(short_engine) + 6


# --- demonstration E: padded runtime reduces throughput ----------------------


def test_padded_runtime_takes_longer_than_compact() -> None:
    compact = build_canonical_copy_capable_program()
    padded = build_padded_runtime_program(padding=5)

    def run(program: DesignProgram, ticks: int) -> Any:
        engine = _engine(program)
        while engine.tick_count < ticks:
            engine.tick()
        return engine

    compact_engine = run(compact, 40)
    padded_engine = run(padded, 40)
    compact_cycles = compact_engine.units[0]._construction_state.construction_cycle_index
    padded_cycles = padded_engine.units[0]._construction_state.construction_cycle_index
    # Same developmental phenotype (both decode the accepted baseline), but
    # the padded program's extra runtime no-op steps reduce completed cycles.
    compact_desc = compact_engine.units[0]._architecture_descriptor
    padded_desc = padded_engine.units[0]._architecture_descriptor
    assert (compact_desc.hidden_size, round(compact_desc.recurrent_density, 9),
            compact_desc.plasticity_rate) == (
        padded_desc.hidden_size, round(padded_desc.recurrent_density, 9),
        padded_desc.plasticity_rate)
    assert compact_cycles > padded_cycles


# --- multiple construction cycles per source ---------------------------------


def test_single_source_completes_two_construction_cycles() -> None:
    engine = _engine(build_canonical_copy_capable_program())
    while engine.tick_count < 120 and len(_succeeded(engine)) < 2:
        engine.tick()
    state = engine.units[0]._construction_state
    assert state.construction_cycle_index >= 2
    assert len(_succeeded(engine)) >= 2
    assert engine.fabrication_engine._fabrication_successes >= 2
    assert len(engine.fabrication_engine.get_lineage_records()) >= 2
    # Each successful cycle created exactly one real registered unit.
    successors = [u for u in engine.units if u.unit_id != "unit-a"]
    assert len(successors) == len(engine.fabrication_engine.get_lineage_records())


# --- copy-error channel -------------------------------------------------------


def test_copy_error_channel_deterministic_and_mechanism_capable() -> None:
    import random

    from machine_sim.agents.design_program import M23_ALL_OPCODES

    records = [[OP_SET_HIDDEN, 16.0], [OP_END, 0.0]]
    bounds = ConstructionExecutionBounds(copy_error_probability=1.0)

    out_a = list(records)
    err_a = _apply_copy_error(out_a, random.Random(5), bounds)
    out_a2 = list(records)
    err_a2 = _apply_copy_error(out_a2, random.Random(5), bounds)
    assert err_a == err_a2
    assert out_a == out_a2

    out_other = list(records)
    seen = set()
    for seed in range(20):
        candidate = list(records)
        error = _apply_copy_error(candidate, random.Random(seed), bounds)
        seen.add(error["error_type"])
        assert all(isinstance(pair[0], int) for pair in candidate)
        assert all(pair[0] in M23_ALL_OPCODES for pair in candidate)
    # All four mechanisms are reachable through the channel.
    assert {"opcode_substitution", "operand_perturbation",
            "record_insertion", "record_deletion"} <= seen


def test_copy_errors_occur_during_record_copy_not_post_variation() -> None:
    program = build_canonical_copy_capable_program()
    engine = _engine(program, copy_error_probability=0.6)
    while engine.tick_count < 80 and not _succeeded(engine):
        engine.tick()
    state = engine.units[0]._construction_state
    # Errors were counted during copying (per-record channel), and the M22
    # whole-program variation path stayed bypassed (zero variation ops used).
    assert state.copy_error_count > 0
    assert not hasattr(engine, "_design_program_transfer_trace") or (
        engine._design_program_transfer_trace == []
    )
    # The copied successor program differs from the source under errors.
    successors = [u for u in engine.units if u.unit_id != "unit-a"]
    if successors:
        assert (
            successors[0]._design_program.program_digest()
            != program.program_digest()
        ) or state.copy_error_count == 0


def test_copy_error_can_change_runtime_construction_opcode() -> None:
    """Substitution capability onto/from runtime construction opcodes."""
    import random

    from machine_sim.agents.design_program import M23_ALL_OPCODES

    records = [[OP_COPY_RECORD, 0.0]]
    runtime_hits = 0
    for seed in range(200):
        candidate = [list(records[0])]
        error = _apply_copy_error(
            candidate, random.Random(seed), ConstructionExecutionBounds()
        )
        new_opcode = None
        if error["error_type"] == "opcode_substitution":
            new_opcode = candidate[0][0]
        elif error["error_type"] == "record_insertion":
            new_opcode = error.get("opcode_inserted")
        if new_opcode in (91, 92, 93):
            runtime_hits += 1
    assert runtime_hits > 0  # runtime opcodes can be created by copy errors


# --- reservations and concurrency --------------------------------------------


def test_reservation_exclusivity_under_contention() -> None:
    from machine_sim.agents.unit import MachineUnitImpl

    config = _config(unit_count=0, unit_capacity=8)
    engine = build_engine(config)
    engine.units.clear()
    for index, position in enumerate([(4, 4), (4, 5)]):
        unit = MachineUnitImpl(
            unit_id=f"unit-{index}",
            position=position,
            neural_controller_enabled=False,
            design_program=build_canonical_copy_capable_program(),
            unit_executed_construction_enabled=True,
        )
        unit.power_reserve = 10000.0
        unit.max_power = 10000.0
        engine.register_unit(unit)
    engine.initialize()
    for position in ((4, 4), (4, 5)):
        engine.world.grid[position].resources["component_scrap"] = Resource(
            resource_type=ResourceType.COMPONENT_SCRAP, quantity=500.0
        )

    for _ in range(40):
        engine.tick()

    # No overlapping reservations; every committed successor sits on a
    # distinct cell; lineage edges match real units.
    reserved = list(engine.world.reserved_cells.items())
    positions = [pos for pos, _owner in reserved]
    assert len(positions) == len(set(positions))
    for pos, _owner in reserved:
        assert engine.world.grid[pos].unit_id is None  # reservations ≠ occupancy

    successors = [u for u in engine.units if u.unit_id != "unit-0" and u.unit_id != "unit-1"]
    successor_positions = sorted(u.position for u in successors)
    assert len(successor_positions) == len(set(successor_positions))
    lineage_ids = [r.successor_unit_id for r in engine.fabrication_engine.get_lineage_records()]
    assert len(lineage_ids) == len(set(lineage_ids))
    unit_ids = {u.unit_id for u in engine.units}
    assert set(lineage_ids) <= unit_ids


# --- source inactivity policy -------------------------------------------------


def test_source_inactive_midcycle_releases_and_records_once() -> None:
    engine = _engine(build_canonical_copy_capable_program())
    unit = engine.units[0]
    # Advance into an active copy cycle.
    while engine.tick_count < 30 and unit._construction_state.construction_phase != "copying":
        engine.tick()
    assert unit._construction_state.construction_phase == "copying"
    assert engine.world.reserved_cells

    unit.is_active = False
    engine.tick()
    state = unit._construction_state
    assert state.construction_phase == "idle"
    assert state.last_construction_fault == "source_inactive"
    assert not engine.world.reserved_cells
    failed = _failed(engine, "source_inactive")
    assert len(failed) == 1
    # Costs remain consumed; no success/lineage appeared.
    assert engine.fabrication_engine._fabrication_successes == 0


def _failed(engine: Any, cause: str):
    return [
        e for e in engine.event_log.all_events()
        if e.event_type.name == "CONSTRUCTION_FAILED" and e.data.get("cause") == cause
    ]


# --- mid-copy checkpoint roundtrip --------------------------------------------


def _twin_pair(program: DesignProgram):
    engine_a = _engine(program)
    engine_b = _engine(program)
    return engine_a, engine_b


def test_midcopy_checkpoint_roundtrip_preserves_future_trajectory() -> None:
    program = build_long_developmental_program(extra_neutral_records=3)
    engine_uninterrupted, engine_paused = _twin_pair(program)

    # Drive paused twin into a strictly mid-copy condition.
    resume_at = None
    while engine_paused.tick_count < 60:
        state = engine_paused.units[0]._construction_state
        if (
            state.construction_phase == "copying"
            and 0 < state.source_cursor < len(program.instructions)
        ):
            resume_at = engine_paused.tick_count
            break
        engine_uninterrupted.tick()
        engine_paused.tick()
    assert resume_at is not None, "never reached mid-copy"

    restored = decode_state(encode_state(engine_paused))
    assert deep_state_digest(restored) == deep_state_digest(engine_paused)

    # Continue both to completion.
    while not _succeeded(engine_uninterrupted) and engine_uninterrupted.tick_count < 120:
        engine_uninterrupted.tick()
    while not _succeeded(restored) and restored.tick_count < 120:
        restored.tick()

    assert deep_state_digest(restored) == deep_state_digest(engine_uninterrupted)
    restored_state = restored.units[0]._construction_state
    uninterrupted_state = engine_uninterrupted.units[0]._construction_state
    assert restored_state.source_cursor == uninterrupted_state.source_cursor
    assert restored_state.copied_record_count == uninterrupted_state.copied_record_count
    restored_lineage = restored.fabrication_engine.get_lineage_records()
    direct_lineage = engine_uninterrupted.fabrication_engine.get_lineage_records()
    assert [r.successor_unit_id for r in restored_lineage] == [
        r.successor_unit_id for r in direct_lineage
    ]


# --- deep digest sensitivity ---------------------------------------------------


def test_deep_digest_sensitive_to_runtime_construction_state() -> None:
    program = build_long_developmental_program(extra_neutral_records=3)
    engine = _engine(program)
    unit = engine.units[0]
    while engine.tick_count < 60 and not (
        unit._construction_state.construction_phase == "copying"
        and len(unit._construction_state.target_copy_buffer) >= 2
        and 0 < unit._construction_state.source_cursor < len(program.instructions)
    ):
        engine.tick()
    state = unit._construction_state
    assert state.construction_phase == "copying"
    assert state.target_copy_buffer

    baseline = deep_state_digest(engine)

    saved_pc = state.runtime_program_counter
    state.runtime_program_counter += 1
    pc_sensitive = deep_state_digest(engine) != baseline
    state.runtime_program_counter = saved_pc

    saved_cursor = state.source_cursor
    state.source_cursor += 1
    cursor_sensitive = deep_state_digest(engine) != baseline
    state.source_cursor = saved_cursor

    saved_buffer = [list(pair) for pair in state.target_copy_buffer]
    state.target_copy_buffer[0][0] = OP_NO_OP
    buffer_sensitive = deep_state_digest(engine) != baseline
    state.target_copy_buffer = saved_buffer

    saved_position = state.reserved_target_position
    state.reserved_target_position = (saved_position[0] + 1, saved_position[1])
    reservation_sensitive = deep_state_digest(engine) != baseline
    state.reserved_target_position = saved_position

    saved_rng = state.copy_rng.getstate()
    state.copy_rng.random()
    rng_sensitive = deep_state_digest(engine) != baseline
    state.copy_rng.setstate(saved_rng)

    saved_cycle = state.construction_cycle_index
    state.construction_cycle_index += 1
    cycle_sensitive = deep_state_digest(engine) != baseline
    state.construction_cycle_index = saved_cycle

    assert pc_sensitive and cursor_sensitive and buffer_sensitive
    assert reservation_sensitive and rng_sensitive and cycle_sensitive

    engine._construction_runtime_trace.append({"tick": 999999})
    assert deep_state_digest(engine) == baseline


# --- runtime section helpers ---------------------------------------------------


def test_runtime_section_bounds() -> None:
    dev_only = canonical_baseline_program()
    assert runtime_section_bounds(dev_only) is None
    capable = build_canonical_copy_capable_program()
    assert runtime_section_bounds(capable) == len(dev_only.instructions)


def test_two_generation_closure_a_to_b_to_c_zero_errors() -> None:
    program = build_canonical_copy_capable_program()
    config = _config(unit_capacity=16, max_ticks=400)
    engine = build_engine(config)
    engine.units.clear()

    from machine_sim.agents.unit import MachineUnitImpl

    root = MachineUnitImpl(
        unit_id="unit-A",
        position=(4, 4),
        neural_controller_enabled=False,
        design_program=program,
        unit_executed_construction_enabled=True,
    )
    root.power_reserve = 100000.0
    root.max_power = 100000.0
    engine.register_unit(root)
    engine.initialize()
    # Resource-rich world: every cell carries material so any successor can
    # pay construction costs regardless of where placement lands it.
    for cell in engine.world.grid.values():
        cell.resources["component_scrap"] = Resource(
            resource_type=ResourceType.COMPONENT_SCRAP, quantity=500.0
        )

    while engine.tick_count < 300 and len([
        u for u in engine.units if u.unit_id.startswith("unit-")
    ]) < 3:
        engine.tick()

    units_by_gen: Dict[int, List[Any]] = {}
    for unit in engine.units:
        units_by_gen.setdefault(unit._generation_index, []).append(unit)

    assert 0 in units_by_gen and 1 in units_by_gen and 2 in units_by_gen
    gen_digests = {
        generation: {u._design_program.program_digest() for u in units}
        for generation, units in units_by_gen.items()
    }
    # Zero-error closure: A, B, C carry identical programs.
    assert gen_digests[0] == gen_digests[1] == gen_digests[2]

    lineage = engine.fabrication_engine.get_lineage_records()
    assert len(lineage) >= 2
    ids = {u.unit_id for u in engine.units}
    for record in lineage:
        assert record.successor_unit_id in ids
        assert record.successor_generation == record.source_generation + 1

