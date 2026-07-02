"""Command-line interface for After Silicon simulator."""

from __future__ import annotations

import json
import logging
import random
from collections import Counter
from pathlib import Path

import click

from machine_sim.agents.unit import MachineUnitImpl
from machine_sim.agents.variants import ALL_VARIANTS
from machine_sim.sim.config import SimConfig
from machine_sim.sim.engine import SimEngine


@click.group()
def cli() -> None:
    """After Silicon: Machine Civilization Emergence Simulator"""
    pass


@cli.command()
@click.option("--config", "-c", type=click.Path(exists=True), default="configs/milestone_1.toml")
@click.option("--ticks", "-t", type=int, default=None)
@click.option("--seed", "-s", type=int, default=None)
@click.option("--output", "-o", type=click.Path(), default=None)
@click.option("--verbose", "-v", is_flag=True)
def run(config: str, ticks: int | None, seed: int | None, output: str | None, verbose: bool) -> None:
    """Run a simulation."""
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO)

    cfg = SimConfig.from_toml(Path(config))
    if ticks is not None:
        cfg.max_ticks = ticks
    if seed is not None:
        cfg.seed = seed

    engine = SimEngine(cfg, seed=cfg.seed)
    rng = random.Random(cfg.seed)

    for i in range(cfg.unit_count):
        variant = ALL_VARIANTS[i % len(ALL_VARIANTS)]
        unit = MachineUnitImpl(
            unit_id=f"unit-{i:03d}",
            position=(rng.randint(0, cfg.grid_width - 1), rng.randint(0, cfg.grid_height - 1)),
            variant=variant,
            signal_enabled=cfg.signal_enabled,
            signal_pattern_count=cfg.signal_pattern_count,
            signal_energy_cost=cfg.signal_energy_cost,
            signal_default_radius=cfg.signal_default_radius,
            signal_default_decay=cfg.signal_default_decay,
            signal_default_duration=cfg.signal_default_duration,
            adaptive_enabled=cfg.adaptive_enabled,
        )
        engine.register_unit(unit)

    click.echo(f"Starting simulation: {cfg.grid_width}x{cfg.grid_height}, "
               f"{cfg.unit_count} units, {cfg.max_ticks} ticks, seed={cfg.seed}")

    state = engine.run()

    active = sum(1 for a in state.agents if a.is_active)
    click.echo(f"Simulation complete. Tick {state.tick}/{cfg.max_ticks}")
    click.echo(f"Active units: {active}/{cfg.unit_count}")

    # Output correlation summary if signals are enabled
    if cfg.signal_enabled:
        corr_summary = engine.get_correlation_summary()
        click.echo(f"Signal correlation: {corr_summary['total_emissions']} emissions, "
                   f"{corr_summary['total_observations']} observations, "
                   f"{corr_summary['total_associations']} associations")
        for pid, stats in corr_summary.get("patterns", {}).items():
            click.echo(f"  Pattern {pid}: {stats['emissions']} emissions, "
                       f"{stats['observations']} observations, "
                       f"lag_weighted={stats.get('lag_weighted_score', {})}")

    # Output adaptive summary if enabled
    if cfg.adaptive_enabled:
        adaptive_summary = engine.get_adaptive_summary()
        click.echo("Adaptive behavior summary (cumulative / recent-window):")
        for uid, summary in adaptive_summary.items():
            click.echo(f"  {uid}: total_signals={summary['total_signals']}, "
                       f"total_emissions={summary['total_emissions']}, "
                       f"total_scans={summary['total_scans']}, "
                       f"total_hazards={summary['total_hazards']}, "
                       f"recent_emission_rate={summary['emission_rate']:.2f}, "
                       f"recent_scan_rate={summary['scan_rate']:.2f}")

    # Output fabrication summary if enabled
    if cfg.fabrication_enabled:
        fab_summary = engine.get_fabrication_summary()
        click.echo(f"Fabrication: {fab_summary['total_attempts']} attempts, "
                   f"{fab_summary['total_successes']} successes, "
                   f"{fab_summary['total_lineage_records']} lineage records")
        if fab_summary['failures_by_cause']:
            click.echo(f"  Failures: {fab_summary['failures_by_cause']}")
        if fab_summary['generation_distribution']:
            click.echo(f"  Generations: {fab_summary['generation_distribution']}")
        if cfg.capsule_enabled and 'capsules' in fab_summary:
            cap_summary = fab_summary['capsules']
            click.echo(f"  Capsules: {cap_summary['total_capsules']} generated, "
                       f"avg_sparsity={cap_summary['avg_sparsity']:.2f}")

    # Output telemetry summary
    if cfg.telemetry_enabled:
        telemetry_summary = engine.get_telemetry_summary()
        click.echo(f"Telemetry: {telemetry_summary['total_frames']} frames, "
                   f"{telemetry_summary['units_tracked']} units tracked")
        reconciliation_summary = engine.get_reconciliation_summary()
        click.echo(f"Reconciliation: {reconciliation_summary['total_records']} records, "
                   f"avg_divergence={reconciliation_summary['avg_divergence']:.4f}, "
                   f"avg_continuity={reconciliation_summary['avg_continuity']:.4f}")

    # Output lineage drift summary
    if cfg.lineage_drift_enabled:
        drift_summary = engine.get_lineage_drift_summary()
        click.echo(f"Lineage drift: {drift_summary['total_entries']} entries, "
                   f"max_generation={drift_summary['max_generation']}")

    # Output pressure analysis summary
    if cfg.pressure_analysis_enabled:
        pressure = engine.get_pressure_summary()
        click.echo(f"Resource pressure: cells={pressure['resource_pressure_cells']}, "
                   f"avg_depletion={pressure['resource_depletion_rate']:.3f}, "
                   f"max_pressure={pressure['max_resource_pressure']:.3f}")
        click.echo(f"Extraction load: total={pressure['total_extraction_events']}, "
                   f"peak_load={pressure['peak_cell_load']:.3f}, "
                   f"avg_load={pressure['avg_load_per_active_unit']:.3f}")
        click.echo(f"Proximity pressure: avg={pressure['avg_proximity_pressure']:.3f}, "
                   f"max={pressure['max_proximity_pressure']:.3f}, "
                   f"blocked_rate={pressure['blocked_motion_rate']:.3f}")
        if cfg.signal_enabled:
            click.echo(f"Field perturbation: density={pressure['signal_density']:.1f}, "
                       f"perturbation={pressure['field_perturbation_score']:.3f}")

    # Output field dynamics summary
    if cfg.signal_dynamics_enabled:
        dynamics = engine.get_field_dynamics_summary()
        click.echo(f"Signal dynamics: patterns={dynamics['pattern_count']}, "
                   f"total_signals={dynamics['total_signals']}, "
                   f"clusters={dynamics['cluster_count']}")
        click.echo(f"Pattern correlation: records={dynamics['correlation_count']}, "
                   f"avg_score={dynamics['avg_correlation_score']:.3f}, "
                   f"max_score={dynamics['max_correlation_score']:.3f}")
        click.echo(f"Signal gradient: cells={dynamics['signal_gradient_cells']}, "
                   f"avg_gradient={dynamics['avg_signal_gradient']:.3f}, "
                   f"max_gradient={dynamics['max_signal_gradient']:.3f}")

    # Output trace compression summary
    if cfg.trace_compression_enabled:
        trace = engine.get_trace_compression_summary()
        click.echo(f"Trace compression: raw={trace['raw_trace_points']}, "
                   f"compressed={trace['compressed_trace_points']}, "
                   f"ratio={trace['compression_ratio']:.3f}")

    if output:
        outpath = Path(output)
        outpath.mkdir(parents=True, exist_ok=True)
        (outpath / "state.json").write_text(json.dumps(state.to_dict(), indent=2, default=str))
        (outpath / "events.json").write_text(engine.event_log.to_json())
        if cfg.signal_enabled:
            corr_summary = engine.get_correlation_summary()
            (outpath / "correlation.json").write_text(json.dumps(corr_summary, indent=2))
        if cfg.adaptive_enabled:
            adaptive_summary = engine.get_adaptive_summary()
            (outpath / "adaptive.json").write_text(json.dumps(adaptive_summary, indent=2))
        if cfg.fabrication_enabled:
            fab_summary = engine.get_fabrication_summary()
            (outpath / "fabrication.json").write_text(json.dumps(fab_summary, indent=2))
        if cfg.capsule_enabled:
            capsule_summary = engine.get_capsule_summary()
            (outpath / "capsules.json").write_text(json.dumps(capsule_summary, indent=2))
        if cfg.telemetry_enabled:
            telemetry_summary = engine.get_telemetry_summary()
            (outpath / "telemetry.json").write_text(json.dumps(telemetry_summary, indent=2))
            reconciliation_summary = engine.get_reconciliation_summary()
            (outpath / "reconciliation.json").write_text(json.dumps(reconciliation_summary, indent=2))
        if cfg.lineage_drift_enabled:
            drift_summary = engine.get_lineage_drift_summary()
            (outpath / "lineage_drift.json").write_text(json.dumps(drift_summary, indent=2))
        if cfg.pressure_analysis_enabled:
            pressure_summary = engine.get_pressure_summary()
            (outpath / "pressure_analysis.json").write_text(json.dumps(pressure_summary, indent=2))
        if cfg.signal_dynamics_enabled:
            dynamics_summary = engine.get_field_dynamics_summary()
            (outpath / "signal_field_dynamics.json").write_text(json.dumps(dynamics_summary, indent=2))
        if cfg.trace_compression_enabled:
            trace_summary = engine.get_trace_compression_summary()
            (outpath / "trace_compression.json").write_text(json.dumps(trace_summary, indent=2))
        click.echo(f"Output written to {outpath}")


