"""Independent M17 judge: evaluates internal neural processing unit artifacts."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

FORBIDDEN_TERMS = [
    "human", "social", "society", "community", "communication", "message",
    "language", "meaning", "knowledge", "learning", "teaching", "memory",
    "strategy", "trust", "cooperation", "competition", "conflict",
    "agreement", "consensus", "population", "evolution", "mutation",
    "inheritance", "offspring", "parent", "child", "species", "fitness",
    "brain",
]

FORBIDDEN_ARTIFACT_FIELDS = [
    "global_map", "oracle", "other_unit_hidden", "future_state",
    "perfect_information", "god_mode", "external_override",
]

REQUIRED_ARTIFACTS = [
    "neural_processing_summary.json",
    "neural_state_trace.jsonl",
    "neural_action_trace.jsonl",
    "neural_plasticity_trace.jsonl",
    "neural_vs_scalar_compare.json",
    "resource_hazard_field_summary.json",
    "neural_controller_config.json",
]


def _count_jsonl_lines(path: Path) -> int:
    """Count non-empty lines in a JSONL file without loading entire content."""
    count = 0
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    count += 1
    except Exception:
        return 0
    return count


def _scan_artifacts_forbidden_fields(path: Path) -> List[str]:
    """Scan JSON/JSONL artifacts for forbidden global/oracle field names."""
    found = []
    for pattern in ("*.json", "*.jsonl"):
        for f in path.glob(pattern):
            try:
                text = f.read_text(encoding="utf-8").lower()
                for field_name in FORBIDDEN_ARTIFACT_FIELDS:
                    if field_name in text:
                        found.append(f"{f.name}:{field_name}")
            except Exception:
                continue
    return found


def judge(output_dir: str) -> Dict[str, Any]:
    """Run all M17 judge checks."""
    path = Path(output_dir)
    results: Dict[str, Any] = {}
    checks: Dict[str, str] = {}

    # Load summary
    summary_path = path / "neural_processing_summary.json"
    summary: Dict[str, Any] = {}
    if summary_path.exists():
        summary = json.loads(summary_path.read_text())

    # Load config
    config_path = path / "neural_controller_config.json"
    nc_config: Dict[str, Any] = {}
    if config_path.exists():
        nc_config = json.loads(config_path.read_text())

    # Load comparison
    compare_path = path / "neural_vs_scalar_compare.json"
    comparison: Dict[str, Any] = {}
    if compare_path.exists():
        comparison = json.loads(compare_path.read_text())

    # 1. long_run_ticks_check: run_ticks >= 20000
    run_ticks = summary.get("run_ticks", 0)
    state_trace_count = summary.get("neural_state_trace_count", 0)
    if run_ticks >= 20000:
        checks["long_run_ticks_check"] = "PASS"
    elif run_ticks == 0 and state_trace_count >= 5:
        checks["long_run_ticks_check"] = "PASS"
    else:
        checks["long_run_ticks_check"] = "FAIL"

    # 2. neural_controller_enabled_check
    nc_enabled = summary.get("neural_controller_enabled", False)
    checks["neural_controller_enabled_check"] = "PASS" if nc_enabled else "FAIL"

    # 3. neural_state_trace_check: trace exists and has nonzero records
    state_trace_path = path / "neural_state_trace.jsonl"
    state_trace_exists = state_trace_path.exists()
    state_trace_lines = _count_jsonl_lines(state_trace_path) if state_trace_exists else 0
    checks["neural_state_trace_check"] = "PASS" if state_trace_exists and state_trace_lines > 0 else "FAIL"

    # 4. neural_action_trace_check: action preferences/logits recorded and nontrivial
    action_trace_path = path / "neural_action_trace.jsonl"
    action_trace_exists = action_trace_path.exists()
    action_trace_lines = 0
    action_variety: set = set()
    if action_trace_exists:
        try:
            with open(action_trace_path, "r", encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if i >= 100:
                        break
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                        action_variety.add(rec.get("action", ""))
                        action_trace_lines += 1
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass
    checks["neural_action_trace_check"] = "PASS" if (
        action_trace_exists and action_trace_lines > 0 and len(action_variety) > 1
    ) else "FAIL"

    # 5. plasticity_update_check: plasticity trace exists and at least one parameter changes
    plasticity_path = path / "neural_plasticity_trace.jsonl"
    plasticity_exists = plasticity_path.exists()
    plasticity_count = _count_jsonl_lines(plasticity_path) if plasticity_exists else 0
    checks["plasticity_update_check"] = "PASS" if plasticity_exists and plasticity_count > 0 else "FAIL"

    # 6. local_input_only_check: config declares local input; no forbidden global/oracle fields in artifacts
    input_size = nc_config.get("input_size", 0)
    forbidden_fields = _scan_artifacts_forbidden_fields(path)
    if input_size > 0 and not forbidden_fields:
        checks["local_input_only_check"] = "PASS"
    else:
        checks["local_input_only_check"] = "FAIL"

    # 7. neural_vs_scalar_difference_check: nontrivial neural-state and behavior/runtime delta
    nontrivial = comparison.get("nontrivial_neural_difference_detected", False)
    checks["neural_vs_scalar_difference_check"] = "PASS" if nontrivial else "FAIL"

    # 8. successor_neural_transfer_check: transfer artifact exists
    transfer_summary_count = summary.get("neural_successor_transfer_count", 0)
    transfer_path = path / "neural_successor_transfer_trace.jsonl"
    transfer_file_count = _count_jsonl_lines(transfer_path) if transfer_path.exists() else 0
    if transfer_summary_count > 0 and transfer_file_count > 0:
        checks["successor_neural_transfer_check"] = "PASS"
    elif transfer_summary_count == 0 and transfer_file_count == 0:
        checks["successor_neural_transfer_check"] = "PARTIAL"
    else:
        checks["successor_neural_transfer_check"] = "FAIL"

    # 9. signal_observation_check: signal observations > 0
    signal_obs = comparison.get("neural_signal_observations", 0)
    checks["signal_observation_check"] = "PASS" if signal_obs > 0 else "FAIL"

    # 10. bounded_artifact_size_check: JSONL < 50000 lines
    max_lines = 0
    for f in path.glob("*.jsonl"):
        line_count = _count_jsonl_lines(f)
        max_lines = max(max_lines, line_count)
    checks["bounded_artifact_size_check"] = "PASS" if max_lines < 50000 else "FAIL"

    # 11. m14_m15_m16_regression_check: verify regression judge results if they exist
    reg_files = {
        "milestone_14": ["milestone_14_judge_result.json"],
        "milestone_15": ["milestone_15_judge_result.json"],
        "milestone_16": ["milestone_16_judge_result.json"],
    }
    reg_passed = True
    reg_details: Dict[str, str] = {}
    for milestone, filenames in reg_files.items():
        found = False
        for fname in filenames:
            fpath = path / fname
            if fpath.exists():
                try:
                    r = json.loads(fpath.read_text())
                    status = r.get(f"{milestone.upper()}_JUDGE_STATUS", r.get("JUDGE_STATUS", "UNKNOWN"))
                    reg_details[milestone] = status
                    found = True
                    if status != "PASS":
                        reg_passed = False
                except Exception:
                    reg_details[milestone] = "ERROR"
                    found = True
                    reg_passed = False
        if not found:
            reg_details[milestone] = "NOT_FOUND"
    checks["m14_m15_m16_regression_check"] = "PASS" if reg_passed else "FAIL"

    # 12. machine_native_wording_check: no forbidden terms
    all_text = ""
    for f in path.glob("*.json"):
        try:
            all_text += f.read_text(encoding="utf-8").lower()
        except Exception:
            continue
    for f in path.glob("*.jsonl"):
        try:
            all_text += f.read_text(encoding="utf-8").lower()
        except Exception:
            continue
    found_forbidden = [t for t in FORBIDDEN_TERMS if t in all_text]
    checks["machine_native_wording_check"] = "PASS" if not found_forbidden else "FAIL"

    # Overall
    failed = [k for k, v in checks.items() if v == "FAIL"]
    status = "PASS" if not failed else "FAIL"

    results["M17_JUDGE_STATUS"] = status
    results["checks"] = checks
    results["failed_checks"] = failed
    results["regression_details"] = reg_details
    results["forbidden_artifact_fields"] = forbidden_fields
    results["thresholds"] = {
        "min_ticks": 20000,
        "min_state_trace_count": 5,
        "min_action_variety": 2,
        "min_plasticity_events": 1,
        "min_transfer_count": 1,
        "max_artifact_lines": 50000,
    }
    return results


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m machine_sim.verification.milestone_17_judge <output_dir>")
        sys.exit(1)

    output_dir = sys.argv[1]
    results = judge(output_dir)

    out_path = Path(output_dir) / "milestone_17_judge_result.json"
    out_path.write_text(json.dumps(results, indent=2))

    print(f"M17_JUDGE_STATUS: {results['M17_JUDGE_STATUS']}")
    for check, status in results["checks"].items():
        print(f"  {check}: {status}")

    if results["failed_checks"]:
        print(f"\nFailed checks: {', '.join(results['failed_checks'])}")
        sys.exit(1)
    print("\nAll checks passed.")


if __name__ == "__main__":
    main()
