"""M21 repeatable benchmark harness and standard-library profiling substrate.

All measurements use ``time.perf_counter()`` and :mod:`cprofile`-grade
standard-library tooling. Benchmark instrumentation never alters simulation
outcomes: counters are plain integers that nothing in the tick loop reads, and
they are excluded from the deep semantic-state digest by construction.
"""

from __future__ import annotations

import cProfile
import json
import pstats
import io
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from machine_sim.cli.main import build_engine
from machine_sim.sim.checkpoint import config_digest, list_checkpoints
from machine_sim.sim.config import SimConfig
from machine_sim.sim.run_control import RunController


def _active_unit_count(engine: Any) -> int:
    return sum(1 for u in engine.units if u.is_active)


def _neural_forward_total(engine: Any) -> int:
    total = 0
    for unit in engine.units:
        controller = getattr(unit, "_neural_controller", None)
        if controller is not None:
            total += getattr(controller, "forward_evaluations", 0)
    return total


def measure_run(
    config: SimConfig,
    ticks: Optional[int] = None,
    checkpoint_interval: Optional[int] = None,
) -> Dict[str, Any]:
    """Run one measured simulation pass and return its metric mapping."""
    ticks = int(ticks if ticks is not None else config.max_ticks)
    engine = build_engine(config)

    started = time.perf_counter()
    engine.initialize()
    initialization_seconds = time.perf_counter() - started

    checkpoint_write_seconds = 0.0
    checkpoint_count = 0
    controller: Optional[RunController] = None
    if checkpoint_interval:
        output_dir = Path("output/_benchmark_checkpoint_probe")
        controller = RunController(
            engine,
            output_dir,
            checkpoint_enabled=True,
            checkpoint_interval=max(1, checkpoint_interval),
            run_digest_enabled=True,
        )
        controller.start()
        original_create = controller.create_checkpoint

        def timed_create() -> Any:
            nonlocal checkpoint_write_seconds, checkpoint_count
            mark = time.perf_counter()
            result = original_create()
            checkpoint_write_seconds += time.perf_counter() - mark
            checkpoint_count += 1
            return result

        controller.create_checkpoint = timed_create  # type: ignore[method-assign]

    peak_active = _active_unit_count(engine)
    simulation_started = time.perf_counter()
    if controller is not None:
        while engine.tick_count < ticks:
            target = min(ticks, engine.tick_count + max(1, checkpoint_interval or ticks))
            controller.advance(target)
            peak_active = max(peak_active, _active_unit_count(engine))
            if controller.manifest.run_state != "running":
                break
    else:
        while engine.tick_count < ticks:
            engine.tick()
            peak_active = max(peak_active, _active_unit_count(engine))
    simulation_seconds = time.perf_counter() - simulation_started
    wall_seconds = time.perf_counter() - started

    checkpoint_bytes_written = 0
    if controller is not None:
        controller.finalize_artifact_index()
        for path in list_checkpoints(controller.output_dir):
            checkpoint_bytes_written += path.stat().st_size

    world = engine.world
    metrics: Dict[str, Any] = {
        "initialization_seconds": round(initialization_seconds, 6),
        "simulation_seconds": round(simulation_seconds, 6),
        "wall_seconds": round(wall_seconds, 6),
        "ticks": engine.tick_count,
        "ticks_per_second": round(engine.tick_count / simulation_seconds, 4)
        if simulation_seconds > 0
        else 0.0,
        "unit_decisions_total": engine.bench_unit_decisions,
        "unit_decisions_per_second": round(
            engine.bench_unit_decisions / simulation_seconds, 4
        )
        if simulation_seconds > 0
        else 0.0,
        "neural_forward_evaluations_total": _neural_forward_total(engine),
        "neural_forward_evaluations_per_second": round(
            _neural_forward_total(engine) / simulation_seconds, 4
        )
        if simulation_seconds > 0
        else 0.0,
        "world_update_calls": world.update_calls,
        "world_cells_visited_total": world.cells_visited_total,
        "world_cells_updated_total": world.cells_updated_total,
        "peak_active_unit_count": peak_active,
        "final_active_unit_count": _active_unit_count(engine),
        "total_unit_count": len(engine.units),
        "checkpoint_write_seconds": round(checkpoint_write_seconds, 6)
        if checkpoint_interval
        else None,
        "checkpoint_bytes_written": checkpoint_bytes_written
        if checkpoint_interval
        else None,
        "checkpoint_count": checkpoint_count if checkpoint_interval else None,
    }
    return metrics


