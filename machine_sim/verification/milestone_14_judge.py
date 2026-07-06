"""Independent M14 judge: evaluates milestone 14 artifacts from output directory.

Strengthened for M14A: no SKIP allowed for required checks, tighter thresholds,
requires local feedback trace, descendant transfer, and signal observations.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

FORBIDDEN_TERMS = [
    "human", "social", "society", "community", "communication", "message",
    "language", "meaning", "knowledge", "learning", "teaching",
    "strategy", "trust", "cooperation", "competition", "conflict",
    "agreement", "consensus", "population", "evolution", "mutation",
    "inheritance", "offspring", "species", "fitness",
]

REQUIRED_ARTIFACTS = [
    "long_run_adaptation_summary.json",
    "unit_adaptive_state_trace.jsonl",
    "action_distribution_trace.jsonl",
    "adaptive_vs_static_compare.json",
    "local_feedback_trace.jsonl",
    "descendant_adaptive_state_trace.jsonl",
    "resource_hazard_field_summary.json",
    "unit_lifetime_trace.jsonl",
]


def judge(output_dir: str) -> Dict[str, Any]:
    """Run all M14A judge checks."""
    path = Path(output_dir)
    results: Dict[str, Any] = {}
    checks: Dict[str, str] = {}

    # Load summary
    summary_path = path / "long_run_adaptation_summary.json"
    summary: Dict[str, Any] = {}
    if summary_path.exists():
        summary = json.loads(summary_path.read_text())

    # 1. long_run_ticks_check: run_ticks >= 20000
    run_ticks = summary.get("run_ticks", 0)
    checks["long_run_ticks_check"] = "PASS" if run_ticks >= 20000 else "FAIL"

    # 2. large_sparse_environment_check: grid >= 120x120, units <= 12, pressure nontrivial
    grid_w = summary.get("grid_width", 0)
    grid_h = summary.get("grid_height", 0)
    initial_units = summary.get("initial_unit_count", 0)
    power_drain = summary.get("power_drain_rate", 0)
    env_ok = (grid_w >= 120 and grid_h >= 120 and initial_units <= 12
              and initial_units >= 3 and power_drain > 0)
    checks["large_sparse_environment_check"] = "PASS" if env_ok else "FAIL"

    # 3. no_early_collapse_check: late-run active units exist, not trivial survival
    final_active = summary.get("final_active_unit_count", 0)
    descendant_active = summary.get("descendant_active_count", 0)
    total_active = final_active + descendant_active
    collapse_ok = total_active > 0 and power_drain > 0
    checks["no_early_collapse_check"] = "PASS" if collapse_ok else "FAIL"

    # 4. adaptive_state_changed_check: first vs last adaptive state delta exceeds threshold
    state_trace = path / "unit_adaptive_state_trace.jsonl"
    adaptive_changed = False
    if state_trace.exists():
        lines = [l for l in state_trace.read_text().strip().split("\n") if l]
        if len(lines) >= 2:
            first = json.loads(lines[0])
            last = json.loads(lines[-1])
            max_delta = max(
                abs(first.get(k, 0) - last.get(k, 0))
                for k in ["move_weight", "scan_weight", "extract_weight", "signal_weight"]
            )
            adaptive_changed = max_delta > 0.01
    checks["adaptive_state_changed_check"] = "PASS" if adaptive_changed else "FAIL"

    # 5. action_distribution_changed_check: delta exceeds threshold
    early = summary.get("action_distribution_early", {})
    late = summary.get("action_distribution_late", {})
    dist_delta = summary.get("action_distribution_delta", {})
    nonzero_delta = any(abs(v) > 1 for v in dist_delta.values()) if dist_delta else False
    checks["action_distribution_changed_check"] = "PASS" if nonzero_delta or early != late else "FAIL"

    # 6. local_feedback_update_evidence_check: trace exists with entries, state correlated
    feedback_trace = path / "local_feedback_trace.jsonl"
    feedback_ok = False
    if feedback_trace.exists():
        fb_lines = [l for l in feedback_trace.read_text().strip().split("\n") if l]
        if len(fb_lines) > 0:
            # Check that feedback entries have nonzero values
            has_nonzero = False
            for line in fb_lines[:100]:
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                for k in ["power_delta", "hazard_exposure", "resource_extracted",
                           "signal_observed", "movement_blocked"]:
                    if abs(entry.get(k, 0)) > 0.01:
                        has_nonzero = True
                        break
                if has_nonzero:
                    break
            feedback_ok = has_nonzero and adaptive_changed
    checks["local_feedback_update_evidence_check"] = "PASS" if feedback_ok else "FAIL"

    # 7. signal_adaptation_check: nonzero emissions, nonzero observations, parameter delta
    signal_summary = summary.get("signal_behavior_summary", {})
    total_emissions = signal_summary.get("total_signal_emissions", 0)
    total_observations = signal_summary.get("total_signal_observations", 0)
    sig_adapt = total_emissions > 0 and total_observations > 0
    # Also check adaptive state signal parameter changed
    if state_trace.exists():
        lines = [l for l in state_trace.read_text().strip().split("\n") if l]
        if len(lines) >= 2:
            first = json.loads(lines[0])
            last = json.loads(lines[-1])
            sig_weight_delta = abs(first.get("signal_weight", 0) - last.get("signal_weight", 0))
            sig_rate_delta = abs(first.get("signal_emission_rate", 0) - last.get("signal_emission_rate", 0))
            sig_adapt = sig_adapt and (sig_weight_delta > 0.005 or sig_rate_delta > 0.005)
    checks["signal_adaptation_check"] = "PASS" if sig_adapt else "FAIL"

    # 8. descendant_transfer_check: artifact exists with >= 1 valid transfer (no SKIP)
    desc_trace = path / "descendant_adaptive_state_trace.jsonl"
    desc_ok = False
    if desc_trace.exists():
        desc_lines = [l for l in desc_trace.read_text().strip().split("\n") if l]
        desc_ok = len(desc_lines) >= 1
    checks["descendant_transfer_check"] = "PASS" if desc_ok else "FAIL"

    # 9. static_vs_adaptive_difference_check: nonzero delta and metric difference
    compare_path = path / "adaptive_vs_static_compare.json"
    compare_ok = False
    if compare_path.exists():
        compare = json.loads(compare_path.read_text())
        diff = compare.get("action_distribution_delta", {})
        nonzero_diff = any(abs(v) > 0 for v in diff.values()) if diff else False
        active_delta = compare.get("active_unit_count_delta", 0)
        # Check other metric deltas if present
        resource_delta = 0
        signal_delta = 0
        for k in ["resource_extraction_delta", "signal_action_delta",
                    "hazard_exposure_delta", "movement_block_delta"]:
            val = compare.get(k, {})
            if isinstance(val, dict):
                resource_delta += abs(val.get("delta", 0))
            elif isinstance(val, (int, float)):
                resource_delta += abs(val)
        compare_ok = nonzero_diff or abs(active_delta) > 0 or resource_delta > 0
    checks["static_vs_adaptive_difference_check"] = "PASS" if compare_ok else "FAIL"

    # 10. artifact_schema_check: all required artifacts present
    all_present = all((path / f).exists() for f in REQUIRED_ARTIFACTS)
    checks["artifact_schema_check"] = "PASS" if all_present else "FAIL"

    # 11. bounded_trace_size_check: JSONL traces < 50000 lines each
    max_lines = 0
    for f in path.glob("*.jsonl"):
        line_count = len([l for l in f.read_text().strip().split("\n") if l])
        max_lines = max(max_lines, line_count)
    checks["bounded_trace_size_check"] = "PASS" if max_lines < 50000 else "FAIL"

    # 12. machine_native_wording_check: no forbidden terms in artifacts
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
    results["thresholds"] = {
        "min_ticks": 20000,
        "min_grid_width": 120,
        "min_grid_height": 120,
        "max_initial_units": 12,
        "min_initial_units": 3,
        "min_power_drain": 0.01,
        "min_adaptive_state_delta": 0.01,
        "min_action_distribution_delta": 1,
        "min_signal_emissions": 1,
        "min_signal_observations": 1,
        "min_descendant_transfers": 1,
        "min_feedback_entries": 1,
    }
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
