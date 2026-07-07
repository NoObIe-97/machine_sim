"""Independent M15 judge: evaluates multi-generation adaptive trace evolution artifacts."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

FORBIDDEN_TERMS = [
    "human", "social", "society", "community", "communication", "message",
    "language", "meaning", "knowledge", "learning", "teaching",
    "strategy", "trust", "cooperation", "competition", "conflict",
    "agreement", "consensus", "population", "evolution", "mutation",
    "inheritance", "offspring", "species", "fitness",
    "parent", "child",
]

REQUIRED_ARTIFACTS = [
    "adaptive_trajectory_summary.json",
    "generation_adaptive_state_trace.jsonl",
    "adaptive_transfer_compare.json",
    "unit_adaptive_state_trace.jsonl",
    "action_distribution_trace.jsonl",
    "local_feedback_trace.jsonl",
    "descendant_adaptive_state_trace.jsonl",
    "resource_hazard_field_summary.json",
]


def judge(output_dir: str) -> Dict[str, Any]:
    """Run all M15 judge checks."""
    path = Path(output_dir)
    results: Dict[str, Any] = {}
    checks: Dict[str, str] = {}

    # Load trajectory summary
    summary_path = path / "adaptive_trajectory_summary.json"
    summary: Dict[str, Any] = {}
    if summary_path.exists():
        summary = json.loads(summary_path.read_text())

    run_params = summary.get("run_parameters", {})
    transfer_summary = summary.get("transfer_summary", {})
    gen_summary = summary.get("generation_summary", {})

    # 1. long_run_ticks_check: run_ticks >= 30000
    max_ticks = run_params.get("max_ticks", 0)
    checks["long_run_ticks_check"] = "PASS" if max_ticks >= 30000 else "FAIL"

    # 2. large_field_check: grid >= 120x120
    grid_w = run_params.get("grid_width", 0)
    grid_h = run_params.get("grid_height", 0)
    checks["large_field_check"] = "PASS" if grid_w >= 120 and grid_h >= 120 else "FAIL"

    # 3. transfer_count_check: >= 5 transfers
    transfer_count = transfer_summary.get("transfer_count", 0)
    checks["transfer_count_check"] = "PASS" if transfer_count >= 5 else "FAIL"

    # 4. generation_span_check: >= 3 distinct generation indices
    gen_span = gen_summary.get("generation_index_span", 0)
    checks["generation_span_check"] = "PASS" if gen_span >= 3 else "FAIL"

    # 5. trajectory_artifact_schema_check: required artifacts present
    all_present = all((path / f).exists() for f in REQUIRED_ARTIFACTS)
    checks["trajectory_artifact_schema_check"] = "PASS" if all_present else "FAIL"

    # 6. adaptive_state_delta_check: transfer deltas numeric and nonzero
    delta_summary = summary.get("adaptive_state_delta_summary", {})
    has_nonzero = any(abs(v) > 1e-6 for v in delta_summary.values()) if delta_summary else False
    checks["adaptive_state_delta_check"] = "PASS" if has_nonzero else "FAIL"

    # 7. trajectory_continuity_check: continuity score numeric and bounded
    cont_summary = summary.get("trajectory_continuity_summary", {})
    cont_score = cont_summary.get("score", -1)
    checks["trajectory_continuity_check"] = "PASS" if 0.0 <= cont_score <= 1.0 else "FAIL"

    # 8. signal_observation_check: signal observations > 0
    gen_trace_path = path / "generation_adaptive_state_trace.jsonl"
    signal_ok = False
    if gen_trace_path.exists():
        lines = [l for l in gen_trace_path.read_text().strip().split("\n") if l]
        # Check if any transfer record has signal-related deltas
        for line in lines[:50]:
            try:
                rec = json.loads(line)
                delta = rec.get("adaptive_state_delta", {})
                if any("signal" in k and abs(v) > 1e-6 for k, v in delta.items()):
                    signal_ok = True
                    break
            except json.JSONDecodeError:
                continue
    # Also check the trajectory summary for signal adaptation
    signal_summary = summary.get("signal_adaptation_summary", {})
    if any(abs(v) > 1e-6 for v in signal_summary.values()) if signal_summary else False:
        signal_ok = True
    checks["signal_observation_check"] = "PASS" if signal_ok else "FAIL"

    # 9. late_run_activity_check: active source or successor near late-run
    late_survival = summary.get("late_run_survival_summary", {})
    active_count = late_survival.get("final_active_count", 0)
    checks["late_run_activity_check"] = "PASS" if active_count > 0 else "FAIL"

    # 10. reference_comparison_check: nonzero structural difference
    compare_path = path / "adaptive_transfer_compare.json"
    compare_ok = False
    if compare_path.exists():
        compare = json.loads(compare_path.read_text())
        enabled_count = compare.get("transfer_enabled_count", 0)
        ref_count = compare.get("reference_transfer_count", 0)
        span_delta = compare.get("generation_index_span_delta", 0)
        compare_ok = (enabled_count != ref_count) or (span_delta != 0)
    checks["reference_comparison_check"] = "PASS" if compare_ok else "FAIL"

    # 11. bounded_artifact_size_check: JSONL traces bounded
    max_lines = 0
    for f in path.glob("*.jsonl"):
        line_count = len([l for l in f.read_text().strip().split("\n") if l])
        max_lines = max(max_lines, line_count)
    checks["bounded_artifact_size_check"] = "PASS" if max_lines < 50000 else "FAIL"

    # 12. machine_native_wording_check: no forbidden terms
    all_text = ""
    for f in path.glob("*.json"):
        all_text += f.read_text().lower()
    for f in path.glob("*.jsonl"):
        all_text += f.read_text().lower()
    found_forbidden = [t for t in FORBIDDEN_TERMS if t in all_text]
    checks["machine_native_wording_check"] = "PASS" if not found_forbidden else "FAIL"

    # Overall
    failed = [k for k, v in checks.items() if v == "FAIL"]
    status = "PASS" if not failed else "FAIL"

    results["M15_JUDGE_STATUS"] = status
    results["checks"] = checks
    results["failed_checks"] = failed
    results["thresholds"] = {
        "min_ticks": 30000,
        "min_grid_width": 120,
        "min_grid_height": 120,
        "min_transfer_count": 5,
        "min_generation_span": 3,
        "min_feedback_entries": 1,
    }
    return results


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m machine_sim.verification.milestone_15_judge <output_dir>")
        sys.exit(1)

    output_dir = sys.argv[1]
    results = judge(output_dir)

    # Write result
    out_path = Path(output_dir) / "milestone_15_judge_result.json"
    out_path.write_text(json.dumps(results, indent=2))

    print(f"M15_JUDGE_STATUS: {results['M15_JUDGE_STATUS']}")
    for check, status in results["checks"].items():
        print(f"  {check}: {status}")

    if results["failed_checks"]:
        print(f"\nFailed checks: {', '.join(results['failed_checks'])}")
        sys.exit(1)
    print("\nAll checks passed.")


if __name__ == "__main__":
    main()
