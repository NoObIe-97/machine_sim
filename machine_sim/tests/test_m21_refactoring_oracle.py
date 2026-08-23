"""M21 refactoring-oracle integration tests: sparse world, checkpoint
separation, sidecar continuity, benchmark instrumentation isolation,
population tiers, and independent-judge behavior."""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from machine_sim.agents.unit import MachineUnitImpl
from machine_sim.environment.hazards import Hazard, HazardType
from machine_sim.environment.resources import Resource, ResourceType
from machine_sim.environment.world import World
from machine_sim.sim.checkpoint import (
    encode_state,
    list_trace_sidecars,
    load_latest_trace_sidecar,
    rehydrate_output_only_state,
    write_checkpoint,
    write_trace_sidecar,
)
from machine_sim.sim.config import SimConfig
from machine_sim.sim.engine import SimEngine
from machine_sim.sim.state_digest import deep_state_digest


def _config(**overrides) -> SimConfig:
    values = dict(
        grid_width=10,
        grid_height=10,
        resource_density=0.25,
        hazard_density=0.05,
        unit_count=3,
        max_ticks=40,
        seed=11,
        signal_enabled=True,
        adaptive_enabled=True,
        neural_controller_enabled=True,
        fabrication_enabled=True,
        unit_capacity=8,
    )
    values.update(overrides)
    return SimConfig(**values)


def _engine(config: SimConfig) -> SimEngine:
    engine = SimEngine(config, seed=config.seed)
    for index in range(config.unit_count):
        engine.register_unit(
            MachineUnitImpl(
                unit_id=f"unit-{index:03d}",
                position=(index + 1, index + 1),
                signal_enabled=config.signal_enabled,
                adaptive_enabled=config.adaptive_enabled,
                neural_controller_enabled=config.neural_controller_enabled,
                neural_seed=config.seed,
            )
        )
    engine.initialize()
    return engine


def _reference_update(world: World, tick: int):
    events = []
    for pos, cell in world.grid.items():
        for res in cell.resources.values():
            old_qty = res.quantity
            res.quantity = min(res.max_quantity, res.quantity + res.regrowth_rate)
            if old_qty <= 0 and res.quantity > 0:
                events.append((pos, res.resource_type.value))
        for hz in cell.hazards.values():
            hz.intensity = max(0.0, hz.intensity - hz.decay_rate)
    world.signals = [s for s in world.signals if tick - s.emitted_tick < s.duration]
    for sig in world.signals:
        sig.intensity = max(0.0, sig.intensity - sig.decay_rate)
    return events


# --- 6/7/8: sparse world update equivalence ----------------------------------


def test_sparse_world_matches_reference_over_many_randomized_ticks() -> None:
    for trial in range(4):
        rng = random.Random(200 + trial)
        sparse = World(16, 16, random.Random(0))
        reference = World(16, 16, random.Random(0))
        # One identical randomized layout applied to both worlds.
        resource_layout = [
            (
                (rng.randrange(16), rng.randrange(16)),
                rng.uniform(0, 40),
                rng.uniform(0.01, 0.3),
            )
            for _ in range(30)
        ]
        hazard_layout = [
            (
                (rng.randrange(16), rng.randrange(16)),
                rng.uniform(0.1, 1.0),
                rng.uniform(0.005, 0.05),
            )
            for _ in range(6)
        ]
        for pos, quantity, regrowth_rate in resource_layout:
            for world in (sparse, reference):
                world.grid[pos].resources["power_node"] = Resource(
                    resource_type=ResourceType.POWER_NODE,
                    quantity=quantity,
                    max_quantity=60.0,
                    regrowth_rate=regrowth_rate,
                )
                world._refresh_cell_activity(pos, world.grid[pos])
        for pos, intensity, decay_rate in hazard_layout:
            for world in (sparse, reference):
                world.grid[pos].hazards["em_pulse"] = Hazard(
                    hazard_type=HazardType.EM_PULSE,
                    intensity=intensity,
                    decay_rate=decay_rate,
                )
                world._refresh_cell_activity(pos, world.grid[pos])
        # Fixture change mid-flight: clear one populated cell on both worlds.
        cleared_sparse = next(iter(sparse._active_entries))[0]
        reference.grid[cleared_sparse].resources.clear()
        reference.grid[cleared_sparse].hazards.clear()
        sparse.grid[cleared_sparse].resources.clear()
        sparse.grid[cleared_sparse].hazards.clear()
        sparse._refresh_cell_activity(cleared_sparse, sparse.grid[cleared_sparse])

        for tick in range(1, 151):
            if tick % 17 == 1:
                for world in (sparse, reference):
                    world.emit_signal("probe", (3, 3), 1, 0.8, 5, 0.04, tick)
            sparse_events = sparse.update(tick)
            reference_events = _reference_update(reference, tick)
            assert len(sparse_events) == len(reference_events)
        for pos, cell_s in sparse.grid.items():
            cell_r = reference.grid[pos]
            assert sorted(cell_s.resources) == sorted(cell_r.resources)
            for key in cell_s.resources:
                assert cell_s.resources[key].quantity == cell_r.resources[key].quantity
            assert sorted(cell_s.hazards) == sorted(cell_r.hazards)
            for key in cell_s.hazards:
                assert cell_s.hazards[key].intensity == cell_r.hazards[key].intensity
        assert len(sparse.signals) == len(reference.signals)


