"""Tests for the M22 design-program representation, interpreter, variation,
and cost model."""

from __future__ import annotations

import json
import random
import subprocess
import sys
import os
from pathlib import Path

import pytest

from machine_sim.agents.design_program import (
    ALL_OPCODES,
    DESIGN_INSTRUCTION_SET_VERSION,
    DESIGN_PROGRAM_SCHEMA_VERSION,
    DesignExecutionBounds,
    DesignProgram,
    DesignProgramError,
    DesignProgramInterpreter,
    DesignProgramVariationBounds,
    InstructionRecord,
    OP_ADJUST_HIDDEN,
    OP_ADJUST_PLASTICITY_RATE,
    OP_ADJUST_RECURRENCE_DENSITY,
    OP_DISABLE_PLASTICITY,
    OP_ENABLE_PLASTICITY,
    OP_END,
    OP_NO_OP,
    OP_SET_HIDDEN,
    OP_SET_PLASTICITY_RATE,
    OP_SET_RECURRENCE_DENSITY,
    RESERVED_FUTURE_OPCODES,
    STATUS_BUDGET_EXHAUSTED,
    STATUS_COMPLETE,
    STATUS_INVALID_OPERAND,
    STATUS_INVALID_PROGRAM,
    canonical_baseline_program,
    canonical_explicit_program,
    random_instruction,
    vary_design_program,
)
from machine_sim.agents.neural_architecture import NeuralArchitectureDescriptor

BOUNDS = DesignExecutionBounds()
VAR_BOUNDS = DesignProgramVariationBounds()


def _program(*pairs) -> DesignProgram:
    return DesignProgram(
        instructions=[InstructionRecord(opcode=op, operand=arg) for op, arg in pairs]
    )


# --- representation ----------------------------------------------------------


def test_canonical_serialization_is_deterministic() -> None:
    program = canonical_baseline_program()
    document_one = json.dumps(program.to_dict(), sort_keys=True)
    document_two = json.dumps(program.to_dict(), sort_keys=True)
    assert document_one == document_two
    restored = DesignProgram.from_dict(json.loads(document_one))
    assert restored.program_digest() == program.program_digest()


