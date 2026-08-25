"""M23 unit-executed runtime construction executor.

Phase separation over one inherited ``DesignProgram``:

* instructions from index 0 through the first developmental ``END`` are the
  M22 developmental section — decoded by the unchanged
  ``DesignProgramInterpreter`` into a ``NeuralArchitectureDescriptor``;
* instructions after that first ``END`` are the runtime construction section,
  executed by :func:`execute_runtime_step` below.

Runtime opcodes (previously reserved values):

* ``CONSTRUCTION_BEGIN`` requests a deterministic construction reservation
  through engine-provided services (physical ability to pay, local material,
  free adjacent placement, capacity). On success it consumes the base
  power/material cost exactly once, initializes cursor/buffer/RNG, and starts
  a construction cycle. No success or lineage state is touched.
* ``COPY_RECORD`` copies at most ``copy_records_per_step`` source records into
  the target buffer through the bounded copy-error channel, keeping the
  program counter on itself while source records remain.
* ``CONSTRUCTION_COMMIT`` asks the engine to assemble and transactionally
  finalize the copied program. Success requires an active reservation, a
  complete copy within length/schema bounds, and a usable developmental
  architecture from the copied program.

The whole source DesignProgram is copied — developmental section, its END
marker, and the runtime construction section itself — so construction
capability is heritable.

The engine services interface (implemented by ``SimEngine``):

* ``begin_unit_construction(unit, state) -> bool``
* ``commit_unit_construction(unit, state) -> bool``
* ``charge_unit_construction_cost(unit, amount, kind) -> None``

All costs are simulation-semantic amounts charged to the unit's power reserve
and retained on failure, exactly like the M22A fabrication model.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from machine_sim.agents.design_program import (
    OP_CONSTRUCTION_BEGIN,
    OP_CONSTRUCTION_COMMIT,
    OP_COPY_RECORD,
    RUNTIME_OPCODE_NAMES,
    stable_seed,
)

PHASE_IDLE = "idle"
PHASE_COPYING = "copying"
PHASE_READY = "ready"

FAULT_BEGIN_FAILED = "begin_reservation_failed"
FAULT_COPY_WITHOUT_CYCLE = "copy_without_active_cycle"
FAULT_COMMIT_WITHOUT_CYCLE = "commit_without_active_cycle"
FAULT_COMMIT_INCOMPLETE_COPY = "commit_incomplete_copy"


@dataclass(slots=True)
class ConstructionExecutionBounds:
    """Bounded stepping and copy-error configuration for one unit."""

    copy_records_per_step: int = 1
    copy_error_probability: float = 0.0
    minimum_program_length: int = 1
    maximum_program_length: int = 128


@dataclass(slots=True)
class ConstructionRuntimeState:
    """Future-causal per-unit runtime construction state.

    Every field here can affect future execution and therefore enters the M21
    deep semantic snapshot and checkpoint payloads.
    """

    construction_enabled: bool = False
    runtime_section_start: int = -1
    runtime_program_counter: int = -1
    construction_phase: str = PHASE_IDLE
    construction_cycle_index: int = 0
    source_program_digest_at_begin: str = ""
    source_cursor: int = 0
    target_copy_buffer: List[List[Any]] = field(default_factory=list)
    reserved_target_position: Optional[Tuple[int, int]] = None
    provisional_successor_id: Optional[str] = None
    copy_rng: Optional[random.Random] = None
    cycle_start_tick: int = -1
    executed_runtime_instruction_count: int = 0
    copied_record_count: int = 0
    copy_error_count: int = 0
    accumulated_copy_cost: float = 0.0
    last_construction_fault: Optional[str] = None


def runtime_section_bounds(program) -> Optional[int]:
    """Return the index of the first instruction after the first
    developmental END, or None when the program has no runtime section."""
    for index, record in enumerate(program.instructions):
        if record.opcode == 10:  # developmental END
            if index + 1 < len(program.instructions):
                return index + 1
            return None
    return None


def init_construction_state(
    program,
    enabled: bool,
    seed_parts: Tuple[int, str],
) -> ConstructionRuntimeState:
    """Build initial future-causal runtime state for one program-backed unit."""
    if program is None or not enabled:
        return ConstructionRuntimeState(
            construction_enabled=False, runtime_section_start=-1, runtime_program_counter=-1
        )
    start = runtime_section_bounds(program)
    state = ConstructionRuntimeState(
        construction_enabled=start is not None,
        runtime_section_start=start if start is not None else -1,
        runtime_program_counter=start if start is not None else -1,
    )
    if state.construction_enabled and program.instructions:
        state.copy_rng = random.Random(
            stable_seed("construction_copy", seed_parts[0], seed_parts[1])
        )
    return state


def _copy_error_universe() -> Tuple[int, ...]:
    from machine_sim.agents.design_program import M23_ALL_OPCODES

    return M23_ALL_OPCODES


def _apply_copy_error(
    emitted: List[List[Any]],
    rng: random.Random,
    bounds: ConstructionExecutionBounds,
) -> Dict[str, Any]:
    """Apply one bounded copy-error mechanism to freshly emitted records.

    Mechanisms mirror the M22 variation series but act per copied record:
    opcode substitution, operand perturbation, record insertion, record
    deletion. Length/schema bounds are enforced by the caller's buffer checks
    at commit time; deletion never empties beyond the emitted window here.
    """
    opcode_universe = _copy_error_universe()
    mechanism = rng.randrange(4)
    if mechanism == 0 and emitted:
        target_index = rng.randrange(len(emitted))
        old_opcode = emitted[target_index][0]
        new_opcode = opcode_universe[rng.randrange(len(opcode_universe))]
        emitted[target_index][0] = new_opcode
        return {
            "error_type": "opcode_substitution",
            "index": target_index,
            "opcode_from": old_opcode,
            "opcode_to": new_opcode,
        }
    if mechanism == 1 and emitted:
        target_index = rng.randrange(len(emitted))
        delta = rng.choice([-2.0, -1.0, 1.0, 2.0])
        old_operand = emitted[target_index][1]
        emitted[target_index][1] = float(old_operand) + delta
        return {
            "error_type": "operand_perturbation",
            "index": target_index,
            "operand_from": old_operand,
            "operand_to": emitted[target_index][1],
        }
    if mechanism == 2:
        new_record = [
            opcode_universe[rng.randrange(len(opcode_universe))],
            float(rng.randint(1, 24)),
        ]
        emitted.append(new_record)
        return {
            "error_type": "record_insertion",
            "index": len(emitted) - 1,
            "opcode_inserted": new_record[0],
        }
    # Mechanism 3: deletion (only meaningful when something was emitted).
    if emitted:
        target_index = rng.randrange(len(emitted))
        removed_opcode = emitted[target_index][0]
        emitted.pop(target_index)
        return {
            "error_type": "record_deletion",
            "index": target_index,
            "opcode_removed": removed_opcode,
        }
    return {"error_type": "deletion_skipped_empty"}


def execute_runtime_step(
    program,
    state: ConstructionRuntimeState,
    services: Any,
    bounds: ConstructionExecutionBounds,
    current_tick: int,
) -> Dict[str, Any]:
    """Execute at most one runtime construction instruction for this tick.

    Returns a trace row describing the bounded work performed. The program
    counter wraps to the runtime-section start after the physical end of the
    sequence, enabling repeated construction cycles without engine scheduling.
    """
    trace: Dict[str, Any] = {
        "phase": state.construction_phase,
        "runtime_pc": state.runtime_program_counter,
        "runtime_opcode": None,
        "source_cursor": state.source_cursor,
        "target_buffer_length": len(state.target_copy_buffer),
        "copy_operation": None,
        "copy_error_type": None,
        "fault": None,
    }
    if not state.construction_enabled or state.runtime_section_start < 0:
        trace["fault"] = "construction_disabled"
        return trace

    instructions = program.instructions
    if not instructions:
        trace["fault"] = "empty_program"
        return trace

    if state.runtime_program_counter < state.runtime_section_start or (
        state.runtime_program_counter >= len(instructions)
    ):
        state.runtime_program_counter = state.runtime_section_start

    record = instructions[state.runtime_program_counter]
    trace["runtime_opcode"] = RUNTIME_OPCODE_NAMES.get(record.opcode, f"op_{record.opcode}")
    state.executed_runtime_instruction_count += 1
    # A successful step clears the previous fault; faults are per-step facts.
    state.last_construction_fault = None
    services.charge_runtime_instruction()

    if record.opcode == OP_CONSTRUCTION_BEGIN:
        if state.construction_phase != PHASE_IDLE:
            state.last_construction_fault = "begin_while_cycle_active"
            trace["fault"] = state.last_construction_fault
            state.runtime_program_counter += 1
        elif services.begin_unit_construction(current_tick):
            trace["copy_operation"] = "construction_begin"
            trace["reserved_position"] = list(state.reserved_target_position or ())
            state.runtime_program_counter += 1
        else:
            state.last_construction_fault = FAULT_BEGIN_FAILED
            trace["fault"] = FAULT_BEGIN_FAILED
            state.runtime_program_counter += 1

    elif record.opcode == OP_COPY_RECORD:
        if state.construction_phase == PHASE_IDLE:
            state.last_construction_fault = FAULT_COPY_WITHOUT_CYCLE
            trace["fault"] = FAULT_COPY_WITHOUT_CYCLE
            state.runtime_program_counter += 1
        else:
            copied_this_step = 0
            while (
                state.source_cursor < len(instructions)
                and copied_this_step < bounds.copy_records_per_step
            ):
                source_record = instructions[state.source_cursor]
                emitted: List[List[Any]] = [source_record.to_pair()]
                if (
                    bounds.copy_error_probability > 0.0
                    and state.copy_rng is not None
                    and state.copy_rng.random() < bounds.copy_error_probability
                ):
                    error = _apply_copy_error(emitted, state.copy_rng, bounds)
                    state.copy_error_count += 1
                    trace["copy_error_type"] = error["error_type"]
                state.target_copy_buffer.extend([list(item) for item in emitted])
                state.source_cursor += 1
                state.copied_record_count += 1
                copied_this_step += 1
                services.charge_copy_record()
            trace["copied_records"] = copied_this_step
            trace["copy_operation"] = "copy_record"
            if state.source_cursor >= len(instructions):
                state.construction_phase = PHASE_READY
                state.runtime_program_counter += 1
            # else: keep the program counter on this COPY_RECORD instruction.

    elif record.opcode == OP_CONSTRUCTION_COMMIT:
        if state.construction_phase == PHASE_IDLE:
            state.last_construction_fault = FAULT_COMMIT_WITHOUT_CYCLE
            trace["fault"] = FAULT_COMMIT_WITHOUT_CYCLE
            state.runtime_program_counter += 1
        elif state.construction_phase != PHASE_READY or (
            state.source_cursor < len(instructions)
        ):
            # M22A: incomplete COMMIT releases reservations through the
            # universal cancel service (releases cell + clears fields).
            if hasattr(services, "cancel_unit_construction"):
                services.cancel_unit_construction(FAULT_COMMIT_INCOMPLETE_COPY)
            else:
                state.last_construction_fault = FAULT_COMMIT_INCOMPLETE_COPY
                state.construction_phase = PHASE_IDLE
                state.target_copy_buffer = []
                state.source_cursor = 0
                state.reserved_target_position = None
                state.provisional_successor_id = None
            trace["fault"] = FAULT_COMMIT_INCOMPLETE_COPY
            state.runtime_program_counter += 1
        else:
            outcome = services.commit_unit_construction()
            trace["copy_operation"] = "construction_commit"
            trace["commit_status"] = outcome.get("status", "unknown")
            trace["successor_unit_id"] = outcome.get("successor_unit_id")
            trace["successor_program_digest"] = outcome.get("successor_program_digest")
            state.last_construction_fault = outcome.get("fault")
            # Cycle closed either way: return to idle and wrap to the runtime
            # section start for a future construction cycle.
            state.construction_phase = PHASE_IDLE
            state.target_copy_buffer = []
            state.source_cursor = 0
            state.reserved_target_position = None
            state.provisional_successor_id = None
            state.runtime_program_counter = state.runtime_section_start

    else:
        # Developmental opcodes inside the runtime section are runtime no-ops
        # that still consume a step and their instruction cost.
        pass

    if state.runtime_program_counter >= len(instructions):
        state.runtime_program_counter = state.runtime_section_start

    trace["runtime_pc_after"] = state.runtime_program_counter
    trace["phase_after"] = state.construction_phase
    return trace


def build_canonical_copy_capable_program(plasticity_rate: float = 0.01):
    """Developmental baseline prefix + runtime copy section."""
    from machine_sim.agents.design_program import (
        InstructionRecord,
        canonical_baseline_program,
        OP_CONSTRUCTION_BEGIN,
        OP_CONSTRUCTION_COMMIT,
        OP_COPY_RECORD,
    )

    base = canonical_baseline_program(plasticity_rate=plasticity_rate)
    return type(base)(
        instructions=base.instructions
        + [
            InstructionRecord(opcode=OP_CONSTRUCTION_BEGIN, operand=0.0),
            InstructionRecord(opcode=OP_COPY_RECORD, operand=0.0),
            InstructionRecord(opcode=OP_CONSTRUCTION_COMMIT, operand=0.0),
        ]
    )


def build_broken_program(remove: str, plasticity_rate: float = 0.01):
    """Same developmental phenotype with one runtime opcode removed."""
    from machine_sim.agents.design_program import (
        OP_CONSTRUCTION_BEGIN,
        OP_CONSTRUCTION_COMMIT,
        OP_COPY_RECORD,
    )

    targets = {"begin": OP_CONSTRUCTION_BEGIN, "copy": OP_COPY_RECORD, "commit": OP_CONSTRUCTION_COMMIT}
    opcode = targets[remove]
    program = build_canonical_copy_capable_program(plasticity_rate)
    return type(program)(
        instructions=[
            record
            for record in program.instructions
            if record.opcode != opcode or record.opcode == 10
        ]
    )


def build_padded_runtime_program(padding: int, plasticity_rate: float = 0.01):
    """Compact copy-capable program with extra runtime NO_OP steps inserted
    between BEGIN and COPY_RECORD (same phenotype, longer cycle)."""
    from machine_sim.agents.design_program import InstructionRecord, OP_NO_OP

    program = build_canonical_copy_capable_program(plasticity_rate)
    instructions = list(program.instructions)
    insert_at = next(
        i + 1 for i, record in enumerate(instructions) if record.opcode == OP_CONSTRUCTION_BEGIN
    )
    padded = (
        instructions[:insert_at]
        + [InstructionRecord(opcode=OP_NO_OP, operand=0.0) for _ in range(padding)]
        + instructions[insert_at:]
    )
    return type(program)(instructions=padded)


def build_long_developmental_program(extra_neutral_records: int, plasticity_rate: float = 0.01):
    """Longer source program with the same developmental phenotype and the
    same runtime copy machinery: neutral NO_OP records are inserted directly
    before the developmental END, so decoding is unchanged while the copy
    burden grows by ``extra_neutral_records``."""
    from machine_sim.agents.design_program import InstructionRecord, OP_NO_OP

    program = build_canonical_copy_capable_program(plasticity_rate)
    end_index = next(
        i for i, record in enumerate(program.instructions) if record.opcode == 10
    )
    filler = [
        InstructionRecord(opcode=OP_NO_OP, operand=0.0) for _ in range(extra_neutral_records)
    ]
    return type(program)(
        instructions=(
            program.instructions[:end_index]
            + filler
            + program.instructions[end_index:]
        )
    )


__all__ = [
    "ConstructionExecutionBounds",
    "ConstructionRuntimeState",
    "FAULT_BEGIN_FAILED",
    "FAULT_COMMIT_INCOMPLETE_COPY",
    "FAULT_COMMIT_WITHOUT_CYCLE",
    "FAULT_COPY_WITHOUT_CYCLE",
    "PHASE_COPYING",
    "PHASE_IDLE",
    "PHASE_READY",
    "build_broken_program",
    "build_canonical_copy_capable_program",
    "build_long_developmental_program",
    "build_padded_runtime_program",
    "execute_runtime_step",
    "init_construction_state",
    "runtime_section_bounds",
]