@cli.command()
@click.argument("output_dir", type=click.Path(exists=True))
def inspect(output_dir: str) -> None:
    """Inspect a simulation run's output."""
    outpath = Path(output_dir)
    events = json.loads((outpath / "events.json").read_text())
    click.echo(f"Total events: {len(events)}")

    counts = Counter(e["event_type"] for e in events)
    for etype, count in counts.most_common():
        click.echo(f"  {etype}: {count}")


@cli.command()
def check() -> None:
    """Run guardrail checks on source code."""
    from machine_sim.guardrails.lexical import scan_directory
    from machine_sim.guardrails.codecheck import check_ast as check_ast_file

    project_root = Path(__file__).parent.parent.parent
    source_dir = project_root / "machine_sim"

    violations = scan_directory(source_dir, exclude_patterns=["tests/", "docs/", "__pycache__", "guardrails/", "cli/"])
    ast_violations = {}
    for py_file in source_dir.rglob("*.py"):
        rel = py_file.relative_to(source_dir).as_posix()
        if any(ex in rel for ex in ["tests/", "docs/", "__pycache__", "guardrails/", "cli/"]):
            continue
        viols = check_ast_file(py_file)
        if viols:
            ast_violations[str(py_file)] = viols

    if violations or ast_violations:
        click.echo("GUARDRAIL VIOLATIONS FOUND:")
        for filepath, viols in violations.items():
            click.echo(f"\n  {filepath}:")
            for line_no, term, line_text in viols:
                click.echo(f"    L{line_no}: '{term}' — {line_text}")
        for filepath, viols in ast_violations.items():
            click.echo(f"\n  {filepath} (AST):")
            for v in viols:
                click.echo(f"    L{v['line']}: {v['type']} — {v['name']}")
        raise SystemExit(1)
    else:
        click.echo("All guardrail checks passed.")


