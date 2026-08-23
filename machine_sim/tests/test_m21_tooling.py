"""Functional tests for the M21 measurement tooling (benchmark harness,
reference runner helpers, checkpoint growth probe)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from machine_sim.perf.benchmark import (
    compare_performance,
    measure_checkpoint_growth,
    measure_run,
    profile_hotspots,
    run_benchmark_suite,
)
from machine_sim.perf.reference import compare_traces, read_deep_trace, write_sample
from machine_sim.sim.config import SimConfig


def _tiny_config(**overrides) -> SimConfig:
    values = dict(
        grid_width=8,
        grid_height=8,
        resource_density=0.25,
        hazard_density=0.05,
        unit_count=2,
        max_ticks=12,
        seed=5,
        signal_enabled=True,
        adaptive_enabled=True,
        neural_controller_enabled=True,
    )
    values.update(overrides)
    return SimConfig(**values)


@pytest.mark.parametrize("tier", [1, 3])
def test_measure_run_reports_required_metrics(tier: int) -> None:
    metrics = measure_run(_tiny_config(unit_count=tier), ticks=4)
    for key in (
        "initialization_seconds",
        "simulation_seconds",
        "wall_seconds",
        "ticks_per_second",
        "unit_decisions_total",
        "unit_decisions_per_second",
        "neural_forward_evaluations_total",
        "neural_forward_evaluations_per_second",
        "world_update_calls",
        "world_cells_visited_total",
        "world_cells_updated_total",
        "peak_active_unit_count",
    ):
        assert key in metrics
    assert metrics["world_update_calls"] == 4
    assert metrics["ticks"] == 4


def test_benchmark_suite_writes_artifact(tmp_path: Path) -> None:
    config_path = tmp_path / "tiny.toml"
    values = _tiny_config().to_dict()
    lines = ["[simulation]"]
    for key, value in values.items():
        if isinstance(value, bool):
            rendered = "true" if value else "false"
        elif isinstance(value, str):
            rendered = f'"{value}"'
        else:
            rendered = str(value)
        lines.append(f"{key} = {rendered}")
    config_path.write_text("\n".join(lines), encoding="utf-8")

    summary = run_benchmark_suite(
        config_path=config_path,
        output_dir=tmp_path / "perf",
        label="probe",
        repetitions=2,
        warmup=0,
        ticks=4,
    )
    assert summary["repetitions"] == 2
    assert summary["metrics_median"]["ticks_per_second"] > 0
    artifact = tmp_path / "perf" / "performance_probe.json"
    assert json.loads(artifact.read_text(encoding="utf-8"))["label"] == "probe"


def test_profile_hotspots_writes_reports(tmp_path: Path) -> None:
    report = profile_hotspots.__wrapped__ if hasattr(profile_hotspots, "__wrapped__") else None
    from machine_sim.perf.benchmark import profile_hotspots as profile_fn

    result = None
    # Direct call with a tiny in-memory config is not supported (it reads a
    # path), so reuse the suite artifact path via a temp TOML.
    config_path = tmp_path / "tiny.toml"
    lines = ["[simulation]"]
    for key, value in _tiny_config(max_ticks=6).to_dict().items():
        if isinstance(value, bool):
            rendered = "true" if value else "false"
        elif isinstance(value, str):
            rendered = f'"{value}"'
        else:
            rendered = str(value)
        lines.append(f"{key} = {rendered}")
    config_path.write_text("\n".join(lines), encoding="utf-8")
    result = profile_fn(config_path, tmp_path / "prof", "probe", ticks=4)
    assert result["top_by_cumulative"]
    assert (tmp_path / "prof" / "hotspot_profile_probe.json").exists()
    assert (tmp_path / "prof" / "profile_probe.txt").exists()
    assert report is None


def test_compare_performance_records_ratio(tmp_path: Path) -> None:
    baseline = {
        "label": "baseline",
        "repetitions": 3,
        "metrics_median": {"ticks_per_second": 50.0, "simulation_seconds": 2.0,
                           "initialization_seconds": 0.1},
    }
    optimized = {
        "label": "optimized",
        "repetitions": 3,
        "metrics_median": {"ticks_per_second": 130.0, "simulation_seconds": 0.8,
                           "initialization_seconds": 0.1},
    }
    baseline_path = tmp_path / "b.json"
    optimized_path = tmp_path / "o.json"
    out_path = tmp_path / "cmp.json"
    baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
    optimized_path.write_text(json.dumps(optimized), encoding="utf-8")
    report = compare_performance(baseline_path, optimized_path, out_path, 2.5)
    assert report["primary_end_to_end_speedup"] == pytest.approx(2.6, abs=0.01)
    assert report["meets_required_speedup"] is True


def test_checkpoint_growth_probe_runs(tmp_path: Path) -> None:
    config_path = tmp_path / "tiny.toml"
    lines = ["[simulation]"]
    values = _tiny_config(
        max_ticks=9, run_control_enabled=True, checkpoint_interval=3,
        control_poll_interval=100, run_progress_interval=100,
    ).to_dict()
    for key, value in values.items():
        if isinstance(value, bool):
            rendered = "true" if value else "false"
        elif isinstance(value, str):
            rendered = f'"{value}"'
        else:
            rendered = str(value)
        lines.append(f"{key} = {rendered}")
    config_path.write_text("\n".join(lines), encoding="utf-8")
    report = measure_checkpoint_growth(
        config_path, tmp_path / "growth", ticks=9, checkpoint_interval=3
    )
    assert len(report["checkpoint_bytes_by_tick"]) >= 3
    assert 0 <= report["checkpoint_growth_ratio"] < 5


def test_trace_helpers_round_trip(tmp_path: Path) -> None:
    trace_path = tmp_path / "trace.jsonl"
    with open(trace_path, "w", encoding="utf-8") as handle:
        write_sample(handle, 100, type("E", (), {})(), "digest-a") if False else None
    # write_sample needs an engine; use a manual record instead for the reader.
    trace_path.write_text(
        '{"deep_digest": "aa", "run_digest": "r1", "tick": 100}\n'
        '{"deep_digest": "bb", "run_digest": "r2", "tick": 200}\n',
        encoding="utf-8",
    )
    samples = read_deep_trace(trace_path)
    assert set(samples) == {100, 200}
    other = tmp_path / "other.jsonl"
    other.write_text(
        '{"deep_digest": "aa", "run_digest": "r1", "tick": 100}\n'
        '{"deep_digest": "cc", "run_digest": "r2", "tick": 300}\n',
        encoding="utf-8",
    )
    outcome = compare_traces(trace_path, other)
    assert outcome["sample_count"] == 1
    assert outcome["mismatch_count"] == 0
    assert outcome["missing_optimized_samples"] == [200]
    assert outcome["unexpected_optimized_samples"] == [300]