def test_program_digest_stable_across_subprocess(tmp_path: Path) -> None:
    program = canonical_baseline_program()
    script = (
        "import json, sys\n"
        "from machine_sim.agents.design_program import DesignProgram\n"
        "document = json.loads(sys.argv[1])\n"
        "print(DesignProgram.from_dict(document).program_digest())\n"
    )
    script_path = tmp_path / "digest_child.py"
    script_path.write_text(script, encoding="utf-8")
    environment = dict(os.environ)
    repo_root = str(Path(__file__).resolve().parents[2])
    environment["PYTHONPATH"] = repo_root + os.pathsep + environment.get("PYTHONPATH", "")
    completed = subprocess.run(
        [sys.executable, str(script_path), json.dumps(program.to_dict())],
        capture_output=True,
        text=True,
        cwd=repo_root,
        env=environment,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == program.program_digest()


def test_digest_changes_when_content_changes() -> None:
    base = _program((OP_SET_HIDDEN, 16), (OP_END, 0))
    changed_opcode = _program((OP_NO_OP, 16), (OP_END, 0))
    changed_operand = _program((OP_SET_HIDDEN, 20), (OP_END, 0))
    assert len({base.program_digest(), changed_opcode.program_digest(), changed_operand.program_digest()}) == 3


def test_variable_program_lengths_supported() -> None:
    short = _program((OP_END, 0))
    long_instructions = [
        InstructionRecord(opcode=OP_NO_OP, operand=0.0) for _ in range(100)
    ] + [InstructionRecord(opcode=OP_END, operand=0.0)]
    long_program = DesignProgram(instructions=long_instructions)
    assert short.length == 1
    assert long_program.length == 101
    result_short = DesignProgramInterpreter(BOUNDS).execute(short)
    result_long = DesignProgramInterpreter(BOUNDS).execute(long_program)
    assert result_short.status == STATUS_COMPLETE
    assert result_long.status == STATUS_COMPLETE


def test_min_max_length_enforced_at_execution() -> None:
    empty = DesignProgram(instructions=[])
    result = DesignProgramInterpreter(BOUNDS).execute(empty)
    assert result.status == STATUS_INVALID_PROGRAM

    overlong = DesignProgram(
        instructions=[
            InstructionRecord(opcode=OP_NO_OP, operand=0.0) for _ in range(200)
        ]
    )
    result = DesignProgramInterpreter(BOUNDS).execute(
        overlong, program_length_bounds=(1, 128)
    )
    assert result.status == STATUS_INVALID_PROGRAM


def test_invalid_schema_rejected() -> None:
    with pytest.raises(DesignProgramError):
        DesignProgram.from_dict({"schema_version": "9.9.9", "instructions": []})
    with pytest.raises(DesignProgramError):
        DesignProgram.from_dict(
            {
                "schema_version": DESIGN_PROGRAM_SCHEMA_VERSION,
                "instruction_set_version": 999,
                "instructions": [],
            }
        )
    with pytest.raises(DesignProgramError):
        DesignProgram.from_dict(
            {
                "schema_version": DESIGN_PROGRAM_SCHEMA_VERSION,
                "instruction_set_version": DESIGN_INSTRUCTION_SET_VERSION,
                "instructions": [["SET_NOT_AN_INT", 1.0]],
            }
        )
    tampered = canonical_baseline_program().to_dict()
    tampered["program_digest"] = "0" * 64
    with pytest.raises(DesignProgramError):
        DesignProgram.from_dict(tampered)


def test_no_executable_code_in_records() -> None:
    program = canonical_baseline_program()
    text = json.dumps(program.canonical_payload())
    for banned in ("callable", "eval", "lambda", "__", "import"):
        assert banned not in text


# --- interpreter -------------------------------------------------------------


def test_interpreter_deterministic_for_same_inputs() -> None:
    program = canonical_baseline_program()
    interpreter = DesignProgramInterpreter(BOUNDS)
    one = interpreter.execute(program)
    two = interpreter.execute(program)
    assert one.status == two.status == STATUS_COMPLETE
    assert one.construction_state == two.construction_state
    assert one.execution_cost == two.execution_cost
    assert one.decoded_architecture.hidden_size == two.decoded_architecture.hidden_size


def test_all_opcodes_execute_without_error() -> None:
    program = _program(
        (OP_SET_HIDDEN, 12),
        (OP_ADJUST_HIDDEN, -4),
        (OP_SET_RECURRENCE_DENSITY, 0.5),
        (OP_ADJUST_RECURRENCE_DENSITY, 0.25),
        (OP_SET_PLASTICITY_RATE, 0.02),
        (OP_ADJUST_PLASTICITY_RATE, 0.01),
        (OP_DISABLE_PLASTICITY, 0.0),
        (OP_ENABLE_PLASTICITY, 0.0),
        (OP_NO_OP, 0.0),
        (999, 0.0),  # unknown opcode: no-op with fault record
        (OP_END, 0.0),
    )
    result = DesignProgramInterpreter(BOUNDS).execute(program)
    assert result.status == STATUS_COMPLETE
    state = result.construction_state
    assert state["hidden_size"] == 8
    assert state["recurrence_density"] == pytest.approx(0.75)
    assert state["plasticity_rate"] == pytest.approx(0.03)
    assert state["plasticity_enabled"] is True
    kinds = {fault["kind"] for fault in result.fault_records}
    assert "unknown_opcode_no_op" in kinds
    decoded = result.decoded_architecture
    assert decoded.hidden_size == 8
    assert decoded.recurrent_density == pytest.approx(0.75)


def test_operand_clamping_to_architecture_bounds() -> None:
    program = _program(
        (OP_SET_HIDDEN, 5000),
        (OP_ADJUST_HIDDEN, -9999),
        (OP_SET_RECURRENCE_DENSITY, 42.0),
        (OP_SET_PLASTICITY_RATE, -5.0),
        (OP_END, 0.0),
    )
    result = DesignProgramInterpreter(BOUNDS).execute(program)
    assert result.status == STATUS_COMPLETE
    assert result.construction_state["hidden_size"] == BOUNDS.minimum_hidden_size
    assert result.construction_state["recurrence_density"] == BOUNDS.maximum_recurrence_density
    assert result.construction_state["plasticity_rate"] == BOUNDS.minimum_plasticity_rate
    clamps = [f for f in result.fault_records if f["kind"] == "operand_clamped"]
    assert len(clamps) >= 3


def test_nonfinite_operand_halts_with_invalid_operand() -> None:
    program = _program((OP_SET_HIDDEN, float("nan")), (OP_END, 0.0))
    result = DesignProgramInterpreter(BOUNDS).execute(program)
    assert result.status == STATUS_INVALID_OPERAND
    assert result.decoded_architecture is None


def test_unknown_opcode_policy_is_noop_with_fault_record() -> None:
    program = _program((OP_SET_HIDDEN, 10), (321, 7.0), (OP_END, 0.0))
    result = DesignProgramInterpreter(BOUNDS).execute(program)
    assert result.status == STATUS_COMPLETE
    assert result.construction_state["hidden_size"] == 10
    assert result.fault_records[-1]["kind"] == "unknown_opcode_no_op"
    assert result.fault_records[-1]["opcode"] == 321


def test_end_terminates_and_budget_enforced() -> None:
    terminated = _program((OP_SET_HIDDEN, 24), (OP_END, 0.0), (OP_SET_HIDDEN, 99))
    result = DesignProgramInterpreter(BOUNDS).execute(terminated)
    assert result.final_program_counter == 2
    assert result.construction_state["hidden_size"] == 24

    tight_bounds = DesignExecutionBounds(execution_budget=3)
    endless = DesignProgram(
        instructions=[
            InstructionRecord(opcode=OP_NO_OP, operand=0.0) for _ in range(50)
        ]
    )
    result = DesignProgramInterpreter(tight_bounds).execute(endless)
    assert result.status == STATUS_BUDGET_EXHAUSTED
    assert result.executed_instruction_count == 3
    assert result.decoded_architecture is None


def test_execution_cost_monotone_in_instruction_count() -> None:
    interpreter = DesignProgramInterpreter(BOUNDS)
    small = interpreter.execute(_program((OP_END, 0.0)))
    large = interpreter.execute(
        DesignProgram(
            instructions=[
                InstructionRecord(opcode=OP_NO_OP, operand=0.0) for _ in range(40)
            ]
            + [InstructionRecord(opcode=OP_END, operand=0.0)]
        )
    )
    expected_small = BOUNDS.program_base_cost + BOUNDS.program_per_instruction_cost * 1
    expected_large = BOUNDS.program_base_cost + BOUNDS.program_per_instruction_cost * 41
    assert small.execution_cost == pytest.approx(expected_small)
    assert large.execution_cost == pytest.approx(expected_large)
    assert large.execution_cost > small.execution_cost


# --- canonical compatibility programs ----------------------------------------


def test_canonical_baseline_decodes_accepted_baseline_descriptor() -> None:
    result = DesignProgramInterpreter(BOUNDS).execute(canonical_baseline_program())
    assert result.status == STATUS_COMPLETE
    decoded = result.decoded_architecture
    legacy = NeuralArchitectureDescriptor(
        architecture_id="arch-init-000",
        hidden_size=16,
        recurrent_density=1.0,
        plasticity_rate=0.01,
        plasticity_enabled=True,
    )
    assert decoded.hidden_size == legacy.hidden_size
    assert decoded.recurrent_density == legacy.recurrent_density
    assert decoded.plasticity_rate == legacy.plasticity_rate
    assert decoded.plasticity_enabled == legacy.plasticity_enabled


def test_multiple_distinct_programs_decode_same_descriptor_fields() -> None:
    decomposed = canonical_baseline_program()
    explicit = canonical_explicit_program(16, 1.0, 0.01, True)
    third = _program(
        (OP_SET_HIDDEN, 32),
        (OP_ADJUST_HIDDEN, -16),
        (OP_SET_RECURRENCE_DENSITY, 0.25),
        (OP_ADJUST_RECURRENCE_DENSITY, 0.75),
        (OP_SET_PLASTICITY_RATE, 0.005),
        (OP_ADJUST_PLASTICITY_RATE, 0.005),
        (OP_ENABLE_PLASTICITY, 0.0),
        (OP_NO_OP, 0.0),
        (OP_END, 0.0),
    )
    interpreter = DesignProgramInterpreter(BOUNDS)
    fields = set()
    for program in (decomposed, explicit, third):
        result = interpreter.execute(program)
        assert result.status == STATUS_COMPLETE
        descriptor = result.decoded_architecture
        fields.add(
            (
                descriptor.hidden_size,
                descriptor.recurrent_density,
                descriptor.plasticity_rate,
                descriptor.plasticity_enabled,
            )
        )
    assert len(fields) == 1


def test_reserved_future_opcodes_absent_from_instruction_set() -> None:
    for reserved in RESERVED_FUTURE_OPCODES:
        assert reserved not in ALL_OPCODES


# --- variation ---------------------------------------------------------------


def _varied(program: DesignProgram, seed: int, **overrides) -> tuple:
    bounds = DesignProgramVariationBounds(**overrides)
    outcome = vary_design_program(program, random.Random(seed), BOUNDS, bounds)
    return outcome.program, outcome.operations


def test_zero_variation_transfer_is_pure_copy() -> None:
    program = canonical_baseline_program()
    varied, operations = _varied(program, 1, substitution_probability=0.0,
                                 operand_mutation_probability=0.0,
                                 insertion_probability=0.0,
                                 deletion_probability=0.0)
    assert varied.program_digest() == program.program_digest()
    assert operations == []


def test_substitution_and_operand_mutation_occur_under_high_probabilities() -> None:
    program = canonical_baseline_program()
    varied, operations = _varied(
        program,
        7,
        substitution_probability=0.9,
        operand_mutation_probability=0.9,
        insertion_probability=0.0,
        deletion_probability=0.0,
    )
    kinds = {operation["operation"] for operation in operations}
    assert "substitution" in kinds or "operand_mutation" in kinds
    assert varied.program_digest() != program.program_digest()


def test_insertion_extends_and_deletion_contracts_length() -> None:
    program = canonical_baseline_program()
    grown, grown_ops = _varied(
        program, 11, insertion_probability=0.95, deletion_probability=0.0,
        substitution_probability=0.0, operand_mutation_probability=0.0,
    )
    shrunk, shrunk_ops = _varied(
        program, 13, deletion_probability=0.85, insertion_probability=0.0,
        substitution_probability=0.0, operand_mutation_probability=0.0,
        minimum_program_length=1,
    )
    assert grown.length > program.length
    assert any(op["operation"] == "insertion" for op in grown_ops)
    assert shrunk.length < program.length
    assert any(op["operation"] == "deletion" for op in shrunk_ops)


def test_variation_respects_length_bounds() -> None:
    program = canonical_explicit_program(16, 1.0, 0.01, True)
    filler = [InstructionRecord(opcode=OP_NO_OP, operand=0.0) for _ in range(120)]
    long_program = DesignProgram(instructions=filler + program.instructions)
    varied, _ = _varied(
        long_program, 17, insertion_probability=0.9, deletion_probability=0.9,
        substitution_probability=0.9, operand_mutation_probability=0.9,
        maximum_program_length=128, minimum_program_length=1,
    )
    assert 1 <= varied.length <= 128


def test_variation_deterministic_under_same_seed_different_under_other() -> None:
    program = canonical_baseline_program()
    high = dict(substitution_probability=0.6, operand_mutation_probability=0.6,
                insertion_probability=0.4, deletion_probability=0.4)
    one_program, one_ops = _varied(program, 23, **high)
    two_program, two_ops = _varied(program, 23, **high)
    other_program, other_ops = _varied(program, 24, **high)
    assert one_ops == two_ops
    assert one_program.program_digest() == two_program.program_digest()
    assert other_ops != one_ops or other_program.program_digest() != one_program.program_digest()


def test_phenotype_neutral_change_capability() -> None:
    # Substituting an instruction for NO_OP after the phenotype is fully
    # constructed leaves the decoded architecture unchanged.
    original = canonical_explicit_program(16, 1.0, 0.01, True)
    neutral = _program(
        (OP_SET_HIDDEN, 16),
        (OP_SET_RECURRENCE_DENSITY, 1.0),
        (OP_SET_PLASTICITY_RATE, 0.01),
        (OP_ENABLE_PLASTICITY, 0.0),
        (OP_NO_OP, 0.0),
        (OP_END, 0.0),
    )
    interpreter = DesignProgramInterpreter(BOUNDS)
    a = interpreter.execute(original).decoded_architecture
    b = interpreter.execute(neutral).decoded_architecture
    assert a.hidden_size == b.hidden_size
    assert a.recurrent_density == b.recurrent_density
    assert a.plasticity_rate == b.plasticity_rate
    assert a.plasticity_enabled == b.plasticity_enabled
    assert original.program_digest() != neutral.program_digest()


def test_phenotype_changing_capability() -> None:
    baseline = DesignProgramInterpreter(BOUNDS).execute(canonical_baseline_program())
    changed_program = _program(
        (OP_SET_HIDDEN, 24),
        (OP_SET_RECURRENCE_DENSITY, 0.5),
        (OP_SET_PLASTICITY_RATE, 0.03),
        (OP_DISABLE_PLASTICITY, 0.0),
        (OP_END, 0.0),
    )
    changed = DesignProgramInterpreter(BOUNDS).execute(changed_program)
    a = baseline.decoded_architecture
    b = changed.decoded_architecture
    assert (a.hidden_size, a.recurrent_density, a.plasticity_rate, a.plasticity_enabled) != (
        b.hidden_size, b.recurrent_density, b.plasticity_rate, b.plasticity_enabled
    )


def test_varied_programs_always_execute_within_bounds() -> None:
    program = canonical_baseline_program()
    interpreter = DesignProgramInterpreter(BOUNDS)
    for seed in range(30):
        varied, _ = _varied(program, seed, substitution_probability=0.5,
                            operand_mutation_probability=0.5,
                            insertion_probability=0.4, deletion_probability=0.4)
        result = interpreter.execute(varied, program_length_bounds=(1, 128))
        assert result.status in (STATUS_COMPLETE, STATUS_BUDGET_EXHAUSTED)
        if result.decoded_architecture is not None:
            descriptor = result.decoded_architecture
            assert BOUNDS.minimum_hidden_size <= descriptor.hidden_size <= BOUNDS.maximum_hidden_size
            assert BOUNDS.minimum_recurrence_density <= descriptor.recurrent_density <= BOUNDS.maximum_recurrence_density
            assert BOUNDS.minimum_plasticity_rate <= descriptor.plasticity_rate <= BOUNDS.maximum_plasticity_rate


def test_random_instruction_draws_bounded_operands() -> None:
    rng = random.Random(3)
    for _ in range(50):
        record = random_instruction(rng, BOUNDS)
        assert record.opcode in ALL_OPCODES