@cli.command()
@click.option("--config", "-c", type=click.Path(exists=True),
              default="configs/milestone_5_adaptive.toml")
@click.option("--ticks", "-t", type=int, default=None)
@click.option("--seed", "-s", type=int, default=42)
def compare(config: str, ticks: int | None, seed: int) -> None:
    """Compare baseline vs adaptive mode."""
    from machine_sim.agents.unit import MachineUnitImpl as Unit

    cfg = SimConfig.from_toml(Path(config))
    if ticks is not None:
        cfg.max_ticks = ticks

    results = {}
    for mode_name, adaptive in [("baseline", False), ("adaptive", True)]:
        cfg_copy = SimConfig(**cfg.to_dict())
        cfg_copy.adaptive_enabled = adaptive
        engine = SimEngine(cfg_copy, seed=seed)
        rng = random.Random(seed)
        for i in range(cfg_copy.unit_count):
            variant = ALL_VARIANTS[i % len(ALL_VARIANTS)]
            unit = Unit(
                unit_id=f"unit-{i:03d}",
                position=(rng.randint(0, cfg_copy.grid_width - 1),
                          rng.randint(0, cfg_copy.grid_height - 1)),
                variant=variant,
                signal_enabled=cfg_copy.signal_enabled,
                adaptive_enabled=adaptive,
            )
            engine.register_unit(unit)
        state = engine.run()
        events = engine.event_log.all_events()
        emitted = [e for e in events if e.event_type.name == "SIGNAL_EMITTED"]
        received = [e for e in events if e.event_type.name == "SIGNAL_RECEIVED"]
        blocked = [e for e in events if e.event_type.name == "MOVEMENT_BLOCKED"]
        hazards = [e for e in events if e.event_type.name == "HAZARD_ENCOUNTER"]
        active = sum(1 for a in state.agents if a.is_active)

        results[mode_name] = {
            "active_units": active,
            "total_events": len(events),
            "emitted": len(emitted),
            "received": len(received),
            "blocked": len(blocked),
            "hazards": len(hazards),
        }

    click.echo("Baseline vs Adaptive Comparison:")
    click.echo(f"  {'Metric':<20} {'Baseline':>10} {'Adaptive':>10} {'Delta':>10}")
    click.echo(f"  {'-'*50}")
    for metric in ["active_units", "total_events", "emitted", "received", "blocked", "hazards"]:
        b = results["baseline"][metric]
        a = results["adaptive"][metric]
        delta = a - b
        sign = "+" if delta > 0 else ""
        click.echo(f"  {metric:<20} {b:>10} {a:>10} {sign}{delta:>9}")


