"""Negative and positive fixture tests for the independent M22 judge."""

from __future__ import annotations

import json
from pathlib import Path


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _build_fixture(base: Path) -> None:
    transfer_rows = [
        {
            "tick": tick,
            "source_unit_id": f"unit-0",
            "successor_unit_id": f"unit-1{tick}",
            "source_program_digest": "a" * 64,
            "successor_program_digest": ("a" * 64 if tick == 300 else "b" * 64),
            "source_program_length": 7,
            "successor_program_length": 7 + tick % 2,
            "variation_operations": [],
            "execution_status": "complete",
            "executed_instruction_count": 7,
            "execution_cost": 0.57,
            "decoded_hidden_size": 16,
            "decoded_recurrent_density": 1.0,
            "decoded_plasticity_rate": 0.01,
            "decoded_plasticity_enabled": True,
            "phenotype_changed": tick != 300,
        }
        for tick in (300, 600, 900)
    ]
    base.mkdir(parents=True, exist_ok=True)
    for name, rows in (
        ("design_program_transfer_trace.jsonl", transfer_rows),
        ("design_program_execution_trace.jsonl", [
            {"tick": t, "unit_id": "x", "status": "complete",
             "executed_instruction_count": 7, "final_program_counter": 7,
             "execution_cost": 0.57, "fault_records": []}
            for t in (300, 600, 900)
        ]),
        ("design_program_distribution_trace.jsonl", [{"tick": 100}]),
        ("design_program_initial_state.jsonl", [
            {"unit_id": "unit-000", "program_digest": "z" * 64, "program_length": 7},
        ]),
    ):
        with open(base / name, "w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, sort_keys=True) + "\n")

    _write_json(
        base / "design_program_compatibility_report.json",
        {
            "compatible": True,
            "descriptor_field_equality": True,
            "shallow_chain_equal_throughout": True,
            "projection_equal_throughout": True,
            "sample_count": 6,
            "descriptor_pairs": [],
        },
    )
    _write_json(
        base / "design_program_variation_summary.json",
        {
            "transfer_count": 3,
            "successful_transfer_count": 3,
            "content_changed_transfer_count": 2,
            "zero_change_transfer_count": 1,
            "length_changed_transfer_count": 1,
            "phenotype_changed_transfer_count": 2,
            "distinct_decoded_architecture_count": 2,
            "out_of_bounds_decoded_count": 0,
            "total_program_execution_cost": 1.71,
            "variation_operation_counts": {"substitution": 2},
        },
    )
    _write_json(
        base / "design_program_lineage_summary.json",
        {"initial_program_count": 4, "interpreter_crash_count": 0},
    )
    _write_json(
        base / "design_program_run_summary.json",
        {
            "all_demonstrations_met": True,
            "evidence": {key: True for key in (
                "several_successful_transfers", "zero_change_transfer_present",
                "content_change_present", "length_change_present",
                "phenotype_change_present",
                "two_or_more_distinct_decoded_architectures",
                "no_out_of_bounds_architecture", "no_interpreter_crash",
            )},
        },
    )
    _write_json(
        base / "program_pause_resume_equivalence_report.json",
        {
            "process_isolated": True,
            "equivalent": True,
            "mismatch_count": 0,
            "shallow_run_digest_mismatch_count": 0,
            "sample_count": 9,
            "resumed_span": 275,
        },
    )
    _write_json(
        base / "design_program_performance.json",
        {"canonical_programs_per_second": 63000.0},
    )
    _write_json(
        base / "regression" / "m14_m21_subprocess_results.json",
        {
            "all_pass": True,
            "results": {
                f"m{n}": {"status": "PASS", "exit_code": 0, "first_line": "", "command": ""}
                for n in range(14, 22)
            },
        },
    )
    _write_json(
        base / "test_summary.json",
        {"passed": 600, "failed": 0, "coverage_percent": 79.1},
    )

    # Sibling M21 oracle evidence for m21_oracle_regression_check.
    m21_dir = base.parent / "demo_m21" / "determinism"
    series = {
        name: {"sample_count": 10, "mismatch_count": 0, "final_equal": True}
        for name in ("a", "b", "c-uninterrupted", "c-pause-resume")
    }
    _write_json(
        m21_dir / "deep_equivalence_report.json",
        {
            "series": series,
            "sample_count": 40,
            "mismatch_count": 0,
            "zero_mismatch_acceptance": True,
        },
    )
    _write_json(
        m21_dir / "pause_resume_deep_equivalence_report.json",
        {
            "process_isolated": True,
            "deep_and_shallow_equal": True,
            "mismatch_count": 0,
            "shallow_run_digest_mismatch_count": 0,
            "sample_count": 9,
            "resumed_span": 275,
        },
    )


def test_judge_passes_valid_fixture_set(tmp_path: Path):
    from machine_sim.verification.milestone_22_judge import judge

    base = tmp_path / "demo_m22"
    _build_fixture(base)
    result = judge(str(base))
    assert result["M22_JUDGE_STATUS"] == "PASS", result["failed_checks"]
    assert result["failed_checks"] == []


def test_judge_fails_when_pause_resume_report_missing(tmp_path: Path):
    from machine_sim.verification.milestone_22_judge import judge

    base = tmp_path / "demo_m22"
    _build_fixture(base)
    (base / "program_pause_resume_equivalence_report.json").unlink()
    result = judge(str(base))
    assert result["M22_JUDGE_STATUS"] == "FAIL"
    assert "pause_resume_program_equivalence_check" in result["failed_checks"]


def test_judge_fails_on_pause_resume_mismatch(tmp_path: Path):
    from machine_sim.verification.milestone_22_judge import judge

    base = tmp_path / "demo_m22"
    _build_fixture(base)
    report_path = base / "program_pause_resume_equivalence_report.json"
    document = json.loads(report_path.read_text(encoding="utf-8"))
    document["mismatch_count"] = 2
    document["equivalent"] = False
    report_path.write_text(json.dumps(document), encoding="utf-8")
    result = judge(str(base))
    assert result["M22_JUDGE_STATUS"] == "FAIL"
    assert "pause_resume_program_equivalence_check" in result["failed_checks"]


def test_judge_fails_on_insufficient_successful_transfers(tmp_path: Path):
    from machine_sim.verification.milestone_22_judge import judge

    base = tmp_path / "demo_m22"
    _build_fixture(base)
    trace = base / "design_program_transfer_trace.jsonl"
    rows = trace.read_text(encoding="utf-8").splitlines()
    trace.write_text(rows[0] + "\n", encoding="utf-8")
    variation = base / "design_program_variation_summary.json"
    document = json.loads(variation.read_text(encoding="utf-8"))
    document["successful_transfer_count"] = 1
    variation.write_text(json.dumps(document), encoding="utf-8")
    run_summary = base / "design_program_run_summary.json"
    document = json.loads(run_summary.read_text(encoding="utf-8"))
    document["evidence"]["several_successful_transfers"] = False
    run_summary.write_text(json.dumps(document), encoding="utf-8")
    result = judge(str(base))
    assert result["M22_JUDGE_STATUS"] == "FAIL"
    assert "successor_program_transfer_check" in result["failed_checks"]


def test_judge_fails_when_regression_capture_missing_or_incomplete(tmp_path: Path):
    from machine_sim.verification.milestone_22_judge import judge

    base = tmp_path / "demo_m22"
    _build_fixture(base)
    capture_path = base / "regression" / "m14_m21_subprocess_results.json"
    document = json.loads(capture_path.read_text(encoding="utf-8"))
    document["results"]["m17"]["status"] = "FAIL"
    capture_path.write_text(json.dumps(document), encoding="utf-8")
    result = judge(str(base))
    assert result["M22_JUDGE_STATUS"] == "FAIL"
    assert "m14_m15_m16_m17_m18_m19_m20_m21_regression_check" in result["failed_checks"]


def test_judge_fails_when_coverage_below_threshold(tmp_path: Path):
    from machine_sim.verification.milestone_22_judge import judge

    base = tmp_path / "demo_m22"
    _build_fixture(base)
    _write_json(
        base / "test_summary.json",
        {"passed": 600, "failed": 0, "coverage_percent": 74.0},
    )
    result = judge(str(base))
    assert result["M22_JUDGE_STATUS"] == "FAIL"
    assert "tests_and_coverage_check" in result["failed_checks"]


def test_judge_fails_on_forbidden_wording(tmp_path: Path):
    from machine_sim.verification.milestone_22_judge import judge

    base = tmp_path / "demo_m22"
    _build_fixture(base)
    lineage = base / "design_program_lineage_summary.json"
    document = json.loads(lineage.read_text(encoding="utf-8"))
    document["note"] = "genome analysis"
    lineage.write_text(json.dumps(document), encoding="utf-8")
    result = judge(str(base))
    assert result["M22_JUDGE_STATUS"] == "FAIL"
    assert "machine_native_wording_check" in result["failed_checks"]


def test_judge_sanctioned_compound_not_flagged(tmp_path: Path):
    from machine_sim.verification.milestone_22_judge import _scan_wording

    base = tmp_path / "demo_m22"
    _build_fixture(base)
    # The spec-mandated compound appears in real artifacts and must not trip
    # the screen, while standalone biological vocabulary still does.
    assert "mutation" not in _scan_wording(base)
