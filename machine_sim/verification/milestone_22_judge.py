"""Independent M22 judge: evaluates the executable per-unit design-program
substrate.

Overall status is PASS only when every required check is exactly PASS. A
missing artifact or inconclusive probe is a FAIL — never PARTIAL, SKIP,
UNKNOWN, NOT_FOUND, or a default pass.

Representation-only program metadata is future-causal state and is covered by
the standard deep-digest checks; the legacy-compatibility projection lives in
the compatibility report artifact and is re-verified here by a live probe.

Wording note: this judge screens milestone artifacts for anthropomorphic and
biological vocabulary. The specification-mandated machine-native compound
"operand mutation" (a variation-mechanism name) is exempt as an exact
compound; standalone "mutation" remains forbidden. No other term is exempt.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

MINIMUM_COVERAGE_PERCENT = 77.0
MINIMUM_TEST_COUNT = 400
MINIMUM_SUCCESSFUL_TRANSFERS = 3

FORBIDDEN_TERMS = [
    "human", "social", "society", "community", "communication", "message",
    "language", "meaning", "knowledge", "learning", "teaching",
    "strategy", "trust", "cooperation", "competition", "conflict",
    "agreement", "consensus", "evolution", "mutation",
    "inheritance", "offspring", "parent", "child", "species", "fitness",
    "brain", "family", "identity", "reason",
    "genome", "chromosome", "organism", "reproduction",
]


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _read_jsonl_rows(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    try:
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
    except OSError:
        return []
    return rows


# --- shared probe helpers ----------------------------------------------------


def _probe_engine(config_overrides: Optional[Dict[str, Any]] = None):
    from machine_sim.agents.design_program import canonical_baseline_program
    from machine_sim.agents.unit import MachineUnitImpl
    from machine_sim.sim.config import SimConfig
    from machine_sim.sim.engine import SimEngine

    values = dict(
        grid_width=8, grid_height=8, resource_density=0.25, hazard_density=0.05,
        unit_count=2, max_ticks=6, seed=7, signal_enabled=True,
        adaptive_enabled=True, neural_controller_enabled=True,
        fabrication_enabled=False, design_program_enabled=True,
    )
    if config_overrides:
        values.update(config_overrides)
    config = SimConfig(**values)
    engine = SimEngine(config, seed=config.seed)
    for index in range(config.unit_count):
        engine.register_unit(
            MachineUnitImpl(
                unit_id=f"unit-{index:03d}", position=(index, index),
                signal_enabled=True, adaptive_enabled=True,
                neural_controller_enabled=True, neural_seed=config.seed,
                design_program=canonical_baseline_program(),
            )
        )
    engine.initialize()
    return engine


# --- live probes -------------------------------------------------------------


def _probe_schema_and_digest() -> Dict[str, bool]:
    outcome = {"schema": False, "digest_determinism": False}
    try:
        from machine_sim.agents.design_program import (
            DESIGN_PROGRAM_SCHEMA_VERSION,
            DesignProgram,
            DesignProgramError,
            canonical_baseline_program,
        )
    except ImportError:
        return outcome

    program = canonical_baseline_program()
    document_one = json.dumps(program.to_dict(), sort_keys=True)
    document_two = json.dumps(program.to_dict(), sort_keys=True)
    restored_ok = True
    try:
        restored = DesignProgram.from_dict(json.loads(document_one))
        restored_ok = restored.program_digest() == program.program_digest()
    except DesignProgramError:
        restored_ok = False
    rejects_bad_schema = False
    try:
        DesignProgram.from_dict({"schema_version": "9.9.9", "instructions": []})
    except DesignProgramError:
        rejects_bad_schema = True

    outcome["schema"] = bool(
        program.schema_version == DESIGN_PROGRAM_SCHEMA_VERSION
        and document_one == document_two
        and restored_ok
        and rejects_bad_schema
    )

    script = (
        "import json, sys\n"
        "from machine_sim.agents.design_program import DesignProgram\n"
        "document = json.loads(sys.argv[1])\n"
        "print(DesignProgram.from_dict(document).program_digest())\n"
    )
    try:
        repo_root = Path(__file__).resolve().parents[2]
        environment = dict(os.environ)
        environment["PYTHONPATH"] = (
            str(repo_root) + os.pathsep + environment.get("PYTHONPATH", "")
        )
        completed = subprocess.run(
            [sys.executable, "-c", script, document_one],
            capture_output=True, text=True, timeout=120,
            cwd=str(repo_root), env=environment,
        )
        outcome["digest_determinism"] = (
            completed.returncode == 0
            and completed.stdout.strip() == program.program_digest()
        )
    except (OSError, subprocess.TimeoutExpired):
        outcome["digest_determinism"] = False
    return outcome


def _probe_bounded_interpreter() -> Dict[str, bool]:
    try:
        from machine_sim.agents.design_program import (
            DesignExecutionBounds,
            DesignProgram,
            DesignProgramInterpreter,
            InstructionRecord,
            OP_END,
            OP_NO_OP,
            OP_SET_HIDDEN,
            STATUS_BUDGET_EXHAUSTED,
            STATUS_COMPLETE,
            STATUS_INVALID_OPERAND,
            STATUS_INVALID_PROGRAM,
        )
    except ImportError:
        return {"bounded": False}

    interpreter = DesignProgramInterpreter(DesignExecutionBounds(execution_budget=3))
    endless = DesignProgram(
        instructions=[InstructionRecord(opcode=OP_NO_OP, operand=0.0) for _ in range(50)]
    )
    budget_result = interpreter.execute(endless)
    terminated = DesignProgram(
        instructions=[
            InstructionRecord(opcode=OP_SET_HIDDEN, operand=24.0),
            InstructionRecord(opcode=OP_END, operand=0.0),
            InstructionRecord(opcode=OP_SET_HIDDEN, operand=99.0),
        ]
    )
    end_result = interpreter.execute(terminated)
    invalid = interpreter.execute(DesignProgram(instructions=[]))
    nonfinite = interpreter.execute(
        DesignProgram(instructions=[InstructionRecord(opcode=OP_SET_HIDDEN, operand=float("nan"))])
    )
    overlong = interpreter.execute(
        DesignProgram(
            instructions=[InstructionRecord(opcode=OP_NO_OP, operand=0.0) for _ in range(200)]
        ),
        program_length_bounds=(1, 128),
    )
    return {
        "bounded": bool(
            budget_result.status == STATUS_BUDGET_EXHAUSTED
            and budget_result.executed_instruction_count == 3
            and end_result.status == STATUS_COMPLETE
            and end_result.construction_state["hidden_size"] == 24
            and end_result.final_program_counter == 2
            and invalid.status == STATUS_INVALID_PROGRAM
            and nonfinite.status == STATUS_INVALID_OPERAND
            and overlong.status == STATUS_INVALID_PROGRAM
        )
    }


def _probe_instruction_set_completeness() -> bool:
    try:
        from machine_sim.agents.design_program import (
            ALL_OPCODES,
            DesignExecutionBounds,
            DesignProgram,
            DesignProgramInterpreter,
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
        )
    except ImportError:
        return False

    program = DesignProgram(
        instructions=[
            InstructionRecord(opcode=OP_SET_HIDDEN, operand=12.0),
            InstructionRecord(opcode=OP_ADJUST_HIDDEN, operand=-4.0),
            InstructionRecord(opcode=OP_SET_RECURRENCE_DENSITY, operand=1.0),
            InstructionRecord(opcode=OP_ADJUST_RECURRENCE_DENSITY, operand=-0.25),
            InstructionRecord(opcode=OP_SET_PLASTICITY_RATE, operand=0.01),
            InstructionRecord(opcode=OP_ADJUST_PLASTICITY_RATE, operand=0.005),
            InstructionRecord(opcode=OP_DISABLE_PLASTICITY, operand=0.0),
            InstructionRecord(opcode=OP_ENABLE_PLASTICITY, operand=0.0),
            InstructionRecord(opcode=OP_NO_OP, operand=0.0),
            InstructionRecord(opcode=OP_END, operand=0.0),
        ]
    )
    result = DesignProgramInterpreter(DesignExecutionBounds()).execute(program)
    expected_ops = {
        OP_SET_HIDDEN, OP_ADJUST_HIDDEN,
        OP_SET_RECURRENCE_DENSITY, OP_ADJUST_RECURRENCE_DENSITY,
        OP_SET_PLASTICITY_RATE, OP_ADJUST_PLASTICITY_RATE,
        OP_ENABLE_PLASTICITY, OP_DISABLE_PLASTICITY, OP_NO_OP, OP_END,
    }
    return bool(
        result.status == "complete"
        and set(ALL_OPCODES) == expected_ops
        and result.decoded_architecture is not None
        and result.decoded_architecture.hidden_size == 8
        and abs(result.decoded_architecture.recurrent_density - 0.75) < 1e-12
        and abs(result.decoded_architecture.plasticity_rate - 0.015) < 1e-12
        and result.decoded_architecture.plasticity_enabled is True
    )


def _probe_canonical_descriptor_compatibility() -> bool:
    try:
        from machine_sim.agents.design_program import (
            DesignExecutionBounds,
            DesignProgramInterpreter,
            canonical_baseline_program,
        )
        from machine_sim.agents.neural_architecture import NeuralArchitectureDescriptor
    except ImportError:
        return False

    decoded = DesignProgramInterpreter(DesignExecutionBounds()).execute(
        canonical_baseline_program(plasticity_rate=0.01)
    ).decoded_architecture
    legacy = NeuralArchitectureDescriptor(
        architecture_id="arch-legacy",
        hidden_size=16, recurrent_density=1.0,
        plasticity_rate=0.01, plasticity_enabled=True,
    )
    return bool(
        decoded is not None
        and decoded.hidden_size == legacy.hidden_size
        and decoded.recurrent_density == legacy.recurrent_density
        and decoded.plasticity_rate == legacy.plasticity_rate
        and decoded.plasticity_enabled == legacy.plasticity_enabled
    )


def _probe_per_unit_ownership_and_transfer_causality() -> Dict[str, bool]:
    try:
        from machine_sim.agents.design_program import (
            InstructionRecord,
            OP_NO_OP,
            OP_SET_HIDDEN,
            canonical_baseline_program,
        )
        from machine_sim.sim.state_digest import deep_state_digest
    except ImportError:
        return {"ownership": False, "causality": False}

    engine = _probe_engine()
    programs = [
        getattr(unit, "_design_program", None) for unit in engine.units
    ]
    ownership = all(
        program is not None and program.length > 0 for program in programs
    ) and len({program.program_digest() for program in programs if program}) >= 1

    baseline = deep_state_digest(engine)
    mutated = _probe_engine()
    first_program = next(
        getattr(unit, "_design_program", None) for unit in mutated.units
    )
    first_program.instructions[0] = InstructionRecord(
        opcode=OP_SET_HIDDEN, operand=float(first_program.instructions[0].operand) + 4.0
    )
    operand_sensitive = deep_state_digest(mutated) != baseline

    mutated = _probe_engine()
    first_program = next(
        getattr(unit, "_design_program", None) for unit in mutated.units
    )
    first_program.instructions[0] = InstructionRecord(opcode=OP_NO_OP, operand=0.0)
    opcode_sensitive = deep_state_digest(mutated) != baseline

    # Output-only program analysis traces must not affect the digest.
    annotated = _probe_engine()
    annotated._design_program_transfer_trace.append({"tick": 999999})
    annotated._design_program_execution_trace.append({"tick": 999999})
    annotated._design_program_distribution_trace.append({"tick": 999999})
    annotation_independent = deep_state_digest(annotated) == baseline

    return {
        "ownership": bool(ownership),
        "causality": bool(operand_sensitive and opcode_sensitive and annotation_independent),
    }


def _probe_variation() -> Dict[str, bool]:
    try:
        import random

        from machine_sim.agents.design_program import (
            DesignExecutionBounds,
            DesignProgramInterpreter,
            DesignProgramVariationBounds,
            vary_design_program,
            canonical_baseline_program,
        )
    except ImportError:
        return {
            "determinism": False, "mechanisms": False,
            "bounds": False, "cost": False,
        }

    program = canonical_baseline_program()

    def varied(seed: int, target_program=None, **probabilities):
        bounds = DesignProgramVariationBounds(**probabilities)
        return vary_design_program(
            target_program or program,
            random.Random(seed), DesignExecutionBounds(), bounds,
        )

    zero_a = varied(1, substitution_probability=0.0, operand_mutation_probability=0.0,
                    insertion_probability=0.0, deletion_probability=0.0)
    zero_b = varied(1, substitution_probability=0.0, operand_mutation_probability=0.0,
                    insertion_probability=0.0, deletion_probability=0.0)
    same_seed_a = varied(9, substitution_probability=0.6, operand_mutation_probability=0.6,
                         insertion_probability=0.4, deletion_probability=0.4)
    same_seed_b = varied(9, substitution_probability=0.6, operand_mutation_probability=0.6,
                         insertion_probability=0.4, deletion_probability=0.4)
    other_seed = varied(10, substitution_probability=0.6, operand_mutation_probability=0.6,
                        insertion_probability=0.4, deletion_probability=0.4)
    determinism = bool(
        zero_a.program.program_digest() == zero_b.program.program_digest()
        and zero_a.operations == zero_b.operations
        and same_seed_a.program.program_digest() == same_seed_b.program.program_digest()
        and same_seed_a.operations == same_seed_b.operations
        and (other_seed.operations != same_seed_a.operations
             or other_seed.program.program_digest() != same_seed_a.program.program_digest())
    )

    grown = varied(11, program, insertion_probability=1.0, deletion_probability=0.0,
                   substitution_probability=0.0, operand_mutation_probability=0.0,
                   maximum_program_length=128)
    shrunk_base = canonical_explicit_for_probe()
    shrunk = varied(13, shrunk_base, deletion_probability=1.0,
                    insertion_probability=0.0, substitution_probability=0.0,
                    operand_mutation_probability=0.0, minimum_program_length=1)
    substituted = varied(19, program, substitution_probability=1.0,
                         deletion_probability=0.0, insertion_probability=0.0,
                         operand_mutation_probability=0.0)
    mechanisms = bool(
        grown.program.length > program.length
        and shrunk.program.length < shrunk_base.length
        and substituted.program.program_digest() != program.program_digest()
    )

    from machine_sim.agents.design_program import InstructionRecord as _IR

    long_program = type(grown.program)(
        instructions=[_IR(opcode=9, operand=0.0) for _ in range(120)] + list(program.instructions)
    )
    stressed = varied(23, long_program, substitution_probability=0.9,
                      operand_mutation_probability=0.9, insertion_probability=0.9,
                      deletion_probability=0.9, maximum_program_length=128,
                      minimum_program_length=1)
    interpreter = DesignProgramInterpreter(DesignExecutionBounds())
    within_bounds = True
    for seed in range(12):
        candidate = varied(seed + 40, substitution_probability=0.5,
                           operand_mutation_probability=0.5,
                           insertion_probability=0.4, deletion_probability=0.4).program
        if not (1 <= candidate.length <= 128):
            within_bounds = False
            break
        result = interpreter.execute(candidate, program_length_bounds=(1, 128))
        decoded = result.decoded_architecture
        if decoded is not None:
            bounds = DesignExecutionBounds()
            if not (
                bounds.minimum_hidden_size <= decoded.hidden_size <= bounds.maximum_hidden_size
                and bounds.minimum_recurrence_density <= decoded.recurrent_density
                <= bounds.maximum_recurrence_density
                and bounds.minimum_plasticity_rate <= decoded.plasticity_rate
                <= bounds.maximum_plasticity_rate
            ):
                within_bounds = False
                break
    return {
        "determinism": determinism,
        "mechanisms": mechanisms and stressed.program.length <= 128,
        "bounds": within_bounds,
        "cost": _probe_cost_monotonicity(),
    }


def canonical_explicit_for_probe():
    from machine_sim.agents.design_program import canonical_explicit_program

    return canonical_explicit_program(16, 1.0, 0.01, True)


def _probe_cost_monotonicity() -> bool:
    try:
        from machine_sim.agents.design_program import (
            DesignExecutionBounds,
            DesignProgram,
            DesignProgramInterpreter,
            InstructionRecord,
            OP_END,
            OP_NO_OP,
        )
    except ImportError:
        return False

    bounds = DesignExecutionBounds()
    interpreter = DesignProgramInterpreter(bounds)
    small = interpreter.execute(
        DesignProgram(instructions=[InstructionRecord(opcode=OP_END, operand=0.0)])
    )
    large_instructions = [
        InstructionRecord(opcode=OP_NO_OP, operand=0.0) for _ in range(30)
    ] + [InstructionRecord(opcode=OP_END, operand=0.0)]
    large = interpreter.execute(DesignProgram(instructions=large_instructions))
    expected_small = bounds.program_base_cost + bounds.program_per_instruction_cost * 1
    expected_large = bounds.program_base_cost + bounds.program_per_instruction_cost * 31
    return bool(
        large.execution_cost > small.execution_cost
        and small.execution_cost == expected_small
        and large.execution_cost == expected_large
    )


def _probe_malformed_handling() -> bool:
    try:
        from machine_sim.agents.design_program import (
            DesignExecutionBounds,
            DesignProgram,
            DesignProgramInterpreter,
            InstructionRecord,
            OP_END,
            STATUS_BUDGET_EXHAUSTED,
            STATUS_INVALID_OPERAND,
            STATUS_INVALID_PROGRAM,
        )
    except ImportError:
        return False

    interpreter = DesignProgramInterpreter(DesignExecutionBounds())
    empty_status = interpreter.execute(DesignProgram(instructions=[])).status
    nonfinite_status = interpreter.execute(
        DesignProgram(instructions=[
            InstructionRecord(opcode=1, operand=float("inf")),
            InstructionRecord(opcode=OP_END, operand=0.0),
        ])
    ).status
    tight = DesignProgramInterpreter(
        DesignExecutionBounds(execution_budget=2)
    ).execute(
        DesignProgram(instructions=[
            InstructionRecord(opcode=9, operand=0.0) for _ in range(40)
        ])
    ).status
    return bool(
        empty_status == STATUS_INVALID_PROGRAM
        and nonfinite_status == STATUS_INVALID_OPERAND
        and tight == STATUS_BUDGET_EXHAUSTED
    )


def _probe_checkpoint_roundtrip() -> bool:
    try:
        from machine_sim.sim.checkpoint import decode_state, encode_state
        from machine_sim.sim.state_digest import deep_state_digest
    except ImportError:
        return False

    engine = _probe_engine()
    for _ in range(4):
        engine.tick()
    before = deep_state_digest(engine)
    restored = decode_state(encode_state(engine))
    after = deep_state_digest(restored)

    program_a = engine.units[0]._design_program
    program_b = restored.units[0]._design_program
    byte_equal = program_a.to_dict() == program_b.to_dict()

    for _ in range(3):
        engine.tick()
        restored.tick()
    continuation_equal = deep_state_digest(engine) == deep_state_digest(restored)
    return bool(before == after and byte_equal and continuation_equal)


def _probe_analysis_read_only() -> bool:
    try:
        from machine_sim.analysis.design_program_lineage import (
            collect_initial_program_state,
            compatibility_projection_digest,
            summarize_distribution_trace,
            summarize_transfers,
        )
        from machine_sim.sim.state_digest import deep_state_digest
    except ImportError:
        return False

    engine = _probe_engine()
    engine._design_program_transfer_trace.append({
        "tick": 1, "source_unit_id": "u", "successor_unit_id": "s",
        "source_program_digest": "a", "successor_program_digest": "a",
        "source_program_length": 7, "successor_program_length": 7,
        "variation_operations": [], "execution_status": "complete",
        "executed_instruction_count": 7, "execution_cost": 0.57,
        "decoded_hidden_size": 16, "decoded_recurrent_density": 1.0,
        "decoded_plasticity_rate": 0.01, "decoded_plasticity_enabled": True,
        "phenotype_changed": False,
    })
    before = deep_state_digest(engine)
    collect_initial_program_state(engine)
    summarize_transfers(engine)
    summarize_distribution_trace(engine)
    compatibility_projection_digest(engine)
    after = deep_state_digest(engine)
    return before == after


def _probe_dimension_changing_transfer() -> bool:
    try:
        from machine_sim.agents.neural_architecture import (
            NeuralArchitectureDescriptor,
            resize_state_for_successor,
        )
        from machine_sim.agents.neural_controller import NeuralController
    except ImportError:
        return False

    source_descriptor = NeuralArchitectureDescriptor(
        architecture_id="src", hidden_size=16, recurrent_density=1.0,
        plasticity_rate=0.01, plasticity_enabled=True,
    )
    successor_descriptor = NeuralArchitectureDescriptor(
        architecture_id="dst", hidden_size=24, recurrent_density=0.75,
        plasticity_rate=0.02, plasticity_enabled=True,
    )
    controller = NeuralController(unit_id="resize-probe", seed=13)
    state = controller.state
    new_h, new_w_in, new_w_rec, new_w_out, new_w_param, new_b, new_mask, retained = \
        resize_state_for_successor(
            state.hidden_state, state.W_in, state.W_rec, state.W_out,
            state.W_param, state.b_hidden, state.recurrent_mask,
            successor_descriptor, source_descriptor, __import__("random").Random(5),
            weight_bound=2.0,
        )
    shapes_ok = (
        len(new_h) == 24
        and len(new_w_in) == 24
        and len(new_w_out) == 7
        and all(len(row) == 24 for row in new_w_out)
        and len(new_mask) == 24
    )
    return bool(shapes_ok)


def _probe_no_self_replication() -> Dict[str, bool]:
    outcome = {"instruction_whitelist": False, "no_copy_api": False}
    try:
        from machine_sim.agents import design_program as dp
        from machine_sim.agents.design_program import (
            ALL_OPCODES,
            DesignProgramInterpreter,
        )
    except ImportError:
        return outcome

    expected = {
        dp.OP_SET_HIDDEN, dp.OP_ADJUST_HIDDEN,
        dp.OP_SET_RECURRENCE_DENSITY, dp.OP_ADJUST_RECURRENCE_DENSITY,
        dp.OP_SET_PLASTICITY_RATE, dp.OP_ADJUST_PLASTICITY_RATE,
        dp.OP_ENABLE_PLASTICITY, dp.OP_DISABLE_PLASTICITY,
        dp.OP_NO_OP, dp.OP_END,
    }
    outcome["instruction_whitelist"] = set(ALL_OPCODES) == expected

    # Reserved future opcodes must be unknown to the dispatcher (handled only
    # by the documented unknown-opcode policy), and no copy/divide operations
    # may exist.
    reserved_unknown = True
    for reserved in dp.RESERVED_FUTURE_OPCODES:
        program = dp.DesignProgram(
            instructions=[dp.InstructionRecord(opcode=reserved, operand=0.0)]
        )
        result = DesignProgramInterpreter(dp.DesignExecutionBounds()).execute(program)
        if result.fault_records[-1].get("kind") != "unknown_opcode_no_op":
            reserved_unknown = False
    forbidden_names = (
        "copy_pointer", "allocate_copy", "copy_divide", "self_copy",
        "unit_executed_copy",
    )
    module_text = " ".join(
        name.lower() for name in dir(dp)
    )
    outcome["no_copy_api"] = reserved_unknown and not any(
        name in module_text for name in forbidden_names
    )
    return outcome


# --- M22A transactional-finalization live probes -----------------------------


def _run_m22a_scenario(program) -> Dict[str, Any]:
    """Deterministic single-unit fabrication scenario (M22A).

    Returns pre/post accounting, event lists, and exact cost snapshots around
    the attempt phase.
    """
    try:
        from machine_sim.cli.main import build_engine
        from machine_sim.environment.resources import Resource, ResourceType
        from machine_sim.sim.config import SimConfig
    except ImportError:
        return {"available": False}

    config = SimConfig(
        grid_width=8, grid_height=8, resource_density=0.0, hazard_density=0.0,
        unit_count=1, max_ticks=60, seed=41,
        signal_enabled=False, adaptive_enabled=False,
        neural_controller_enabled=False, telemetry_enabled=False,
        multi_generation_trace_enabled=False, long_run_adaptation_enabled=False,
        fabrication_enabled=True, unit_capacity=8, fabrication_interval=3,
        fabrication_power_cost=30.0, fabrication_material_cost=0.3,
        capsule_enabled=False, design_program_enabled=True,
        program_execution_budget=512, program_min_length=1, program_max_length=128,
        program_base_cost=0.5, program_per_instruction_cost=0.01,
        program_substitution_probability=0.0, program_operand_mutation_probability=0.0,
        program_insertion_probability=0.0, program_deletion_probability=0.0,
    )
    engine = build_engine(config)
    from machine_sim.agents.unit import MachineUnitImpl

    engine.units.clear()
    unit = MachineUnitImpl(
        unit_id="unit-src", position=(4, 4),
        signal_enabled=False, adaptive_enabled=False,
        neural_controller_enabled=False, neural_seed=config.seed,
        design_program=program,
    )
    unit.power_reserve = 10000.0
    unit.max_power = 10000.0
    engine.register_unit(unit)
    engine.initialize()
    engine.world.grid[(4, 4)].resources["component_scrap"] = Resource(
        resource_type=ResourceType.COMPONENT_SCRAP, quantity=50.0
    )
    unit._last_fabrication_tick = -999
    unit._last_fabrication_attempt_tick = -999

    snapshots: Dict[str, Any] = {}
    fabricator = engine.fabrication_engine
    original_prepare = fabricator.prepare_fabricate

    def snapshotting_prepare(source_unit, current_tick, world, population, rng):
        snapshots["pre_power"] = source_unit.power_reserve
        scrap = world.grid[(4, 4)].resources.get("component_scrap")
        snapshots["pre_material"] = scrap.quantity if scrap else None
        snapshots["tick"] = current_tick
        return original_prepare(source_unit, current_tick, world, population, rng)

    fabricator.prepare_fabricate = snapshotting_prepare  # type: ignore[method-assign]

    def occupied():
        return sum(1 for cell in engine.world.grid.values() if cell.unit_id is not None)

    before = {
        "attempts": fabricator._fabrication_attempts,
        "successes": fabricator._fabrication_successes,
        "lineage": len(fabricator._lineage_records),
        "failures": dict(fabricator._fabrication_failures),
        "units": len(engine.units),
        "occupied": occupied(),
        "marker": unit._last_fabrication_tick,
    }
    engine.tick()
    succeeded_events = [
        e for e in engine.event_log.all_events()
        if e.event_type.name == "FABRICATION_SUCCEEDED"
    ]
    failed_invalid_events = [
        e for e in engine.event_log.all_events()
        if e.event_type.name == "FABRICATION_FAILED"
        and e.data.get("cause") == "successor_program_invalid"
    ]
    failed_other_events = [
        e for e in engine.event_log.all_events()
        if e.event_type.name == "FABRICATION_FAILED"
        and e.data.get("cause") != "successor_program_invalid"
    ]
    after = {
        "attempts": fabricator._fabrication_attempts,
        "successes": fabricator._fabrication_successes,
        "lineage": len(fabricator._lineage_records),
        "failures": dict(fabricator._fabrication_failures),
        "units": len(engine.units),
        "occupied": occupied(),
        "marker": unit._last_fabrication_tick,
        "attempt_marker": unit._last_fabrication_attempt_tick,
    }
    lineage_ids = [r.successor_unit_id for r in fabricator._lineage_records]
    return {
        "available": True,
        "before": before,
        "after": after,
        "snapshots": snapshots,
        "succeeded_events": succeeded_events,
        "failed_invalid_events": failed_invalid_events,
        "failed_other_events": failed_other_events,
        "lineage_ids": lineage_ids,
        "power_after": unit.power_reserve,
        "material_after": (
            engine.world.grid[(4, 4)].resources.get("component_scrap").quantity
            if engine.world.grid[(4, 4)].resources.get("component_scrap") else 0.0
        ),
        "transfer_trace_rows": list(engine._design_program_transfer_trace),
        "engine": engine,
    }


def _probe_m22a_failure_accounting() -> Dict[str, bool]:
    """Invalid-program attempt: attempts +1; successes/lineage unchanged;
    deterministic failure cause recorded; no unit; no occupancy; marker
    untouched; exactly one FAILED event with the cause and zero SUCCEEDED."""
    try:
        from machine_sim.agents.design_program import DesignProgram

        empty = DesignProgram(instructions=[])
    except ImportError:
        return {"accounting": False, "events": False, "phantom": False}

    scenario = _run_m22a_scenario(empty)
    if not scenario.get("available"):
        return {"accounting": False, "events": False, "phantom": False}
    before, after = scenario["before"], scenario["after"]

    accounting = bool(
        after["attempts"] == before["attempts"] + 1
        and after["successes"] == before["successes"]
        and after["failures"].get("successor_program_invalid") == 1
    )
    events = bool(
        len(scenario["failed_invalid_events"]) == 1
        and not scenario["succeeded_events"]
        and not scenario["failed_other_events"]
    )
    phantom = bool(
        after["lineage"] == before["lineage"]
        and after["units"] == before["units"]
        and after["occupied"] == before["occupied"]
        and after["marker"] == before["marker"]
        and not scenario["lineage_ids"]
    )
    return {"accounting": accounting, "events": events, "phantom": phantom}


def _probe_m22a_valid_finalization_and_sequence() -> Dict[str, bool]:
    """Valid attempt finalizes success/lineage/unit/occupancy/marker exactly
    once; a failed-then-valid sequence leaves no phantom lineage edge."""
    try:
        from machine_sim.agents.design_program import (
            DesignProgram,
            canonical_baseline_program,
        )
    except ImportError:
        return {"finalization": False, "sequence": False}

    valid = canonical_baseline_program()
    scenario = _run_m22a_scenario(valid)
    if not scenario.get("available"):
        return {"finalization": False, "sequence": False}
    before, after = scenario["before"], scenario["after"]
    finalization = bool(
        after["attempts"] == before["attempts"] + 1
        and after["successes"] == before["successes"] + 1
        and after["lineage"] == before["lineage"] + 1
        and after["units"] == before["units"] + 1
        and after["occupied"] == before["occupied"] + 1
        and after["marker"] == scenario["snapshots"]["tick"]
        and len(scenario["succeeded_events"]) == 1
        and not scenario["failed_invalid_events"]
        and len(scenario["lineage_ids"]) == 1
    )

    # Sequence: failed attempt, then valid repair attempt.
    empty = DesignProgram(instructions=[])
    fail_scenario = _run_m22a_scenario(empty)
    provisional_ids = {
        row.get("successor_unit_id")
        for row in fail_scenario["transfer_trace_rows"]
    }
    sequence_engine = fail_scenario["engine"]
    unit = sequence_engine.units[0]
    unit._design_program = canonical_baseline_program()
    unit._last_fabrication_attempt_tick = -999
    unit._last_fabrication_tick = -999
    while sequence_engine.tick_count < 40:
        pre_units = len(sequence_engine.units)
        sequence_engine.tick()
        if len(sequence_engine.units) > pre_units:
            break
    fabricator = sequence_engine.fabrication_engine
    lineage_ids = [r.successor_unit_id for r in fabricator._lineage_records]
    generations = {r.successor_generation for r in fabricator._lineage_records}
    successors = [u for u in sequence_engine.units if u.unit_id != "unit-src"]
    sequence_ok = bool(
        fabricator._fabrication_successes == 1
        and len(fabricator._lineage_records) == 1
        and lineage_ids
        and all(lid not in provisional_ids for lid in lineage_ids)
        and generations == {1}
        and len(successors) == 1
        and successors[0]._generation_index == 1
    )
    return {"finalization": finalization, "sequence": sequence_ok}


def _probe_m22a_cost_exactness() -> bool:
    try:
        from machine_sim.agents.design_program import DesignProgram

        empty = DesignProgram(instructions=[])
    except ImportError:
        return False

    scenario = _run_m22a_scenario(empty)
    if not scenario.get("available"):
        return False
    # Empty program: execution cost is base-only (0.5); no per-instruction
    # term applies. Base fabrication power (30.0) consumed once; material
    # (0.3) consumed once; nothing refunded on program failure.
    expected_power = scenario["snapshots"]["pre_power"] - 30.0 - 0.5
    expected_material = scenario["snapshots"]["pre_material"] - 0.3
    return bool(
        abs(scenario["power_after"] - expected_power) < 1e-9
        and abs(scenario["material_after"] - expected_material) < 1e-9
    )


# --- judge -------------------------------------------------------------------


def _find_demo_dir(milestone_dir: Path, demo_name: str) -> Path:
    """Resolve sibling demo directories strictly beside the milestone dir."""
    return milestone_dir.parent / demo_name


def judge(output_dir: str) -> Dict[str, Any]:
    path = Path(output_dir)
    checks: Dict[str, str] = {}
    detail: Dict[str, Any] = {}

    compatibility = _read_json(path / "design_program_compatibility_report.json")
    variation_summary = _read_json(path / "design_program_variation_summary.json")
    lineage_summary = _read_json(path / "design_program_lineage_summary.json")
    run_summary = _read_json(path / "design_program_run_summary.json")
    pause_report = _read_json(path / "program_pause_resume_equivalence_report.json")
    performance = _read_json(path / "design_program_performance.json")
    initial_rows = _read_jsonl_rows(path / "design_program_initial_state.jsonl")
    transfer_rows = _read_jsonl_rows(path / "design_program_transfer_trace.jsonl")
    execution_rows = _read_jsonl_rows(path / "design_program_execution_trace.jsonl")
    distribution_rows = _read_jsonl_rows(path / "design_program_distribution_trace.jsonl")
    regression_capture = _read_json(
        path / "regression" / "m14_m21_subprocess_results.json"
    )
    test_summary = _read_json(path / "test_summary.json")

    # 1. schema / 2. digest determinism
    schema_probe = _probe_schema_and_digest()
    checks["design_program_schema_check"] = "PASS" if schema_probe["schema"] else "FAIL"
    checks["program_digest_determinism_check"] = (
        "PASS" if schema_probe["digest_determinism"] else "FAIL"
    )

    # 3. bounded interpreter
    checks["bounded_interpreter_check"] = (
        "PASS" if _probe_bounded_interpreter()["bounded"] else "FAIL"
    )

    # 4. instruction set completeness
    checks["instruction_set_completeness_check"] = (
        "PASS" if _probe_instruction_set_completeness() else "FAIL"
    )

    # 5. canonical descriptor compatibility (live)
    checks["canonical_descriptor_compatibility_check"] = (
        "PASS" if _probe_canonical_descriptor_compatibility() else "FAIL"
    )

    # 6. canonical behavior compatibility (artifact)
    behavior_ok = (
        isinstance(compatibility, dict)
        and compatibility.get("compatible") is True
        and compatibility.get("descriptor_field_equality") is True
        and compatibility.get("shallow_chain_equal_throughout") is True
        and compatibility.get("projection_equal_throughout") is True
        and int(compatibility.get("sample_count", 0)) > 0
    )
    checks["canonical_behavior_compatibility_check"] = (
        "PASS" if behavior_ok else "FAIL"
    )

    # 7. per-unit program ownership (live)
    ownership_probe = _probe_per_unit_ownership_and_transfer_causality()
    checks["per_unit_program_ownership_check"] = (
        "PASS" if ownership_probe["ownership"] else "FAIL"
    )

    # 8. successor program transfer (artifact evidence)
    successful_transfers = [
        row for row in transfer_rows if row.get("execution_status") == "complete"
    ]
    transfer_ok = (
        len(successful_transfers) >= MINIMUM_SUCCESSFUL_TRANSFERS
        and len(execution_rows) >= MINIMUM_SUCCESSFUL_TRANSFERS
        and all(
            row.get("successor_program_digest") and row.get("source_program_digest")
            for row in successful_transfers
        )
        and isinstance(run_summary, dict)
        and run_summary.get("evidence", {}).get("several_successful_transfers") is True
    )
    checks["successor_program_transfer_check"] = "PASS" if transfer_ok else "FAIL"

    # 9-11. variation determinism / mechanisms / bounds (live)
    variation_probe = _probe_variation()
    checks["program_variation_determinism_check"] = (
        "PASS" if variation_probe["determinism"] else "FAIL"
    )
    checks["program_insertion_deletion_substitution_check"] = (
        "PASS" if variation_probe["mechanisms"] else "FAIL"
    )
    checks["program_bounds_check"] = "PASS" if variation_probe["bounds"] else "FAIL"

    # 12. program-to-architecture causality (live)
    checks["program_to_architecture_causality_check"] = (
        "PASS" if ownership_probe["causality"] else "FAIL"
    )

    # 13. dimension-changing transfer regression (live)
    checks["dimension_changing_transfer_regression_check"] = (
        "PASS" if _probe_dimension_changing_transfer() else "FAIL"
    )

    # 14. execution cost (live monotonicity + accounting evidence)
    cost_ok = bool(
        variation_probe["cost"]
        and isinstance(variation_summary, dict)
        and float(variation_summary.get("total_program_execution_cost", -1.0)) >= 0.0
    )
    checks["program_execution_cost_check"] = "PASS" if cost_ok else "FAIL"

    # 15. malformed program handling (live)
    checks["malformed_program_handling_check"] = (
        "PASS" if _probe_malformed_handling() else "FAIL"
    )

    # 16. deep digest sensitivity incl. output-only independence (live)
    checks["deep_digest_program_sensitivity_check"] = (
        "PASS" if ownership_probe["causality"] else "FAIL"
    )

    # 17. checkpoint roundtrip (live)
    checks["checkpoint_program_roundtrip_check"] = (
        "PASS" if _probe_checkpoint_roundtrip() else "FAIL"
    )

    # 18. pause/resume program equivalence (artifact)
    pause_ok = (
        isinstance(pause_report, dict)
        and pause_report.get("process_isolated") is True
        and pause_report.get("equivalent") is True
        and int(pause_report.get("mismatch_count", -1)) == 0
        and int(pause_report.get("shallow_run_digest_mismatch_count", -1)) == 0
        and int(pause_report.get("sample_count", 0)) > 0
        and int(pause_report.get("resumed_span", 0)) > 0
    )
    checks["pause_resume_program_equivalence_check"] = (
        "PASS" if pause_ok else "FAIL"
    )

    # 19. analysis read-only (live)
    checks["analysis_read_only_check"] = (
        "PASS" if _probe_analysis_read_only() else "FAIL"
    )

    # 20. M21 oracle regression (fresh sibling artifacts)
    m21_determinism = _read_json(
        _find_demo_dir(path, "demo_m21") / "determinism" / "deep_equivalence_report.json"
    )
    m21_pause = _read_json(
        _find_demo_dir(path, "demo_m21")
        / "determinism"
        / "pause_resume_deep_equivalence_report.json"
    )
    m21_oracle_ok = (
        isinstance(m21_determinism, dict)
        and m21_determinism.get("zero_mismatch_acceptance") is True
        and int(m21_determinism.get("mismatch_count", -1)) == 0
        and isinstance(m21_pause, dict)
        and m21_pause.get("deep_and_shallow_equal") is True
        and int(m21_pause.get("mismatch_count", -1)) == 0
    )
    checks["m21_oracle_regression_check"] = "PASS" if m21_oracle_ok else "FAIL"

    # 21. full regression chain (captured subprocess results)
    regression_ok = (
        isinstance(regression_capture, dict)
        and regression_capture.get("all_pass") is True
        and all(
            entry.get("status") == "PASS" and entry.get("exit_code") == 0
            for entry in (regression_capture.get("results", {}) or {}).values()
        )
        and set((regression_capture.get("results", {}) or {}).keys())
        == {"m14", "m15", "m16", "m17", "m18", "m19", "m20", "m21"}
    )
    checks["m14_m15_m16_m17_m18_m19_m20_m21_regression_check"] = (
        "PASS" if regression_ok else "FAIL"
    )

    # 22. tests and coverage
    coverage_value = float((test_summary or {}).get("coverage_percent", -1.0))
    test_count = int((test_summary or {}).get("passed", -1))
    tests_ok = (
        isinstance(test_summary, dict)
        and coverage_value >= MINIMUM_COVERAGE_PERCENT
        and test_count >= MINIMUM_TEST_COUNT
        and int((test_summary or {}).get("failed", 1)) == 0
    )
    checks["tests_and_coverage_check"] = "PASS" if tests_ok else "FAIL"
    detail["coverage_percent"] = coverage_value
    detail["passed_tests"] = test_count

    # 23. machine-native wording
    found_terms = _scan_wording(path)
    checks["machine_native_wording_check"] = "PASS" if not found_terms else "FAIL"
    detail["forbidden_terms_found"] = found_terms[:20]

    # 24. no self-replication semantics (live structural probes)
    replication_probe = _probe_no_self_replication()
    checks["no_self_replication_semantics_check"] = (
        "PASS"
        if replication_probe["instruction_whitelist"] and replication_probe["no_copy_api"]
        else "FAIL"
    )

    # Demonstration evidence completeness (variable-run requirements).
    demonstrations_ok = (
        isinstance(run_summary, dict)
        and run_summary.get("all_demonstrations_met") is True
        and isinstance(variation_summary, dict)
        and variation_summary.get("successful_transfer_count", 0)
        >= MINIMUM_SUCCESSFUL_TRANSFERS
        and variation_summary.get("zero_change_transfer_count", 0) >= 1
        and variation_summary.get("phenotype_changed_transfer_count", 0) >= 1
        and variation_summary.get("distinct_decoded_architecture_count", 0) >= 2
        and variation_summary.get("out_of_bounds_decoded_count", -1) == 0
        and isinstance(initial_rows, list) and len(initial_rows) > 0
        and isinstance(distribution_rows, list) and len(distribution_rows) > 0
        and isinstance(lineage_summary, dict)
        and isinstance(performance, dict)
        and float(performance.get("canonical_programs_per_second", 0.0)) > 0
    )
    checks["variable_run_demonstrations_check"] = (
        "PASS" if demonstrations_ok else "FAIL"
    )

    # 26-31. M22A transactional finalization (live probes)
    failure_accounting = _probe_m22a_failure_accounting()
    checks["m22a_program_failure_accounting_check"] = (
        "PASS" if failure_accounting["accounting"] else "FAIL"
    )
    checks["m22a_failure_event_exactness_check"] = (
        "PASS" if failure_accounting["events"] else "FAIL"
    )
    checks["m22a_phantom_lineage_prevention_check"] = (
        "PASS" if failure_accounting["phantom"] else "FAIL"
    )
    checks["m22a_program_cost_accounting_exact_check"] = (
        "PASS" if _probe_m22a_cost_exactness() else "FAIL"
    )
    sequence_probe = _probe_m22a_valid_finalization_and_sequence()
    checks["m22a_success_finalization_once_check"] = (
        "PASS" if sequence_probe["finalization"] else "FAIL"
    )
    checks["m22a_failed_then_valid_sequence_check"] = (
        "PASS" if sequence_probe["sequence"] else "FAIL"
    )

    non_pass = [name for name, result in checks.items() if result != "PASS"]
    status = "PASS" if not non_pass else "FAIL"

    return {
        "M22_JUDGE_STATUS": status,
        "checks": checks,
        "failed_checks": non_pass,
        "detail": detail,
        "thresholds": {
            "minimum_successful_transfers": MINIMUM_SUCCESSFUL_TRANSFERS,
            "minimum_coverage_percent": MINIMUM_COVERAGE_PERCENT,
        },
    }


def _scan_wording(path: Path) -> List[str]:
    found: List[str] = []
    lower_terms = [term.lower() for term in FORBIDDEN_TERMS]
    # The M22 specification mandates the machine-native compound term
    # "operand mutation" as a variation-mechanism name; that exact compound is
    # exempt from the biological-vocabulary screen, while standalone
    # "mutation" remains forbidden.
    sanctioned_compounds = ("operand mutation", "operand_mutation")
    for pattern in ("*.json", "*.jsonl"):
        for candidate in sorted(path.glob(pattern)):
            if candidate.name == "milestone_22_judge_result.json":
                continue
            try:
                text = candidate.read_text(encoding="utf-8").lower()
            except OSError:
                continue
            for compound in sanctioned_compounds:
                text = text.replace(compound, " ")
            for term in lower_terms:
                if term in text and term not in found:
                    found.append(term)
    return found


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m machine_sim.verification.milestone_22_judge <output_dir>")
        sys.exit(1)

    output_dir = sys.argv[1]
    results = judge(output_dir)

    out_path = Path(output_dir) / "milestone_22_judge_result.json"
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    print(f"M22_JUDGE_STATUS: {results['M22_JUDGE_STATUS']}")
    for check_name, check_status in results["checks"].items():
        print(f"  {check_name}: {check_status}")

    if results["failed_checks"]:
        print(f"\nFailed checks: {', '.join(results['failed_checks'])}")
        sys.exit(1)
    print("\nAll checks passed.")


if __name__ == "__main__":
    main()
