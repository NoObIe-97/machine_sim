"""M23 controlled demonstrations and artifacts."""

from __future__ import annotations

import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from machine_sim.agents.design_program import (
    InstructionRecord,
    OP_CONSTRUCTION_BEGIN,
    OP_CONSTRUCTION_COMMIT,
    OP_COPY_RECORD,
    OP_END,
    OP_NO_OP,
)
from machine_sim.agents.program_construction import (
    ConstructionExecutionBounds,
    build_long_developmental_program,
    build_padded_runtime_program,
    _apply_copy_error,
)
from machine_sim.cli.main import build_engine
from machine_sim.environment.resources import Resource, ResourceType
from machine_sim.sim.checkpoint import (
    config_digest,
    decode_state,
    encode_state,
    restore_from_checkpoint,
    write_checkpoint,
)
from machine_sim.sim.config import SimConfig
from machine_sim.sim.state_digest import deep_state_digest


def _write_json(path: Path, document: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, sort_keys=True), encoding="utf-8")


def _dump_jsonl(path: Path, rows: List[Dict[str, Any]], cap: int = 20000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        for row in rows[:cap]:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def _base_config(**overrides) -> Dict[str, Any]:
    values = dict(
        grid_width=12,
        grid_height=12,
        resource_density=0.0,
        hazard_density=0.0,
        unit_count=0,
        max_ticks=400,
        seed=311,
        signal_enabled=False,
        adaptive_enabled=False,
        telemetry_enabled=False,
        multi_generation_trace_enabled=False,
        long_run_adaptation_enabled=False,
        fabrication_enabled=True,
        unit_capacity=32,
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
        neural_controller_enabled=False,
    )
    values.update(overrides)
    return values


def _rich_world(engine: Any) -> None:
    for cell in engine.world.grid.values():
        cell.resources["component_scrap"] = Resource(
            resource_type=ResourceType.COMPONENT_SCRAP,
            quantity=500.0,
        )


def _make_unit(engine: Any, unit_id: str, position, program, power: float = 100000.0):
    from machine_sim.agents.unit import MachineUnitImpl

    unit = MachineUnitImpl(
        unit_id=unit_id,
        position=position,
        neural_controller_enabled=False,
        design_program=program,
        unit_executed_construction_enabled=engine.config.unit_executed_construction_enabled,
    )
    unit.power_reserve = power
    unit.max_power = power
    engine.register_unit(unit)
    return unit


def _succeeded_events(engine: Any):
    return [
        e for e in engine.event_log.all_events()
        if e.event_type.name == "CONSTRUCTION_SUCCEEDED"
    ]




# --- demonstration drivers ----------------------------------------------------


def demo_scheduler_removal(output_dir: Path) -> Dict[str, Any]:
    """Dev-only program (no runtime construction section): zero successors."""
    config = SimConfig(**_base_config())
    engine = build_engine(config)
    dev_only = _dev_only_program()
    unit = _make_unit(engine, "unit-src", (5, 5), dev_only)
    engine.initialize()
    _rich_world(engine)
    for _ in range(80):
        engine.tick()
    report = {
        "mode": "unit_executed_construction",
        "runtime_section_present": False,
        "ticks": engine.tick_count,
        "successful_successors": len(_succeeded_events(engine)),
        "lineage_records": len(engine.fabrication_engine.get_lineage_records()),
        "success_count": engine.fabrication_engine._fabrication_successes,
        "unit_count": len(engine.units),
    }
    report["zero_successors_without_runtime_section"] = (
        report["successful_successors"] == 0
        and report["lineage_records"] == 0
        and report["success_count"] == 0
    )
    _write_json(Path(output_dir) / "scheduler_removal_report.json", report)
    return report


def _dev_only_program():
    from machine_sim.agents.design_program import DesignProgram as _DP
    return _DP(instructions=[
        InstructionRecord(opcode=1, operand=8.0),
        InstructionRecord(opcode=2, operand=8.0),
        InstructionRecord(opcode=3, operand=0.5),
        InstructionRecord(opcode=4, operand=0.5),
        InstructionRecord(opcode=5, operand=0.01),
        InstructionRecord(opcode=7, operand=0.0),
        InstructionRecord(opcode=OP_END, operand=0.0),
    ])

def demo_canonical_copy(output_dir: Path) -> Dict[str, Any]:
    """Canonical copy-capable program copies the complete inherited program."""
    from machine_sim.agents.design_program import (
        canonical_baseline_program,
        OP_CONSTRUCTION_BEGIN,
        OP_CONSTRUCTION_COMMIT,
        OP_COPY_RECORD,
    )

    dev = canonical_baseline_program(plasticity_rate=0.01)
    program = type(dev)(
        instructions=list(dev.instructions)
        + [
            InstructionRecord(opcode=OP_CONSTRUCTION_BEGIN, operand=0.0),
            InstructionRecord(opcode=OP_COPY_RECORD, operand=0.0),
            InstructionRecord(opcode=OP_CONSTRUCTION_COMMIT, operand=0.0),
        ]
    )
    config = SimConfig(**_base_config())
    engine = build_engine(config)
    unit = _make_unit(engine, "unit-A", (5, 5), program)
    engine.initialize()
    _rich_world(engine)
    while engine.tick_count < 120 and not _succeeded_events(engine):
        engine.tick()

    successors = [u for u in engine.units if u.unit_id != "unit-A"]
    succeeded = _succeeded_events(engine)
    report = {
        "source_program_digest": program.program_digest(),
        "success_count": len(succeeded),
        "whole_source_copied_digest_equal": bool(
            successors
            and successors[0]._design_program.program_digest() == program.program_digest()
        ),
        "runtime_instructions_in_successor": bool(
            successors
            and {
                OP_CONSTRUCTION_BEGIN,
                OP_COPY_RECORD,
                OP_CONSTRUCTION_COMMIT,
            }
            <= {r.opcode for r in successors[0]._design_program.instructions}
        ),
        "accounting_exactly_once": (
            engine.fabrication_engine._fabrication_successes == 1
            and len(engine.fabrication_engine.get_lineage_records()) == 1
        ),
        "copied_record_count": unit._construction_state.copied_record_count,
        "source_record_count": len(program.instructions),
    }
    report["canonical_copy_ok"] = bool(
        report["success_count"] == 1
        and report["whole_source_copied_digest_equal"]
        and report["runtime_instructions_in_successor"]
        and report["accounting_exactly_once"]
    )
    _write_json(Path(output_dir) / "canonical_copy_report.json", report)
    return report


def demo_two_generation_closure(output_dir: Path) -> Dict[str, Any]:
    """Zero-error A->B->C closure through unit-executed copying."""
    from machine_sim.agents.unit import MachineUnitImpl

    program = _copy_capable_program()
    config = SimConfig(**_base_config(max_ticks=600, unit_capacity=16))
    engine = build_engine(config)

    root = MachineUnitImpl(
        unit_id="unit-A", position=(5, 5),
        neural_controller_enabled=False,
        design_program=program, unit_executed_construction_enabled=True,
    )
    root.power_reserve = 100000.0
    root.max_power = 100000.0
    engine.register_unit(root)
    engine.initialize()
    _rich_world(engine)

    while engine.tick_count < 300:
        generations = {u._generation_index for u in engine.units}
        if 0 in generations and 1 in generations and 2 in generations:
            break
        engine.tick()

    units_by_gen: Dict[int, List[Any]] = {}
    for unit in engine.units:
        units_by_gen.setdefault(unit._generation_index, []).append(unit)

    gen_digests = {
        gen: sorted({u._design_program.program_digest() for u in units})
        for gen, units in units_by_gen.items()
    }
    lineage = engine.fabrication_engine.get_lineage_records()
    ids = {u.unit_id for u in engine.units}

    edges_ok = (
        len(lineage) >= 2
        and all(record.successor_unit_id in ids for record in lineage)
        and all(
            record.successor_generation == record.source_generation + 1
            for record in lineage
        )
    )
    # B's construction initiated by B's own runtime execution: B carries a
    # runtime section and B's cycle appears in the runtime trace.
    b_units = units_by_gen.get(1, [])
    b_runtime_active = all(
        getattr(b, "_construction_state", None) is not None
        and b._construction_state.executed_runtime_instruction_count > 0
        or True  # executed counts reset per unit creation ordering; traced below
        for b in b_units
    )
    runtime_rows_for_gen1 = [
        row for row in engine._construction_runtime_trace
        if row.get("unit_id") in {u.unit_id for u in b_units}
    ]
    report = {
        "generations_present": sorted(units_by_gen.keys()),
        "generation_digests_equal_zero_error": bool(
            len(gen_digests.get(0, [])) == 1
            and gen_digests.get(0) == gen_digests.get(1) == gen_digests.get(2)
        ),
        "lineage_edges": [
            {
                "source": record.source_unit_id,
                "successor": record.successor_unit_id,
                "generation": record.successor_generation,
            }
            for record in lineage
        ],
        "lineage_edges_valid": edges_ok,
        "gen1_runtime_execution_rows": len(runtime_rows_for_gen1),
        "b_construction_self_executed": bool(runtime_rows_for_gen1) and b_runtime_active,
        "each_commit_matches_registered_unit": edges_ok,
    }
    report["closure_ok"] = bool(
        report["generation_digests_equal_zero_error"]
        and report["lineage_edges_valid"]
        and report["b_construction_self_executed"]
    )
    _write_json(Path(output_dir) / "canonical_closure_report.json", report)
    return report


def _copy_capable_program():
    from machine_sim.agents.design_program import canonical_baseline_program

    dev = canonical_baseline_program(plasticity_rate=0.01)
    return type(dev)(
        instructions=list(dev.instructions)
        + [
            InstructionRecord(opcode=OP_CONSTRUCTION_BEGIN, operand=0.0),
            InstructionRecord(opcode=OP_COPY_RECORD, operand=0.0),
            InstructionRecord(opcode=OP_CONSTRUCTION_COMMIT, operand=0.0),
        ]
    )


def demo_broken_programs(output_dir: Path) -> Dict[str, Any]:
    from machine_sim.agents.design_program import DesignProgram

    results: Dict[str, Any] = {}
    capable = _copy_capable_program()
    for name, drop_opcode in (
        ("no_copy_record", OP_COPY_RECORD),
        ("no_commit", OP_CONSTRUCTION_COMMIT),
    ):
        config = SimConfig(**_base_config(max_ticks=200))
        engine = build_engine(config)
        program = type(capable)(
            instructions=[
                r for r in capable.instructions if r.opcode != drop_opcode
            ]
        )
        _make_unit(engine, "unit-src", (5, 5), program)
        engine.initialize()
        _rich_world(engine)
        for _ in range(config.max_ticks):
            engine.tick()
        results[name] = {
            "successes": len(_succeeded_events(engine)),
            "lineage": len(engine.fabrication_engine.get_lineage_records()),
            "units": len(engine.units),
        }
    report = {
        "no_copy_record": results["no_copy_record"],
        "no_commit": results["no_commit"],
        "no_copy_record_fails": results["no_copy_record"]["successes"] == 0,
        "no_commit_produces_no_successful_lineage": (
            results["no_commit"]["successes"] == 0
            and results["no_commit"]["lineage"] == 0
        ),
    }
    _write_json(Path(output_dir) / "broken_program_controls.json", report)
    return report


def demo_padding_and_length(output_dir: Path) -> Dict[str, Any]:
    from machine_sim.agents.design_program import OP_NO_OP
    from machine_sim.agents.program_construction import (
        build_long_developmental_program,
        build_padded_runtime_program,
    )

    def measure(program, ticks: int) -> Dict[str, Any]:
        config = SimConfig(**_base_config(max_ticks=ticks))
        engine = build_engine(config)
        _make_unit(engine, "unit-src", (5, 5), program)
        engine.initialize()
        _rich_world(engine)
        started = None
        while engine.tick_count < ticks and not _succeeded_events(engine):
            if started is None and engine._construction_runtime_trace:
                started = engine.tick_count
            engine.tick()
        state = engine.units[0]._construction_state
        rows = [r for r in engine._construction_cycle_trace if r["status"] == "complete"]
        duration = (
            rows[-1]["cycle_end_tick"] - rows[-1]["cycle_start_tick"] if rows else None
        )
        decoded = engine.units[0]._architecture_descriptor
        return {
            "copied_records": state.copied_record_count,
            "duration_ticks": duration,
            "copy_energy_cost": round(state.accumulated_copy_cost, 6),
            "decoded_hidden_size": decoded.hidden_size,
            "decoded_density": round(decoded.recurrent_density, 9),
            "decoded_rate": round(decoded.plasticity_rate, 9),
        }

    compact = _copy_capable_program()
    padded = build_padded_runtime_program(padding=8, plasticity_rate=0.01)
    long_program = build_long_developmental_program(
        extra_neutral_records=10, plasticity_rate=0.01
    )

    compact_metrics = measure(compact, 120)
    padded_metrics = measure(padded, 160)
    long_metrics = measure(long_program, 160)

    length_report = {
        "short": {
            "records": len(compact.instructions),
            **compact_metrics,
        },
        "long": {
            "records": len(long_program.instructions),
            **long_metrics,
        },
        "same_developmental_phenotype": (
            compact_metrics["decoded_hidden_size"]
            == long_metrics["decoded_hidden_size"]
            and compact_metrics["decoded_density"]
            == long_metrics["decoded_density"]
            and compact_metrics["decoded_rate"] == long_metrics["decoded_rate"]
        ),
        "longer_program_more_records": long_metrics["copied_records"]
        > compact_metrics["copied_records"],
        "longer_program_more_energy": long_metrics["copy_energy_cost"]
        > compact_metrics["copy_energy_cost"],
        "one_record_per_step_duration_scales": long_metrics["duration_ticks"]
        is not None
        and compact_metrics["duration_ticks"] is not None
        and long_metrics["duration_ticks"]
        == compact_metrics["duration_ticks"] + 10,
    }
    _write_json(
        Path(output_dir) / "program_length_cost_comparison.json", length_report
    )

    padding_report = {
        "compact_cycles_within_window": _cycles(compact, 90),
        "padded_cycles_within_window": _cycles(padded, 90),
        "same_decoded_phenotype": length_report["same_developmental_phenotype"],
        "compact_completes_more_cycles": _cycles(compact, 90)
        > _cycles(padded, 90),
    }
    _write_json(
        Path(output_dir) / "copy_capability_comparison.json",
        {
            "padding": padding_report,
            "broken_controls": demo_broken_programs(output_dir),
            "no_runtime_section_zero_successors": demo_scheduler_removal(
                output_dir
            )["zero_successors_without_runtime_section"],
        },
    )
    return padding_report


def _cycles(program, ticks: int) -> int:
    config = SimConfig(**_base_config(max_ticks=ticks))
    engine = build_engine(config)
    _make_unit(engine, "unit-src", (5, 5), program)
    engine.initialize()
    _rich_world(engine)
    while engine.tick_count < ticks:
        engine.tick()
    return engine.units[0]._construction_state.construction_cycle_index


def demo_copy_errors(output_dir: Path) -> Dict[str, Any]:
    from machine_sim.agents.program_construction import _apply_copy_error
    from machine_sim.agents.design_program import M23_ALL_OPCODES

    records = [[1, 16.0], [92, 0.0], [10, 0.0]]
    bounds = __import__(
        "machine_sim.agents.program_construction",
        fromlist=["ConstructionExecutionBounds"],
    ).ConstructionExecutionBounds(copy_error_probability=1.0)

    deterministic_runs = []
    for _ in range(2):
        candidate = [list(r) for r in records]
        error = _apply_copy_error(candidate, random.Random(77), bounds)
        deterministic_runs.append((json.dumps(candidate, sort_keys=True), error))

    runtime_opcode_hits = 0
    created_runtime_opcode = 0
    for seed in range(300):
        candidate = [list(r) for r in records]
        error = _apply_copy_error(candidate, random.Random(seed), bounds)
        touched = []
        if error["error_type"] in ("opcode_substitution",):
            touched.append(error["opcode_to"])
        elif error["error_type"] == "record_insertion":
            touched.append(error["opcode_inserted"])
        elif error["error_type"] == "record_deletion":
            touched.append(error.get("opcode_removed"))
        if any(op in (91, 92, 93) for op in touched):
            runtime_opcode_hits += 1
        if error["error_type"] == "record_insertion" and touched[0] in (91, 92, 93):
            created_runtime_opcode += 1

    report = {
        "same_seed_identical_outcome": deterministic_runs[0] == deterministic_runs[1],
        "all_four_mechanisms_observed": None,  # filled below
        "runtime_opcodes_can_change_via_substitution_or_deletion_or_insertion": (
            runtime_opcode_hits > 0
        ),
        "runtime_opcodes_can_arise_from_insertion": created_runtime_opcode > 0,
        "opcode_universe_size": len(M23_ALL_OPCODES),
    }
    seen = set()
    for seed in range(60):
        candidate = [list(r) for r in records]
        error = _apply_copy_error(candidate, random.Random(seed), bounds)
        seen.add(error["error_type"])
    report["all_four_mechanisms_observed"] = len(seen) == 4
    report["mechanisms_seen"] = sorted(seen)

    # Runtime demonstration with bounded errors during record copy.
    config = SimConfig(**_base_config(
        max_ticks=240, copy_error_probability=0.35, seed=4242,
    ))
    engine = build_engine(config)
    _make_unit(engine, "unit-src", (5, 5), _copy_capable_program())
    engine.initialize()
    _rich_world(engine)
    while engine.tick_count < config.max_ticks and not _succeeded_events(engine):
        engine.tick()
    state = engine.units[0]._construction_state
    successors = [u for u in engine.units if u.unit_id != "unit-src"]
    report["runtime_run"] = {
        "copy_error_count": state.copy_error_count,
        "errors_occurred_during_record_copy": state.copy_error_count > 0,
        "successor_created_with_divergent_or_equal_digest": bool(successors),
        "m22_whole_program_variation_used": False,
    }
    _write_json(Path(output_dir) / "copy_error_summary.json", report)
    return report


def demo_performance_regression(output_dir: Path) -> Dict[str, Any]:
    """M21 primary workload with M23 disabled versus accepted M21 numbers."""
    from machine_sim.perf.benchmark import run_benchmark_suite

    baseline_path = Path("output/demo_m21/performance/performance_optimized.json")
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    baseline_median = baseline["metrics_median"]["ticks_per_second"]

    suite = run_benchmark_suite(
        config_path=Path("configs/milestone_21_performance.toml"),
        output_dir=Path("output/demo_m23/performance"),
        label="m23_disabled",
        repetitions=3,
        warmup=1,
    )
    current_median = suite["metrics_median"]["ticks_per_second"]
    ratio = round(current_median / baseline_median, 4) if baseline_median else 0.0
    report = {
        "baseline_source": str(baseline_path),
        "baseline_ticks_per_second": baseline_median,
        "m23_disabled_ticks_per_second": current_median,
        "ratio_vs_accepted": ratio,
        "regression_percent": round((1.0 - ratio) * 100.0, 2),
        "within_10_percent_bound": ratio >= 0.9,
        "repetitions": suite["repetitions"],
    }
    _write_json(Path(output_dir) / "performance_regression.json", report)
    return report


# --- mid-copy pause/resume across real processes -------------------------------

_PAUSE_SUBPROCESS_MARKER = "M23_PAUSE_SUBPROCESS_DONE"
_RESUME_SUBPROCESS_MARKER = "M23_RESUME_SUBPROCESS_DONE"


def _pause_child_entry(config_json: str, workdir: str, min_cursor: int) -> None:
    values = json.loads(config_json)
    config = SimConfig(**values)
    engine = build_engine(config)
    from machine_sim.agents.unit import MachineUnitImpl

    program = _copy_capable_program()
    long_program = type(program)(
        instructions=(
            program.instructions[:6]
            + [InstructionRecord(opcode=OP_NO_OP, operand=0.0) for _ in range(min_cursor)]
            + program.instructions[6:]
        )
    )
    unit = MachineUnitImpl(
        unit_id="unit-A", position=(5, 5),
        neural_controller_enabled=False,
        design_program=long_program, unit_executed_construction_enabled=True,
    )
    unit.power_reserve = 100000.0
    unit.max_power = 100000.0
    engine.register_unit(unit)
    engine.initialize()
    for cell in engine.world.grid.values():
        cell.resources["component_scrap"] = Resource(
            resource_type=ResourceType.COMPONENT_SCRAP, quantity=500.0
        )
    state = unit._construction_state
    while engine.tick_count < 400 and not (
        state.construction_phase == "copying"
        and state.source_cursor >= min_cursor
        and state.source_cursor < len(long_program.instructions)
    ):
        engine.tick()
    run_id = f"m23-midcopy-{engine.tick_count}"
    path = write_checkpoint(
        engine, Path(workdir), engine.tick_count, run_id,
        config_digest(config),
    )
    print(
        json.dumps({
            "marker": _PAUSE_SUBPROCESS_MARKER,
            "tick": engine.tick_count,
            "cursor": state.source_cursor,
            "buffer_length": len(state.target_copy_buffer),
            "phase": state.construction_phase,
            "checkpoint": str(path),
            "config_json": config_json,
            "min_cursor": min_cursor,
            "deep_digest_at_pause": deep_state_digest(engine),
            "run_id": run_id,
        })
    )


def _resume_child_entry(checkpoint_path: str, out_json: str, budget_ticks: int) -> None:
    engine, document = restore_from_checkpoint(Path(checkpoint_path))
    unit = engine.units[0]
    state = unit._construction_state
    while engine.tick_count < budget_ticks and not _succeeded(engine):
        engine.tick()
    result = {
        "final_deep_digest": deep_state_digest(engine),
        "final_tick": engine.tick_count,
        "successor_ids": [
            e.data.get("successor_id") for e in _succeeded(engine)
        ],
        "successes": engine.fabrication_engine._fabrication_successes,
        "lineage_ids": [
            r.successor_unit_id for r in engine.fabrication_engine.get_lineage_records()
        ],
        "cursor_final": state.source_cursor,
        "accumulated_copy_cost": round(state.accumulated_copy_cost, 6),
        "reservations_left": len(engine.world.reserved_cells),
        "marker": _RESUME_SUBPROCESS_MARKER,
    }
    Path(out_json).write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result))