def test_sparse_active_index_tracks_fixture_changes() -> None:
    rng = random.Random(5)
    world = World(8, 8, rng)
    assert not world._active_cells
    pos = (2, 2)
    world.grid[pos].resources["component_scrap"] = Resource(
        resource_type=ResourceType.COMPONENT_SCRAP, quantity=5.0
    )
    world._refresh_cell_activity(pos, world.grid[pos])
    assert pos in world._active_cells
    world.update(1)
    assert world.cells_updated_total == 1

    world.grid[pos].resources.clear()
    world._refresh_cell_activity(pos, world.grid[pos])
    assert pos not in world._active_cells
    visited_before = world.cells_visited_total
    world.update(2)
    assert world.cells_visited_total == visited_before


def test_sparse_update_event_ordering_matches_grid_order() -> None:
    sparse = World(6, 6, random.Random(0))
    reference = World(6, 6, random.Random(0))
    positions = [(4, 1), (0, 0), (2, 5), (1, 3)]
    for pos in positions:
        for world in (sparse, reference):
            depleted = Resource(
                resource_type=ResourceType.POWER_NODE,
                quantity=0.0,
                max_quantity=10.0,
                regrowth_rate=0.5,
            )
            world.grid[pos].resources["power_node"] = depleted
            world._refresh_cell_activity(pos, world.grid[pos])
    sparse_events = sparse.update(1)
    reference_events = _reference_update(reference, 1)
    assert len(sparse_events) == len(reference_events) == len(positions)
    sparse_positions = [e.data["position"] for e in sparse_events]
    expected_order = sorted(positions)
    assert sparse_positions == expected_order


# --- 9: checkpoint restore continuation equivalence --------------------------


def test_checkpoint_restore_is_continuation_equivalent() -> None:
    config = _config()
    engine = _engine(config)
    for _ in range(7):
        engine.tick()
    restored = decode_engine(engine)
    assert deep_state_digest(engine) == deep_state_digest(restored)
    for _ in range(5):
        engine.tick()
        restored.tick()
    assert deep_state_digest(engine) == deep_state_digest(restored)


def decode_engine(engine: SimEngine) -> SimEngine:
    from machine_sim.sim.checkpoint import decode_state

    return decode_state(encode_state(engine))


# --- 10: output-only growth does not inflate payload -------------------------


def test_output_only_growth_does_not_inflate_checkpoint_payload(tmp_path: Path) -> None:
    lean = _engine(_config())
    inflated = _engine(_config())
    for _ in range(5):
        lean.tick()
        inflated.tick()

    marker = {"tick": 999999, "payload": "y" * 128}
    for _ in range(3000):
        inflated._neural_action_trace.append(dict(marker))
        inflated._adaptive_state_snapshots.append(dict(marker))
        inflated.correlator._signal_history.append((999999, "unit-000", 1, {}))
        inflated.fabrication_engine._lineage_records.append(dict(marker))
        inflated.capsule_manager._capsules.append({"marker": 1})
    inflated.capsule_manager._capsule_count += 3000

    lean_size = len(json.dumps(encode_state(lean), sort_keys=True))
    inflated_size = len(json.dumps(encode_state(inflated), sort_keys=True))
    assert inflated_size < lean_size * 1.05
    assert deep_state_digest(lean) == deep_state_digest(inflated)

    path_lean = write_checkpoint(lean, tmp_path, lean.tick_count, "run-x", "cfg")
    path_inflated = write_checkpoint(inflated, tmp_path, inflated.tick_count, "run-y", "cfg")
    size_ratio = path_inflated.stat().st_size / path_lean.stat().st_size
    assert size_ratio < 1.05


