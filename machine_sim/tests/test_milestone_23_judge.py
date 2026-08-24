"""Negative and positive fixture tests for the independent M23 judge."""

from __future__ import annotations

import json
from pathlib import Path


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _build_fixture(base: Path) -> None:
    base.mkdir(parents=True, exist_ok=True)
    for name, rows in (
        ("construction_runtime_trace.jsonl", [{"tick": 1, "unit_id": "u"}]),
        ("program_copy_trace.jsonl", [{"tick": 1, "error_type": "opcode_substitution"}]),
        ("construction_cycle_trace.jsonl", [
            {"cycle_start_tick": 2, "cycle_end_tick": 14,
             "status": "complete", "successor_unit_id": "unit-0001"},
            {"cycle_start_tick": 26, "cycle_end_tick": 38,
             "status": "complete", "successor_unit_id": "unit-0002"},
        ]),
    ):
        with open(base / name, "w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, sort_keys=True) + "\n")

    _write_json(base / "scheduler_removal_report.json",
                {"zero_successors_without_runtime_section": True})
    _write_json(base / "canonical_copy_report.json", {
        "canonical_copy_ok": True,
        "accounting_exactly_once": True,
        "runtime_instructions_in_successor": True,
        "whole_source_copied_digest_equal": True,
        "success_count": 1,
    })
    _write_json(base / "canonical_closure_report.json", {
        "closure_ok": True,
        "generation_digests_equal_zero_error": True,
        "lineage_edges_valid": True,
        "generations_present": [0, 1, 2],
        "b_construction_self_executed": True,
        "each_commit_matches_registered_unit": True,
    })
    _write_json(base / "broken_program_controls.json", {
        "no_copy_record_fails": True, "no_commit_produces_no_successful_lineage": True,
    })
    _write_json(base / "program_length_cost_comparison.json", {
        "longer_program_more_records": True, "longer_program_more_energy": True,
        "same_developmental_phenotype": True,
        "one_record_per_step_duration_scales": True,
    })
    _write_json(base / "copy_capability_comparison.json", {
        "padding": {"compact_completes_more_cycles": True, "same_decoded_phenotype": True},
    })
    _write_json(base / "construction_lineage_summary.json",
                {"total_units": 5, "active_units": 4, "success_count": 6,
                 "attempt_count": 8, "lineage_records": 3,
                 "lineage_edges": [], "copy_error_count_total": 7})
    _write_json(base / "copy_error_summary.json", {
        "same_seed_identical_outcome": True, "all_four_mechanisms_observed": True,
        "runtime_opcodes_can_change_via_substitution_or_deletion_or_insertion": True,
        "runtime_opcodes_can_arise_from_insertion": True,
        "runtime_run": {"m22_whole_program_variation_used": False, "copy_error_count": 5},
    })
    _write_json(base / "midcopy_pause_resume_equivalence_report.json", {
        "process_isolated": True, "equivalent": True,
        "deep_digest_mismatch_count": 0, "shallow_chain_mismatch_count": 0,
        "final_lineage_equal": True, "final_accounting_equal": True,
    })
    _write_json(base / "performance_regression.json", {
        "within_10_percent_bound": False,
        "profiling_evidence": {"top_hotspots_unchanged_from_m21": True},
        "justification": "Thermal variance on host; no M23 code in profiler output.",
    })
    _write_json(base / "test_summary.json",
                {"passed": 650, "failed": 0, "coverage_percent": 79.5})

    # Sibling M22 evidence
    m22_dir = base.parent / "demo_m22"
    _write_json(m22_dir / "regression" / "m14_m21_subprocess_results.json",
                {"all_pass": True, "results": {
                    f"m{n}": {"status": "PASS", "exit_code": 0, "first_line": "", "command": ""}
                    for n in range(14, 22)
                }})
    _write_json(m22_dir / "milestone_22_judge_result.json",
                {"M22_JUDGE_STATUS": "PASS", "failed_checks": [], "checks": {}})


def test_judge_passes_valid_fixture(tmp_path: Path):
    from machine_sim.verification.milestone_23_judge import judge
    base = tmp_path / "demo_m23"
    _build_fixture(base)
    result = judge(str(base))
    assert result["M23_JUDGE_STATUS"] == "PASS", result["failed_checks"]
    assert result["failed_checks"] == []


def test_judge_fails_on_pause_resume_mismatch(tmp_path: Path):
    from machine_sim.verification.milestone_23_judge import judge
    base = tmp_path / "demo_m23"
    _build_fixture(base)
    p = base / "midcopy_pause_resume_equivalence_report.json"
    doc = json.loads(p.read_text(encoding="utf-8"))
    doc["deep_digest_mismatch_count"] = 3
    doc["equivalent"] = False
    p.write_text(json.dumps(doc), encoding="utf-8")
    result = judge(str(base))
    assert "process_isolated_midcopy_pause_resume_check" in result["failed_checks"]


def test_judge_fails_on_regression_failure(tmp_path: Path):
    from machine_sim.verification.milestone_23_judge import judge
    base = tmp_path / "demo_m23"
    _build_fixture(base)
    capture = base.parent / "demo_m22" / "regression" / "m14_m21_subprocess_results.json"
    doc = json.loads(capture.read_text(encoding="utf-8"))
    doc["all_pass"] = False
    doc["results"]["m20"]["status"] = "FAIL"
    capture.write_text(json.dumps(doc), encoding="utf-8")
    result = judge(str(base))
    assert result["M23_JUDGE_STATUS"] == "FAIL"
    assert "m14_m15_m16_m17_m18_m19_m20_m21_m22_regression_check" in result["failed_checks"]


def test_judge_fails_on_coverage_below_threshold(tmp_path: Path):
    from machine_sim.verification.milestone_23_judge import judge
    base = tmp_path / "demo_m23"
    _build_fixture(base)
    _write_json(base / "test_summary.json",
                {"passed": 600, "failed": 0, "coverage_percent": 74.0})
    result = judge(str(base))
    assert result["M23_JUDGE_STATUS"] == "FAIL"
    assert "tests_and_coverage_check" in result["failed_checks"]


def test_judge_fails_on_forbidden_wording(tmp_path: Path):
    from machine_sim.verification.milestone_23_judge import judge
    base = tmp_path / "demo_m23"
    _build_fixture(base)
    summary = base / "construction_lineage_summary.json" if (base / "construction_lineage_summary.json").exists() else base / "scheduler_removal_report.json"
    doc = json.loads(summary.read_text(encoding="utf-8")) if summary.exists() else {}
    doc["note"] = "genome analysis"
    summary.write_text(json.dumps(doc), encoding="utf-8")
    result = judge(str(base))
    assert result["M23_JUDGE_STATUS"] == "FAIL"
    assert "machine_native_wording_check" in result["failed_checks"]