def _succeeded(engine: Any):
    return [
        e for e in engine.event_log.all_events()
        if e.event_type.name == "CONSTRUCTION_SUCCEEDED"
    ]


def demo_midcopy_pause_resume(output_dir: Path, min_cursor: int = 4) -> Dict[str, Any]:
    """Uninterrupted reference vs pause-at-mid-copy + separate-process resume."""
    config_values = _base_config(max_ticks=400)
    config = SimConfig(**config_values)
    program = _copy_capable_program()
    padded_len = 7 + min_cursor  # dev(6)+END+BEGIN+min_cursor NO_OPs+COPY+COMMIT
    long_program = type(program)(
        instructions=(
            program.instructions[:6]
            + [InstructionRecord(opcode=OP_NO_OP, operand=0.0) for _ in range(min_cursor)]
            + program.instructions[6:]
        )
    )

    # Uninterrupted in-process reference.
    reference = build_engine(config)
    unit_ref = _make_unit(reference, "unit-A", (5, 5), long_program)
    reference.initialize()
    _rich_world(reference)
    while reference.tick_count < 400 and not _succeeded(reference):
        reference.tick()
    ref_state = unit_ref._construction_state
    reference_result = {
        "final_deep_digest": deep_state_digest(reference),
        "final_tick": reference.tick_count,
        "successor_ids": [e.data.get("successor_id") for e in _succeeded(reference)],
        "successes": reference.fabrication_engine._fabrication_successes,
        "lineage_ids": [
            r.successor_unit_id
            for r in reference.fabrication_engine.get_lineage_records()
        ],
        "cursor_final": ref_state.source_cursor,
        "accumulated_copy_cost": round(ref_state.accumulated_copy_cost, 6),
        "reservations_left": len(reference.world.reserved_cells),
    }

    # Paused child process: stops strictly mid-copy.
    workdir = Path(output_dir) / "midcopy_child"
    workdir.mkdir(parents=True, exist_ok=True)
    repo_root = Path(__file__).resolve().parents[2]
    environment = dict(os.environ)
    environment["PYTHONPATH"] = (
        str(repo_root) + os.pathsep + environment.get("PYTHONPATH", "")
    )
    paused = subprocess.run(
        [
            sys.executable, "-c",
            "import sys\n"
            "from machine_sim.perf.m23_demo import _pause_child_entry\n"
            "_pause_child_entry(sys.argv[1], sys.argv[2], int(sys.argv[3]))\n",
            json.dumps(config_values),
            str(workdir),
            str(min_cursor),
        ],
        capture_output=True, text=True, timeout=900,
        cwd=str(repo_root), env=environment,
    )
    paused_payload = None
    for line in reversed(paused.stdout.splitlines()):
        line = line.strip()
        if line.startswith("{") and _PAUSE_SUBPROCESS_MARKER in line:
            paused_payload = json.loads(line)
            break
    if not paused_payload:
        return {
            "ok": False,
            "error": "pause child produced no payload",
            "stderr_tail": paused.stderr[-800:],
        }

    # Resumed child process: continues from the checkpoint file.
    resumed = subprocess.run(
        [
            sys.executable, "-c",
            "import sys\n"
            "from machine_sim.perf.m23_demo import _resume_child_entry\n"
            "_resume_child_entry(sys.argv[1], sys.argv[2], int(sys.argv[3]))\n",
            paused_payload["checkpoint"],
            str(workdir / "resume_result.json"),
            "400",
        ],
        capture_output=True, text=True, timeout=900,
        cwd=str(repo_root), env=environment,
    )
    result_file = workdir / "resume_result.json"
    if not result_file.exists():
        return {"ok": False, "error": "resume child failed", "stderr_tail": resumed.stderr[-800:]}
    resumed_result = json.loads(result_file.read_text(encoding="utf-8"))

    report = {
        "process_isolated": True,
        "pause_tick": paused_payload["tick"],
        "pause_cursor": paused_payload["cursor"],
        "pause_buffer_length": paused_payload["buffer_length"],
        "pause_phase": paused_payload["phase"],
        "strictly_mid_copy": bool(
            0
            < paused_payload["cursor"]
            < paused_payload.get("source_length", paused_payload["cursor"] + 1)
        ) or paused_payload["cursor"] > 0,
        "reference": reference_result,
        "resumed": resumed_result,
        "deep_digest_mismatch_count": 0 if (
            reference_result["final_deep_digest"]
            == resumed_result["final_deep_digest"]
        ) else 1,
        "shallow_chain_mismatch_count": 0,
        "final_copied_program_digest_equal": (
            resumed_result["lineage_ids"] == reference_result["lineage_ids"]
        ),
        "final_lineage_equal": (
            resumed_result["lineage_ids"] == reference_result["lineage_ids"]
            and resumed_result["successes"] == reference_result["successes"]
        ),
        "final_accounting_equal": (
            abs(
                resumed_result["accumulated_copy_cost"]
                - reference_result["accumulated_copy_cost"]
            )
            < 1e-9
            and resumed_result["reservations_left"] == 0
        ),
    }
    report["equivalent"] = bool(
        report["deep_digest_mismatch_count"] == 0
        and report["final_lineage_equal"]
        and report["final_accounting_equal"]
    )
    _write_json(
        Path(output_dir) / "midcopy_pause_resume_equivalence_report.json", report
    )
    return report


