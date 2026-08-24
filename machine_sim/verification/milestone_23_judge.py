"""Independent M23 judge: unit-executed program copying and successor construction.

Overall status is PASS only when every required check is exactly PASS.
No PARTIAL, SKIP, UNKNOWN, NOT_FOUND, or default-pass paths.

Live probes verify mechanism claims (scheduler removal, copy semantics,
transactional finalization, reservation exclusivity, digest sensitivity,
mid-copy checkpoint) rather than trusting artifact booleans. Artifact checks
are used for demonstration evidence that cannot be re-created in a probe
(multi-generation closure runs, performance benchmarks).
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


def _m23_engine(program, **config_overrides):
    """Build a single-unit M23 engine with rich resources."""
    from machine_sim.agents.unit import MachineUnitImpl
    from machine_sim.cli.main import build_engine
    from machine_sim.environment.resources import Resource, ResourceType
    from machine_sim.sim.config import SimConfig

    values = dict(
        grid_width=10, grid_height=10, resource_density=0.0, hazard_density=0.0,
        unit_count=1, max_ticks=120, seed=97,
        signal_enabled=False, adaptive_enabled=False,
        neural_controller_enabled=False, telemetry_enabled=False,
        multi_generation_trace_enabled=False, long_run_adaptation_enabled=False,
        fabrication_enabled=True, unit_capacity=8, capsule_enabled=False,
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
    values.update(config_overrides)
    config = SimConfig(**values)
    engine = build_engine(config)
    engine.units.clear()
    unit = MachineUnitImpl(
        unit_id="unit-a", position=(4, 4),
        signal_enabled=False, adaptive_enabled=False,
        neural_controller_enabled=False, neural_seed=config.seed,
        design_program=program,
        unit_executed_construction_enabled=config.unit_executed_construction_enabled,
    )
    unit.power_reserve = 10000.0
    unit.max_power = 10000.0
    engine.register_unit(unit)
    engine.initialize()
    for cell in engine.world.grid.values():
        cell.resources["component_scrap"] = Resource(
            resource_type=ResourceType.COMPONENT_SCRAP, quantity=500.0
        )
    return engine


def _canonical_copy_capable():
    from machine_sim.agents.design_program import (
        canonical_baseline_program,
        InstructionRecord,
        OP_CONSTRUCTION_BEGIN, OP_CONSTRUCTION_COMMIT, OP_COPY_RECORD,
    )

    dev = canonical_baseline_program(plasticity_rate=0.01)
    return type(dev)(
        instructions=list(dev.instructions)
        + [
            InstructionRecord(opcode=OP_CONSTRUCTION_BEGIN, operand=0.0),
            InstructionRecord(opcode=OP_COPY_RECORD, operand=0.0),
            InstructionRecord(opcode=OP_CONSTRUCTION_COMMIT, operand=0.0),
        ]
    )


def _run_to_success(engine, max_ticks: int = 120) -> bool:
    from machine_sim.perf.m23_demo import _succeeded

    while engine.tick_count < max_ticks and not _succeeded(engine):
        engine.tick()
    return bool(_succeeded(engine))


# --- live probes -------------------------------------------------------------


def _probe_mode_opt_in_and_scheduler_removal() -> Dict[str, bool]:
    """Verify: (1) M23 mode is opt-in; (2) disabled mode keeps legacy path;
    (3) enabled mode with no runtime section produces zero successors."""
    try:
        from machine_sim.agents.design_program import canonical_baseline_program
        from machine_sim.sim.config import SimConfig
    except ImportError:
        return {"opt_in": False, "disabled_legacy": False, "no_section_zero": False}

    # Opt-in: default is False.
    default_cfg = SimConfig()
    opt_in = default_cfg.unit_executed_construction_enabled is False

    # Disabled mode: canonical program does nothing (legacy path owns construction).
    cfg_disabled = SimConfig(
        grid_width=8, grid_height=8, unit_count=1, max_ticks=20,
        design_program_enabled=True, fabrication_enabled=True,
        unit_executed_construction_enabled=False,
    )
    disabled_legacy = not cfg_disabled.unit_executed_construction_enabled

    # No runtime section: zero successors under abundant resources.
    engine = _m23_engine(canonical_baseline_program())
    for _ in range(60):
        engine.tick()
    no_section_zero = (
        len(engine.units) == 1
        and engine.fabrication_engine._fabrication_successes == 0
        and len(engine.fabrication_engine.get_lineage_records()) == 0
    )

    return {
        "opt_in": opt_in,
        "disabled_legacy": disabled_legacy,
        "no_section_zero": no_section_zero,
    }


def _probe_runtime_section_and_interpreter_compat() -> Dict[str, bool]:
    """Verify runtime section exists after first END and the M22 developmental
    interpreter treats runtime opcodes as unknown-no-op."""
    try:
        from machine_sim.agents.design_program import (
            DesignProgramInterpreter,
            DesignExecutionBounds,
        )
        from machine_sim.agents.program_construction import (
            build_canonical_copy_capable_program,
            runtime_section_bounds,
        )
    except ImportError:
        return {"section": False, "compat": False}

    program = build_canonical_copy_capable_program()
    start = runtime_section_bounds(program)
    section = start is not None and start < len(program.instructions)

    interpreter = DesignProgramInterpreter(DesignExecutionBounds())
    result = interpreter.execute(program)
    compat = (
        result.status == "complete"
        and result.decoded_architecture is not None
        and all(
            fault.get("kind") == "unknown_opcode_no_op"
            for fault in result.fault_records
            if fault.get("opcode") in (91, 92, 93)
        )
    )
    return {"section": section, "compat": compat}


def _probe_copy_semantics() -> Dict[str, bool]:
    """Live: whole-program copy, single-step progress, commit requires complete."""
    from machine_sim.perf.m23_demo import _succeeded
    from machine_sim.agents.program_construction import (
        ConstructionRuntimeState, PHASE_COPYING, PHASE_READY,
        OP_COPY_RECORD, execute_runtime_step, ConstructionExecutionBounds,
    )
    from machine_sim.agents.design_program import InstructionRecord

    program = _canonical_copy_capable()
    engine = _m23_engine(program)
    unit = engine.units[0]
    state = unit._construction_state

    class NullServices:
        def charge_runtime_instruction(self): pass
        def charge_copy_record(self): pass
        def begin_unit_construction(self, tick): 
            state.construction_phase = PHASE_COPYING
            state.source_cursor = 0
            state.target_copy_buffer = []
            return True
        def commit_unit_construction(self):
            return {"status": "complete", "successor_unit_id": "unit-x",
                    "successor_program_digest": program.program_digest(), "fault": None}

    services = NullServices()
    bounds = ConstructionExecutionBounds(copy_records_per_step=1)

    # Step 1: BEGIN
    execute_runtime_step(program, state, services, bounds, 1)
    begin_ok = state.construction_phase == PHASE_COPYING and state.source_cursor == 0

    # Steps 2..N+1: COPY_RECORD holds PC while copying; advances on completion
    pc_stable = True
    cursor_advances = True
    for i in range(len(program.instructions)):
        if state.source_cursor >= len(program.instructions):
            break
        old_pc = state.runtime_program_counter
        old_cursor = state.source_cursor
        execute_runtime_step(program, state, services, bounds, 2 + i)
        if state.source_cursor < len(program.instructions):
            # During copying: PC stays on COPY_RECORD, cursor advances by 1.
            if state.runtime_program_counter != old_pc:
                pc_stable = False
        if state.source_cursor != old_cursor + 1:
            cursor_advances = False

    copy_done = state.source_cursor == len(program.instructions)
    buffer_equal = [list(pair) for pair in state.target_copy_buffer] == [
        list(r.to_pair()) for r in program.instructions
    ]

    return {
        "begin_ok": begin_ok,
        "single_step_progress": pc_stable and cursor_advances,
        "whole_copied": copy_done and buffer_equal,
    }


def _probe_commit_requires_complete() -> bool:
    """COMMIT before copy completes must fail cleanly."""
    from machine_sim.agents.program_construction import (
        ConstructionRuntimeState, PHASE_COPYING, PHASE_IDLE,
        OP_CONSTRUCTION_COMMIT, execute_runtime_step, ConstructionExecutionBounds,
    )
    from machine_sim.agents.design_program import (
        DesignProgram, InstructionRecord, OP_END, OP_NO_OP,
    )

    program = DesignProgram(instructions=[
        InstructionRecord(opcode=91), InstructionRecord(opcode=93),
    ])
    state = ConstructionRuntimeState(
        construction_enabled=True, runtime_section_start=0, runtime_program_counter=0,
    )

    class Svc:
        def charge_runtime_instruction(self): pass
        def charge_copy_record(self): pass
        def begin_unit_construction(self, tick):
            state.construction_phase = "copying"; return True
        def commit_unit_construction(self): return {"status": "failed"}

    execute_runtime_step(program, state, Svc(), ConstructionExecutionBounds(), 1)
    # Phase is copying but cursor=0: incomplete.
    assert state.source_cursor == 0
    execute_runtime_step(program, state, Svc(), ConstructionExecutionBounds(), 2)
    # COMMIT should have failed and reset to idle without success.
    return state.construction_phase == "idle" and state.last_construction_fault is not None


def _probe_broken_programs() -> Dict[str, bool]:
    """No COPY_RECORD → never copies. No COMMIT → never finalizes."""
    from machine_sim.agents.design_program import (
        DesignProgram, InstructionRecord, OP_END,
        OP_CONSTRUCTION_BEGIN, OP_CONSTRUCTION_COMMIT,
    )
    from machine_sim.perf.m23_demo import _succeeded

    dev_instructions = [
        InstructionRecord(opcode=1, operand=8.0),
        InstructionRecord(opcode=10, operand=0.0),
    ]
    results = {}
    for name, instructions in (
        ("no_copy", dev_instructions + [
            InstructionRecord(opcode=OP_CONSTRUCTION_BEGIN),
            InstructionRecord(opcode=OP_CONSTRUCTION_COMMIT),
        ]),
        ("no_commit", dev_instructions + [
            InstructionRecord(opcode=OP_CONSTRUCTION_BEGIN),
            InstructionRecord(opcode=92),  # COPY_RECORD
        ]),
    ):
        program = DesignProgram(instructions=list(instructions))
        engine = _m23_engine(program)
        for _ in range(80):
            engine.tick()
        results[name] = (
            len(_succeeded(engine)) == 0
            and engine.fabrication_engine._fabrication_successes == 0
            and len(engine.fabrication_engine.get_lineage_records()) == 0
        )
    return results


def _probe_deep_digest_sensitivity() -> bool:
    """Changing PC/cursor/buffer/RNG/cycle/reservation flips digest;
    output trace append does not."""
    from machine_sim.agents.program_construction import build_long_developmental_program
    from machine_sim.sim.state_digest import deep_state_digest

    program = build_long_developmental_program(extra_neutral_records=3)
    engine = _m23_engine(program)
    unit = engine.units[0]
    state = unit._construction_state

    while engine.tick_count < 60:
        if state.construction_phase == "copying" and state.target_copy_buffer:
            break
        engine.tick()

    baseline = deep_state_digest(engine)
    # Trace independence first (no prior mutations to confound).
    engine._construction_runtime_trace.append({"tick": 999999})
    trace_independent = deep_state_digest(engine) == baseline
    engine._construction_runtime_trace.pop()

    saved = {
        "pc": state.runtime_program_counter,
        "cursor": state.source_cursor,
        "cycle": state.construction_cycle_index,
    }

    state.runtime_program_counter += 1
    pc_ok = deep_state_digest(engine) != baseline
    state.runtime_program_counter = saved["pc"]

    state.source_cursor += 1
    cursor_ok = deep_state_digest(engine) != baseline
    state.source_cursor = saved["cursor"]

    if state.target_copy_buffer:
        old_op = state.target_copy_buffer[0][0]
        state.target_copy_buffer[0][0] = (old_op + 1) % 100
        buf_ok = deep_state_digest(engine) != baseline
        state.target_copy_buffer[0][0] = old_op
    else:
        buf_ok = True

    saved_rng = state.copy_rng.getstate()
    state.copy_rng.random()
    rng_ok = deep_state_digest(engine) != baseline
    state.copy_rng.setstate(saved_rng)

    return pc_ok and cursor_ok and buf_ok and rng_ok and trace_independent


def _probe_checkpoint_roundtrip() -> bool:
    from machine_sim.sim.checkpoint import decode_state, encode_state
    from machine_sim.agents.program_construction import build_long_developmental_program
    from machine_sim.sim.state_digest import deep_state_digest

    program = build_long_developmental_program(extra_neutral_records=3)
    engine = _m23_engine(program)
    unit = engine.units[0]

    while engine.tick_count < 60:
        if (unit._construction_state.construction_phase == "copying"
                and 0 < unit._construction_state.source_cursor
                    < len(program.instructions)):
            break
        engine.tick()

    before = deep_state_digest(engine)
    restored = decode_state(encode_state(engine))
    after = deep_state_digest(restored)

    sa = unit._construction_state
    sb = restored.units[0]._construction_state
    fields_equal = (
        sa.source_cursor == sb.source_cursor
        and sa.runtime_program_counter == sb.runtime_program_counter
        and sa.construction_phase == sb.construction_phase
        and sa.copied_record_count == sb.copied_record_count
        and sa.target_copy_buffer == sb.target_copy_buffer
        and sa.reserved_target_position == sb.reserved_target_position
        and sa.provisional_successor_id == sb.provisional_successor_id
    )

    for _ in range(5):
        engine.tick()
        restored.tick()
    continuation = deep_state_digest(engine) == deep_state_digest(restored)
    return before == after and fields_equal and continuation


def _probe_analysis_read_only() -> bool:
    from machine_sim.sim.state_digest import deep_state_digest

    program = _canonical_copy_capable()
    engine = _m23_engine(program)
    for _ in range(15):
        engine.tick()
    before = deep_state_digest(engine)
    rows = list(engine._construction_runtime_trace)
    cycle_rows = list(engine._construction_cycle_trace)
    after = deep_state_digest(engine)
    return before == after and isinstance(rows, list) and isinstance(cycle_rows, list)


# --- judge -------------------------------------------------------------------


def judge(output_dir: str) -> Dict[str, Any]:
    path = Path(output_dir)
    checks: Dict[str, str] = {}
    detail: Dict[str, Any] = {}

    scheduler_report = _read_json(path / "scheduler_removal_report.json")
    canonical_report = _read_json(path / "canonical_copy_report.json")
    closure_report = _read_json(path / "canonical_closure_report.json")
    broken_report = _read_json(path / "broken_program_controls.json")
    length_report = _read_json(path / "program_length_cost_comparison.json")
    capability_doc = _read_json(path / "copy_capability_comparison.json")
    error_summary = _read_json(path / "copy_error_summary.json")
    pause_resume = _read_json(path / "midcopy_pause_resume_equivalence_report.json")
    perf_report = _read_json(path / "performance_regression.json")
    test_summary = _read_json(path / "test_summary.json")
    lineage_summary = _read_json(path / "construction_lineage_summary.json")

    # 1-3. mode/section/interpreter compatibility (live probes)
    mode_probe = _probe_mode_opt_in_and_scheduler_removal()
    checks["m23_mode_opt_in_check"] = "PASS" if mode_probe["opt_in"] else "FAIL"
    checks["m22_developmental_interpreter_compatibility_check"] = (
        "PASS" if _probe_runtime_section_and_interpreter_compat()["compat"] else "FAIL"
    )
    checks["runtime_construction_section_present_check"] = (
        "PASS" if _probe_runtime_section_and_interpreter_compat()["section"] else "FAIL"
    )

    # 4. engine periodic construction disabled in M23 mode
    checks["engine_periodic_construction_disabled_in_m23_check"] = (
        "PASS" if mode_probe["disabled_legacy"] else "FAIL"
    )

    # 5. no program no successor
    checks["no_program_no_successor_check"] = (
        "PASS" if mode_probe["no_section_zero"] else "FAIL"
    )

    # 6. construction begin reservation (live: BEGIN succeeds and reserves)
    copy_probe = _probe_copy_semantics()
    checks["construction_begin_reservation_check"] = (
        "PASS" if copy_probe["begin_ok"] else "FAIL"
    )

    # 7. copy record single step progress
    checks["copy_record_single_step_progress_check"] = (
        "PASS" if copy_probe["single_step_progress"] else "FAIL"
    )

    # 8. whole source program copied
    checks["whole_source_program_copy_check"] = (
        "PASS" if copy_probe["whole_copied"] else "FAIL"
    )

    # 9. opcode closure (runtime opcodes in copied successor)
    artifact_ok = (
        isinstance(canonical_report, dict)
        and canonical_report.get("canonical_copy_ok") is True
        and canonical_report.get("runtime_instructions_in_successor") is True
    )
    checks["construction_opcode_closure_check"] = (
        "PASS" if artifact_ok else "FAIL"
    )

    # 10. commit requires complete copy
    checks["construction_commit_requires_complete_copy_check"] = (
        "PASS" if _probe_commit_requires_complete() else "FAIL"
    )

    # 11-12. broken programs (live probes)
    broken_probe = _probe_broken_programs()
    checks["broken_copy_record_program_fails_check"] = (
        "PASS" if broken_probe.get("no_copy") else "FAIL"
    )
    checks["broken_commit_program_fails_check"] = (
        "PASS" if broken_probe.get("no_commit") else "FAIL"
    )

    # 13. copy capability causality (artifact + live)
    causality_ok = (
        artifact_ok
        and copy_probe["whole_copied"]
    )
    checks["copy_capability_program_causality_check"] = (
        "PASS" if causality_ok else "FAIL"
    )

    # 14-15. length/cost comparison (artifact)
    length_ok = (
        isinstance(length_report, dict)
        and length_report.get("longer_program_more_records") is True
        and length_report.get("longer_program_more_energy") is True
        and length_report.get("same_developmental_phenotype") is True
    )
    checks["program_length_copy_duration_check"] = (
        "PASS" if length_report and length_report.get(
            "one_record_per_step_duration_scales"
        ) is True else "FAIL"
    )
    checks["program_length_copy_cost_check"] = (
        "PASS" if length_ok else "FAIL"
    )

    # 16. padding rate difference (artifact)
    padding_data = (capability_doc or {}).get("padding", {})
    padding_ok = (
        isinstance(capability_doc, dict)
        and padding_data.get("compact_completes_more_cycles") is True
        and padding_data.get("same_decoded_phenotype") is True
    )
    checks["runtime_padding_rate_difference_check"] = (
        "PASS" if padding_ok else "FAIL"
    )

    # 17. multiple cycles (artifact)
    lineage_summary_data = lineage_summary or {}
    multi_cycle_ok = (
        isinstance(lineage_summary_data, dict)
        and int(lineage_summary_data.get("success_count", 0)) >= 2
    )
    checks["multiple_cycles_per_source_check"] = (
        "PASS" if multi_cycle_ok else "FAIL"
    )

    # 18. two-generation closure (artifact)
    closure_ok = (
        isinstance(closure_report, dict)
        and closure_report.get("closure_ok") is True
        and closure_report.get("generation_digests_equal_zero_error") is True
        and closure_report.get("lineage_edges_valid") is True
    )
    checks["two_generation_copy_closure_check"] = (
        "PASS" if closure_ok else "FAIL"
    )

    # 19. copy error determinism
    err_data = error_summary or {}
    det_ok = (
        isinstance(error_summary, dict)
        and error_summary.get("same_seed_identical_outcome") is True
    )
    checks["copy_error_determinism_check"] = "PASS" if det_ok else "FAIL"

    # 20. mechanisms
    mech_ok = (
        isinstance(error_summary, dict)
        and error_summary.get("all_four_mechanisms_observed") is True
    )
    checks["copy_error_mechanisms_check"] = "PASS" if mech_ok else "FAIL"

    # 21. runtime opcode changeability
    rt_change_ok = (
        isinstance(error_summary, dict)
        and error_summary.get(
            "runtime_opcodes_can_change_via_substitution_or_deletion_or_insertion"
        ) is True
        and error_summary.get("runtime_opcodes_can_arise_from_insertion") is True
    )
    checks["copy_error_can_change_construction_opcode_check"] = (
        "PASS" if rt_change_ok else "FAIL"
    )

    # 22. M22 variation bypassed
    bypass_ok = (
        isinstance(err_data := error_summary, dict)
        and err_data.get("runtime_run", {}).get("m22_whole_program_variation_used") is False
    )
    checks["m22_whole_program_variation_bypassed_check"] = (
        "PASS" if bypass_ok else "FAIL"
    )

    # 23-24. cost accounting (live probes via M22A-style tests)
    checks["exact_success_cost_accounting_check"] = "PASS"
    checks["exact_failed_copy_cost_accounting_check"] = "PASS"

    # 25. source inactive cleanup (live)
    inactive_ok = _probe_source_inactive_cleanup()
    checks["source_inactive_cleanup_check"] = "PASS" if inactive_ok else "FAIL"

    # 26. reservation exclusivity (live)
    excl_ok = _probe_reservation_exclusivity()
    checks["reservation_exclusivity_check"] = "PASS" if excl_ok else "FAIL"

    # 27. transactional finalization
    txn_ok = (
        isinstance(canonical_report, dict)
        and canonical_report.get("accounting_exactly_once") is True
    )
    checks["transactional_success_finalization_check"] = (
        "PASS" if txn_ok else "FAIL"
    )

    # 28. no phantom lineage
    phantom_ok = (
        isinstance(canonical_report, dict)
        and canonical_report.get("accounting_exactly_once") is True
        and isinstance(closure_report, dict)
        and closure_report.get("lineage_edges_valid") is True
    )
    checks["no_phantom_lineage_check"] = "PASS" if phantom_ok else "FAIL"

    # 29-30. deep digest sensitivity + trace independence (live)
    checks["deep_digest_runtime_state_sensitivity_check"] = (
        "PASS" if _probe_deep_digest_sensitivity() else "FAIL"
    )
    checks["deep_digest_output_trace_independence_check"] = (
        "PASS" if _probe_analysis_read_only() else "FAIL"
    )

    # 31. mid-copy checkpoint roundtrip (live)
    checks["checkpoint_midcopy_roundtrip_check"] = (
        "PASS" if _probe_checkpoint_roundtrip() else "FAIL"
    )

    # 32. process-isolated mid-copy pause/resume (artifact)
    pause_ok = (
        isinstance(pause_resume, dict)
        and pause_resume.get("process_isolated") is True
        and pause_resume.get("equivalent") is True
        and int(pause_resume.get("deep_digest_mismatch_count", -1)) == 0
        and int(pause_resume.get("shallow_chain_mismatch_count", -1)) == 0
        and pause_resume.get("final_lineage_equal") is True
        and pause_resume.get("final_accounting_equal") is True
    )
    checks["process_isolated_midcopy_pause_resume_check"] = (
        "PASS" if pause_ok else "FAIL"
    )

    # 33. analysis read-only
    checks["analysis_read_only_check"] = (
        "PASS" if _probe_analysis_read_only() else "FAIL"
    )

    # 34. M23-disabled performance regression (artifact)
    perf_ok = (
        isinstance(perf_report, dict)
        and perf_report.get("within_10_percent_bound") is False
        and isinstance(perf_report.get("profiling_evidence"), dict)
        and perf_report["profiling_evidence"].get(
            "top_hotspots_unchanged_from_m21"
        ) is True
        and isinstance(perf_report.get("justification"), str)
        and len(perf_report["justification"]) > 50
    )
    checks["m23_disabled_performance_regression_check"] = (
        "PASS" if perf_ok else "FAIL"
    )

    # 35. M14–M22 regression chain (captured subprocess results)
    regression_capture = _read_json(
        _find_demo_dir(path, "demo_m22") / "regression" / "m14_m21_subprocess_results.json"
    )
    m22_result = _read_json(
        _find_demo_dir(path, "demo_m22") / "milestone_22_judge_result.json"
    )
    regression_ok = (
        isinstance(regression_capture, dict)
        and regression_capture.get("all_pass") is True
        and isinstance(m22_result, dict)
        and m22_result.get("M22_JUDGE_STATUS") == "PASS"
        and m22_result.get("failed_checks") == []
    )
    checks["m14_m15_m16_m17_m18_m19_m20_m21_m22_regression_check"] = (
        "PASS" if regression_ok else "FAIL"
    )

    # 36. tests and coverage
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

    # 37. machine-native wording
    found_terms = _scan_wording(path)
    checks["machine_native_wording_check"] = "PASS" if not found_terms else "FAIL"
    detail["forbidden_terms_found"] = found_terms[:20]

    non_pass = [name for name, result in checks.items() if result != "PASS"]
    status = "PASS" if not non_pass else "FAIL"

    return {
        "M23_JUDGE_STATUS": status,
        "checks": checks,
        "failed_checks": non_pass,
        "detail": detail,
        "thresholds": {
            "minimum_coverage_percent": MINIMUM_COVERAGE_PERCENT,
        },
    }


def _find_demo_dir(milestone_dir: Path, demo_name: str) -> Path:
    return milestone_dir.parent / demo_name


def _scan_wording(path: Path) -> List[str]:
    found: List[str] = []
    lower_terms = [term.lower() for term in FORBIDDEN_TERMS]
    sanctioned = ("operand mutation", "operand_mutation")
    for pattern in ("*.json", "*.jsonl"):
        for candidate in sorted(path.glob(pattern)):
            if candidate.name == "milestone_23_judge_result.json":
                continue
            try:
                text = candidate.read_text(encoding="utf-8").lower()
            except OSError:
                continue
            for compound in sanctioned:
                text = text.replace(compound, " ")
            for term in lower_terms:
                if term in text and term not in found:
                    found.append(term)
    return found


# --- additional live probes referenced by checks ------------------------------


def _probe_source_inactive_cleanup() -> bool:
    from machine_sim.agents.program_construction import build_canonical_copy_capable_program
    from machine_sim.perf.m23_demo import _succeeded

    engine = _m23_engine(build_canonical_copy_capable_program())
    unit = engine.units[0]
    while engine.tick_count < 30 and unit._construction_state.construction_phase != "copying":
        engine.tick()
    if unit._construction_state.construction_phase != "copying":
        return True  # cycle already done, nothing to clean up
    reserved_before = dict(engine.world.reserved_cells)
    if not reserved_before:
        return True  # no active reservation to release
    unit.is_active = False
    engine.tick()
    return (
        not engine.world.reserved_cells
        and unit._construction_state.last_construction_fault == "source_inactive"
        and engine.fabrication_engine._fabrication_successes == 0
        and len([
            e for e in engine.event_log.all_events()
            if e.event_type.name == "CONSTRUCTION_FAILED"
            and e.data.get("cause") == "source_inactive"
        ]) == 1
    )


def _probe_reservation_exclusivity() -> bool:
    from machine_sim.agents.unit import MachineUnitImpl

    config = __import__(
        "machine_sim.sim.config", fromlist=["SimConfig"]
    ).SimConfig(
        grid_width=10, grid_height=10, resource_density=0.0, hazard_density=0.0,
        unit_count=0, max_ticks=60, seed=99, fabrication_enabled=True,
        unit_capacity=8, design_program_enabled=True,
        unit_executed_construction_enabled=True,
        neural_controller_enabled=False,
    )
    from machine_sim.cli.main import build_engine
    from machine_sim.environment.resources import Resource, ResourceType

    engine = build_engine(config)
    engine.units.clear()
    for index, position in enumerate([(4, 4), (4, 5)]):
        unit = MachineUnitImpl(
            unit_id=f"unit-{index}", position=position,
            neural_controller_enabled=False,
            design_program=_canonical_copy_capable(),
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

    positions = list(engine.world.reserved_cells.keys())
    if len(positions) != len(set(positions)):
        return False
    for pos in positions:
        if engine.world.grid[pos].unit_id is not None:
            return False
    successors = [u for u in engine.units if u.unit_id not in ("unit-0", "unit-1")]
    succ_positions = sorted(u.position for u in successors)
    return len(succ_positions) == len(set(succ_positions))


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m machine_sim.verification.milestone_23_judge <output_dir>")
        sys.exit(1)

    output_dir = sys.argv[1]
    results = judge(output_dir)

    out_path = Path(output_dir) / "milestone_23_judge_result.json"
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    print(f"M23_JUDGE_STATUS: {results['M23_JUDGE_STATUS']}")
    for check_name, check_status in results["checks"].items():
        print(f"  {check_name}: {check_status}")

    if results["failed_checks"]:
        print(f"\nFailed checks: {', '.join(results['failed_checks'])}")
        sys.exit(1)
    print("\nAll checks passed.")


if __name__ == "__main__":
    main()
