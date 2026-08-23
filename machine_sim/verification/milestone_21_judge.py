"""Independent M21 judge: evaluates high-throughput refactoring evidence.

Overall status is PASS only when every required check is exactly PASS. A
missing artifact, missing evidence, or inconclusive probe is a FAIL — never a
SKIP, never a PARTIAL, never a default pass.

Evidence model:

* frozen-reference, profiling, throughput, scaling, and checkpoint artifacts
  are read from the milestone output directory;
* digest properties (cross-process determinism, future-causal sensitivity,
  output-only independence), sparse-world equivalence, and checkpoint trace
  separation are verified by bounded live probes executed inside this judge so
  the checks cannot pass on stale or hand-written evidence alone;
* milestone regression evidence comes only from actual judge-result artifacts
  written by the corresponding milestone judges.

Wording note: the milestone specification mandates "population scaling"
terminology for benchmark artifacts and check names, so the term
"population" is exempt from this judge's lexical screen; every other term of
the machine-native vocabulary boundary applies.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ACCEPTED_REFERENCE_COMMIT = "ab20cdc4f2ea63c2a42f1ffb58c52568afebd487"

MINIMUM_SPEEDUP = 2.5
MINIMUM_REPETITIONS = 3
MINIMUM_COVERAGE_PERCENT = 77.0
MINIMUM_TEST_COUNT = 400

FORBIDDEN_TERMS = [
    "human", "social", "society", "community", "communication", "message",
    "language", "meaning", "knowledge", "learning", "teaching",
    "strategy", "trust", "cooperation", "competition", "conflict",
    "agreement", "consensus", "evolution", "mutation",
    "inheritance", "offspring", "parent", "child", "species", "fitness",
    "brain", "family", "identity", "reason",
]


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _read_jsonl_rows(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    try:
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
    except OSError:
        return []
    return rows


# --- live probes -------------------------------------------------------------


def _probe_cross_process_determinism() -> bool:
    try:
        from machine_sim.agents.unit import MachineUnitImpl
        from machine_sim.sim.config import SimConfig
        from machine_sim.sim.engine import SimEngine
        from machine_sim.sim.state_digest import deep_state_digest
    except ImportError:
        return False

    config = SimConfig(
        grid_width=8, grid_height=8, resource_density=0.25, hazard_density=0.05,
        unit_count=2, max_ticks=6, seed=7, signal_enabled=True,
        adaptive_enabled=True, neural_controller_enabled=True,
    )
    engine = SimEngine(config, seed=config.seed)
    for index in range(config.unit_count):
        engine.register_unit(
            MachineUnitImpl(
                unit_id=f"unit-{index:03d}", position=(index, index),
                signal_enabled=True, adaptive_enabled=True,
                neural_controller_enabled=True, neural_seed=config.seed,
            )
        )
    engine.initialize()
    for _ in range(4):
        engine.tick()
    expected = deep_state_digest(engine)

    script = (
        "import sys\n"
        "from machine_sim.agents.unit import MachineUnitImpl\n"
        "from machine_sim.sim.config import SimConfig\n"
        "from machine_sim.sim.engine import SimEngine\n"
        "from machine_sim.sim.state_digest import deep_state_digest\n"
        "config = SimConfig(grid_width=8, grid_height=8,"
        " resource_density=0.25, hazard_density=0.05, unit_count=2,"
        " max_ticks=6, seed=7, signal_enabled=True, adaptive_enabled=True,"
        " neural_controller_enabled=True)\n"
        "engine = SimEngine(config, seed=7)\n"
        "for index in range(2):\n"
        "    engine.register_unit(MachineUnitImpl(unit_id=f'unit-{index:03d}',"
        " position=(index, index), signal_enabled=True, adaptive_enabled=True,"
        " neural_controller_enabled=True, neural_seed=7))\n"
        "engine.initialize()\n"
        "for _ in range(4):\n"
        "    engine.tick()\n"
        "print(deep_state_digest(engine))\n"
    )
    try:
        completed = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0 and completed.stdout.strip() == expected


def _probe_future_causal_sensitivity() -> bool:
    try:
        from machine_sim.agents.unit import MachineUnitImpl
        from machine_sim.sim.config import SimConfig
        from machine_sim.sim.engine import SimEngine
        from machine_sim.sim.state_digest import deep_state_digest
    except ImportError:
        return False

    def make() -> SimEngine:
        config = SimConfig(
            grid_width=8, grid_height=8, resource_density=0.25,
            hazard_density=0.05, unit_count=2, max_ticks=6, seed=7,
            signal_enabled=True, adaptive_enabled=True,
            neural_controller_enabled=True,
        )
        engine = SimEngine(config, seed=config.seed)
        for index in range(config.unit_count):
            engine.register_unit(
                MachineUnitImpl(
                    unit_id=f"unit-{index:03d}", position=(index, index),
                    signal_enabled=True, adaptive_enabled=True,
                    neural_controller_enabled=True, neural_seed=config.seed,
                )
            )
        engine.initialize()
        for _ in range(3):
            engine.tick()
        return engine

    baseline = deep_state_digest(make())

    mutated = make()
    mutated.units[0].power_reserve = max(
        0.0, mutated.units[0].power_reserve - 1.5
    )
    power_sensitive = deep_state_digest(mutated) != baseline

    mutated = make()
    for cell in mutated.world.grid.values():
        if cell.resources:
            next(iter(cell.resources.values())).quantity += 1.25
            break
    resource_sensitive = deep_state_digest(mutated) != baseline

    mutated = make()
    controller = mutated.units[0]._neural_controller
    controller.state.W_out[0][0] += 0.02
    weight_sensitive = deep_state_digest(mutated) != baseline

    return power_sensitive and resource_sensitive and weight_sensitive


def _probe_output_trace_independence() -> bool:
    try:
        from machine_sim.agents.unit import MachineUnitImpl
        from machine_sim.sim.config import SimConfig
        from machine_sim.sim.engine import SimEngine
        from machine_sim.sim.state_digest import deep_state_digest
    except ImportError:
        return False

    config = SimConfig(
        grid_width=8, grid_height=8, resource_density=0.25, hazard_density=0.05,
        unit_count=2, max_ticks=6, seed=7, adaptive_enabled=True,
        neural_controller_enabled=True,
    )
    engine = SimEngine(config, seed=config.seed)
    for index in range(config.unit_count):
        engine.register_unit(
            MachineUnitImpl(
                unit_id=f"unit-{index:03d}", position=(index, index),
                adaptive_enabled=True, neural_controller_enabled=True,
                neural_seed=config.seed,
            )
        )
    engine.initialize()
    for _ in range(3):
        engine.tick()
    before = deep_state_digest(engine)
    engine._neural_action_trace.append({"tick": 999999, "action_logits": [0.0] * 7})
    engine._adaptive_state_snapshots.append({"tick": 999999})
    engine._architecture_cost_trace.append({"tick": 999999})
    engine.correlator._signal_history.append((999999, "unit-000", 1, {}))
    engine.fabrication_engine._lineage_records.append({"marker": 1})
    after = deep_state_digest(engine)
    return before == after


def _probe_sparse_world_equivalence() -> bool:
    try:
        import random

        from machine_sim.environment.hazards import Hazard, HazardType
        from machine_sim.environment.resources import Resource, ResourceType
        from machine_sim.environment.world import World
    except ImportError:
        return False

    def reference_update(world: World, tick: int) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        for pos, cell in world.grid.items():
            for res in cell.resources.values():
                old_qty = res.quantity
                res.quantity = min(res.max_quantity, res.quantity + res.regrowth_rate)
                if old_qty <= 0 and res.quantity > 0:
                    events.append({"position": pos, "regrew": True})
            for hz in cell.hazards.values():
                hz.intensity = max(0.0, hz.intensity - hz.decay_rate)
        world.signals = [
            s for s in world.signals if tick - s.emitted_tick < s.duration
        ]
        for sig in world.signals:
            sig.intensity = max(0.0, sig.intensity - sig.decay_rate)
        return events

    for trial in range(3):
        rng = random.Random(100 + trial)
        # One identical randomized layout applied to both worlds.
        resource_layout = [
            (
                (rng.randrange(24), rng.randrange(24)),
                rng.uniform(0, 30),
                rng.uniform(0.01, 0.2),
            )
            for _ in range(60)
        ]
        hazard_layout = [
            (
                (rng.randrange(24), rng.randrange(24)),
                rng.uniform(0.1, 1.0),
                rng.uniform(0.01, 0.05),
            )
            for _ in range(12)
        ]
        world_sparse = World(24, 24, random.Random(0))
        world_reference = World(24, 24, random.Random(0))
        for pos, quantity, regrowth_rate in resource_layout:
            for world in (world_sparse, world_reference):
                world.grid[pos].resources["power_node"] = Resource(
                    resource_type=ResourceType.POWER_NODE,
                    quantity=quantity,
                    max_quantity=50.0,
                    regrowth_rate=regrowth_rate,
                )
                world._refresh_cell_activity(pos, world.grid[pos])
        for pos, intensity, decay_rate in hazard_layout:
            for world in (world_sparse, world_reference):
                world.grid[pos].hazards["em_pulse"] = Hazard(
                    hazard_type=HazardType.EM_PULSE,
                    intensity=intensity,
                    decay_rate=decay_rate,
                )
                world._refresh_cell_activity(pos, world.grid[pos])

        for tick in range(1, 121):
            # Identical signal fixture on both worlds.
            if tick % 40 == 1:
                for world in (world_sparse, world_reference):
                    world.emit_signal("probe", (5, 5), 1, 0.9, 4, 0.05, tick)
            sparse_events = world_sparse.update(tick)
            reference_events = reference_update(world_reference, tick)
            if len(sparse_events) != len(reference_events):
                return False
        # State equality over all cells.
        for pos, cell_sparse in world_sparse.grid.items():
            cell_reference = world_reference.grid[pos]
            keys_a = sorted(cell_sparse.resources)
            keys_b = sorted(cell_reference.resources)
            if keys_a != keys_b:
                return False
            for key in keys_a:
                if (
                    cell_sparse.resources[key].quantity
                    != cell_reference.resources[key].quantity
                ):
                    return False
            haz_a = sorted(cell_sparse.hazards)
            haz_b = sorted(cell_reference.hazards)
            if haz_a != haz_b:
                return False
            for key in haz_a:
                if (
                    cell_sparse.hazards[key].intensity
                    != cell_reference.hazards[key].intensity
                ):
                    return False
        if len(world_sparse.signals) != len(world_reference.signals):
            return False
    return True


def _probe_checkpoint_trace_separation() -> bool:
    try:
        from machine_sim.agents.unit import MachineUnitImpl
        from machine_sim.sim.checkpoint import encode_state
        from machine_sim.sim.config import SimConfig
        from machine_sim.sim.engine import SimEngine
        from machine_sim.sim.state_digest import deep_state_digest
    except ImportError:
        return False

    def make() -> SimEngine:
        config = SimConfig(
            grid_width=8, grid_height=8, resource_density=0.25, hazard_density=0.05,
            unit_count=2, max_ticks=6, seed=7, adaptive_enabled=True,
            neural_controller_enabled=True,
        )
        engine = SimEngine(config, seed=config.seed)
        for index in range(config.unit_count):
            engine.register_unit(
                MachineUnitImpl(
                    unit_id=f"unit-{index:03d}", position=(index, index),
                    adaptive_enabled=True, neural_controller_enabled=True,
                    neural_seed=config.seed,
                )
            )
        engine.initialize()
        for _ in range(3):
            engine.tick()
        return engine

    lean = make()
    inflated = make()
    marker = {"tick": 999999, "payload": "x" * 64}
    for _ in range(2000):
        inflated._neural_action_trace.append(dict(marker))
        inflated._adaptive_state_snapshots.append(dict(marker))
        inflated.correlator._signal_history.append((999999, "u", 1, {}))
        inflated.fabrication_engine._lineage_records.append(dict(marker))
        inflated.capsule_manager._capsules.append({"marker": 1})

    lean_size = len(json.dumps(encode_state(lean), sort_keys=True))
    inflated_size = len(json.dumps(encode_state(inflated), sort_keys=True))

    size_ok = inflated_size < lean_size * 1.05
    continuation_equal = deep_state_digest(lean) == deep_state_digest(inflated)
    return size_ok and continuation_equal


# --- judge -------------------------------------------------------------------


def judge(output_dir: str) -> Dict[str, Any]:
    """Run every M21 check against the milestone output directory."""
    path = Path(output_dir)
    checks: Dict[str, str] = {}
    detail: Dict[str, Any] = {}

    reference_summary = _read_json(path / "reference" / "reference_run_summary.json")
    reference_manifest = _read_json(path / "reference" / "reference_config_manifest.json")
    reference_trace = path / "reference" / "deep_state_digest_trace.jsonl"
    schema = _read_json(path / "determinism" / "deep_state_digest_schema.json")
    equivalence = _read_json(path / "determinism" / "deep_equivalence_report.json")
    pause_report = _read_json(
        path / "determinism" / "pause_resume_deep_equivalence_report.json"
    )
    profile_before = _read_json(path / "performance" / "hotspot_profile_before.json")
    profile_after = _read_json(path / "performance" / "hotspot_profile_after.json")
    perf_baseline = _read_json(path / "performance" / "performance_baseline.json")
    perf_optimized = _read_json(path / "performance" / "performance_optimized.json")
    perf_comparison = _read_json(path / "performance" / "performance_comparison.json")
    population_rows = _read_jsonl_rows(path / "performance" / "population_scaling.jsonl")
    dependency_decision = _read_json(path / "performance" / "dependency_decision.json")
    checkpoint_growth = _read_json(path / "performance" / "checkpoint_growth_comparison.json")
    test_summary = _read_json(path / "verification" / "test_run_summary.json")

    # 1. reference_commit_recorded_check
    recorded_commit = (reference_summary or {}).get("accepted_reference_commit", "")
    freeze_commit = (reference_summary or {}).get("freeze_commit", "")
    checks["reference_commit_recorded_check"] = (
        "PASS"
        if recorded_commit == ACCEPTED_REFERENCE_COMMIT
        and isinstance(freeze_commit, str) and len(freeze_commit) >= 7
        else "FAIL"
    )

    # 2. reference_artifacts_present_check
    series = (reference_summary or {}).get("series", {})
    required_series = ("a", "b", "c")
    series_ok = (
        isinstance(reference_summary, dict)
        and isinstance(reference_manifest, dict)
        and reference_trace.exists()
        and all(
            series.get(name, {}).get("meets_minimum") is True for name in required_series
        )
        and all(name in reference_manifest for name in required_series)
    )
    checks["reference_artifacts_present_check"] = "PASS" if series_ok else "FAIL"

    # 3. deep_state_schema_present_check
    schema_ok = (
        isinstance(schema, dict)
        and bool(schema.get("schema_version"))
        and bool(schema.get("included"))
        and bool(schema.get("excluded"))
    )
    checks["deep_state_schema_present_check"] = "PASS" if schema_ok else "FAIL"

    # 4. deep_digest_cross_process_determinism_check
    checks["deep_digest_cross_process_determinism_check"] = (
        "PASS" if _probe_cross_process_determinism() else "FAIL"
    )

    # 5. deep_digest_future_causal_sensitivity_check
    checks["deep_digest_future_causal_sensitivity_check"] = (
        "PASS" if _probe_future_causal_sensitivity() else "FAIL"
    )

    # 6. deep_digest_output_trace_independence_check
    checks["deep_digest_output_trace_independence_check"] = (
        "PASS" if _probe_output_trace_independence() else "FAIL"
    )

    # 7. reference_vs_optimized_zero_mismatch_check
    eq_series = (equivalence or {}).get("series", {})
    zero_mismatch_ok = (
        isinstance(equivalence, dict)
        and equivalence.get("zero_mismatch_acceptance") is True
        and int(equivalence.get("sample_count", 0)) > 0
        and int(equivalence.get("mismatch_count", -1)) == 0
        and bool(eq_series)
        and all(
            outcome.get("mismatch_count") == 0 and outcome.get("final_equal") is True
            and int(outcome.get("sample_count", 0)) > 0
            for outcome in eq_series.values()
        )
    )
    checks["reference_vs_optimized_zero_mismatch_check"] = (
        "PASS" if zero_mismatch_ok else "FAIL"
    )

    # 8. pause_resume_deep_equivalence_check
    pause_ok = (
        isinstance(pause_report, dict)
        and pause_report.get("process_isolated") is True
        and pause_report.get("deep_and_shallow_equal") is True
        and int(pause_report.get("sample_count", 0)) > 0
        and int(pause_report.get("mismatch_count", -1)) == 0
        and int(pause_report.get("shallow_run_digest_mismatch_count", -1)) == 0
        and int(pause_report.get("resumed_span", 0)) > 0
    )
    checks["pause_resume_deep_equivalence_check"] = "PASS" if pause_ok else "FAIL"

    # 9. profiling_evidence_present_check
    profiling_ok = (
        isinstance(profile_before, dict)
        and isinstance(profile_after, dict)
        and isinstance(perf_baseline, dict)
        and isinstance(perf_optimized, dict)
        and bool(profile_before.get("top_by_cumulative"))
        and bool(profile_after.get("top_by_cumulative"))
        and int(perf_baseline.get("repetitions", 0)) >= MINIMUM_REPETITIONS
        and int(perf_optimized.get("repetitions", 0)) >= MINIMUM_REPETITIONS
    )
    checks["profiling_evidence_present_check"] = "PASS" if profiling_ok else "FAIL"

    # 10. sparse_world_update_equivalence_check
    baseline_metrics = (perf_baseline or {}).get("metrics_median", {})
    optimized_metrics = (perf_optimized or {}).get("metrics_median", {})
    visited_before = baseline_metrics.get("world_cells_visited_total", 0)
    visited_after = optimized_metrics.get("world_cells_visited_total", 0)
    sparse_ok = (
        _probe_sparse_world_equivalence()
        and visited_before > 0
        and visited_after > 0
        and visited_after < visited_before
    )
    checks["sparse_world_update_equivalence_check"] = "PASS" if sparse_ok else "FAIL"

    # 11. material_throughput_improvement_check
    speedup = float((perf_comparison or {}).get("primary_end_to_end_speedup", 0.0))
    throughput_ok = (
        isinstance(perf_comparison, dict)
        and speedup >= MINIMUM_SPEEDUP
        and perf_comparison.get("meets_required_speedup") is True
        and float((perf_baseline or {}).get("metrics_median", {}).get("ticks_per_second", 0.0)) > 0
        and float(optimized_metrics.get("ticks_per_second", 0.0)) > 0
    )
    checks["material_throughput_improvement_check"] = (
        "PASS" if throughput_ok else "FAIL"
    )
    detail["primary_end_to_end_speedup"] = speedup

    # 12-14. population scaling checks
    tier_seen: Dict[int, bool] = {10: False, 100: False, 1000: False}
    for row in population_rows:
        tier = row.get("initial_units")
        if tier in tier_seen and float(row.get("simulation_seconds", 0.0)) > 0:
            tier_seen[tier] = True
    checks["population_scaling_10_check"] = "PASS" if tier_seen[10] else "FAIL"
    checks["population_scaling_100_check"] = "PASS" if tier_seen[100] else "FAIL"
    checks["population_scaling_1000_check"] = "PASS" if tier_seen[1000] else "FAIL"

    # 15. checkpoint_trace_separation_check
    checks["checkpoint_trace_separation_check"] = (
        "PASS" if _probe_checkpoint_trace_separation() else "FAIL"
    )

    # 16. checkpoint_growth_improvement_check
    growth_entries = (checkpoint_growth or {}).get("checkpoint_bytes_by_tick", [])
    growth_ratio = float((checkpoint_growth or {}).get("checkpoint_growth_ratio", -1.0))
    documented_ratio = float(
        (checkpoint_growth or {})
        .get("m20_documented_pattern", {})
        .get("documented_growth_ratio", -1.0)
    )
    growth_ok = (
        isinstance(checkpoint_growth, dict)
        and len(growth_entries) >= 3
        and 0 <= growth_ratio < documented_ratio
        and (checkpoint_growth or {}).get("separation_effect", {}).get(
            "observation_history_location"
        )
        is not None
    )
    checks["checkpoint_growth_improvement_check"] = "PASS" if growth_ok else "FAIL"
    detail["checkpoint_growth_ratio"] = growth_ratio
    detail["m20_documented_growth_ratio"] = documented_ratio

    # 17. m20_pause_resume_regression_check (actual judge-result artifact only)
    m20_result = _read_json(_find_demo_dir(path, "demo_m20") / "milestone_20_judge_result.json")
    m20_ok = (
        isinstance(m20_result, dict)
        and m20_result.get("M20_JUDGE_STATUS") == "PASS"
        and m20_result.get("failed_checks") == []
    )
    checks["m20_pause_resume_regression_check"] = "PASS" if m20_ok else "FAIL"

    # 18. m14_m15_m16_m17_m18_m19_m20_regression_check
    regression_all_pass = True
    regression_detail: Dict[str, str] = {}
    for milestone in ("14", "15", "16", "17", "18", "19", "20"):
        result = _read_json(
            _find_demo_dir(path, f"demo_m{milestone}")
            / f"milestone_{milestone}_judge_result.json"
        )
        status = None
        if isinstance(result, dict):
            status = result.get(
                f"M{milestone}_JUDGE_STATUS",
                result.get(f"MILESTONE_{milestone}_JUDGE_STATUS"),
            )
            if status == "PASS" and result.get("failed_checks"):
                status = "FAIL"
        regression_detail[f"m{milestone}"] = status or "MISSING"
        if status != "PASS":
            regression_all_pass = False
    checks["m14_m15_m16_m17_m18_m19_m20_regression_check"] = (
        "PASS" if regression_all_pass else "FAIL"
    )
    detail["regression_statuses"] = regression_detail

    # 19. tests_and_coverage_check
    coverage_value = float((test_summary or {}).get("coverage_percent", -1.0))
    test_count = int((test_summary or {}).get("passed", -1))
    tests_ok = (
        isinstance(test_summary, dict)
        and coverage_value >= MINIMUM_COVERAGE_PERCENT
        and test_count >= MINIMUM_TEST_COUNT
        and int((test_summary or {}).get("failed", 1)) == 0
    )
    checks["tests_and_coverage_check"] = "PASS" if tests_ok else "FAIL"
    detail["coverage_percent"] = coverage_value
    detail["passed_tests"] = test_count

    # 20. machine_native_wording_check
    found_terms = _scan_wording(path)
    checks["machine_native_wording_check"] = "PASS" if not found_terms else "FAIL"
    detail["forbidden_terms_found"] = found_terms[:20]

    # Dependency decision artifact must exist and carry a verdict either way.
    dependency_ok = (
        isinstance(dependency_decision, dict)
        and dependency_decision.get("added") in (True, False)
        and bool(dependency_decision.get("verdict_text"))
    )
    checks["dependency_decision_evidence_check"] = "PASS" if dependency_ok else "FAIL"

    non_pass = [name for name, result in checks.items() if result != "PASS"]
    status = "PASS" if not non_pass else "FAIL"

    return {
        "M21_JUDGE_STATUS": status,
        "checks": checks,
        "failed_checks": non_pass,
        "detail": detail,
        "thresholds": {
            "minimum_speedup": MINIMUM_SPEEDUP,
            "minimum_repetitions": MINIMUM_REPETITIONS,
            "minimum_coverage_percent": MINIMUM_COVERAGE_PERCENT,
            "accepted_reference_commit": ACCEPTED_REFERENCE_COMMIT,
        },
    }


def _find_demo_dir(milestone_dir: Path, demo_name: str) -> Path:
    """Resolve a sibling demo directory strictly beside the milestone dir.

    No working-directory fallback: the judge must be reproducible from any
    launch location and must never read unrelated repositories' artifacts.
    """
    return milestone_dir.parent / demo_name


def _scan_wording(path: Path) -> List[str]:
    found: List[str] = []
    lower_terms = [term.lower() for term in FORBIDDEN_TERMS]
    for pattern in ("*.json", "*.jsonl"):
        for candidate in sorted(path.glob(pattern)):
            if candidate.name == "milestone_21_judge_result.json":
                continue
            try:
                text = candidate.read_text(encoding="utf-8").lower()
            except OSError:
                continue
            for term in lower_terms:
                if term in text and term not in found:
                    found.append(term)
    return found


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m machine_sim.verification.milestone_21_judge <output_dir>")
        sys.exit(1)

    output_dir = sys.argv[1]
    results = judge(output_dir)

    out_path = Path(output_dir) / "milestone_21_judge_result.json"
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    print(f"M21_JUDGE_STATUS: {results['M21_JUDGE_STATUS']}")
    for check_name, check_status in results["checks"].items():
        print(f"  {check_name}: {check_status}")

    if results["failed_checks"]:
        print(f"\nFailed checks: {', '.join(results['failed_checks'])}")
        sys.exit(1)
    print("\nAll checks passed.")


if __name__ == "__main__":
    main()