def run_benchmark_suite(
    config_path: Path,
    output_dir: Path,
    label: str,
    repetitions: int = 3,
    warmup: int = 1,
    ticks: Optional[int] = None,
    checkpoint_interval: Optional[int] = None,
) -> Dict[str, Any]:
    """Warm up, then measure the configured benchmark repeatedly."""
    config = SimConfig.from_toml(Path(config_path))
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for _ in range(max(0, warmup)):
        measure_run(config, ticks=ticks)

    repetitions_metrics: List[Dict[str, Any]] = []
    for index in range(max(1, repetitions)):
        metrics = measure_run(config, ticks=ticks, checkpoint_interval=checkpoint_interval)
        metrics["repetition"] = index
        repetitions_metrics.append(metrics)

    def median_of(key: str) -> float:
        values = [m[key] for m in repetitions_metrics if m.get(key) is not None]
        return round(statistics.median(values), 6) if values else 0.0

    summary: Dict[str, Any] = {
        "label": label,
        "config_path": str(config_path),
        "config_digest": config_digest(config),
        "seed": int(config.seed),
        "grid_width": int(config.grid_width),
        "grid_height": int(config.grid_height),
        "requested_ticks": ticks or int(config.max_ticks),
        "repetitions": len(repetitions_metrics),
        "warmup_runs": max(0, warmup),
        "checkpoint_interval": checkpoint_interval,
        "metrics_median": {
            key: median_of(key)
            for key in (
                "initialization_seconds",
                "simulation_seconds",
                "wall_seconds",
                "ticks_per_second",
                "unit_decisions_per_second",
                "neural_forward_evaluations_per_second",
                "world_update_calls",
                "world_cells_visited_total",
                "world_cells_updated_total",
                "checkpoint_write_seconds",
                "checkpoint_bytes_written",
                "peak_active_unit_count",
            )
        },
        "repetitions_detail": repetitions_metrics,
    }
    target = output_dir / f"performance_{label}.json"
    target.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return summary


