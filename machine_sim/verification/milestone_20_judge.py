"""Independent M20 judge: evaluates user-owned unattended run-control artifacts.

Overall status is PASS only when every check is exactly PASS. A missing artifact
is a FAIL, never a SKIP and never a default PASS.
"""

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

MANIFEST_SCHEMA_VERSION = "1.0.0"
MINIMUM_RUN_TICKS = 20000
MINIMUM_CHECKPOINTS = 4
MINIMUM_RESUMED_TICK_SPAN = 5000
MAXIMUM_ARTIFACT_LINES = 100000

REQUIRED_ARTIFACT_LABELS = (
    "run_manifest",
    "run_progress_trace",
    "checkpoint_index",
    "control_history",
    "checkpoint_validation_report",
    "resume_equivalence_report",
    "unattended_run_summary",
    "run_status_snapshot",
    "run_dashboard",
)

EXTERNAL_REFERENCE_MARKERS = (
    "http://", "https://", "//cdn", "@import", "fetch(", "xmlhttprequest", "websocket",
)


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    try:
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return records


def _count_lines(path: Path) -> int:
    count = 0
    try:
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    count += 1
    except OSError:
        return 0
    return count


def judge(output_dir: str) -> Dict[str, Any]:
    """Run every M20 check against a run-control output directory."""
    path = Path(output_dir)
    checks: Dict[str, str] = {}

    manifest = _read_json(path / "run_manifest.json")
    summary = _read_json(path / "unattended_run_summary.json")
    equivalence = _read_json(path / "resume_equivalence_report.json")
    validation = _read_json(path / "checkpoint_validation_report.json")
    index = _read_json(path / "checkpoints" / "checkpoint_index.json")
    artifact_index = _read_json(path / "artifact_index.json").get("artifact_index", {})
    control_records = _read_jsonl(path / "control" / "control_history.jsonl")
    progress_records = _read_jsonl(path / "run_progress_trace.jsonl")
    stop_manifest = _read_json(path / "stop_run" / "run_manifest.json")
    reference_manifest = _read_json(path / "reference_run" / "run_manifest.json")

    # 1. manifest_present_check
    checks["manifest_present_check"] = "PASS" if manifest else "FAIL"

    # 2. manifest_schema_version_check
    checks["manifest_schema_version_check"] = (
        "PASS" if manifest.get("manifest_schema_version") == MANIFEST_SCHEMA_VERSION else "FAIL"
    )

    # 3. manifest_terminal_run_state_check
    checks["manifest_terminal_run_state_check"] = (
        "PASS" if manifest.get("run_state") == "completed" else "FAIL"
    )

    # 4. progress_monotonic_check
    ticks = [r.get("tick", -1) for r in progress_records]
    monotonic = bool(ticks) and all(
        isinstance(t, int) for t in ticks
    ) and all(ticks[i] <= ticks[i + 1] for i in range(len(ticks) - 1))
    ratios = [r.get("progress_ratio", -1.0) for r in progress_records]
    ratios_bounded = all(isinstance(v, (int, float)) and 0.0 <= v <= 1.0 for v in ratios)
    checks["progress_monotonic_check"] = "PASS" if monotonic and ratios_bounded else "FAIL"

    # 5. checkpoint_count_check
    index_entries = index.get("checkpoints", [])
    checks["checkpoint_count_check"] = (
        "PASS" if len(index_entries) >= MINIMUM_CHECKPOINTS else "FAIL"
    )

    # 6. checkpoint_index_consistency_check
    consistent = bool(index_entries)
    for entry in index_entries:
        candidate = path / "checkpoints" / str(entry.get("path", ""))
        if not candidate.exists():
            consistent = False
            break
        if not isinstance(entry.get("tick"), int) or entry["tick"] < 0:
            consistent = False
            break
        if not isinstance(entry.get("state_digest"), str) or not entry["state_digest"]:
            consistent = False
            break
    checks["checkpoint_index_consistency_check"] = "PASS" if consistent else "FAIL"

    # 7. checkpoint_digest_integrity_check
    integrity = bool(index_entries)
    try:
        from machine_sim.sim.checkpoint import payload_digest
    except ImportError:
        payload_digest = None  # type: ignore[assignment]
        integrity = False
    if payload_digest is not None:
        for entry in index_entries:
            candidate = path / "checkpoints" / str(entry.get("path", ""))
            document = _read_json(candidate)
            if not document:
                integrity = False
                break
            if payload_digest(document.get("payload", {})) != document.get("state_digest"):
                integrity = False
                break
            if document.get("state_digest") != entry.get("state_digest"):
                integrity = False
                break
    checks["checkpoint_digest_integrity_check"] = "PASS" if integrity else "FAIL"

    # 8. checkpoint_validation_report_check
    validation_ok = (
        bool(validation)
        and validation.get("validated_count", 0) >= MINIMUM_CHECKPOINTS
        and validation.get("fail_count", 1) == 0
        and validation.get("pass_count", 0) == validation.get("validated_count", -1)
    )
    checks["checkpoint_validation_report_check"] = "PASS" if validation_ok else "FAIL"

    # 9. checkpoint_retention_bound_check
    retention_limit = summary.get("checkpoint_retention_limit", 0)
    retained = summary.get("retained_checkpoint_count", -1)
    retention_ok = (
        isinstance(retention_limit, int)
        and retention_limit > 0
        and 0 < retained <= retention_limit
        and len(index_entries) <= retention_limit
    )
    checks["checkpoint_retention_bound_check"] = "PASS" if retention_ok else "FAIL"

    # 10. pause_request_applied_check
    pause_records = [r for r in control_records if r.get("requested_state") == "pause"]
    pause_ok = (
        bool(pause_records)
        and summary.get("pause_applied") is True
        and all(r.get("resulting_run_state") == "paused" for r in pause_records)
        and all(isinstance(r.get("applied_tick"), int) for r in pause_records)
    )
    checks["pause_request_applied_check"] = "PASS" if pause_ok else "FAIL"

    # 11. stop_request_applied_check
    stop_history = _read_jsonl(path / "stop_run" / "control" / "control_history.jsonl")
    stop_records = [r for r in stop_history if r.get("requested_state") == "stop"]
    stop_ok = (
        summary.get("stop_applied") is True
        and stop_manifest.get("run_state") == "stopped"
        and bool(stop_records)
        and all(r.get("resulting_run_state") == "stopped" for r in stop_records)
    )
    checks["stop_request_applied_check"] = "PASS" if stop_ok else "FAIL"

    # 12. control_history_consistency_check
    # A control record must name a checkpoint the manifest recorded. The file
    # itself may since have been pruned by the retention limit, so the
    # append-only manifest record is the authority here.
    manifest_control = manifest.get("control_records", [])
    history_ids = [r.get("request_id") for r in control_records]
    recorded_checkpoint_paths = {
        entry.get("path") for entry in manifest.get("checkpoint_records", [])
    }
    consistency = (
        bool(control_records)
        and len(history_ids) == len(set(history_ids))
        and all(isinstance(rid, str) and rid for rid in history_ids)
        and len(manifest_control) == len(control_records)
        and all(
            (not r.get("checkpoint_path"))
            or r["checkpoint_path"] in recorded_checkpoint_paths
            for r in control_records
        )
    )
    checks["control_history_consistency_check"] = "PASS" if consistency else "FAIL"

    # 13. resume_from_checkpoint_check
    resume_ok = (
        summary.get("resume_applied") is True
        and int(equivalence.get("pause_tick", 0)) > 0
        and int(equivalence.get("final_tick", 0)) > int(equivalence.get("pause_tick", 0))
    )
    checks["resume_from_checkpoint_check"] = "PASS" if resume_ok else "FAIL"

    # 14. process_isolated_resume_check
    checks["process_isolated_resume_check"] = (
        "PASS"
        if equivalence.get("process_isolated") is True
        and reference_manifest.get("run_state") == "completed"
        and reference_manifest.get("run_id") == manifest.get("run_id")
        else "FAIL"
    )

    # 15. continuation_equivalence_check
    equivalence_ok = (
        equivalence.get("digests_equal") is True
        and bool(equivalence.get("reference_run_digest"))
        and equivalence.get("reference_run_digest") == equivalence.get("resumed_run_digest")
        and summary.get("continuation_equivalence") is True
    )
    checks["continuation_equivalence_check"] = "PASS" if equivalence_ok else "FAIL"

    # 16. resumed_tick_span_check
    checks["resumed_tick_span_check"] = (
        "PASS"
        if int(equivalence.get("resumed_tick_span", 0)) >= MINIMUM_RESUMED_TICK_SPAN
        else "FAIL"
    )

    # 17. sampled_digest_mismatch_check
    mismatch_ok = (
        equivalence.get("sampled_digest_mismatch_count") == 0
        and int(equivalence.get("compared_tick_count", 0)) > 0
        and int(equivalence.get("post_resume_compared_tick_count", 0)) > 0
    )
    checks["sampled_digest_mismatch_check"] = "PASS" if mismatch_ok else "FAIL"

    # 18. long_run_ticks_check
    checks["long_run_ticks_check"] = (
        "PASS" if int(summary.get("run_ticks", 0)) >= MINIMUM_RUN_TICKS else "FAIL"
    )

    # 19. artifact_index_completeness_check
    index_ok = bool(artifact_index)
    for label in REQUIRED_ARTIFACT_LABELS:
        relative = artifact_index.get(label)
        if not relative or not (path / relative).exists():
            index_ok = False
            break
    checks["artifact_index_completeness_check"] = "PASS" if index_ok else "FAIL"

    # 20. status_surface_read_only_check
    snapshot = _read_json(path / "run_status_snapshot.json")
    checks["status_surface_read_only_check"] = (
        "PASS"
        if summary.get("status_surface_read_only") is True and bool(snapshot.get("input_digest"))
        else "FAIL"
    )

    # 21. self_contained_status_page_check
    page_path = path / "run_dashboard.html"
    page_ok = page_path.exists()
    if page_ok:
        page_text = page_path.read_text(encoding="utf-8").lower()
        page_ok = not any(marker in page_text for marker in EXTERNAL_REFERENCE_MARKERS)
    checks["self_contained_status_page_check"] = (
        "PASS" if page_ok and summary.get("status_page_self_contained") is True else "FAIL"
    )

    # 22. bounded_artifact_size_check
    max_lines = 0
    for candidate in path.rglob("*.jsonl"):
        max_lines = max(max_lines, _count_lines(candidate))
    checks["bounded_artifact_size_check"] = (
        "PASS" if 0 < max_lines < MAXIMUM_ARTIFACT_LINES else "FAIL"
    )

    # 23. m14_m15_m16_m17_m18_m19_regression_check
    regression = summary.get("strict_regression_summary", {})
    required_regression = [f"m{n}_regression" for n in ("14", "15", "16", "17", "18", "19")]
    regression_ok = bool(regression) and all(
        regression.get(key) == "PASS" for key in required_regression
    )
    checks["m14_m15_m16_m17_m18_m19_regression_check"] = "PASS" if regression_ok else "FAIL"

    # 24. machine_native_wording_check
    all_text = ""
    for pattern in ("*.json", "*.jsonl"):
        for candidate in path.glob(pattern):
            try:
                all_text += candidate.read_text(encoding="utf-8").lower()
            except OSError:
                continue
    found = [term for term in FORBIDDEN_TERMS if term in all_text]
    checks["machine_native_wording_check"] = "PASS" if not found else "FAIL"

    non_pass = [name for name, result in checks.items() if result != "PASS"]
    status = "PASS" if not non_pass else "FAIL"

    return {
        "M20_JUDGE_STATUS": status,
        "checks": checks,
        "failed_checks": non_pass,
        "forbidden_terms_found": found,
        "thresholds": {
            "minimum_run_ticks": MINIMUM_RUN_TICKS,
            "minimum_checkpoints": MINIMUM_CHECKPOINTS,
            "minimum_resumed_tick_span": MINIMUM_RESUMED_TICK_SPAN,
            "maximum_artifact_lines": MAXIMUM_ARTIFACT_LINES,
        },
    }


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m machine_sim.verification.milestone_20_judge <output_dir>")
        sys.exit(1)

    output_dir = sys.argv[1]
    results = judge(output_dir)

    out_path = Path(output_dir) / "milestone_20_judge_result.json"
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    print(f"M20_JUDGE_STATUS: {results['M20_JUDGE_STATUS']}")
    for check_name, check_status in results["checks"].items():
        print(f"  {check_name}: {check_status}")

    if results["failed_checks"]:
        print(f"\nFailed checks: {', '.join(results['failed_checks'])}")
        sys.exit(1)
    print("\nAll checks passed.")


if __name__ == "__main__":
    main()
