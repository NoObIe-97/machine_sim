"""Executable per-unit design-program substrate (M22).

A design program is a bounded sequence of explicit instruction records that a
deterministic interpreter executes to produce a neural architecture
descriptor. The program is heritable machine-native data: no Python callables,
source text, eval strings, or dynamic imports are representable in it.

Execution model (M22):

* strictly sequential, straight-line execution with an explicit program
  counter and a hard execution budget;
* no recursion, no jumps, no file/network/process access, no arbitrary code;
* construction starts from documented defaults and every instruction mutates
  that construction state through bounded clamps;
* unknown opcodes are deterministic no-ops with a fault record;
* non-finite operands halt execution with status ``invalid_operand``;
* an empty or structurally invalid program yields ``invalid_program``.

The interpreter output feeds the existing M19 neural-architecture pipeline, so
program-decoded descriptors flow through the unchanged dimension-changing
successor construction path.

Cost model (simulation semantics, not host CPU time):

    program_execution_cost = program_base_cost
                           + program_per_instruction_cost * executed_instruction_count

This cost is charged to the constructing unit during successor construction in
program-enabled mode, alongside the existing neural architecture fabrication
cost. No reward or penalty is attached to program length or content quality.

Self-copy semantics (copy pointers, allocate/copy/divide operations,
unit-executed successor construction) are intentionally absent; they belong to
a later milestone.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from machine_sim.agents.neural_architecture import (
    NeuralArchitectureConfig,
    NeuralArchitectureDescriptor,
    stable_seed,
)

DESIGN_PROGRAM_SCHEMA_VERSION = "1.0.0"
DESIGN_INSTRUCTION_SET_VERSION = 1


class DesignProgramError(Exception):
    """Raised for structurally invalid program documents."""


# Instruction set -------------------------------------------------------------
#
# Operands are bounded at execution time against the architecture bounds.
# Unknown integer opcodes are deterministic no-ops that record a fault.

OP_SET_HIDDEN = 1
OP_ADJUST_HIDDEN = 2
OP_SET_RECURRENCE_DENSITY = 3
OP_ADJUST_RECURRENCE_DENSITY = 4
OP_SET_PLASTICITY_RATE = 5
OP_ADJUST_PLASTICITY_RATE = 6
OP_ENABLE_PLASTICITY = 7
OP_DISABLE_PLASTICITY = 8
OP_NO_OP = 9
OP_END = 10

OPCODE_NAMES: Dict[int, str] = {
    OP_SET_HIDDEN: "SET_HIDDEN",
    OP_ADJUST_HIDDEN: "ADJUST_HIDDEN",
    OP_SET_RECURRENCE_DENSITY: "SET_RECURRENCE_DENSITY",
    OP_ADJUST_RECURRENCE_DENSITY: "ADJUST_RECURRENCE_DENSITY",
    OP_SET_PLASTICITY_RATE: "SET_PLASTICITY_RATE",
    OP_ADJUST_PLASTICITY_RATE: "ADJUST_PLASTICITY_RATE",
    OP_ENABLE_PLASTICITY: "ENABLE_PLASTICITY",
    OP_DISABLE_PLASTICITY: "DISABLE_PLASTICITY",
    OP_NO_OP: "NO_OP",
    OP_END: "END",
}

ALL_OPCODES: Tuple[int, ...] = tuple(OPCODE_NAMES.keys())

# Opcodes whose operand is an integer-valued hidden-size quantity.
_INTEGER_OPERAND_OPCODES = frozenset({OP_SET_HIDDEN, OP_ADJUST_HIDDEN})
# Opcodes whose operand is ignored.
_OPERAND_FREE_OPCODES = frozenset({OP_ENABLE_PLASTICITY, OP_DISABLE_PLASTICITY, OP_NO_OP, OP_END})

# Opcodes reserved for a later unit-executed construction milestone. They are
# deliberately absent from the dispatch table; their presence in a program is
# handled by the unknown-opcode no-op policy.
RESERVED_FUTURE_OPCODES: Tuple[int, ...] = (91, 92, 93)


@dataclass(slots=True)
class InstructionRecord:
    """One bounded instruction: an integer opcode plus a finite operand."""

    opcode: int
    operand: float = 0.0

    def to_pair(self) -> List[Any]:
        return [int(self.opcode), float(self.operand)]

    @classmethod
    def from_pair(cls, pair: Sequence[Any]) -> "InstructionRecord":
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise DesignProgramError(f"invalid instruction record: {pair!r}")
        opcode, operand = pair
        if not isinstance(opcode, int) or isinstance(opcode, bool):
            raise DesignProgramError(f"opcode must be an integer: {opcode!r}")
        if isinstance(operand, bool) or not isinstance(operand, (int, float)):
            raise DesignProgramError(f"operand must be numeric: {operand!r}")
        return cls(opcode=int(opcode), operand=float(operand))


@dataclass(slots=True)
class DesignProgram:
    """Immutable-by-convention bounded instruction sequence."""

    schema_version: str = DESIGN_PROGRAM_SCHEMA_VERSION
    instruction_set_version: int = DESIGN_INSTRUCTION_SET_VERSION
    instructions: List[InstructionRecord] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.instructions = list(self.instructions)

    @property
    def length(self) -> int:
        return len(self.instructions)

    def canonical_payload(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "instruction_set_version": int(self.instruction_set_version),
            "instructions": [record.to_pair() for record in self.instructions],
        }

    def program_digest(self) -> str:
        payload = json.dumps(
            self.canonical_payload(), sort_keys=True, separators=(",", ":")
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        document = self.canonical_payload()
        document["program_digest"] = self.program_digest()
        return document

    @classmethod
    def from_dict(cls, document: Dict[str, Any]) -> "DesignProgram":
        if not isinstance(document, dict):
            raise DesignProgramError("program document must be a mapping")
        if document.get("schema_version") != DESIGN_PROGRAM_SCHEMA_VERSION:
            raise DesignProgramError(
                f"unsupported program schema version: {document.get('schema_version')!r}"
            )
        if document.get("instruction_set_version") != DESIGN_INSTRUCTION_SET_VERSION:
            raise DesignProgramError(
                "unsupported instruction set version: "
                f"{document.get('instruction_set_version')!r}"
            )
        raw_instructions = document.get("instructions")
        if not isinstance(raw_instructions, list):
            raise DesignProgramError("instructions must be a list")
        instructions = [InstructionRecord.from_pair(pair) for pair in raw_instructions]
        program = cls(
            schema_version=document["schema_version"],
            instruction_set_version=int(document["instruction_set_version"]),
            instructions=instructions,
        )
        recorded_digest = document.get("program_digest")
        if recorded_digest is not None and recorded_digest != program.program_digest():
            raise DesignProgramError("program digest mismatch")
        return program

    def copy(self) -> "DesignProgram":
        return DesignProgram(
            schema_version=self.schema_version,
            instruction_set_version=self.instruction_set_version,
            instructions=[
                InstructionRecord(opcode=record.opcode, operand=record.operand)
                for record in self.instructions
            ],
        )


# Execution bounds ------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DesignExecutionBounds:
    """Architecture, budget, length, and cost bounds for interpretation."""

    minimum_hidden_size: int = 8
    maximum_hidden_size: int = 64
    initial_hidden_size: int = 16
    minimum_recurrence_density: float = 0.15
    maximum_recurrence_density: float = 1.0
    initial_recurrence_density: float = 1.0
    minimum_plasticity_rate: float = 0.0
    maximum_plasticity_rate: float = 0.05
    initial_plasticity_rate: float = 0.01
    initial_plasticity_enabled: bool = True
    execution_budget: int = 512
    program_base_cost: float = 0.5
    program_per_instruction_cost: float = 0.01

    @classmethod
    def from_architecture_config(
        cls,
        config: NeuralArchitectureConfig,
        execution_budget: int = 512,
        program_base_cost: float = 0.5,
        program_per_instruction_cost: float = 0.01,
    ) -> "DesignExecutionBounds":
        return cls(
            minimum_hidden_size=config.minimum_hidden_size,
            maximum_hidden_size=config.maximum_hidden_size,
            initial_hidden_size=config.initial_hidden_size,
            minimum_recurrence_density=config.minimum_recurrent_density,
            maximum_recurrence_density=config.maximum_recurrent_density,
            initial_recurrence_density=config.initial_recurrent_density,
            minimum_plasticity_rate=config.minimum_plasticity_rate,
            maximum_plasticity_rate=config.maximum_plasticity_rate,
            initial_plasticity_rate=config.initial_plasticity_rate,
            initial_plasticity_enabled=True,
            execution_budget=execution_budget,
            program_base_cost=program_base_cost,
            program_per_instruction_cost=program_per_instruction_cost,
        )


# Interpreter -----------------------------------------------------------------

STATUS_COMPLETE = "complete"
STATUS_BUDGET_EXHAUSTED = "budget_exhausted"
STATUS_INVALID_OPERAND = "invalid_operand"
STATUS_INVALID_PROGRAM = "invalid_program"


@dataclass(slots=True)
class ProgramExecutionResult:
    """Structured outcome of one bounded interpretation."""

    status: str
    executed_instruction_count: int
    final_program_counter: int
    construction_state: Dict[str, Any]
    decoded_architecture: Optional[NeuralArchitectureDescriptor]
    execution_cost: float
    fault_records: List[Dict[str, Any]] = field(default_factory=list)


class DesignProgramInterpreter:
    """Deterministic bounded interpreter over design programs."""

    def __init__(self, bounds: DesignExecutionBounds) -> None:
        self.bounds = bounds

    def _initial_state(self) -> Dict[str, Any]:
        bounds = self.bounds
        return {
            "hidden_size": int(bounds.initial_hidden_size),
            "recurrence_density": float(bounds.initial_recurrence_density),
            "plasticity_rate": float(bounds.initial_plasticity_rate),
            "plasticity_enabled": bool(bounds.initial_plasticity_enabled),
        }

    def execute(
        self,
        program: DesignProgram,
        program_length_bounds: Optional[Tuple[int, int]] = None,
    ) -> ProgramExecutionResult:
        bounds = self.bounds
        faults: List[Dict[str, Any]] = []

        if program.schema_version != DESIGN_PROGRAM_SCHEMA_VERSION:
            return ProgramExecutionResult(
                status=STATUS_INVALID_PROGRAM,
                executed_instruction_count=0,
                final_program_counter=0,
                construction_state=self._initial_state(),
                decoded_architecture=None,
                execution_cost=bounds.program_base_cost,
                fault_records=[{"kind": "unsupported_schema_version"}],
            )
        if program.instruction_set_version != DESIGN_INSTRUCTION_SET_VERSION:
            return ProgramExecutionResult(
                status=STATUS_INVALID_PROGRAM,
                executed_instruction_count=0,
                final_program_counter=0,
                construction_state=self._initial_state(),
                decoded_architecture=None,
                execution_cost=bounds.program_base_cost,
                fault_records=[{"kind": "unsupported_instruction_set_version"}],
            )
        if not program.instructions:
            return ProgramExecutionResult(
                status=STATUS_INVALID_PROGRAM,
                executed_instruction_count=0,
                final_program_counter=0,
                construction_state=self._initial_state(),
                decoded_architecture=None,
                execution_cost=bounds.program_base_cost,
                fault_records=[{"kind": "empty_program"}],
            )
        if program_length_bounds is not None:
            minimum_length, maximum_length = program_length_bounds
            if program.length < minimum_length or program.length > maximum_length:
                return ProgramExecutionResult(
                    status=STATUS_INVALID_PROGRAM,
                    executed_instruction_count=0,
                    final_program_counter=0,
                    construction_state=self._initial_state(),
                    decoded_architecture=None,
                    execution_cost=bounds.program_base_cost,
                    fault_records=[
                        {
                            "kind": "program_length_out_of_bounds",
                            "length": program.length,
                            "minimum": minimum_length,
                            "maximum": maximum_length,
                        }
                    ],
                )

        state = self._initial_state()
        program_counter = 0
        executed = 0
        status = STATUS_COMPLETE

        while program_counter < program.length:
            if executed >= bounds.execution_budget:
                status = STATUS_BUDGET_EXHAUSTED
                faults.append(
                    {"kind": "execution_budget_exhausted", "program_counter": program_counter}
                )
                break
            record = program.instructions[program_counter]
            executed += 1
            opcode = record.opcode
            operand = record.operand

            if opcode == OP_END:
                program_counter += 1
                break
            if opcode in _OPERAND_FREE_OPCODES or opcode == OP_NO_OP:
                if opcode not in OPCODE_NAMES:
                    faults.append(
                        {
                            "kind": "unknown_opcode_no_op",
                            "program_counter": program_counter,
                            "opcode": opcode,
                        }
                    )
                program_counter += 1
                continue
            if isinstance(operand, float) and not math.isfinite(operand):
                status = STATUS_INVALID_OPERAND
                faults.append(
                    {
                        "kind": "nonfinite_operand",
                        "program_counter": program_counter,
                        "opcode": opcode,
                        "operand": operand,
                    }
                )
                break

            if opcode == OP_SET_HIDDEN:
                target = int(round(operand))
                clamped = max(
                    bounds.minimum_hidden_size, min(bounds.maximum_hidden_size, target)
                )
                if clamped != target:
                    faults.append(
                        {
                            "kind": "operand_clamped",
                            "program_counter": program_counter,
                            "opcode": opcode,
                            "operand": operand,
                            "applied": clamped,
                        }
                    )
                state["hidden_size"] = int(clamped)
            elif opcode == OP_ADJUST_HIDDEN:
                target = int(round(state["hidden_size"] + operand))
                clamped = max(
                    bounds.minimum_hidden_size, min(bounds.maximum_hidden_size, target)
                )
                if clamped != target:
                    faults.append(
                        {
                            "kind": "operand_clamped",
                            "program_counter": program_counter,
                            "opcode": opcode,
                            "operand": operand,
                            "applied": clamped,
                        }
                    )
                state["hidden_size"] = int(clamped)
            elif opcode == OP_SET_RECURRENCE_DENSITY:
                clamped = max(
                    bounds.minimum_recurrence_density,
                    min(bounds.maximum_recurrence_density, float(operand)),
                )
                if clamped != float(operand):
                    faults.append(
                        {
                            "kind": "operand_clamped",
                            "program_counter": program_counter,
                            "opcode": opcode,
                            "operand": operand,
                            "applied": clamped,
                        }
                    )
                state["recurrence_density"] = float(clamped)
            elif opcode == OP_ADJUST_RECURRENCE_DENSITY:
                target = float(state["recurrence_density"]) + float(operand)
                clamped = max(
                    bounds.minimum_recurrence_density,
                    min(bounds.maximum_recurrence_density, target),
                )
                if clamped != target:
                    faults.append(
                        {
                            "kind": "result_clamped",
                            "program_counter": program_counter,
                            "opcode": opcode,
                            "target": target,
                            "applied": clamped,
                        }
                    )
                state["recurrence_density"] = float(clamped)
            elif opcode == OP_SET_PLASTICITY_RATE:
                clamped = max(
                    bounds.minimum_plasticity_rate,
                    min(bounds.maximum_plasticity_rate, float(operand)),
                )
                if clamped != float(operand):
                    faults.append(
                        {
                            "kind": "operand_clamped",
                            "program_counter": program_counter,
                            "opcode": opcode,
                            "operand": operand,
                            "applied": clamped,
                        }
                    )
                state["plasticity_rate"] = float(clamped)
            elif opcode == OP_ADJUST_PLASTICITY_RATE:
                target = float(state["plasticity_rate"]) + float(operand)
                clamped = max(
                    bounds.minimum_plasticity_rate,
                    min(bounds.maximum_plasticity_rate, target),
                )
                if clamped != target:
                    faults.append(
                        {
                            "kind": "result_clamped",
                            "program_counter": program_counter,
                            "opcode": opcode,
                            "target": target,
                            "applied": clamped,
                        }
                    )
                state["plasticity_rate"] = float(clamped)
            elif opcode == OP_ENABLE_PLASTICITY:
                state["plasticity_enabled"] = True
            elif opcode == OP_DISABLE_PLASTICITY:
                state["plasticity_enabled"] = False
            else:
                # Unknown opcode policy: deterministic no-op with a fault
                # record, so varied programs degrade instead of crashing.
                faults.append(
                    {
                        "kind": "unknown_opcode_no_op",
                        "program_counter": program_counter,
                        "opcode": opcode,
                    }
                )
            program_counter += 1

        execution_cost = (
            bounds.program_base_cost
            + bounds.program_per_instruction_cost * executed
        )
        decoded: Optional[NeuralArchitectureDescriptor] = None
        if status == STATUS_COMPLETE:
            decoded = NeuralArchitectureDescriptor(
                architecture_id=f"arch-pgm-{program.program_digest()[:8]}",
                hidden_size=int(state["hidden_size"]),
                recurrent_density=float(state["recurrence_density"]),
                plasticity_rate=float(state["plasticity_rate"]),
                plasticity_enabled=bool(state["plasticity_enabled"]),
            )
        return ProgramExecutionResult(
            status=status,
            executed_instruction_count=executed,
            final_program_counter=program_counter,
            construction_state=state,
            decoded_architecture=decoded,
            execution_cost=execution_cost,
            fault_records=faults,
        )


# Canonical programs ----------------------------------------------------------


def canonical_baseline_program(
    plasticity_rate: float = 0.01,
) -> DesignProgram:
    """Canonical program decoding to the accepted baseline architecture.

    The hidden size and recurrence density are built through construction
    state (set plus adjust steps with exactly representable operands), so the
    program exercises the interpreter rather than serializing the descriptor.
    """
    return DesignProgram(
        instructions=[
            InstructionRecord(opcode=OP_SET_HIDDEN, operand=8.0),
            InstructionRecord(opcode=OP_ADJUST_HIDDEN, operand=8.0),
            InstructionRecord(opcode=OP_SET_RECURRENCE_DENSITY, operand=0.5),
            InstructionRecord(opcode=OP_ADJUST_RECURRENCE_DENSITY, operand=0.5),
            InstructionRecord(opcode=OP_SET_PLASTICITY_RATE, operand=float(plasticity_rate)),
            InstructionRecord(opcode=OP_ENABLE_PLASTICITY, operand=0.0),
            InstructionRecord(opcode=OP_END, operand=0.0),
        ]
    )


def canonical_explicit_program(
    hidden_size: int,
    recurrence_density: float,
    plasticity_rate: float,
    plasticity_enabled: bool,
) -> DesignProgram:
    """A second canonical form of the same construction series: direct construction sets.

    Together with :func:`canonical_baseline_program` this demonstrates that
    multiple distinct programs decode to the same architecture descriptor.
    """
    instructions = [
        InstructionRecord(opcode=OP_SET_HIDDEN, operand=float(hidden_size)),
        InstructionRecord(opcode=OP_SET_RECURRENCE_DENSITY, operand=float(recurrence_density)),
        InstructionRecord(opcode=OP_SET_PLASTICITY_RATE, operand=float(plasticity_rate)),
        InstructionRecord(
            opcode=OP_ENABLE_PLASTICITY if plasticity_enabled else OP_DISABLE_PLASTICITY,
            operand=0.0,
        ),
        InstructionRecord(opcode=OP_END, operand=0.0),
    ]
    return DesignProgram(instructions=instructions)


def random_instruction(rng: random.Random, bounds: DesignExecutionBounds) -> InstructionRecord:
    """Draw one bounded legal instruction from ``rng`` deterministically."""
    opcode = rng.choice(ALL_OPCODES)
    if opcode in _INTEGER_OPERAND_OPCODES:
        operand = float(
            rng.randint(bounds.minimum_hidden_size, bounds.maximum_hidden_size)
        )
    elif opcode in (
        OP_SET_RECURRENCE_DENSITY,
        OP_ADJUST_RECURRENCE_DENSITY,
        OP_SET_PLASTICITY_RATE,
        OP_ADJUST_PLASTICITY_RATE,
    ):
        if opcode in (OP_SET_RECURRENCE_DENSITY, OP_ADJUST_RECURRENCE_DENSITY):
            low, high = bounds.minimum_recurrence_density, bounds.maximum_recurrence_density
        else:
            low, high = bounds.minimum_plasticity_rate, bounds.maximum_plasticity_rate
        operand = round(rng.uniform(low, high), 6)
    else:
        operand = 0.0
    return InstructionRecord(opcode=opcode, operand=operand)


# Variation -------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DesignProgramVariationBounds:
    """Configurable bounded variation probabilities and magnitudes."""

    substitution_probability: float = 0.08
    operand_mutation_probability: float = 0.08
    insertion_probability: float = 0.05
    deletion_probability: float = 0.05
    integer_operand_step: int = 2
    float_operand_step: float = 0.05
    minimum_program_length: int = 1
    maximum_program_length: int = 128


@dataclass(slots=True)
class ProgramVariationOutcome:
    program: DesignProgram
    operations: List[Dict[str, Any]]


def _mutated_operand(
    record: InstructionRecord,
    rng: random.Random,
    variation_bounds: DesignProgramVariationBounds,
    execution_bounds: DesignExecutionBounds,
) -> float:
    if record.opcode in _INTEGER_OPERAND_OPCODES:
        delta = rng.randint(1, max(1, variation_bounds.integer_operand_step))
        return float(record.operand + delta if rng.random() < 0.5 else record.operand - delta)
    if record.opcode in _OPERAND_FREE_OPCODES:
        return float(record.operand)
    span = 2.0 * variation_bounds.float_operand_step
    return float(record.operand + rng.uniform(-span, span))


def vary_design_program(
    program: DesignProgram,
    rng: random.Random,
    execution_bounds: DesignExecutionBounds,
    variation_bounds: DesignProgramVariationBounds,
) -> ProgramVariationOutcome:
    """Apply bounded deterministic variation to ``program``.

    Per instruction index, in ascending order and with the documented roll
    order: deletion, opcode substitution, operand mutation, then insertion
    after the index. Length bounds are respected throughout; structural value
    bounds are enforced later by the interpreter's clamps, never by repair.
    """
    instructions: List[InstructionRecord] = [
        InstructionRecord(opcode=record.opcode, operand=record.operand)
        for record in program.instructions
    ]
    operations: List[Dict[str, Any]] = []
    index = 0
    while index < len(instructions):
        record = instructions[index]

        if (
            len(instructions) > variation_bounds.minimum_program_length
            and rng.random() < variation_bounds.deletion_probability
        ):
            instructions.pop(index)
            operations.append(
                {"operation": "deletion", "index": index, "opcode_removed": record.opcode}
            )
            continue

        if rng.random() < variation_bounds.substitution_probability:
            new_opcode = rng.choice(ALL_OPCODES)
            operations.append(
                {
                    "operation": "substitution",
                    "index": index,
                    "opcode_from": record.opcode,
                    "opcode_to": new_opcode,
                }
            )
            record = InstructionRecord(opcode=new_opcode, operand=record.operand)
            instructions[index] = record

        if rng.random() < variation_bounds.operand_mutation_probability:
            new_operand = _mutated_operand(record, rng, variation_bounds, execution_bounds)
            operations.append(
                {
                    "operation": "operand_mutation",
                    "index": index,
                    "opcode": record.opcode,
                    "operand_from": record.operand,
                    "operand_to": new_operand,
                }
            )
            record = InstructionRecord(opcode=record.opcode, operand=new_operand)
            instructions[index] = record

        if (
            len(instructions) < variation_bounds.maximum_program_length
            and rng.random() < variation_bounds.insertion_probability
        ):
            inserted = random_instruction(rng, execution_bounds)
            instructions.insert(index + 1, inserted)
            operations.append(
                {
                    "operation": "insertion",
                    "index": index + 1,
                    "opcode_inserted": inserted.opcode,
                    "operand_inserted": inserted.operand,
                }
            )
            index += 1

        index += 1

    varied = DesignProgram(
        schema_version=program.schema_version,
        instruction_set_version=program.instruction_set_version,
        instructions=instructions,
    )
    return ProgramVariationOutcome(program=varied, operations=operations)


def derive_program_rng(tick: int, unit_id: str, role: str) -> random.Random:
    """Deterministic RNG for program transfer/variation at a construction."""
    return random.Random(stable_seed("design_program", role, unit_id, int(tick)))


__all__ = [
    "ALL_OPCODES",
    "DESIGN_INSTRUCTION_SET_VERSION",
    "DESIGN_PROGRAM_SCHEMA_VERSION",
    "DesignExecutionBounds",
    "DesignProgram",
    "DesignProgramError",
    "DesignProgramInterpreter",
    "DesignProgramVariationBounds",
    "InstructionRecord",
    "OPCODE_NAMES",
    "OP_ADJUST_HIDDEN",
    "OP_ADJUST_PLASTICITY_RATE",
    "OP_ADJUST_RECURRENCE_DENSITY",
    "OP_DISABLE_PLASTICITY",
    "OP_ENABLE_PLASTICITY",
    "OP_END",
    "OP_NO_OP",
    "OP_SET_HIDDEN",
    "OP_SET_PLASTICITY_RATE",
    "OP_SET_RECURRENCE_DENSITY",
    "ProgramExecutionResult",
    "ProgramVariationOutcome",
    "RESERVED_FUTURE_OPCODES",
    "STATUS_BUDGET_EXHAUSTED",
    "STATUS_COMPLETE",
    "STATUS_INVALID_OPERAND",
    "STATUS_INVALID_PROGRAM",
    "canonical_baseline_program",
    "canonical_explicit_program",
    "derive_program_rng",
    "random_instruction",
    "vary_design_program",
]
