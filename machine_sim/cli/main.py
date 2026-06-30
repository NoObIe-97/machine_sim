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


if __name__ == "__main__":
    cli()
