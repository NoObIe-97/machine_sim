"""Independent M18 judge: evaluates neural controller variant sensitivity artifacts."""

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


def _count_jsonl_lines(path: Path) -> int:
    count = 0
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    count += 1
    except Exception:
        return 0
    return count


def judge(output_dir: str) -> Dict[str, Any]:
    """Run all M18 judge checks. Overall PASS only when every check is exactly PASS."""
    path = Path(output_dir)
    checks: Dict[str, str] = {}

    # Load sweep summary
    sweep_path = path / "neural_variant_sweep_summary.json"
    sweep: Dict[str, Any] = {}
    if sweep_path.exists():
        sweep = json.loads(sweep_path.read_text())

    # Load similarity matrix
    sim_path = path / "neural_variant_similarity_matrix.json"
    sim_matrix: Dict[str, Any] = {}
    if sim_path.exists():
        sim_matrix = json.loads(sim_path.read_text())

    # Load sensitivity summary
    sens_path = path / "neural_controller_sensitivity_summary.json"
    sensitivity: Dict[str, Any] = {}
    if sens_path.exists():
        sensitivity = json.loads(sens_path.read_text())

    # Load per-variant runtime summary
    runtime_path = path / "per_variant_runtime_summary.jsonl"
    runtimes: List[Dict[str, Any]] = []
    if runtime_path.exists():
        with open(runtime_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        runtimes.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

    variant_defs = sweep.get("variant_definitions", [])
    variant_ids = sim_matrix.get("variant_ids", [])

    # 1. variant_count_check: at least 5 variants
    checks["variant_count_check"] = "PASS" if len(variant_ids) >= 5 else "FAIL"

    # 2. accepted_m17_variant_check: one variant matches M17 baseline (h16, rate001)
    has_m17 = any(
        v.get("neural_hidden_size") == 16 and v.get("neural_plasticity_rate") == 0.01
        for v in variant_defs
    )
    checks["accepted_m17_variant_check"] = "PASS" if has_m17 else "FAIL"

    # 3. hidden_size_variant_check: at least one differs from 16
    has_hidden_diff = any(v.get("neural_hidden_size", 16) != 16 for v in variant_defs)
    checks["hidden_size_variant_check"] = "PASS" if has_hidden_diff else "FAIL"

    # 4. plasticity_rate_variant_check: at least one differs from 0.01
    has_rate_diff = any(v.get("neural_plasticity_rate", 0.01) != 0.01 for v in variant_defs)
    checks["plasticity_rate_variant_check"] = "PASS" if has_rate_diff else "FAIL"

    # 5. plasticity_disabled_variant_check: at least one has plasticity disabled
    has_plast_disabled = any(not v.get("neural_plasticity_enabled", True) for v in variant_defs)
    checks["plasticity_disabled_variant_check"] = "PASS" if has_plast_disabled else "FAIL"

    # 6. per_variant_artifact_check: required per-variant artifacts exist
    all_artifacts_ok = True
    for vid in variant_ids:
        vdir = path / "variants" / vid
        if not vdir.exists():
            all_artifacts_ok = False
            break
        summary = vdir / "neural_processing_summary.json"
        if not summary.exists():
            all_artifacts_ok = False
            break
    checks["per_variant_artifact_check"] = "PASS" if all_artifacts_ok else "FAIL"

    # 7. per_variant_runtime_check: strict — file must exist, have rows for every variant, thresholds met
    runtime_ok = True
    runtime_fail_reasons: List[str] = []

    if not runtime_path.exists():
        runtime_ok = False
        runtime_fail_reasons.append("per_variant_runtime_summary.jsonl missing")
    elif not runtimes:
        runtime_ok = False
        runtime_fail_reasons.append("per_variant_runtime_summary.jsonl empty")
    else:
        # Check every expected variant_id has a runtime row
        runtime_ids = [rt.get("variant_id") for rt in runtimes]
        for vid in variant_ids:
            if vid not in runtime_ids:
                runtime_ok = False
                runtime_fail_reasons.append(f"missing runtime row for variant {vid}")

        # Check for duplicate variant_ids
        seen_ids: set = set()
        for rt in runtimes:
            vid = rt.get("variant_id")
            if vid in seen_ids:
                runtime_ok = False
                runtime_fail_reasons.append(f"duplicate runtime row for variant {vid}")
            seen_ids.add(vid)

        # Check required fields and thresholds for each row
        required_fields = ("variant_id", "run_ticks", "neural_controller_enabled",
                           "neural_hidden_size", "neural_plasticity_rate")
        for rt in runtimes:
            for field_name in required_fields:
                if field_name not in rt:
                    runtime_ok = False
                    runtime_fail_reasons.append(f"variant {rt.get('variant_id', '?')} missing field {field_name}")

            ticks = rt.get("run_ticks", 0)
            is_neural = rt.get("neural_controller_enabled", False)
            is_primary = (is_neural
                          and rt.get("neural_hidden_size") == 16
                          and rt.get("neural_plasticity_rate") == 0.01)
            if is_primary and ticks < 10000:
                runtime_ok = False
                runtime_fail_reasons.append(f"variant {rt.get('variant_id')} primary below 10000 ticks ({ticks})")
            elif not is_primary and ticks < 5000:
                runtime_ok = False
                runtime_fail_reasons.append(f"variant {rt.get('variant_id')} below 5000 ticks ({ticks})")

    checks["per_variant_runtime_check"] = "PASS" if runtime_ok else "FAIL"

    # 8. similarity_matrix_check: matrix exists, square, numeric
    sim_ok = True
    if not sim_matrix.get("variant_ids"):
        sim_ok = False
    else:
        for mat_type in ("action_distribution", "neural_state", "runtime_metric"):
            mat = sim_matrix.get("similarity_matrix", {}).get(mat_type, [])
            n = len(mat)
            if n == 0:
                sim_ok = False
                break
            if any(len(row) != n for row in mat):
                sim_ok = False
                break
            # Check diagonal approx 1.0
            for i in range(n):
                if abs(mat[i][i] - 1.0) > 0.01:
                    sim_ok = False
                    break
    checks["similarity_matrix_check"] = "PASS" if sim_ok else "FAIL"

    # 9. nontrivial_difference_check: at least one off-diagonal difference
    checks["nontrivial_difference_check"] = (
        "PASS" if sim_matrix.get("nontrivial_off_diagonal_difference_detected", False) else "FAIL"
    )

    # 10. sensitivity_summary_check: sensitivity artifact exists with numeric bounded scores
    sens_ok = True
    if not sensitivity:
        sens_ok = False
    else:
        scores = sensitivity.get("sensitivity_score_by_parameter", {})
        if not scores:
            sens_ok = False
        for v in scores.values():
            if not isinstance(v, (int, float)) or v < 0 or v > 1:
                sens_ok = False
                break
    checks["sensitivity_summary_check"] = "PASS" if sens_ok else "FAIL"

    # 11. m17_regression_check: strict M17 judge PASS
    m17_judge_path = path / "milestone_17_judge_result.json"
    # Also check in parent demo_m17 if exists
    m17_result_path = path.parent / "demo_m17" / "milestone_17_judge_result.json"
    m17_status = "NOT_FOUND"
    for p in [m17_judge_path, m17_result_path]:
        if p.exists():
            try:
                r = json.loads(p.read_text())
                m17_status = r.get("M17_JUDGE_STATUS", "UNKNOWN")
            except Exception:
                m17_status = "ERROR"
            break
    # Also check sweep summary for regression info
    reg_summary = sweep.get("strict_regression_summary", {})
    if reg_summary.get("m17_regression") == "PASS":
        m17_status = "PASS"
    checks["m17_regression_check"] = "PASS" if m17_status == "PASS" else "FAIL"

    # 12. m14_m15_m16_regression_check
    m14_status = "NOT_FOUND"
    for ms in ("14", "15", "16"):
        ms_path = path.parent / f"demo_m{ms}" / f"milestone_{ms}_judge_result.json"
        if ms_path.exists():
            try:
                r = json.loads(ms_path.read_text())
                # Try both key formats: MILESTONE_{ms}_JUDGE_STATUS and M{ms}_JUDGE_STATUS
                status = r.get(f"MILESTONE_{ms}_JUDGE_STATUS",
                               r.get(f"M{ms}_JUDGE_STATUS", "UNKNOWN"))
                if status != "PASS":
                    m14_status = status
                    break
                m14_status = "PASS"
            except Exception:
                m14_status = "ERROR"
                break
        else:
            m14_status = "NOT_FOUND"
            break
    if reg_summary.get("m14_m15_m16_regression") == "PASS":
        m14_status = "PASS"
    checks["m14_m15_m16_regression_check"] = "PASS" if m14_status == "PASS" else "FAIL"

    # 13. bounded_artifact_size_check
    max_lines = 0
    for f in path.glob("*.jsonl"):
        line_count = _count_jsonl_lines(f)
        max_lines = max(max_lines, line_count)
    for f in path.glob("variants/**/*.jsonl"):
        line_count = _count_jsonl_lines(f)
        max_lines = max(max_lines, line_count)
    checks["bounded_artifact_size_check"] = "PASS" if max_lines < 100000 else "FAIL"

    # 14. machine_native_wording_check
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
    for f in path.glob("variants/**/*.json"):
        try:
            all_text += f.read_text(encoding="utf-8").lower()
        except Exception:
            continue
    found_forbidden = [t for t in FORBIDDEN_TERMS if t in all_text]
    checks["machine_native_wording_check"] = "PASS" if not found_forbidden else "FAIL"

    # Overall: PASS only if every check is exactly "PASS"
    non_pass = [k for k, v in checks.items() if v != "PASS"]
    status = "PASS" if not non_pass else "FAIL"

    return {
        "M18_JUDGE_STATUS": status,
        "checks": checks,
        "failed_checks": non_pass,
        "thresholds": {
            "min_variants": 5,
            "primary_variant_min_ticks": 10000,
            "other_variant_min_ticks": 5000,
            "max_artifact_lines": 100000,
        },
    }


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m machine_sim.verification.milestone_18_judge <output_dir>")
        sys.exit(1)

    output_dir = sys.argv[1]
    results = judge(output_dir)

    out_path = Path(output_dir) / "milestone_18_judge_result.json"
    out_path.write_text(json.dumps(results, indent=2))

    print(f"M18_JUDGE_STATUS: {results['M18_JUDGE_STATUS']}")
    for check, check_status in results["checks"].items():
        print(f"  {check}: {check_status}")

    if results["failed_checks"]:
        print(f"\nFailed checks: {', '.join(results['failed_checks'])}")
        sys.exit(1)
    print("\nAll checks passed.")


if __name__ == "__main__":
    main()