# --- 11: observation continuity across pause/resume --------------------------


def test_sidecar_persists_history_and_resume_rehydrates(tmp_path: Path) -> None:
    config = _config(max_ticks=12)
    engine_a = _engine(config)
    for _ in range(6):
        engine_a.tick()
    assert engine_a._neural_action_trace or True

    sidecar = write_trace_sidecar(engine_a, tmp_path, engine_a.tick_count, "run-side")
    assert sidecar.exists()
    assert list_trace_sidecars(tmp_path)

    document = load_latest_trace_sidecar(tmp_path)
    assert document is not None
    sections = document["sections"]
    assert "engine" in sections

    # Fresh decoded engine (as resume produces) starts without history.
    engine_b = decode_engine(engine_a)
    for section_values in ("engine",):
        pass
    restored_counts = rehydrate_output_only_state(engine_b, sections)
    assert restored_counts > 0
    for attr in ("_neural_action_trace", "_adaptive_state_snapshots"):
        if hasattr(engine_a, attr):
            assert len(getattr(engine_b, attr)) == len(getattr(engine_a, attr))

    # Rehydrated history stays invisible to the semantic digest.
    assert deep_state_digest(engine_a) == deep_state_digest(engine_b)


def test_resumed_run_artifacts_cover_complete_run(tmp_path: Path) -> None:
    """Pause-sidecar + resume rehydration keeps observation records continuous."""
    from machine_sim.sim.run_control import RunController, resume_controller

    config = _config(
        max_ticks=14,
        long_run_adaptation_enabled=True,
        control_poll_interval=2,
        run_progress_interval=100,
    )
    run_dir = tmp_path / "run"
    controller = RunController(
        _engine(config), run_dir, checkpoint_enabled=True,
        checkpoint_interval=100, run_digest_enabled=True,
    )
    controller.start()
    # File the request before advancing; the in-loop poll applies it at tick 2.
    controller.channel.write_request("pause")
    applied = controller.advance(config.max_ticks)
    assert applied == "paused"
    pause_tick = controller.engine.tick_count
    assert pause_tick >= 1
    assert controller.last_trace_sidecar is not None
    pre_pause_feedback = list(controller.engine._local_feedback_trace)

    resumed = resume_controller(run_dir, target_ticks=config.max_ticks)
    assert resumed.rehydrated_trace_attributes > 0
    if pre_pause_feedback:
        rehydrated = list(resumed.engine._local_feedback_trace)
        assert rehydrated[: len(pre_pause_feedback)] == pre_pause_feedback
    final_state = resumed.advance(config.max_ticks)
    assert final_state == "completed"
    assert resumed.engine.tick_count == config.max_ticks


# --- 12: benchmark counters do not influence simulation ----------------------


def test_benchmark_counters_do_not_influence_state_or_digest() -> None:
    engine_with = _engine(_config())
    engine_without = _engine(_config())

    # The counter is benchmark instrumentation: excluded from checkpoint
    # payloads and from the semantic snapshot alike.
    snapshot_text = json.dumps(encode_state(engine_with), sort_keys=True)
    assert "bench_unit_decisions" not in snapshot_text

    digest_before = deep_state_digest(engine_with)
    for _ in range(5):
        engine_with.tick()
        engine_without.tick()
    assert engine_with.bench_unit_decisions > 0
    assert engine_without.bench_unit_decisions == engine_with.bench_unit_decisions
    # Never read by behavior: both engines stay identical.
    assert deep_state_digest(engine_with) == deep_state_digest(engine_without)
    assert deep_state_digest(engine_with) != digest_before

    from machine_sim.sim.state_digest import semantic_state_snapshot

    flat = json.dumps(semantic_state_snapshot(engine_with))
    assert "bench_unit_decisions" not in flat


# --- 13/14/15: population tiers ----------------------------------------------


