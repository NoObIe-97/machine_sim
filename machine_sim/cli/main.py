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
        )
        engine.register_unit(unit)

    click.echo(f"Starting simulation: {cfg.grid_width}x{cfg.grid_height}, "
               f"{cfg.unit_count} units, {cfg.max_ticks} ticks, seed={cfg.seed}")

    state = engine.run()

    active = sum(1 for a in state.agents if a.is_active)
    click.echo(f"Simulation complete. Tick {state.tick}/{cfg.max_ticks}")
    click.echo(f"Active units: {active}/{cfg.unit_count}")

    if output:
        outpath = Path(output)
        outpath.mkdir(parents=True, exist_ok=True)
        (outpath / "state.json").write_text(json.dumps(state.to_dict(), indent=2, default=str))
        (outpath / "events.json").write_text(engine.event_log.to_json())
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


if __name__ == "__main__":
    cli()
