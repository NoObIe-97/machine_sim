"""M21 deterministic reference trajectory freezing and equivalence verification.

Phase 0 of Milestone 21 freezes deep semantic-state trajectories from the
accepted pre-optimization behavior. Phase 4 replays the exact same
configurations after runtime refactoring and requires zero deep-digest
mismatches at every sampled tick.

Reference series:

* A — short deterministic baseline (core loop, neural processing).
* B — neural + architecture-variation baseline with fabrication and capsules.
* C — pause/resume reference driven by M20 run controls across a real process
  boundary, verified against an uninterrupted reference of the same
  configuration for both the shallow M20 run digest chain and the deep digest.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from machine_sim.cli.main import build_engine
from machine_sim.sim.checkpoint import config_digest
from machine_sim.sim.config import SimConfig
from machine_sim.sim.run_control import (
    RUN_STATE_COMPLETED,
    RUN_STATE_PAUSED,
    ControlChannel,
    RunManifest,
    advance_run_digest,
    derive_run_id,
    initial_run_digest,
    latest_checkpoint_file,
    tick_observation,
)
from machine_sim.sim.state_digest import deep_state_digest

DEFAULT_SAMPLE_INTERVAL = 100


def read_deep_trace(path: Path) -> Dict[int, Dict[str, Any]]:
    """Read an append-only deep-digest JSONL trace into a per-tick mapping."""
    samples: Dict[int, Dict[str, Any]] = {}
    if not Path(path).exists():
        return samples
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            samples[int(record["tick"])] = record
    return samples


def write_sample(handle: Any, tick: int, engine: Any, run_digest: str) -> None:
    handle.write(
        json.dumps(
            {
                "tick": int(tick),
                "deep_digest": deep_state_digest(engine),
                "run_digest": run_digest,
            },
            sort_keys=True,
        )
        + "\n"
    )


@dataclass
class DirectRunResult:
    series: str
    config_path: Path
    seed: int
    config_digest: str
    sample_interval: int
    trace_path: Path
    tick_count: int
    wall_seconds: float


def run_direct_family(
    series: str,
    config_path: Path,
    output_dir: Path,
    sample_interval: int,
) -> DirectRunResult:
    """Run a reference series in-process with per-interval deep sampling."""
    config = SimConfig.from_toml(Path(config_path))
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    trace_path = output_dir / f"deep_state_digest_trace_{series}.jsonl"

    fingerprint_seed = derive_run_id(
        config_digest(config),
        int(config.seed),
        int(config.max_ticks),
    )
    run_digest = initial_run_digest(fingerprint_seed)

    engine = build_engine(config)
    started = time.perf_counter()
    engine.initialize()
    # Mirror RunController: the M20 chain value lives on the engine so a
    # resumed run continues it; the direct runner carries the same field.
    engine.run_digest_value = run_digest
    with open(trace_path, "w", encoding="utf-8") as handle:
        while engine.tick_count < config.max_ticks:
            engine.tick()
            run_digest = advance_run_digest(run_digest, tick_observation(engine))
            engine.run_digest_value = run_digest
            if engine.tick_count % sample_interval == 0:
                write_sample(handle, engine.tick_count, engine, run_digest)
    wall_seconds = time.perf_counter() - started

    return DirectRunResult(
        series=series,
        config_path=Path(config_path),
        seed=int(config.seed),
        config_digest=config_digest(config),
        sample_interval=sample_interval,
        trace_path=trace_path,
        tick_count=engine.tick_count,
        wall_seconds=wall_seconds,
    )


@dataclass
class ControlledRunResult:
    series: str
    config_path: Path
    seed: int
    config_digest: str
    sample_interval: int
    trace_path: Path
    reference_trace_path: Path
    work_dir: Path
    pause_tick: int
    resumed_span: int
    process_isolated: bool
    shallow_chain_equal: bool
    deep_samples_equal: bool
    wall_seconds: float


def run_controlled_family(
    config_path: Path,
    output_dir: Path,
    sample_interval: int,
    pause_fraction: float = 0.4,
) -> ControlledRunResult:
    """Freeze the pause/resume reference: uninterrupted baseline + real
    process-isolated pause/restart/resume scenario with deep sampling."""

    config = SimConfig.from_toml(Path(config_path))
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Uninterrupted reference for the same configuration.
    reference_result = run_direct_family("c-ref", config_path, output_dir, sample_interval)

    # Process-isolated pause/resume scenario.
    work_dir = output_dir / "controlled_run"
    if work_dir.exists():
        import shutil

        shutil.rmtree(work_dir)
    trace_path = output_dir / "deep_state_digest_trace_c.jsonl"
    if trace_path.exists():
        trace_path.unlink()

    pause_tick = max(1, int(config.max_ticks * pause_fraction))
    base_command = [
        sys.executable,
        "-m",
        "machine_sim.cli.main",
        "run",
        "-c",
        str(config_path),
        "-o",
        str(work_dir),
        "--deep-digest-interval",
        str(sample_interval),
        "--deep-digest-trace",
        str(trace_path),
    ]

    repo_root = Path(__file__).resolve().parents[2]
    started = time.perf_counter()

    work_dir.mkdir(parents=True, exist_ok=True)
    segment_log = open(work_dir / "segment_one_console.log", "w", encoding="utf-8")
    try:
        segment_one = subprocess.Popen(base_command, cwd=str(repo_root), stdout=segment_log)
        manifest_path = work_dir / "run_manifest.json"
        deadline = time.time() + 3600
        while time.time() < deadline:
            if not manifest_path.exists():
                time.sleep(0.5)
                continue
            manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
            if int(manifest_data.get("completed_ticks", 0)) >= pause_tick:
                break
            if manifest_data.get("run_state") == RUN_STATE_COMPLETED:
                raise RuntimeError(
                    "controlled run completed before the pause target was reached"
                )
            if segment_one.poll() is not None:
                raise RuntimeError(
                    f"controlled segment-one process exited before pause target: "
                    f"rc={segment_one.returncode}"
                )
            time.sleep(0.5)
        channel = ControlChannel(work_dir)
        channel.write_request("pause")
        applied_deadline = time.time() + 600
        while time.time() < applied_deadline:
            manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest_data.get("run_state") == RUN_STATE_PAUSED:
                break
            if manifest_data.get("run_state") == RUN_STATE_COMPLETED:
                raise RuntimeError(
                    "controlled run completed although a pause request was filed"
                )
            if segment_one.poll() is not None and manifest_data.get("run_state") != RUN_STATE_PAUSED:
                raise RuntimeError(
                    f"controlled segment-one exited without pausing: "
                    f"rc={segment_one.returncode}, state={manifest_data.get('run_state')}"
                )
            time.sleep(0.5)
    finally:
        segment_log.close()
    segment_one.wait()
    if segment_one.returncode != 0:
        raise RuntimeError(f"controlled segment-one failed: rc={segment_one.returncode}")
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    applied_pause_tick = int(manifest_data.get("completed_ticks", 0))
    if manifest_data.get("run_state") != RUN_STATE_PAUSED:
        raise RuntimeError(
            f"controlled run did not reach paused state: {manifest_data.get('run_state')}"
        )

    checkpoint = latest_checkpoint_file(work_dir)
    if checkpoint is None:
        raise RuntimeError("controlled run produced no checkpoint before pause")

    resumed_log_path = work_dir / "segment_two_console.log"
    with open(resumed_log_path, "w", encoding="utf-8") as resumed_log:
        resumed = subprocess.run(
            base_command + ["--resume-from", str(checkpoint)],
            cwd=str(repo_root),
            stdout=resumed_log,
            stderr=subprocess.STDOUT,
        )
    if resumed.returncode != 0:
        raise RuntimeError(
            f"controlled resume failed: {resumed_log_path.read_text(encoding='utf-8')[-2000:]}"
        )
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest_data.get("run_state") != RUN_STATE_COMPLETED:
        raise RuntimeError(
            f"resumed run did not complete: {manifest_data.get('run_state')}"
        )

    wall_seconds = time.perf_counter() - started

    reference_samples = read_deep_trace(reference_result.trace_path)
    scenario_samples = read_deep_trace(trace_path)
    common_ticks = sorted(set(reference_samples) & set(scenario_samples))
    deep_equal = bool(common_ticks) and all(
        reference_samples[t]["deep_digest"] == scenario_samples[t]["deep_digest"]
        for t in common_ticks
    )
    shallow_equal = bool(common_ticks) and all(
        reference_samples[t].get("run_digest")
        == scenario_samples[t].get("run_digest")
        for t in common_ticks
    )
    final_manifest = RunManifest.load(work_dir)

    return ControlledRunResult(
        series="c",
        config_path=Path(config_path),
        seed=int(config.seed),
        config_digest=config_digest(config),
        sample_interval=sample_interval,
        trace_path=trace_path,
        reference_trace_path=reference_result.trace_path,
        work_dir=work_dir,
        pause_tick=applied_pause_tick,
        resumed_span=int(final_manifest.data["requested_ticks"]) - applied_pause_tick,
        process_isolated=True,
        shallow_chain_equal=shallow_equal,
        deep_samples_equal=deep_equal,
        wall_seconds=wall_seconds,
    )


def freeze_references(
    config_paths: Dict[str, Path],
    output_dir: Path,
    accepted_commit: str,
    sample_interval: int = DEFAULT_SAMPLE_INTERVAL,
) -> Dict[str, Any]:
    """Run every required reference series and write the frozen artifacts."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    result_a = run_direct_family("a", config_paths["a"], output_dir, sample_interval)
    result_b = run_direct_family("b", config_paths["b"], output_dir, sample_interval)
    result_c = run_controlled_family(config_paths["c"], output_dir, sample_interval)

    # Combined append-only trace artifact.
    combined_trace = output_dir / "deep_state_digest_trace.jsonl"
    with open(combined_trace, "w", encoding="utf-8") as target:
        for source in (
            result_a.trace_path,
            result_b.trace_path,
            result_c.reference_trace_path,
            result_c.trace_path,
        ):
            if not Path(source).exists():
                continue
            with open(source, "r", encoding="utf-8") as handle:
                for line in handle:
                    if line.strip():
                        target.write(line if line.endswith("\n") else line + "\n")

    configs_manifest = {}
    for series, path in (("a", config_paths["a"]), ("b", config_paths["b"]), ("c", config_paths["c"])):
        config = SimConfig.from_toml(Path(path))
    
        configs_manifest[series] = {
            "path": str(Path(path)),
            "seed": int(config.seed),
            "max_ticks": int(config.max_ticks),
            "grid_width": int(config.grid_width),
            "grid_height": int(config.grid_height),
            "unit_count": int(config.unit_count),
            "neural_controller_enabled": bool(config.neural_controller_enabled),
            "neural_architecture_variation_enabled": bool(
                config.neural_architecture_variation_enabled
            ),
            "fabrication_enabled": bool(config.fabrication_enabled),
            "config_digest": config_digest(config),
        }

    summary = {
        "accepted_reference_commit": accepted_commit,
        "freeze_commit": _current_commit(),
        "sample_interval": sample_interval,
        "series": {
            "a": {
                "description": "short deterministic baseline",
                "ticks": result_a.tick_count,
                "minimum_required_ticks": 2000,
                "meets_minimum": result_a.tick_count >= 2000,
                "seed": result_a.seed,
                "config_digest": result_a.config_digest,
                "trace_path": str(result_a.trace_path),
                "wall_seconds": round(result_a.wall_seconds, 3),
            },
            "b": {
                "description": "neural + architecture-variation baseline",
                "ticks": result_b.tick_count,
                "minimum_required_ticks": 5000,
                "meets_minimum": result_b.tick_count >= 5000,
                "seed": result_b.seed,
                "config_digest": result_b.config_digest,
                "trace_path": str(result_b.trace_path),
                "wall_seconds": round(result_b.wall_seconds, 3),
            },
            "c": {
                "description": "process-isolated pause/resume reference",
                "ticks": result_c.work_dir and int(result_c.resumed_span + result_c.pause_tick),
                "minimum_required_ticks": 2000,
                "meets_minimum": (result_c.pause_tick + result_c.resumed_span) >= 2000,
                "seed": result_c.seed,
                "config_digest": result_c.config_digest,
                "pause_tick": result_c.pause_tick,
                "resumed_span": result_c.resumed_span,
                "process_isolated": result_c.process_isolated,
                "uninterrupted_vs_resumed_deep_samples_equal": result_c.deep_samples_equal,
                "uninterrupted_vs_resumed_shallow_chain_equal": result_c.shallow_chain_equal,
                "scenario_trace_path": str(result_c.trace_path),
                "reference_trace_path": str(result_c.reference_trace_path),
                "wall_seconds": round(result_c.wall_seconds, 3),
            },
        },
        "combined_trace_path": str(combined_trace),
    }
    if not (summary["series"]["c"]["uninterrupted_vs_resumed_deep_samples_equal"]
            and summary["series"]["c"]["uninterrupted_vs_resumed_shallow_chain_equal"]):
        summary["series"]["c"]["continuity_warning"] = (
            "frozen pause/resume scenario diverged from its uninterrupted reference"
        )

    summary_path = output_dir / "reference_run_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    manifest_path = output_dir / "reference_config_manifest.json"
    manifest_path.write_text(
        json.dumps(configs_manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    summary["artifact_paths"] = {
        "reference_run_summary": str(summary_path),
        "reference_config_manifest": str(manifest_path),
        "deep_state_digest_trace": str(combined_trace),
    }
    return summary


def compare_traces(
    reference_trace: Path,
    optimized_trace: Path,
) -> Dict[str, Any]:
    """Compare two deep-digest traces sample by sample."""
    reference_samples = read_deep_trace(Path(reference_trace))
    optimized_samples = read_deep_trace(Path(optimized_trace))
    reference_only = sorted(set(reference_samples) - set(optimized_samples))
    optimized_only = sorted(set(optimized_samples) - set(reference_samples))
    common = sorted(set(reference_samples) & set(optimized_samples))
    mismatches = [
        tick
        for tick in common
        if reference_samples[tick]["deep_digest"] != optimized_samples[tick]["deep_digest"]
    ]
    shallow_mismatches = [
        tick
        for tick in common
        if reference_samples[tick].get("run_digest")
        != optimized_samples[tick].get("run_digest")
    ]
    final_tick = common[-1] if common else None
    return {
        "sample_count": len(common),
        "matching_sample_count": len(common) - len(mismatches),
        "mismatch_count": len(mismatches),
        "first_mismatch_tick": mismatches[0] if mismatches else None,
        "missing_optimized_samples": reference_only,
        "unexpected_optimized_samples": optimized_only,
        "final_reference_digest": (
            reference_samples[final_tick]["deep_digest"] if final_tick is not None else None
        ),
        "final_optimized_digest": (
            optimized_samples[final_tick]["deep_digest"] if final_tick is not None else None
        ),
        "final_equal": (
            reference_samples[final_tick]["deep_digest"]
            == optimized_samples[final_tick]["deep_digest"]
            if final_tick is not None
            else False
        ),
        "shallow_run_digest_mismatch_count": len(shallow_mismatches),
    }


def verify_equivalence(
    config_paths: Dict[str, Path],
    reference_dir: Path,
    determinism_dir: Path,
    accepted_commit: str,
    optimized_commit: Optional[str] = None,
    sample_interval: int = DEFAULT_SAMPLE_INTERVAL,
) -> Dict[str, Any]:
    """Rerun the frozen reference configurations and require zero mismatches."""
    reference_dir = Path(reference_dir)
    determinism_dir = Path(determinism_dir)
    determinism_dir.mkdir(parents=True, exist_ok=True)

    rerun_dir = determinism_dir / "rerun"
    rerun_dir.mkdir(parents=True, exist_ok=True)

    report: Dict[str, Any] = {
        "accepted_reference_commit": accepted_commit,
        "optimized_commit": optimized_commit or _current_commit(),
        "sample_interval": sample_interval,
        "series": {},
    }
    total_samples = 0
    total_matches = 0
    total_mismatches = 0
    first_mismatch: Optional[int] = None

    comparisons: List[Tuple[str, Path, Path]] = []

    result_a = run_direct_family("a", config_paths["a"], rerun_dir, sample_interval)
    comparisons.append(("a", reference_dir / "deep_state_digest_trace_a.jsonl", result_a.trace_path))

    result_b = run_direct_family("b", config_paths["b"], rerun_dir, sample_interval)
    comparisons.append(("b", reference_dir / "deep_state_digest_trace_b.jsonl", result_b.trace_path))

    result_c = run_controlled_family(config_paths["c"], rerun_dir / "family_c", sample_interval)
    comparisons.append(
        ("c-uninterrupted", reference_dir / "deep_state_digest_trace_c-ref.jsonl", result_c.reference_trace_path)
    )
    comparisons.append(
        ("c-pause-resume", reference_dir / "deep_state_digest_trace_c.jsonl", result_c.trace_path)
    )

    for series, reference_trace, optimized_trace in comparisons:
        outcome = compare_traces(reference_trace, optimized_trace)
    
        outcome.update(
            {
                "config_digest": config_digest(SimConfig.from_toml(Path(config_paths[series[0]]))),
                "seed": int(SimConfig.from_toml(Path(config_paths[series[0]])).seed),
                "reference_trace": str(reference_trace),
                "optimized_trace": str(optimized_trace),
            }
        )
        report["series"][series] = outcome
        total_samples += outcome["sample_count"]
        total_matches += outcome["matching_sample_count"]
        total_mismatches += outcome["mismatch_count"]
        if outcome["first_mismatch_tick"] is not None:
            if first_mismatch is None or outcome["first_mismatch_tick"] < first_mismatch:
                first_mismatch = outcome["first_mismatch_tick"]

    report.update(
        {
            "config_digest": report["series"]["b"]["config_digest"],
            "seed": report["series"]["b"]["seed"],
            "sample_count": total_samples,
            "matching_sample_count": total_matches,
            "mismatch_count": total_mismatches,
            "first_mismatch_tick": first_mismatch,
            "final_reference_digest": report["series"]["b"]["final_reference_digest"],
            "final_optimized_digest": report["series"]["b"]["final_optimized_digest"],
            "final_equal": all(
                family_outcome["final_equal"] for family_outcome in report["series"].values()
            ),
            "zero_mismatch_acceptance": total_mismatches == 0 and total_samples > 0,
        }
    )

    deep_report_path = determinism_dir / "deep_equivalence_report.json"
    deep_report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    family_c = report["series"]["c-pause-resume"]
    pause_report = {
        "accepted_reference_commit": accepted_commit,
        "optimized_commit": report["optimized_commit"],
        "process_isolated": True,
        "pause_tick": result_c.pause_tick,
        "resumed_span": result_c.resumed_span,
        "sample_interval": sample_interval,
        "sample_count": family_c["sample_count"],
        "matching_sample_count": family_c["matching_sample_count"],
        "mismatch_count": family_c["mismatch_count"],
        "first_mismatch_tick": family_c["first_mismatch_tick"],
        "final_reference_digest": family_c["final_reference_digest"],
        "final_optimized_digest": family_c["final_optimized_digest"],
        "final_equal": family_c["final_equal"],
        "shallow_run_digest_mismatch_count": family_c["shallow_run_digest_mismatch_count"],
        "deep_and_shallow_equal": (
            family_c["mismatch_count"] == 0
            and family_c["shallow_run_digest_mismatch_count"] == 0
            and family_c["sample_count"] > 0
        ),
    }
    pause_report_path = determinism_dir / "pause_resume_deep_equivalence_report.json"
    pause_report_path.write_text(
        json.dumps(pause_report, indent=2, sort_keys=True), encoding="utf-8"
    )
    return report


def _current_commit() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if completed.returncode == 0:
            return completed.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return "unknown"


__all__ = [
    "DEFAULT_SAMPLE_INTERVAL",
    "compare_traces",
    "freeze_references",
    "read_deep_trace",
    "run_controlled_family",
    "run_direct_family",
    "verify_equivalence",
]