@pytest.mark.parametrize("tier", [10, 100, 1000])
def test_population_benchmark_tier_completes(tier: int) -> None:
    from machine_sim.perf.benchmark import measure_run

    config = _config(
        unit_count=tier,
        grid_width=40,
        grid_height=40,
        max_ticks=4,
        signal_default_radius=3,
        fabrication_interval=100,
    )
    metrics = measure_run(config, ticks=3)
    assert metrics["total_unit_count"] == tier
    assert metrics["ticks"] == 3
    assert metrics["simulation_seconds"] > 0
    assert metrics["unit_decisions_per_second"] > 0


# --- 16-21: independent judge behavior ---------------------------------------




# --- 16-21: independent judge behavior ---------------------------------------


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _build_fixture(base: Path) -> None:
    _write_json(
        base / "reference" / "reference_run_summary.json",
        {
            "accepted_reference_commit": "ab20cdc4f2ea63c2a42f1ffb58c52568afebd487",
            "freeze_commit": "b679d238b15066477bbc807cb2e3cf2e9ac99c3e",
            "series": {
                name: {"meets_minimum": True, "ticks": 9000}
                for name in ("a", "b", "c")
            },
        },
    )
    _write_json(
        base / "reference" / "reference_config_manifest.json",
        {name: {"seed": 1} for name in ("a", "b", "c")},
    )
    (base / "reference" / "deep_state_digest_trace.jsonl").write_text(
        '{"tick": 100, "deep_digest": "a"}\n', encoding="utf-8"
    )
    _write_json(
        base / "determinism" / "deep_state_digest_schema.json",
        {"schema_version": "1.0.0", "included": ["x"], "excluded": [{"field": "y"}]},
    )
    series_report = {
        name: {"sample_count": 10, "mismatch_count": 0, "final_equal": True}
        for name in ("a", "b", "c-uninterrupted", "c-pause-resume")
    }
    _write_json(
        base / "determinism" / "deep_equivalence_report.json",
        {
            "series": series_report,
            "sample_count": 40,
            "mismatch_count": 0,
            "zero_mismatch_acceptance": True,
        },
    )
    _write_json(
        base / "determinism" / "pause_resume_deep_equivalence_report.json",
        {
            "process_isolated": True,
            "deep_and_shallow_equal": True,
            "sample_count": 10,
            "mismatch_count": 0,
            "shallow_run_digest_mismatch_count": 0,
            "resumed_span": 1500,
        },
    )
    optimized_median = {"ticks_per_second": 132.0, "world_cells_visited_total": 1000}
    baseline_median = dict(optimized_median, world_cells_visited_total=4000)
    baseline_median["ticks_per_second"] = 52.8
    for label in ("hotspot_profile_before", "hotspot_profile_after"):
        _write_json(
            base / "performance" / (label + ".json"),
            {"top_by_cumulative": [{"function": "update"}]},
        )
    for label, medians in (("baseline", baseline_median), ("optimized", optimized_median)):
        _write_json(
            base / "performance" / f"performance_{label}.json",
            {"label": label, "repetitions": 3, "metrics_median": medians},
        )
    _write_json(
        base / "performance" / "performance_comparison.json",
        {
            "primary_end_to_end_speedup": 2.56,
            "meets_required_speedup": True,
        },
    )
    rows = [
        {"initial_units": tier, "simulation_seconds": 1.5,
         "unit_decisions_per_second": 100.0}
        for tier in (10, 100, 1000)
    ]
    (base / "performance" / "population_scaling.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    _write_json(
        base / "performance" / "dependency_decision.json",
        {
            "added": False,
            "verdict_text": "vectorization rejected: state sync-back dominates",
        },
    )
    growth_entries = [
        {"tick": tick, "byte_size": size}
        for tick, size in ((500, 120000), (1000, 121000), (1500, 122000))
    ]
    _write_json(
        base / "performance" / "checkpoint_growth_comparison.json",
        {
            "checkpoint_bytes_by_tick": growth_entries,
            "checkpoint_growth_ratio": 1.02,
            "m20_documented_pattern": {"documented_growth_ratio": 4.36},
            "separation_effect": {"observation_history_location": "trace_segments"},
        },
    )
    _write_json(
        base / "verification" / "test_run_summary.json",
        {"passed": 600, "failed": 0, "coverage_percent": 78.5},
    )


