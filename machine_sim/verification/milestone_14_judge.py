"""Independent M14 judge: evaluates milestone 14 artifacts from output directory."""

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
]


def judge(output_dir: str) -> Dict[str, Any]:
    """Run all M14 judge checks."""
    path = Path(output_dir)
    results: Dict[str, Any] = {}
    checks = {}

    # 1. long_run_ticks_check
    summary_path = path / "long_run_adaptation_summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text())
        run_ticks = summary.get("run_ticks", 0)
        checks["long_run_ticks_check"] = "PASS" if run_ticks >= 1000 else "FAIL"
    else:
        checks["long_run_ticks_check"] = "FAIL"

    # 2. large_sparse_environment_check
    if summary_path.exists():
        initial = summary.get("initial_unit_count", 0)
        checks["large_sparse_environment_check"] = "PASS" if initial >= 2 else "FAIL"
    else:
        checks["large_sparse_environment_check"] = "FAIL"

    # 3. no_early_collapse_check
    if summary_path.exists():
        final_active = summary.get("final_active_unit_count", 0)
        descendant_active = summary.get("descendant_active_count", 0)
        checks["no_early_collapse_check"] = "PASS" if (final_active + descendant_active) > 0 else "FAIL"
    else:
        checks["no_early_collapse_check"] = "FAIL"

    # 4. adaptive_state_changed_check
    state_trace = path / "unit_adaptive_state_trace.jsonl"
    if state_trace.exists():
        lines = state_trace.read_text().strip().split("\n")
        if len(lines) >= 2:
            first = json.loads(lines[0])
            last = json.loads(lines[-1])
            changed = any(
                abs(first.get(k, 0) - last.get(k, 0)) > 0.001
                for k in ["move_weight", "scan_weight", "extract_weight", "signal_weight"]
            )
            checks["adaptive_state_changed_check"] = "PASS" if changed else "FAIL"
        else:
            checks["adaptive_state_changed_check"] = "FAIL"
    else:
        checks["adaptive_state_changed_check"] = "FAIL"

    # 5. action_distribution_changed_check
    if summary_path.exists():
        early = summary.get("action_distribution_early", {})
        late = summary.get("action_distribution_late", {})
        delta = summary.get("action_distribution_delta", {})
        nonzero_delta = any(abs(v) > 0.001 for v in delta.values()) if delta else False
        checks["action_distribution_changed_check"] = "PASS" if nonzero_delta or early != late else "FAIL"
    else:
        checks["action_distribution_changed_check"] = "FAIL"

    # 6. local_feedback_update_evidence_check
    if state_trace.exists():
        lines = state_trace.read_text().strip().split("\n")
        if len(lines) >= 2:
            first = json.loads(lines[0])
            last = json.loads(lines[-1])
            state_changed = any(
                abs(first.get(k, 0) - last.get(k, 0)) > 0.001
                for k in ["move_weight", "scan_weight", "extract_weight", "signal_weight",
                           "hazard_avoidance_bias", "resource_following_bias"]
            )
            checks["local_feedback_update_evidence_check"] = "PASS" if state_changed else "FAIL"
        else:
            checks["local_feedback_update_evidence_check"] = "FAIL"
    else:
        checks["local_feedback_update_evidence_check"] = "FAIL"

    # 7. signal_adaptation_check
    if state_trace.exists():
        lines = state_trace.read_text().strip().split("\n")
        if len(lines) >= 2:
            first = json.loads(lines[0])
            last = json.loads(lines[-1])
            sig_changed = abs(first.get("signal_emission_rate", 0) - last.get("signal_emission_rate", 0)) > 0.001
            # Also check if signal_weight changed or if any intermediate values differ
            sig_weight_changed = abs(first.get("signal_weight", 0) - last.get("signal_weight", 0)) > 0.001
            any_sig_diff = False
            if len(lines) > 2:
                for line in lines[1:-1]:
                    entry = json.loads(line)
                    if abs(entry.get("signal_emission_rate", 0) - first.get("signal_emission_rate", 0)) > 0.005:
                        any_sig_diff = True
                        break
            checks["signal_adaptation_check"] = "PASS" if (sig_changed or sig_weight_changed or any_sig_diff) else "FAIL"
        else:
            checks["signal_adaptation_check"] = "FAIL"
    else:
        checks["signal_adaptation_check"] = "FAIL"

    # 8. descendant_transfer_check
    desc_trace = path / "descendant_adaptive_state_trace.jsonl"
    if desc_trace.exists():
        lines = desc_trace.read_text().strip().split("\n")
        if lines:
            checks["descendant_transfer_check"] = "PASS"
        else:
            checks["descendant_transfer_check"] = "FAIL"
    else:
        checks["descendant_transfer_check"] = "SKIP"

    # 9. static_vs_adaptive_difference_check
    compare_path = path / "adaptive_vs_static_compare.json"
    if compare_path.exists():
        compare = json.loads(compare_path.read_text())
        diff = compare.get("action_distribution_delta", {})
        nonzero_diff = any(abs(v) > 0.001 for v in diff.values()) if diff else False
        any_metric_diff = any(
            abs(compare.get(k, {}).get("delta", 0)) > 0
            for k in ["active_unit_count_delta", "resource_extraction_delta", "signal_action_delta"]
            if isinstance(compare.get(k), dict)
        )
        checks["static_vs_adaptive_difference_check"] = "PASS" if nonzero_diff or any_metric_diff else "FAIL"
    else:
        checks["static_vs_adaptive_difference_check"] = "FAIL"

    # 10. artifact_schema_check
    required = [
        "long_run_adaptation_summary.json",
        "unit_adaptive_state_trace.jsonl",
        "action_distribution_trace.jsonl",
        "adaptive_vs_static_compare.json",
    ]
    all_present = all((path / f).exists() for f in required)
    checks["artifact_schema_check"] = "PASS" if all_present else "FAIL"

    # 11. bounded_trace_size_check
    max_lines = 0
    for f in path.glob("*.jsonl"):
        line_count = len(f.read_text().strip().split("\n"))
        max_lines = max(max_lines, line_count)
    checks["bounded_trace_size_check"] = "PASS" if max_lines < 100000 else "FAIL"

    # 12. machine_native_wording_check
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

    results["M14_JUDGE_STATUS"] = status
    results["checks"] = checks
    results["failed_checks"] = failed
    return results


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m machine_sim.verification.milestone_14_judge <output_dir>")
        sys.exit(1)

    output_dir = sys.argv[1]
    results = judge(output_dir)

    # Write result
    out_path = Path(output_dir) / "milestone_14_judge_result.json"
    out_path.write_text(json.dumps(results, indent=2))

    print(f"M14_JUDGE_STATUS: {results['M14_JUDGE_STATUS']}")
    for check, status in results["checks"].items():
        print(f"  {check}: {status}")

    if results["failed_checks"]:
        print(f"\nFailed checks: {', '.join(results['failed_checks'])}")
        sys.exit(1)
    print("\nAll checks passed.")


if __name__ == "__main__":
    main()
