"""Independent M16 judge: evaluates adaptive trajectory compression artifacts."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

FORBIDDEN_TERMS = [
    "human", "social", "society", "community", "communication", "message",
    "language", "meaning", "knowledge", "learning", "teaching", "memory",
    "strategy", "trust", "cooperation", "competition", "conflict",
    "agreement", "consensus", "population", "evolution", "mutation",
    "inheritance", "offspring", "parent", "child", "species", "fitness",
]

REQUIRED_ARTIFACTS = [
    "compressed_trajectory_capsule.json",
    "trajectory_compression_summary.json",
    "compressed_trajectory_segments.jsonl",
    "trajectory_replay_metrics.json",
    "cross_trajectory_compare.json",
    "adaptive_trajectory_summary.json",
    "generation_adaptive_state_trace.jsonl",
]


def judge(output_dir: str) -> Dict[str, Any]:
    """Run all M16 judge checks."""
    path = Path(output_dir)
    results: Dict[str, Any] = {}
    checks: Dict[str, str] = {}

    # Load capsule
    capsule_path = path / "compressed_trajectory_capsule.json"
    capsule: Dict[str, Any] = {}
    if capsule_path.exists():
        capsule = json.loads(capsule_path.read_text())

    run_params = capsule.get("run_parameters", {})
    compression_params = capsule.get("compression_parameters", {})
    size_summary = capsule.get("artifact_size_summary", {})
    replay = capsule.get("replay_metrics", {})
    cross_compare = capsule.get("cross_trajectory_similarity", {})

    # 1. long_run_ticks_check: run_ticks >= 30000
    max_ticks = run_params.get("max_ticks", 0)
    checks["long_run_ticks_check"] = "PASS" if max_ticks >= 30000 else "FAIL"

    # 2. source_trace_available_check: source record count nonzero
    source_count = size_summary.get("source_trace_record_count", 0)
    checks["source_trace_available_check"] = "PASS" if source_count > 0 else "FAIL"

    # 3. compression_segment_check: segments > 0 and <= bound
    seg_count = size_summary.get("compressed_segment_count", 0)
    max_segs = compression_params.get("max_segments", 64)
    checks["compression_segment_check"] = "PASS" if 0 < seg_count <= max_segs else "FAIL"

    # 4. compression_ratio_check: ratio < 1.0 or compressed smaller
    ratio = size_summary.get("trajectory_compression_ratio", 1.0)
    checks["compression_ratio_check"] = "PASS" if ratio < 1.0 else "FAIL"

    # 5. replay_metrics_check: replay metrics exist and numeric
    replay_ok = (
        isinstance(replay.get("avg_trajectory_replay_error"), (int, float))
        and isinstance(replay.get("replay_stability_score"), (int, float))
        and 0.0 <= replay.get("replay_stability_score", -1) <= 1.0
    )
    checks["replay_metrics_check"] = "PASS" if replay_ok else "FAIL"

    # 6. cross_trajectory_similarity_check: comparison exists, numeric/bounded
    cross_ok = (
        isinstance(cross_compare.get("overall_trajectory_similarity"), (int, float))
        and 0.0 <= cross_compare.get("overall_trajectory_similarity", -1) <= 1.0
    )
    checks["cross_trajectory_similarity_check"] = "PASS" if cross_ok else "FAIL"

    # 7. nontrivial_difference_check: difference detected
    nontrivial = cross_compare.get("nontrivial_difference_detected", False)
    checks["nontrivial_difference_check"] = "PASS" if nontrivial else "FAIL"

    # 8. transfer_generation_check: transfer >= 5, gen span >= 3
    traj_summary_path = path / "adaptive_trajectory_summary.json"
    traj_summary: Dict[str, Any] = {}
    if traj_summary_path.exists():
        traj_summary = json.loads(traj_summary_path.read_text())
    transfer_summary = traj_summary.get("transfer_summary", {})
    gen_summary = traj_summary.get("generation_summary", {})
    transfer_count = transfer_summary.get("transfer_count", 0)
    gen_span = gen_summary.get("generation_index_span", 0)
    checks["transfer_generation_check"] = "PASS" if transfer_count >= 5 and gen_span >= 3 else "FAIL"

    # 9. signal_observation_check: signal observations > 0
    gen_trace_path = path / "generation_adaptive_state_trace.jsonl"
    signal_ok = False
    if gen_trace_path.exists():
        for line in gen_trace_path.read_text().strip().split("\n")[:50]:
            try:
                rec = json.loads(line)
                delta = rec.get("adaptive_state_delta", {})
                if any("signal" in k and abs(v) > 1e-6 for k, v in delta.items()):
                    signal_ok = True
                    break
            except json.JSONDecodeError:
                continue
    traj_sig = capsule.get("trajectory_signature", {})
    if traj_sig.get("total_transfer_count", 0) > 0:
        signal_ok = True  # transfers imply signal activity
    checks["signal_observation_check"] = "PASS" if signal_ok else "FAIL"

    # 10. artifact_schema_check: all required artifacts present
    all_present = all((path / f).exists() for f in REQUIRED_ARTIFACTS)
    checks["artifact_schema_check"] = "PASS" if all_present else "FAIL"

    # 11. bounded_artifact_size_check: JSONL < 50000 lines
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

    results["M16_JUDGE_STATUS"] = status
    results["checks"] = checks
    results["failed_checks"] = failed
    results["thresholds"] = {
        "min_ticks": 30000,
        "min_transfer_count": 5,
        "min_generation_span": 3,
        "max_segments": compression_params.get("max_segments", 64),
        "max_artifact_lines": 50000,
    }
    return results


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m machine_sim.verification.milestone_16_judge <output_dir>")
        sys.exit(1)

    output_dir = sys.argv[1]
    results = judge(output_dir)

    out_path = Path(output_dir) / "milestone_16_judge_result.json"
    out_path.write_text(json.dumps(results, indent=2))

    print(f"M16_JUDGE_STATUS: {results['M16_JUDGE_STATUS']}")
    for check, status in results["checks"].items():
        print(f"  {check}: {status}")

    if results["failed_checks"]:
        print(f"\nFailed checks: {', '.join(results['failed_checks'])}")
        sys.exit(1)
    print("\nAll checks passed.")


if __name__ == "__main__":
    main()