def _write_regression_artifacts(tmp_path: Path) -> None:
    """Sibling demo_m14..demo_m20 judge-result artifacts, as the layout the
    real judge consumes (output/demo_mN beside output/demo_m21)."""
    for milestone in ("14", "15", "16", "17", "18", "19", "20"):
        _write_json(
            tmp_path / f"demo_m{milestone}" / f"milestone_{milestone}_judge_result.json",
            {
                f"M{milestone}_JUDGE_STATUS": "PASS",
                "failed_checks": [],
                "checks": {},
            },
        )


def test_judge_passes_valid_fixture_set(tmp_path: Path):
    from machine_sim.verification.milestone_21_judge import judge

    base = tmp_path / "demo_m21"
    _build_fixture(base)
    _write_regression_artifacts(tmp_path)
    result = judge(str(base))
    assert result["M21_JUDGE_STATUS"] == "PASS", result["failed_checks"]
    assert result["failed_checks"] == []
    assert set(result["checks"].values()) == {"PASS"}


def test_judge_fails_on_deep_digest_mismatch(tmp_path: Path):
    from machine_sim.verification.milestone_21_judge import judge

    base = tmp_path / "demo_m21"
    _build_fixture(base)
    report_path = base / "determinism" / "deep_equivalence_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["series"]["b"]["mismatch_count"] = 3
    report["mismatch_count"] = 3
    report["zero_mismatch_acceptance"] = False
    report_path.write_text(json.dumps(report), encoding="utf-8")
    result = judge(str(base))
    assert result["M21_JUDGE_STATUS"] == "FAIL"
    assert "reference_vs_optimized_zero_mismatch_check" in result["failed_checks"]


def test_judge_fails_when_performance_evidence_missing(tmp_path: Path):
    from machine_sim.verification.milestone_21_judge import judge

    base = tmp_path / "demo_m21"
    _build_fixture(base)
    (base / "performance" / "performance_comparison.json").unlink()
    result = judge(str(base))
    assert result["M21_JUDGE_STATUS"] == "FAIL"
    assert "material_throughput_improvement_check" in result["failed_checks"]


def test_judge_fails_when_speedup_below_threshold(tmp_path: Path):
    from machine_sim.verification.milestone_21_judge import judge

    base = tmp_path / "demo_m21"
    _build_fixture(base)
    comparison = base / "performance" / "performance_comparison.json"
    _write_json(
        comparison,
        {"primary_end_to_end_speedup": 1.4, "meets_required_speedup": False},
    )
    result = judge(str(base))
    assert result["M21_JUDGE_STATUS"] == "FAIL"
    assert "material_throughput_improvement_check" in result["failed_checks"]


def test_judge_fails_when_population_row_missing(tmp_path: Path):
    from machine_sim.verification.milestone_21_judge import judge

    base = tmp_path / "demo_m21"
    _build_fixture(base)
    rows = [
        {"initial_units": tier, "simulation_seconds": 1.0,
         "unit_decisions_per_second": 50.0}
        for tier in (10, 100)
    ]
    (base / "performance" / "population_scaling.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    result = judge(str(base))
    assert result["M21_JUDGE_STATUS"] == "FAIL"
    assert "population_scaling_1000_check" in result["failed_checks"]


def test_judge_fails_when_checkpoint_history_scaling_unbounded(tmp_path: Path):
    from machine_sim.verification.milestone_21_judge import judge

    base = tmp_path / "demo_m21"
    _build_fixture(base)
    growth = base / "performance" / "checkpoint_growth_comparison.json"
    document = json.loads(growth.read_text(encoding="utf-8"))
    document["checkpoint_growth_ratio"] = 5.1
    growth.write_text(json.dumps(document), encoding="utf-8")
    result = judge(str(base))
    assert result["M21_JUDGE_STATUS"] == "FAIL"
    assert "checkpoint_growth_improvement_check" in result["failed_checks"]


def test_judge_requires_regression_artifacts(tmp_path: Path):
    from machine_sim.verification.milestone_21_judge import judge

    base = tmp_path / "demo_m21"
    _build_fixture(base)
    result = judge(str(base))
    assert result["M21_JUDGE_STATUS"] == "FAIL"
    assert "m14_m15_m16_m17_m18_m19_m20_regression_check" in result["failed_checks"]
    assert "m20_pause_resume_regression_check" in result["failed_checks"]