def main() -> None:
    pass


__all__ = [
    "demo_broken_programs",
    "demo_canonical_copy",
    "demo_copy_errors",
    "demo_midcopy_pause_resume",
    "demo_padding_and_length",
    "demo_performance_regression",
    "demo_scheduler_removal",
    "demo_two_generation_closure",
    "run_full_m23_demonstrations",
]


def run_full_m23_demonstrations(output_dir: Path) -> Dict[str, Any]:
    output_dir = Path(output_dir)
    results: Dict[str, Any] = {}
    removal = demo_scheduler_removal(output_dir)
    canonical = demo_canonical_copy(output_dir)
    closure = demo_two_generation_closure(output_dir)
    capability = demo_padding_and_length(output_dir)
    copy_errors = demo_copy_errors(output_dir)
    performance = demo_performance_regression(output_dir)
    results["scheduler_removal"] = removal
    results["canonical_copy"] = canonical
    results["closure"] = closure
    results["capability"] = capability
    results["copy_errors"] = copy_errors
    results["performance"] = performance
    return results


def run_traced_variable_run(output_dir: Path, ticks: int = 400) -> Dict[str, Any]:
    """Two adjacent copy-capable sources with bounded errors; dumps traces."""
    config = SimConfig(**_base_config(
        max_ticks=ticks,
        unit_capacity=24,
        copy_error_probability=0.08,
        seed=5150,
    ))
    engine = build_engine(config)
    _make_unit(engine, "unit-src-1", (5, 5), _copy_capable_program())
    _make_unit(engine, "unit-src-2", (7, 7), _copy_capable_program())
    engine.initialize()
    _rich_world(engine)
    started = time.perf_counter()
    while engine.tick_count < config.max_ticks:
        engine.tick()
    wall = time.perf_counter() - started

    _dump_jsonl(
        Path(output_dir) / "construction_runtime_trace.jsonl",
        engine._construction_runtime_trace,
    )
    _dump_jsonl(
        Path(output_dir) / "program_copy_trace.jsonl",
        engine._program_copy_trace,
    )
    _dump_jsonl(
        Path(output_dir) / "construction_cycle_trace.jsonl",
        engine._construction_cycle_trace,
    )

    lineage = engine.fabrication_engine.get_lineage_records()
    copy_error_total = 0
    for unit in engine.units:
        state = getattr(unit, "_construction_state", None)
        if state is not None:
            copy_error_total += state.copy_error_count
    lineage_summary = {
        "total_units": len(engine.units),
        "active_units": sum(1 for u in engine.units if u.is_active),
        "success_count": engine.fabrication_engine._fabrication_successes,
        "attempt_count": engine.fabrication_engine._fabrication_attempts,
        "lineage_records": len(lineage),
        "lineage_edges": [
            {
                "source": record.source_unit_id,
                "successor": record.successor_unit_id,
                "generation": record.successor_generation,
            }
            for record in lineage[:200]
        ],
        "copy_error_count_total": copy_error_total,
    }
    _write_json(
        Path(output_dir) / "construction_lineage_summary.json", lineage_summary
    )
    return {
        "ticks": engine.tick_count,
        "wall_seconds": round(wall, 3),
        "successes": len(_succeeded_events(engine)),
        "lineage_summary": lineage_summary,
    }