def run_population_scaling(
    config_path: Path,
    output_dir: Path,
    unit_tiers: Optional[List[int]] = None,
    ticks: Optional[int] = None,
    repetitions: int = 1,
    warmup: int = 1,
) -> Path:
    """Measure initialization and simulation scaling across unit tiers."""
    tiers = unit_tiers or [10, 100, 1000]
    base_config = SimConfig.from_toml(Path(config_path))
    ticks = int(ticks if ticks is not None else min(60, base_config.max_ticks))
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / "population_scaling.jsonl"

    rows: List[Dict[str, Any]] = []
    for tier in tiers:
        config = SimConfig(**{**base_config.to_dict(), "unit_count": tier})
        for _ in range(max(0, warmup)):
            measure_run(config, ticks=ticks)
        best: Optional[Dict[str, Any]] = None
        for repetition in range(max(1, repetitions)):
            metrics = measure_run(config, ticks=ticks)
            metrics["initial_units"] = tier
            metrics["repetition"] = repetition
            rows.append(metrics)
            if best is None or metrics["simulation_seconds"] < best["simulation_seconds"]:
                best = metrics
        assert best is not None

    with open(target, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    return target


def profile_hotspots(
    config_path: Path,
    output_dir: Path,
    label: str,
    ticks: Optional[int] = None,
    top_entries: int = 30,
) -> Dict[str, Any]:
    """Produce a standard-library profiler summary for one representative run."""
    config = SimConfig.from_toml(Path(config_path))
    ticks = int(ticks if ticks is not None else config.max_ticks)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    profiler = cProfile.Profile()
    profiler.enable()
    metrics = measure_run(config, ticks=ticks)
    profiler.disable()

    stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stream)
    stats.strip_dirs().sort_stats("cumulative").print_stats(top_entries)
    text_output = stream.getvalue()

    by_internal: List[Dict[str, Any]] = []
    for (_filename, line_number, name), (
        call_count,
        primitive_calls,
        total_time,
        cumulative_time,
        callers,
    ) in stats.stats.items():
        by_internal.append(
            {
                "function": name,
                "file_line": f"{_filename}:{line_number}",
                "call_count": call_count,
                "primitive_calls": primitive_calls,
                "total_seconds": round(total_time, 6),
                "cumulative_seconds": round(cumulative_time, 6),
            }
        )
    by_internal.sort(key=lambda item: item["cumulative_seconds"], reverse=True)
    top_cumulative = by_internal[:top_entries]
    top_internal = sorted(by_internal, key=lambda item: item["total_seconds"], reverse=True)[
        :top_entries
    ]

    report = {
        "label": label,
        "config_path": str(config_path),
        "config_digest": config_digest(config),
        "profiled_ticks": ticks,
        "run_wall_seconds": metrics["wall_seconds"],
        "run_simulation_seconds": metrics["simulation_seconds"],
        "top_by_cumulative": top_cumulative,
        "top_by_internal": top_internal,
    }
    json_target = output_dir / f"hotspot_profile_{label}.json"
    json_target.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    text_target = output_dir / f"profile_{label}.txt"
    text_target.write_text(text_output, encoding="utf-8")
    return report


def compare_performance(
    baseline_path: Path,
    optimized_path: Path,
    output_path: Path,
    minimum_speedup: float = 2.5,
) -> Dict[str, Any]:
    """Compare two benchmark summaries and record the speedup ratio."""
    baseline = json.loads(Path(baseline_path).read_text(encoding="utf-8"))
    optimized = json.loads(Path(optimized_path).read_text(encoding="utf-8"))
    base_tps = baseline["metrics_median"]["ticks_per_second"]
    opt_tps = optimized["metrics_median"]["ticks_per_second"]
    speedup = round(opt_tps / base_tps, 4) if base_tps else 0.0
    base_world_visited = baseline["metrics_median"]["world_cells_visited_total"]
    opt_world_visited = optimized["metrics_median"]["world_cells_visited_total"]

    report = {
        "baseline_label": baseline.get("label"),
        "optimized_label": optimized.get("label"),
        "baseline_ticks_per_second_median": base_tps,
        "optimized_ticks_per_second_median": opt_tps,
        "primary_end_to_end_speedup": speedup,
        "minimum_required_speedup": minimum_speedup,
        "meets_required_speedup": speedup >= minimum_speedup,
        "baseline_simulation_seconds_median": baseline["metrics_median"][
            "simulation_seconds"
        ],
        "optimized_simulation_seconds_median": optimized["metrics_median"][
            "simulation_seconds"
        ],
        "baseline_initialization_seconds_median": baseline["metrics_median"][
            "initialization_seconds"
        ],
        "optimized_initialization_seconds_median": optimized["metrics_median"][
            "initialization_seconds"
        ],
        "world_cells_visited_baseline_per_run": base_world_visited,
        "world_cells_visited_optimized_per_run": opt_world_visited,
        "baseline_repetitions": baseline.get("repetitions"),
        "optimized_repetitions": optimized.get("repetitions"),
    }
    Path(output_path).write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    return report


__all__ = [
    "compare_performance",
    "measure_run",
    "profile_hotspots",
    "run_benchmark_suite",
    "run_population_scaling",
]