@cli.command()
@click.option("--config", "-c", type=click.Path(exists=True),
              default="configs/milestone_7_calibration_capsules.toml")
@click.option("--ticks", "-t", type=int, default=None)
@click.option("--seed", "-s", type=int, default=42)
def capsule_compare(config: str, ticks: int | None, seed: int) -> None:
    """Compare capsule-enabled vs capsule-disabled fabrication."""
    from machine_sim.agents.unit import MachineUnitImpl as Unit
    from machine_sim.environment.calibration import compute_capsule_impact

    cfg = SimConfig.from_toml(Path(config))
    if ticks is not None:
        cfg.max_ticks = ticks

    results = {}
    for mode_name, cap_enabled in [("capsule_disabled", False), ("capsule_enabled", True)]:
        cfg_copy = SimConfig(**cfg.to_dict())
        cfg_copy.capsule_enabled = cap_enabled
        engine = SimEngine(cfg_copy, seed=seed)
        rng = random.Random(seed)
        for i in range(cfg_copy.unit_count):
            variant = ALL_VARIANTS[i % len(ALL_VARIANTS)]
            unit = Unit(
                unit_id=f"unit-{i:03d}",
                position=(rng.randint(0, cfg_copy.grid_width - 1),
                          rng.randint(0, cfg_copy.grid_height - 1)),
                variant=variant,
            )
            engine.register_unit(unit)
        state = engine.run()

        # Collect successor units (those with generation_index > 0)
        successors = [u for u in engine.units
                      if getattr(u, '_generation_index', 0) > 0]

        fab_summary = engine.get_fabrication_summary()
        cap_summary = engine.get_capsule_summary()
        results[mode_name] = {
            "successor_count": len(successors),
            "fab_successes": fab_summary["total_successes"],
            "capsule_count": cap_summary["total_capsules"],
            "successors": successors,
        }

    impact = compute_capsule_impact(
        results["capsule_enabled"]["successors"],
        results["capsule_disabled"]["successors"],
    )

    click.echo("Capsule Impact Comparison:")
    click.echo(f"  {'Metric':<30} {'Disabled':>12} {'Enabled':>12} {'Delta':>12}")
    click.echo(f"  {'-'*66}")
    d = impact["capsule_disabled"]
    e = impact["capsule_enabled"]
    click.echo(f"  {'count':<30} {d['count']:>12.2f} {e['count']:>12.2f} {e['count']-d['count']:>+12.2f}")
    click.echo(f"  {'avg_power':<30} {d['avg_power']:>12.4f} {e['avg_power']:>12.4f} {e['avg_power']-d['avg_power']:>+12.4f}")
    click.echo(f"  {'avg_sensor_health':<30} {d['avg_sensor_health']:>12.4f} {e['avg_sensor_health']:>12.4f} {e['avg_sensor_health']-d['avg_sensor_health']:>+12.4f}")
    click.echo(f"  {'active_count':<30} {d['active_count']:>12.2f} {e['active_count']:>12.2f} {e['active_count']-d['active_count']:>+12.2f}")
    click.echo(f"  {'warm_start_power_delta':<30} {d['warm_start_power_delta']:>12.4f} {e['warm_start_power_delta']:>12.4f} {e['warm_start_power_delta']-d['warm_start_power_delta']:>+12.4f}")
    click.echo(f"  {'warm_start_sensor_delta':<30} {d['warm_start_sensor_delta']:>12.4f} {e['warm_start_sensor_delta']:>12.4f} {e['warm_start_sensor_delta']-d['warm_start_sensor_delta']:>+12.4f}")
    click.echo(f"  {'capsule_applied':<30} {'N/A':>12} "
               f"{impact['capsule_enabled']['capsule_applied_count']:>12}")
    delta_detected = impact["delta"]["neutral_metric_delta_detected"]
    click.echo(f"  {'neutral_metric_delta_detected':<30} {'no' if not delta_detected else 'yes':>12} "
               f"{'yes' if delta_detected else 'no':>12}")


if __name__ == "__main__":
    cli()
