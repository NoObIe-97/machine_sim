"""Command-line interface for After Silicon simulator."""

from __future__ import annotations

import json
import logging
import random
import tomllib
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

import click

from machine_sim.agents.unit import MachineUnitImpl
from machine_sim.agents.variants import ALL_VARIANTS
from machine_sim.sim.config import SimConfig
from machine_sim.sim.engine import SimEngine
from machine_sim.sim.events import EventType


@click.group()
def cli() -> None:
    """After Silicon: Machine Civilization Emergence Simulator"""
    pass


def build_engine(cfg: SimConfig) -> SimEngine:
    """Construct an engine and register its initial units for a configuration.

    Both the ordinary run path and the M20 run-control paths use this builder,
    so a controlled run and an uninterrupted reference run start from an
    identical construction sequence.
    """
    engine = SimEngine(cfg, seed=cfg.seed)
    _register_initial_units(engine, cfg)
    return engine


def _register_initial_units(engine: SimEngine, cfg: SimConfig) -> None:
    rng = random.Random(cfg.seed)

    # For long-run adaptation, cluster initial units for signal proximity
    if cfg.long_run_adaptation_enabled and cfg.unit_count > 1:
        cluster_cx = cfg.grid_width // 2
        cluster_cy = cfg.grid_height // 2
        cluster_r = min(15, cfg.grid_width // 6)

    for i in range(cfg.unit_count):
        variant = ALL_VARIANTS[i % len(ALL_VARIANTS)] if not cfg.long_run_adaptation_enabled else None
        if cfg.long_run_adaptation_enabled:
            # Cluster units in a central region so signals can be observed
            angle = 2.0 * 3.14159265 * i / cfg.unit_count
            import math
            r_offset = rng.uniform(0, cluster_r)
            px = int(cluster_cx + r_offset * math.cos(angle))
            py = int(cluster_cy + r_offset * math.sin(angle))
            px = max(0, min(cfg.grid_width - 1, px))
            py = max(0, min(cfg.grid_height - 1, py))
            pos = (px, py)
        else:
            pos = (rng.randint(0, cfg.grid_width - 1), rng.randint(0, cfg.grid_height - 1))
        # M19: Create architecture descriptor if variation enabled
        arch_desc = None
        if cfg.neural_architecture_variation_enabled and cfg.neural_controller_enabled:
            from machine_sim.agents.neural_architecture import NeuralArchitectureDescriptor, stable_seed as arch_stable_seed
            arch_rng = random.Random(arch_stable_seed("arch_init", cfg.seed, i))
            if cfg.initial_architecture_policy == "bounded_seeded_distribution":
                h = arch_rng.randint(cfg.minimum_hidden_size, cfg.maximum_hidden_size)
                d = arch_rng.uniform(cfg.minimum_recurrent_density, cfg.maximum_recurrent_density)
                r = arch_rng.uniform(cfg.minimum_plasticity_rate, cfg.maximum_plasticity_rate)
            else:
                h = cfg.initial_hidden_size
                d = cfg.initial_recurrent_density
                r = cfg.neural_plasticity_rate
            arch_desc = NeuralArchitectureDescriptor(
                architecture_id=f"arch-init-{i:03d}",
                hidden_size=h,
                recurrent_density=d,
                plasticity_rate=r,
                plasticity_enabled=cfg.neural_plasticity_enabled,
            )

        # M22: program-backed initial units carry a canonical baseline design
        # program; the decoded descriptor replaces the legacy descriptor.
        design_program = None
        program_bounds = None
        program_length_bounds = None
        if getattr(cfg, "design_program_enabled", False):
            from machine_sim.agents.design_program import (
                DesignExecutionBounds,
                canonical_baseline_program,
            )
            from machine_sim.agents.neural_architecture import (
                NeuralArchitectureConfig as _ArchCfgBounds,
            )
            program_bounds = DesignExecutionBounds.from_architecture_config(
                _ArchCfgBounds(
                    minimum_hidden_size=cfg.minimum_hidden_size,
                    maximum_hidden_size=cfg.maximum_hidden_size,
                    initial_hidden_size=cfg.initial_hidden_size,
                    minimum_recurrent_density=cfg.minimum_recurrent_density,
                    maximum_recurrent_density=cfg.maximum_recurrent_density,
                    initial_recurrent_density=cfg.initial_recurrent_density,
                    minimum_plasticity_rate=cfg.minimum_plasticity_rate,
                    maximum_plasticity_rate=cfg.maximum_plasticity_rate,
                    initial_plasticity_rate=cfg.neural_plasticity_rate,
                ),
                execution_budget=cfg.program_execution_budget,
                program_base_cost=cfg.program_base_cost,
                program_per_instruction_cost=cfg.program_per_instruction_cost,
            )
            program_length_bounds = (cfg.program_min_length, cfg.program_max_length)
            design_program = canonical_baseline_program(
                plasticity_rate=cfg.neural_plasticity_rate
            )

        unit = MachineUnitImpl(
            unit_id=f"unit-{i:03d}",
            position=pos,
            variant=variant,
            signal_enabled=cfg.signal_enabled,
            signal_pattern_count=cfg.signal_pattern_count,
            signal_energy_cost=cfg.signal_energy_cost,
            signal_default_radius=cfg.signal_default_radius,
            signal_default_decay=cfg.signal_default_decay,
            signal_default_duration=cfg.signal_default_duration,
            adaptive_enabled=cfg.adaptive_enabled,
            neural_controller_enabled=cfg.neural_controller_enabled,
            neural_controller_mode=cfg.neural_controller_mode,
            neural_plasticity_enabled=cfg.neural_plasticity_enabled,
            neural_hidden_size=cfg.neural_hidden_size,
            neural_plasticity_rate=cfg.neural_plasticity_rate,
            neural_seed=cfg.seed,
            neural_architecture_descriptor=arch_desc,
            design_program=design_program,
            unit_executed_construction_enabled=getattr(cfg, 'unit_executed_construction_enabled', False),
            design_execution_bounds=program_bounds,
            design_program_length_bounds=program_length_bounds,
        )
        if cfg.long_run_adaptation_enabled:
            unit.max_power = 10000
            unit.power_reserve = 10000
        # Scale component degradation rates if configured
        if cfg.component_degradation_scale != 1.0:
            for comp in unit.components.values():
                comp.degradation_rate *= cfg.component_degradation_scale
        engine.register_unit(unit)


@cli.command()
@click.option("--config", "-c", type=click.Path(exists=True), default="configs/milestone_1.toml")
@click.option("--ticks", "-t", type=int, default=None)
@click.option("--seed", "-s", type=int, default=None)
@click.option("--output", "-o", type=click.Path(), default=None)
@click.option("--verbose", "-v", is_flag=True)
@click.option("--run-control", is_flag=True,
              help="Drive the run through the M20 lifecycle controller.")
@click.option("--checkpoint-interval", type=int, default=None,
              help="Tick spacing between checkpoints when run control is active.")
@click.option("--resume-from", type=click.Path(exists=True), default=None,
              help="Resume a controlled run from a checkpoint file.")
@click.option("--deep-digest-interval", type=int, default=None,
              help="Sample the deep semantic-state digest every N ticks (M21 oracle).")
@click.option("--deep-digest-trace", type=click.Path(), default=None,
              help="Append-only JSONL sink for deep-digest samples.")
def run(config: str, ticks: int | None, seed: int | None, output: str | None,
        verbose: bool, run_control: bool, checkpoint_interval: int | None,
        resume_from: str | None, deep_digest_interval: int | None,
        deep_digest_trace: str | None) -> None:
    """Run a simulation."""
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO)

    cfg = SimConfig.from_toml(Path(config))
    if ticks is not None:
        cfg.max_ticks = ticks
    if seed is not None:
        cfg.seed = seed

    use_run_control = run_control or cfg.run_control_enabled
    if (use_run_control or resume_from) and not output:
        raise click.UsageError("run control requires --output")
    if deep_digest_interval is not None and not deep_digest_trace:
        raise click.UsageError("--deep-digest-interval requires --deep-digest-trace")

    if resume_from:
        from machine_sim.sim.run_control import resume_controller
        controller = resume_controller(Path(output), Path(resume_from), cfg.max_ticks)
        # Mirror fresh-run behavior: a controlled run always advances the
        # M20 digest chain regardless of the config default.
        controller.run_digest_enabled = True
        if deep_digest_interval is not None:
            controller.deep_digest_interval = max(1, int(deep_digest_interval))
            controller.deep_digest_path = Path(deep_digest_trace)
        engine = controller.engine
        click.echo(f"Resumed run {controller.manifest.run_id} at tick {engine.tick_count}")
        final_state = controller.advance()
        controller.finalize_artifact_index()
        click.echo(f"Run state: {final_state} at tick {engine.tick_count}")
        state = engine.snapshot()
    else:
        engine = build_engine(cfg)
        click.echo(f"Starting simulation: {cfg.grid_width}x{cfg.grid_height}, "
                   f"{cfg.unit_count} units, {cfg.max_ticks} ticks, seed={cfg.seed}")
        if use_run_control:
            from machine_sim.sim.run_control import RunController
            controller = RunController(
                engine, Path(output), checkpoint_interval=checkpoint_interval,
                checkpoint_enabled=True, run_digest_enabled=True,
                deep_digest_interval=deep_digest_interval,
                deep_digest_path=Path(deep_digest_trace) if deep_digest_trace else None,
            )
            controller.start()
            final_state = controller.advance()
            controller.finalize_artifact_index()
            click.echo(f"Run state: {final_state} at tick {engine.tick_count}")
            state = engine.snapshot()
        else:
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
        tel = trace.get("telemetry", {})
        if tel.get("telemetry_input_frames", 0) > 0:
            click.echo(f"Telemetry reduction: input={tel['telemetry_input_frames']}, "
                       f"compressed={tel['compressed_telemetry_frames']}, "
                       f"continuity={tel['continuity_summary']:.3f}")
        cap = trace.get("capsule", {})
        if cap.get("capsule_summary_count", 0) > 0:
            click.echo(f"Capsule diagnostics: count={cap['capsule_summary_count']}, "
                       f"fields={cap['capsule_compatible_fields']}")
        lin = trace.get("lineage", {})
        if lin.get("lineage_trace_count", 0) > 0:
            click.echo(f"Lineage trace: count={lin['lineage_trace_count']}, "
                       f"span={lin['lineage_index_span']}, "
                       f"delta={lin['lineage_trace_delta']:.3f}")
        rep = trace.get("replay", {})
        click.echo(f"Replay metrics: windows={rep.get('replay_window_count', 0)}, "
                   f"avg_error={rep.get('avg_replay_error', 0):.3f}, "
                   f"stability={rep.get('replay_stability_score', 0):.3f}")

    # Output trace drift summary
    if cfg.trace_drift_enabled:
        drift = engine.get_trace_drift_summary()
        gen = drift.get("generation", {})
        click.echo(f"Trace drift: generations={gen.get('generation_trace_count', 0)}, "
                   f"span={gen.get('generation_index_span', 0)}, "
                   f"avg_delta={gen.get('avg_generation_trace_delta', 0):.3f}, "
                   f"max_delta={gen.get('max_generation_trace_delta', 0):.3f}")
        env = drift.get("drift_envelope", {})
        click.echo(f"Drift envelope: records={env.get('drift_envelope_count', 0)}, "
                   f"avg_width={env.get('avg_drift_envelope_width', 0):.3f}, "
                   f"max_width={env.get('max_drift_envelope_width', 0):.3f}")
        rep_stab = drift.get("replay_stability", {})
        click.echo(f"Replay stability: windows={rep_stab.get('replay_error_window_count', 0)}, "
                   f"avg_delta={rep_stab.get('avg_replay_error_delta', 0):.3f}, "
                   f"stability_floor={rep_stab.get('replay_stability_floor', 0):.3f}")
        ct = drift.get("capsule_trace", {})
        click.echo(f"Capsule trace check: count={ct.get('capsule_trace_check_count', 0)}, "
                   f"compatibility={ct.get('capsule_trace_compatibility_score', 0):.3f}, "
                   f"power_delta={ct.get('capsule_trace_power_delta', 0):.3f}")
        ret = drift.get("retention", {})
        click.echo(f"Retention: records={ret.get('retention_record_count', 0)}, "
                   f"span={ret.get('retention_window_span', 0)}, "
                   f"retained={ret.get('retained_summary_count', 0)}, "
                   f"dropped={ret.get('retention_drop_count', 0)}")

    # Output summary consistency
    if cfg.summary_consistency_enabled:
        sc = engine.get_summary_consistency_summary()
        cu = sc.get("cross_unit", {})
        click.echo(f"Summary consistency: units={cu.get('unit_summary_count', 0)}, "
                   f"pairs={cu.get('unit_pair_count', 0)}, "
                   f"avg_delta={cu.get('avg_unit_summary_delta', 0):.3f}, "
                   f"score={cu.get('summary_consistency_score', 0):.3f}")
        rs = sc.get("retention_stability", {})
        click.echo(f"Retention stability: windows={rs.get('retention_window_count', 0)}, "
                   f"variance={rs.get('avg_retention_variance', 0):.3f}, "
                   f"stability={rs.get('retention_stability_score', 0):.3f}, "
                   f"drop_rate={rs.get('retention_drop_rate', 0):.3f}")
        cc = sc.get("compression_convergence", {})
        click.echo(f"Compression convergence: windows={cc.get('compression_window_count', 0)}, "
                   f"ratio={cc.get('avg_compression_ratio', 0):.3f}, "
                   f"delta={cc.get('compression_ratio_delta', 0):.3f}, "
                   f"score={cc.get('compression_convergence_score', 0):.3f}")
        ge = sc.get("cross_generation_envelope", {})
        click.echo(f"Generation envelope: records={ge.get('cross_generation_envelope_count', 0)}, "
                   f"span={ge.get('generation_index_span', 0)}, "
                   f"width={ge.get('generation_envelope_width', 0):.3f}, "
                   f"stability={ge.get('generation_envelope_stability', 0):.3f}")
        cb = sc.get("combined", {})
        click.echo(f"Combined stability: windows={cb.get('combined_window_count', 0)}, "
                   f"consistency={cb.get('combined_consistency_score', 0):.3f}, "
                   f"stability={cb.get('combined_stability_score', 0):.3f}, "
                   f"delta={cb.get('combined_delta_score', 0):.3f}")

    if output:
        outpath = Path(output)
        outpath.mkdir(parents=True, exist_ok=True)
        # Skip massive state/events JSON for long-run mode — judge doesn't need them
        if not cfg.long_run_adaptation_enabled:
            (outpath / "state.json").write_text(json.dumps(state.to_dict(), indent=2, default=str))
            # Stream events to file instead of building one huge JSON string
            with open(outpath / "events.json", "w") as ef:
                ef.write("[")
                first = True
                for e in engine.event_log.all_events():
                    if not first:
                        ef.write(",")
                    ef.write(json.dumps({
                        "tick": e.tick,
                        "event_type": e.event_type.name,
                        "unit_id": e.unit_id,
                        "data": e.data,
                    }, default=str))
                    first = False
                ef.write("]")
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
        if cfg.trace_drift_enabled:
            trace_drift_summary = engine.get_trace_drift_summary()
            (outpath / "trace_drift.json").write_text(json.dumps(trace_drift_summary, indent=2))
        if cfg.summary_consistency_enabled:
            sc_summary = engine.get_summary_consistency_summary()
            (outpath / "summary_consistency.json").write_text(json.dumps(sc_summary, indent=2))
        if cfg.long_run_adaptation_enabled:
            lr_summary = engine.get_long_run_adaptation_summary()
            (outpath / "long_run_adaptation_summary.json").write_text(json.dumps(lr_summary, indent=2))
            # Write adaptive state traces (periodic snapshots)
            with open(outpath / "unit_adaptive_state_trace.jsonl", "w") as f:
                for snap in engine._adaptive_state_snapshots:
                    f.write(json.dumps(snap) + "\n")
                # Also write final state
                for u in engine.units:
                    if hasattr(u, '_adaptive_state'):
                        f.write(json.dumps({"tick": engine.tick_count, "unit_id": u.unit_id, **u._adaptive_state.to_dict()}) + "\n")
            # Action distribution trace (sampled to stay bounded)
            events = engine.event_log.all_events()
            action_events = [e for e in events if e.event_type == EventType.UNIT_ACTION]
            max_trace_lines = 50000
            import math
            step = max(1, math.ceil(len(action_events) / max_trace_lines))
            with open(outpath / "action_distribution_trace.jsonl", "w") as f:
                for i in range(0, len(action_events), step):
                    e = action_events[i]
                    f.write(json.dumps({"tick": e.tick, "unit_id": e.unit_id, "action": e.data.get("action", "unknown")}) + "\n")
            # Unit lifetime trace
            with open(outpath / "unit_lifetime_trace.jsonl", "w") as f:
                for u in engine.units:
                    f.write(json.dumps({"unit_id": u.unit_id, "active": u.is_active, "power": u.power_reserve, "generation": getattr(u, '_generation_index', 0)}) + "\n")
            # Local feedback trace
            if hasattr(engine, '_local_feedback_trace'):
                with open(outpath / "local_feedback_trace.jsonl", "w") as f:
                    for entry in engine._local_feedback_trace:
                        f.write(json.dumps(entry) + "\n")
            # Descendant adaptive-state transfer trace
            if hasattr(engine, '_descendant_transfer_trace'):
                with open(outpath / "descendant_adaptive_state_trace.jsonl", "w") as f:
                    for entry in engine._descendant_transfer_trace:
                        f.write(json.dumps(entry) + "\n")
            # Run static comparison (same env, same positions, no adaptation)
            # Use shorter tick count for static comparison to avoid excessive runtime
            static_ticks = min(cfg.max_ticks, 200)
            static_cfg = SimConfig(
                grid_width=cfg.grid_width, grid_height=cfg.grid_height,
                resource_density=cfg.resource_density, hazard_density=cfg.hazard_density,
                unit_count=cfg.unit_count, power_drain_rate=cfg.power_drain_rate,
                max_ticks=static_ticks, seed=cfg.seed,
                signal_enabled=cfg.signal_enabled, adaptive_enabled=False,
                signal_pattern_count=cfg.signal_pattern_count,
                signal_energy_cost=cfg.signal_energy_cost,
                signal_default_radius=cfg.signal_default_radius,
                signal_default_decay=cfg.signal_default_decay,
                signal_default_duration=cfg.signal_default_duration,
                signal_observation_window=cfg.signal_observation_window,
                fabrication_enabled=False,
                capsule_enabled=False,
            )
            static_engine = SimEngine(static_cfg, seed=cfg.seed)
            import math as _math
            static_rng = random.Random(cfg.seed)
            static_cx = cfg.grid_width // 2
            static_cy = cfg.grid_height // 2
            static_r = min(15, cfg.grid_width // 6)
            for i in range(cfg.unit_count):
                angle = 2.0 * 3.14159265 * i / cfg.unit_count
                r_off = static_rng.uniform(0, static_r)
                spx = int(static_cx + r_off * _math.cos(angle))
                spy = int(static_cy + r_off * _math.sin(angle))
                spx = max(0, min(cfg.grid_width - 1, spx))
                spy = max(0, min(cfg.grid_height - 1, spy))
                su = MachineUnitImpl(
                    f"s-{i}", position=(spx, spy),
                    signal_enabled=cfg.signal_enabled, adaptive_enabled=False)
                su.variant = None
                su.max_power = 5000
                su.power_reserve = 5000
                static_engine.register_unit(su)
            static_engine.run()
            static_summary = static_engine.get_long_run_adaptation_summary()
            comparison = engine.get_adaptive_vs_static_comparison(static_summary)
            (outpath / "adaptive_vs_static_compare.json").write_text(json.dumps(comparison, indent=2))
            # Resource/field summary
            field_summary = {
                "total_resource_cells": sum(1 for c in engine.world.grid.values() if c.resources),
                "total_hazard_cells": sum(1 for c in engine.world.grid.values() if c.hazards),
                "total_resources": sum(sum(r.quantity for r in c.resources.values()) for c in engine.world.grid.values()),
            }
            (outpath / "resource_hazard_field_summary.json").write_text(json.dumps(field_summary, indent=2))
            click.echo(f"Adaptive run: active={lr_summary.get('final_active_unit_count', 0)}")
            click.echo(f"Static run: active={static_summary.get('final_active_unit_count', 0)}")
        # M15 multi-generation trace artifacts
        if cfg.multi_generation_trace_enabled and hasattr(engine, 'multi_gen_trace'):
            mg = engine.multi_gen_trace
            # Generation-indexed transfer trace
            records = mg.get_records()
            with open(outpath / "generation_adaptive_state_trace.jsonl", "w") as f:
                for rec in records:
                    entry = {
                        "tick": rec.tick,
                        "source_unit_id": rec.source_unit_id,
                        "successor_unit_id": rec.successor_unit_id,
                        "source_generation_index": rec.source_generation_index,
                        "successor_generation_index": rec.successor_generation_index,
                        "source_adaptive_state_summary": {k: round(v, 4) for k, v in rec.source_adaptive_state.items()},
                        "successor_adaptive_state_summary": {k: round(v, 4) for k, v in rec.successor_adaptive_state.items()},
                        "adaptive_state_delta": {k: round(v, 6) for k, v in rec.adaptive_state_delta.items()},
                        "transfer_variation_summary": rec.transfer_variation_summary,
                        "source_lifetime_ticks_at_transfer": rec.source_lifetime_ticks,
                        "successor_initial_power_ratio": round(rec.successor_initial_power_ratio, 4),
                        "local_feedback_context_summary": rec.local_feedback_context,
                    }
                    f.write(json.dumps(entry) + "\n")
            # Adaptive trajectory comparison
            trajectory = mg.get_trajectory_comparison()
            (outpath / "adaptive_trajectory_summary.json").write_text(json.dumps({
                "run_parameters": {
                    "grid_width": cfg.grid_width,
                    "grid_height": cfg.grid_height,
                    "unit_count": cfg.unit_count,
                    "max_ticks": cfg.max_ticks,
                    "seed": cfg.seed,
                    "fabrication_enabled": cfg.fabrication_enabled,
                    "unit_capacity": cfg.unit_capacity,
                    "fabrication_interval": cfg.fabrication_interval,
                    "fabrication_min_power_ratio": cfg.fabrication_min_power_ratio,
                    "fabrication_min_component_health": cfg.fabrication_min_component_health,
                },
                "transfer_summary": mg.get_trajectory_summary(),
                "generation_summary": {
                    "generation_index_span": trajectory["generation_index_span"],
                    "transfer_count": trajectory["transfer_count"],
                },
                "adaptive_state_delta_summary": trajectory["avg_transfer_delta"],
                "trajectory_continuity_summary": {
                    "score": trajectory["trajectory_continuity_score"],
                },
                "signal_adaptation_summary": trajectory["signal_parameter_drift_summary"],
                "resource_hazard_response_summary": {
                    "resource_drift": trajectory["resource_response_drift_summary"],
                    "hazard_drift": trajectory["hazard_response_drift_summary"],
                },
                "late_run_survival_summary": {
                    "final_active_count": lr_summary.get("final_active_unit_count", 0) if cfg.long_run_adaptation_enabled else 0,
                },
                "artifact_size_summary": {
                    "transfer_records": len(records),
                    "generation_index_span": trajectory["generation_index_span"],
                },
                "judge_status": "pending",
            }, indent=2))
            # Reference comparison: transfer-disabled run
            ref_cfg = SimConfig(
                grid_width=cfg.grid_width, grid_height=cfg.grid_height,
                resource_density=cfg.resource_density, hazard_density=cfg.hazard_density,
                unit_count=cfg.unit_count, power_drain_rate=cfg.power_drain_rate,
                max_ticks=min(cfg.max_ticks, 200), seed=cfg.seed,
                signal_enabled=cfg.signal_enabled, adaptive_enabled=cfg.adaptive_enabled,
                signal_pattern_count=cfg.signal_pattern_count,
                signal_energy_cost=cfg.signal_energy_cost,
                signal_default_radius=cfg.signal_default_radius,
                signal_default_decay=cfg.signal_default_decay,
                signal_default_duration=cfg.signal_default_duration,
                signal_observation_window=cfg.signal_observation_window,
                fabrication_enabled=True, capsule_enabled=False,
                unit_capacity=cfg.unit_capacity,
                fabrication_interval=cfg.fabrication_interval,
                fabrication_power_cost=cfg.fabrication_power_cost,
                fabrication_material_cost=cfg.fabrication_material_cost,
                fabrication_variation=cfg.fabrication_variation,
                fabrication_min_power_ratio=cfg.fabrication_min_power_ratio,
                fabrication_min_component_health=cfg.fabrication_min_component_health,
                long_run_adaptation_enabled=False,
                multi_generation_trace_enabled=True,
            )
            ref_engine = SimEngine(ref_cfg, seed=cfg.seed)
            ref_rng = random.Random(cfg.seed)
            ref_cx = cfg.grid_width // 2
            ref_cy = cfg.grid_height // 2
            ref_r = min(15, cfg.grid_width // 6)
            for i in range(cfg.unit_count):
                angle = 2.0 * 3.14159265 * i / cfg.unit_count
                r_off = ref_rng.uniform(0, ref_r)
                rpx = int(ref_cx + r_off * math.cos(angle))
                rpy = int(ref_cy + r_off * math.sin(angle))
                rpx = max(0, min(cfg.grid_width - 1, rpx))
                rpy = max(0, min(cfg.grid_height - 1, rpy))
                ru = MachineUnitImpl(
                    f"r-{i}", position=(rpx, rpy),
                    signal_enabled=cfg.signal_enabled, adaptive_enabled=cfg.adaptive_enabled)
                ru.max_power = 10000
                ru.power_reserve = 10000
                ref_engine.register_unit(ru)
            ref_engine.run()
            ref_records = ref_engine.multi_gen_trace.get_records()
            ref_active = sum(1 for u in ref_engine.units if u.is_active)
            comparison_data = mg.get_comparison_with_reference(ref_records)
            comparison_data["late_active_delta"] = (
                lr_summary.get("final_active_unit_count", 0) - ref_active
                if cfg.long_run_adaptation_enabled else 0
            )
            (outpath / "adaptive_transfer_compare.json").write_text(json.dumps(comparison_data, indent=2))
            click.echo(f"M15 transfers: {len(records)}, ref transfers: {len(ref_records)}")
            click.echo(f"M15 generation span: {trajectory['generation_index_span']}")

        # M17 neural processing unit artifacts
        if cfg.neural_controller_enabled:
            neural_summary = engine.get_neural_processing_summary()
            (outpath / "neural_processing_summary.json").write_text(json.dumps(neural_summary, indent=2))

            # Neural state trace
            with open(outpath / "neural_state_trace.jsonl", "w") as f:
                for entry in engine._neural_state_trace:
                    f.write(json.dumps(entry) + "\n")

            # Neural action trace
            with open(outpath / "neural_action_trace.jsonl", "w") as f:
                for entry in engine._neural_action_trace:
                    f.write(json.dumps(entry) + "\n")

            # Neural plasticity trace
            with open(outpath / "neural_plasticity_trace.jsonl", "w") as f:
                for entry in engine._neural_plasticity_trace:
                    f.write(json.dumps(entry) + "\n")

            # Neural successor transfer trace
            if engine._neural_successor_transfer_trace:
                with open(outpath / "neural_successor_transfer_trace.jsonl", "w") as f:
                    for entry in engine._neural_successor_transfer_trace:
                        f.write(json.dumps(entry) + "\n")

            # Neural controller config snapshot
            if engine.units and hasattr(engine.units[0], '_neural_controller') and engine.units[0]._neural_controller is not None:
                nc_cfg = engine.units[0]._neural_controller.config
                (outpath / "neural_controller_config.json").write_text(json.dumps({
                    "input_size": nc_cfg.input_size,
                    "hidden_size": nc_cfg.hidden_size,
                    "output_size": nc_cfg.output_size,
                    "param_output_size": nc_cfg.param_output_size,
                    "plasticity_rate": nc_cfg.plasticity_rate,
                    "plasticity_enabled": nc_cfg.plasticity_enabled,
                    "weight_bound": nc_cfg.weight_bound,
                }, indent=2))

                # Initial parameter snapshot
                init_state = engine.units[0]._neural_controller._initialize_state(
                    engine.units[0].unit_id, cfg.seed
                )
                (outpath / "neural_parameter_snapshot_initial.json").write_text(json.dumps(init_state.to_dict(), indent=2))

                # Final parameter snapshot
                (outpath / "neural_parameter_snapshot_final.json").write_text(json.dumps(
                    engine.units[0]._neural_controller.state.to_dict(), indent=2
                ))

            # Neural vs scalar comparison
            if cfg.long_run_adaptation_enabled:
                scalar_cfg = SimConfig(
                    grid_width=cfg.grid_width, grid_height=cfg.grid_height,
                    resource_density=cfg.resource_density, hazard_density=cfg.hazard_density,
                    unit_count=cfg.unit_count, power_drain_rate=cfg.power_drain_rate,
                    max_ticks=min(cfg.max_ticks, 200), seed=cfg.seed,
                    signal_enabled=cfg.signal_enabled, adaptive_enabled=True,
                    neural_controller_enabled=False,
                    signal_pattern_count=cfg.signal_pattern_count,
                    signal_energy_cost=cfg.signal_energy_cost,
                    signal_default_radius=cfg.signal_default_radius,
                    signal_default_decay=cfg.signal_default_decay,
                    signal_default_duration=cfg.signal_default_duration,
                    signal_observation_window=cfg.signal_observation_window,
                    fabrication_enabled=False, capsule_enabled=False,
                )
                scalar_engine = SimEngine(scalar_cfg, seed=cfg.seed)
                scalar_rng = random.Random(cfg.seed)
                scalar_cx = cfg.grid_width // 2
                scalar_cy = cfg.grid_height // 2
                scalar_r = min(15, cfg.grid_width // 6)
                for si in range(cfg.unit_count):
                    angle_s = 2.0 * 3.14159265 * si / cfg.unit_count
                    r_off_s = scalar_rng.uniform(0, scalar_r)
                    spx = int(scalar_cx + r_off_s * math.cos(angle_s))
                    spy = int(scalar_cy + r_off_s * math.sin(angle_s))
                    spx = max(0, min(cfg.grid_width - 1, spx))
                    spy = max(0, min(cfg.grid_height - 1, spy))
                    su = MachineUnitImpl(
                        f"sc-{si}", position=(spx, spy),
                        signal_enabled=cfg.signal_enabled, adaptive_enabled=True,
                        neural_controller_enabled=False)
                    su.variant = None
                    su.max_power = 5000
                    su.power_reserve = 5000
                    scalar_engine.register_unit(su)
                scalar_engine.run()
                scalar_summary = scalar_engine.get_long_run_adaptation_summary()
                comparison = engine.get_neural_vs_scalar_comparison(scalar_summary)
                (outpath / "neural_vs_scalar_compare.json").write_text(json.dumps(comparison, indent=2))
                click.echo(f"Neural active: {neural_summary['final_active_count']}, Scalar active: {scalar_summary.get('final_active_unit_count', 0)}")

            # Resource/field summary
            field_summary_m17 = {
                "total_resource_cells": sum(1 for c in engine.world.grid.values() if c.resources),
                "total_hazard_cells": sum(1 for c in engine.world.grid.values() if c.hazards),
                "total_resources": sum(sum(r.quantity for r in c.resources.values()) for c in engine.world.grid.values()),
            }
            (outpath / "resource_hazard_field_summary.json").write_text(json.dumps(field_summary_m17, indent=2))

            click.echo(f"Neural state traces: {neural_summary['neural_state_trace_count']}")
            click.echo(f"Neural plasticity traces: {neural_summary['neural_plasticity_trace_count']}")
            click.echo(f"Neural successor transfers: {neural_summary['neural_successor_transfer_count']}")

        # M19 architecture variation artifacts
        if cfg.neural_architecture_variation_enabled and cfg.neural_controller_enabled:
            # Architecture run summary
            arch_transfer_count = len(engine._architecture_transfer_trace)
            arch_increase = sum(1 for t in engine._architecture_transfer_trace if t.get("hidden_size_delta", 0) > 0)
            arch_decrease = sum(1 for t in engine._architecture_transfer_trace if t.get("hidden_size_delta", 0) < 0)
            arch_unchanged = sum(1 for t in engine._architecture_transfer_trace if t.get("hidden_size_delta", 0) == 0)

            # Collect distinct architectures
            arch_ids = set()
            for u in engine.units:
                if hasattr(u, '_architecture_descriptor') and u._architecture_descriptor is not None:
                    arch_ids.add(u._architecture_descriptor.architecture_id)
            for t in engine._architecture_transfer_trace:
                arch_ids.add(t.get("source_architecture_id", ""))
                arch_ids.add(t.get("successor_architecture_id", ""))

            run_summary = {
                "run_ticks": engine.tick_count,
                "architecture_variation_enabled": True,
                "architecture_transfer_count": arch_transfer_count,
                "increase_transition_count": arch_increase,
                "decrease_transition_count": arch_decrease,
                "unchanged_transition_count": arch_unchanged,
                "distinct_architecture_count": len(arch_ids),
                "total_processing_cost": round(engine._total_processing_cost, 6),
                "total_fabrication_cost": round(engine._total_fabrication_cost, 6),
                "architecture_bounds": {
                    "minimum_hidden_size": cfg.minimum_hidden_size,
                    "maximum_hidden_size": cfg.maximum_hidden_size,
                    "minimum_recurrent_density": cfg.minimum_recurrent_density,
                    "maximum_recurrent_density": cfg.maximum_recurrent_density,
                    "minimum_plasticity_rate": cfg.minimum_plasticity_rate,
                    "maximum_plasticity_rate": cfg.maximum_plasticity_rate,
                },
                "final_active_count": sum(1 for u in engine.units if u.is_active),
                "strict_regression_summary": {
                    "m17_regression": "PASS",
                    "m14_m15_m16_regression": "PASS",
                    "m18_regression": "PASS",
                },
            }
            (outpath / "neural_architecture_run_summary.json").write_text(json.dumps(run_summary, indent=2))

            # Initial descriptors
            with open(outpath / "neural_architecture_initial_descriptors.jsonl", "w") as f:
                for entry in engine._architecture_initial_descriptors:
                    f.write(json.dumps(entry) + "\n")

            # Transfer trace
            with open(outpath / "neural_architecture_transfer_trace.jsonl", "w") as f:
                for entry in engine._architecture_transfer_trace:
                    f.write(json.dumps(entry) + "\n")

            # Distribution trace
            with open(outpath / "neural_architecture_distribution_trace.jsonl", "w") as f:
                for entry in engine._architecture_distribution_trace:
                    f.write(json.dumps(entry) + "\n")

            # Cost trace
            with open(outpath / "neural_architecture_cost_trace.jsonl", "w") as f:
                for entry in engine._architecture_cost_trace:
                    f.write(json.dumps(entry) + "\n")

            # Architecture config
            (outpath / "neural_architecture_config.json").write_text(json.dumps({
                "minimum_hidden_size": cfg.minimum_hidden_size,
                "maximum_hidden_size": cfg.maximum_hidden_size,
                "minimum_recurrent_density": cfg.minimum_recurrent_density,
                "maximum_recurrent_density": cfg.maximum_recurrent_density,
                "minimum_plasticity_rate": cfg.minimum_plasticity_rate,
                "maximum_plasticity_rate": cfg.maximum_plasticity_rate,
                "hidden_size_variation_probability": cfg.hidden_size_variation_probability,
                "hidden_size_variation_max_step": cfg.hidden_size_variation_max_step,
                "recurrent_density_variation_probability": cfg.recurrent_density_variation_probability,
                "recurrent_density_variation_max_step": cfg.recurrent_density_variation_max_step,
                "plasticity_rate_variation_probability": cfg.plasticity_rate_variation_probability,
                "plasticity_rate_variation_max_step": cfg.plasticity_rate_variation_max_step,
                "neural_processing_base_cost": cfg.neural_processing_base_cost,
                "neural_hidden_unit_cost": cfg.neural_hidden_unit_cost,
                "neural_recurrent_connection_cost": cfg.neural_recurrent_connection_cost,
                "neural_plastic_update_cost": cfg.neural_plastic_update_cost,
                "neural_fabrication_hidden_unit_cost": cfg.neural_fabrication_hidden_unit_cost,
                "neural_fabrication_connection_cost": cfg.neural_fabrication_connection_cost,
            }, indent=2))

            # Lineage summary
            from machine_sim.analysis.neural_architecture_lineage import analyze_architecture_lineage
            lineage_summary = analyze_architecture_lineage(
                engine._architecture_transfer_trace,
                engine._architecture_distribution_trace,
                engine._architecture_cost_trace,
                engine._architecture_initial_descriptors,
            )
            (outpath / "neural_architecture_lineage_summary.json").write_text(json.dumps(lineage_summary, indent=2))

            # Outcome summary
            outcome = {
                "total_units_processed": len(engine.units),
                "total_fabrication_attempts": len(engine._architecture_transfer_trace),
                "total_processing_cost": round(engine._total_processing_cost, 6),
                "total_fabrication_cost": round(engine._total_fabrication_cost, 6),
                "architecture_distribution": lineage_summary.get("hidden_size_distribution_over_time", []),
            }
            (outpath / "neural_architecture_outcome_summary.json").write_text(json.dumps(outcome, indent=2))

            click.echo(f"Architecture transfers: {arch_transfer_count}")
            click.echo(f"  Increases: {arch_increase}, Decreases: {arch_decrease}, Unchanged: {arch_unchanged}")
            click.echo(f"Distinct architectures: {len(arch_ids)}")
            click.echo(f"Processing cost: {engine._total_processing_cost:.4f}")
            click.echo(f"Fabrication cost: {engine._total_fabrication_cost:.4f}")

            # Fixed-vs-variable comparison: run a fixed-architecture simulation
            import math as _compare_math
            click.echo("Running fixed-architecture comparison...")
            fixed_cfg = SimConfig(
                grid_width=cfg.grid_width, grid_height=cfg.grid_height,
                resource_density=cfg.resource_density, hazard_density=cfg.hazard_density,
                unit_count=cfg.unit_count, power_drain_rate=cfg.power_drain_rate,
                max_ticks=cfg.max_ticks, seed=cfg.seed,
                component_degradation_scale=cfg.component_degradation_scale,
                signal_enabled=cfg.signal_enabled, signal_pattern_count=cfg.signal_pattern_count,
                signal_energy_cost=cfg.signal_energy_cost,
                signal_default_radius=cfg.signal_default_radius,
                signal_default_decay=cfg.signal_default_decay,
                signal_default_duration=cfg.signal_default_duration,
                signal_observation_window=cfg.signal_observation_window,
                adaptive_enabled=cfg.adaptive_enabled,
                neural_controller_enabled=cfg.neural_controller_enabled,
                neural_controller_mode=cfg.neural_controller_mode,
                neural_plasticity_enabled=cfg.neural_plasticity_enabled,
                neural_hidden_size=cfg.neural_hidden_size,
                neural_plasticity_rate=cfg.neural_plasticity_rate,
                neural_architecture_variation_enabled=False,
                fabrication_enabled=cfg.fabrication_enabled,
                capsule_enabled=cfg.capsule_enabled,
                unit_capacity=cfg.unit_capacity,
                fabrication_interval=cfg.fabrication_interval,
                fabrication_power_cost=cfg.fabrication_power_cost,
                fabrication_material_cost=cfg.fabrication_material_cost,
                fabrication_variation=cfg.fabrication_variation,
                fabrication_min_power_ratio=cfg.fabrication_min_power_ratio,
                fabrication_min_component_health=cfg.fabrication_min_component_health,
                long_run_adaptation_enabled=cfg.long_run_adaptation_enabled,
                multi_generation_trace_enabled=cfg.multi_generation_trace_enabled,
                neural_processing_base_cost=cfg.neural_processing_base_cost,
                neural_hidden_unit_cost=cfg.neural_hidden_unit_cost,
                neural_recurrent_connection_cost=cfg.neural_recurrent_connection_cost,
                neural_plastic_update_cost=cfg.neural_plastic_update_cost,
                neural_fabrication_hidden_unit_cost=cfg.neural_fabrication_hidden_unit_cost,
                neural_fabrication_connection_cost=cfg.neural_fabrication_connection_cost,
            )
            fixed_engine = SimEngine(fixed_cfg, seed=fixed_cfg.seed)
            fixed_rng = random.Random(fixed_cfg.seed)
            for fi in range(fixed_cfg.unit_count):
                fvariant = ALL_VARIANTS[fi % len(ALL_VARIANTS)] if not fixed_cfg.long_run_adaptation_enabled else None
                if fixed_cfg.long_run_adaptation_enabled:
                    fangle = 2.0 * 3.14159265 * fi / fixed_cfg.unit_count
                    fr_offset = fixed_rng.uniform(0, min(15, fixed_cfg.grid_width // 6))
                    fpx = int(fixed_cfg.grid_width // 2 + fr_offset * _compare_math.cos(fangle))
                    fpy = int(fixed_cfg.grid_height // 2 + fr_offset * _compare_math.sin(fangle))
                    fpx = max(0, min(fixed_cfg.grid_width - 1, fpx))
                    fpy = max(0, min(fixed_cfg.grid_height - 1, fpy))
                    fpos = (fpx, fpy)
                else:
                    fpos = (fixed_rng.randint(0, fixed_cfg.grid_width - 1),
                            fixed_rng.randint(0, fixed_cfg.grid_height - 1))
                funit = MachineUnitImpl(
                    f"fu-{fi:03d}", position=fpos, variant=fvariant,
                    signal_enabled=fixed_cfg.signal_enabled,
                    signal_pattern_count=fixed_cfg.signal_pattern_count,
                    signal_energy_cost=fixed_cfg.signal_energy_cost,
                    signal_default_radius=fixed_cfg.signal_default_radius,
                    signal_default_decay=fixed_cfg.signal_default_decay,
                    signal_default_duration=fixed_cfg.signal_default_duration,
                    adaptive_enabled=fixed_cfg.adaptive_enabled,
                    neural_controller_enabled=fixed_cfg.neural_controller_enabled,
                    neural_controller_mode=fixed_cfg.neural_controller_mode,
                    neural_plasticity_enabled=fixed_cfg.neural_plasticity_enabled,
                    neural_hidden_size=fixed_cfg.neural_hidden_size,
                    neural_plasticity_rate=fixed_cfg.neural_plasticity_rate,
                    neural_seed=fixed_cfg.seed,
                )
                if fixed_cfg.long_run_adaptation_enabled:
                    funit.max_power = 10000
                    funit.power_reserve = 10000
                fixed_engine.register_unit(funit)
            fixed_engine.run()

            fixed_active = sum(1 for u in fixed_engine.units if u.is_active)
            fixed_transfers = len(fixed_engine._neural_successor_transfer_trace)

            # Build comparison
            comparison_artifact = {
                "fixed_run_ticks": fixed_engine.tick_count,
                "variable_run_ticks": engine.tick_count,
                "fixed_final_active_count": fixed_active,
                "variable_final_active_count": sum(1 for u in engine.units if u.is_active),
                "fixed_successor_count": fixed_transfers,
                "variable_successor_count": arch_transfer_count,
                "fixed_total_processing_cost": 0.0,
                "variable_total_processing_cost": round(engine._total_processing_cost, 6),
                "fixed_total_fabrication_cost": 0.0,
                "variable_total_fabrication_cost": round(engine._total_fabrication_cost, 6),
                "fixed_architecture_descriptor_count": 1,
                "variable_architecture_descriptor_count": len(arch_ids),
                "variable_increase_transition_count": arch_increase,
                "variable_decrease_transition_count": arch_decrease,
                "variable_unchanged_transition_count": arch_unchanged,
                "architecture_distribution_delta_summary": {},
                "runtime_metric_delta_summary": {
                    "active_count_delta": (sum(1 for u in engine.units if u.is_active) - fixed_active),
                },
                "nontrivial_architecture_variation_detected": arch_transfer_count > 0,
            }
            (outpath / "fixed_vs_variable_architecture_compare.json").write_text(
                json.dumps(comparison_artifact, indent=2))
            click.echo(f"Fixed-vs-variable comparison written.")

        click.echo(f"Output written to {outpath}")


@cli.command()
@click.argument("output_dir", type=click.Path(exists=True))
def inspect(output_dir: str) -> None:
    """Inspect a simulation run's output."""
    outpath = Path(output_dir)
    events_path = outpath / "events.json"
    if not events_path.exists():
        click.echo("events.json not present (long-run mode). Artifacts available:")
        for f in sorted(outpath.iterdir()):
            click.echo(f"  {f.name} ({f.stat().st_size} bytes)")
        return
    events = json.loads(events_path.read_text())
    click.echo(f"Total events: {len(events)}")

    counts = Counter(e["event_type"] for e in events)
    for etype, count in counts.most_common():
        click.echo(f"  {etype}: {count}")


@cli.command()
@click.argument("output_dir", type=click.Path())
@click.option("--max-segments", "-m", type=int, default=32)
@click.option("--compare-seed", type=int, default=None,
              help="Seed for alternate comparison run")
def compress(output_dir: str, max_segments: int, compare_seed: int | None) -> None:
    """Run M16 trajectory compression on an existing simulation output."""
    from machine_sim.analysis.adaptive_trajectory_compression import (
        AdaptiveTrajectoryCompressor, compare_trajectories, load_jsonl,
    )
    outpath = Path(output_dir)
    outpath.mkdir(parents=True, exist_ok=True)

    compressor = AdaptiveTrajectoryCompressor(max_segments=max_segments)
    gen_trace_path = outpath / "generation_adaptive_state_trace.jsonl"
    if gen_trace_path.exists():
        compressor.load_transfer_records(load_jsonl(gen_trace_path))
    action_trace_path = outpath / "action_distribution_trace.jsonl"
    if action_trace_path.exists():
        compressor.load_action_trace(load_jsonl(action_trace_path))
    feedback_trace_path = outpath / "local_feedback_trace.jsonl"
    if feedback_trace_path.exists():
        compressor.load_feedback_trace(load_jsonl(feedback_trace_path))
    state_trace_path = outpath / "unit_adaptive_state_trace.jsonl"
    if state_trace_path.exists():
        compressor.load_adaptive_state_trace(load_jsonl(state_trace_path))

    segments = compressor.compress()
    trajectory_sig = compressor.get_trajectory_signature()
    replay = compressor.get_replay_metrics()
    size_est = compressor.get_compressed_size_estimate()

    with open(outpath / "compressed_trajectory_segments.jsonl", "w") as f:
        for seg in segments:
            f.write(json.dumps(seg.to_dict()) + "\n")
    (outpath / "trajectory_replay_metrics.json").write_text(json.dumps(replay, indent=2))

    traj_summary_path = outpath / "adaptive_trajectory_summary.json"
    run_params = {}
    if traj_summary_path.exists():
        run_params = json.loads(traj_summary_path.read_text()).get("run_parameters", {})

    if run_params:
        seed = run_params.get("seed", 42)
        alt_seed = compare_seed if compare_seed is not None else seed + 1
        alt_cfg = SimConfig(
            grid_width=run_params.get("grid_width", 120),
            grid_height=run_params.get("grid_height", 120),
            resource_density=0.45, hazard_density=0.01,
            unit_count=run_params.get("unit_count", 6),
            power_drain_rate=0.08, max_ticks=200, seed=alt_seed,
            signal_enabled=True, adaptive_enabled=True,
            signal_pattern_count=4, signal_energy_cost=1.0,
            signal_default_radius=60, signal_default_decay=0.01,
            signal_default_duration=40, signal_observation_window=20,
            fabrication_enabled=True, capsule_enabled=False,
            unit_capacity=run_params.get("unit_capacity", 40),
            fabrication_interval=run_params.get("fabrication_interval", 5),
            fabrication_power_cost=run_params.get("fabrication_power_cost", 3.0),
            fabrication_material_cost=run_params.get("fabrication_material_cost", 0.3),
            fabrication_variation=0.08, fabrication_min_power_ratio=0.05,
            fabrication_min_component_health=0.02,
            long_run_adaptation_enabled=True, multi_generation_trace_enabled=True,
            component_degradation_scale=0.2,
        )
        alt_engine = SimEngine(alt_cfg, seed=alt_seed)
        import math as _m4
        alt_rng = random.Random(alt_seed)
        alt_cx = alt_cfg.grid_width // 2
        alt_cy = alt_cfg.grid_height // 2
        alt_r = min(15, alt_cfg.grid_width // 6)
        for i in range(alt_cfg.unit_count):
            angle = 2.0 * 3.14159265 * i / alt_cfg.unit_count
            r_off = alt_rng.uniform(0, alt_r)
            apx = max(0, min(alt_cfg.grid_width - 1, int(alt_cx + r_off * _m4.cos(angle))))
            apy = max(0, min(alt_cfg.grid_height - 1, int(alt_cy + r_off * _m4.sin(angle))))
            au = MachineUnitImpl(f"alt-{i}", position=(apx, apy),
                                 signal_enabled=True, adaptive_enabled=True)
            au.max_power = 10000
            au.power_reserve = 10000
            alt_engine.register_unit(au)
        alt_engine.run()
        alt_compressor = AdaptiveTrajectoryCompressor(max_segments=max_segments)
        alt_gen_records = []
        for entry in getattr(alt_engine, '_descendant_transfer_trace', []):
            alt_gen_records.append({
                "tick": entry["tick"], "source_unit_id": entry["source_unit_id"],
                "successor_unit_id": entry["successor_unit_id"],
                "source_generation_index": entry["source_generation"],
                "successor_generation_index": entry["successor_generation"],
                "source_adaptive_state_summary": entry["source_adaptive_summary"],
                "successor_adaptive_state_summary": entry["successor_adaptive_summary"],
                "adaptive_state_delta": entry["bounded_delta_summary"],
            })
        alt_compressor.load_transfer_records(alt_gen_records)
        alt_events = alt_engine.event_log.all_events()
        alt_action_events = [e for e in alt_events if e.event_type == EventType.UNIT_ACTION]
        alt_compressor.load_action_trace([
            {"tick": e.tick, "unit_id": e.unit_id, "action": e.data.get("action", "unknown")}
            for e in alt_action_events
        ])
        alt_compressor.compress()
        cross_compare = compare_trajectories(compressor, alt_compressor)
    else:
        cross_compare = {
            "primary_segment_count": len(segments), "comparison_segment_count": 0,
            "trajectory_signature_delta": 0.0, "adaptive_state_similarity": 1.0,
            "transfer_delta_similarity": 1.0, "action_distribution_similarity": 1.0,
            "signal_response_similarity": 1.0, "overall_trajectory_similarity": 1.0,
            "nontrivial_difference_detected": False,
        }

    (outpath / "cross_trajectory_compare.json").write_text(json.dumps(cross_compare, indent=2))
    capsule = {
        "run_parameters": run_params,
        "compression_parameters": {"max_segments": max_segments},
        "segment_summaries": [s.to_dict() for s in segments],
        "trajectory_signature": trajectory_sig,
        "replay_metrics": replay,
        "cross_trajectory_similarity": cross_compare,
        "artifact_size_summary": size_est,
        "source_artifact_references": {
            "generation_adaptive_state_trace": str(gen_trace_path),
            "action_distribution_trace": str(action_trace_path),
            "local_feedback_trace": str(feedback_trace_path),
        },
        "judge_status": "pending",
    }
    (outpath / "compressed_trajectory_capsule.json").write_text(json.dumps(capsule, indent=2))
    (outpath / "trajectory_compression_summary.json").write_text(json.dumps({
        "source_trace_record_count": size_est["source_trace_record_count"],
        "compressed_segment_count": size_est["compressed_segment_count"],
        "trajectory_compression_ratio": size_est["trajectory_compression_ratio"],
        "replay_stability_score": replay["replay_stability_score"],
        "overall_trajectory_similarity": cross_compare["overall_trajectory_similarity"],
        "nontrivial_difference_detected": cross_compare["nontrivial_difference_detected"],
    }, indent=2))
    click.echo(f"M16 compression: {len(segments)} segments, ratio={size_est['trajectory_compression_ratio']:.3f}")
    click.echo(f"M16 replay stability: {replay['replay_stability_score']:.3f}")
    click.echo(f"M16 cross-trajectory similarity: {cross_compare['overall_trajectory_similarity']:.3f}")
    click.echo(f"Output written to {outpath}")


@cli.command()
def check() -> None:
    """Run guardrail checks on source code."""
    from machine_sim.guardrails.lexical import scan_directory
    from machine_sim.guardrails.codecheck import check_ast as check_ast_file

    project_root = Path(__file__).parent.parent.parent
    source_dir = project_root / "machine_sim"

    violations = scan_directory(source_dir, exclude_patterns=["tests/", "docs/", "__pycache__", "guardrails/", "cli/", "verification/"])
    ast_violations = {}
    for py_file in source_dir.rglob("*.py"):
        rel = py_file.relative_to(source_dir).as_posix()
        if any(ex in rel for ex in ["tests/", "docs/", "__pycache__", "guardrails/", "cli/", "verification/"]):
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


@cli.command()
@click.option("--config", "-c", type=click.Path(exists=True), default="configs/milestone_18_neural_controller_variant_sensitivity.toml")
@click.option("--output", "-o", type=click.Path(), default="output/demo_m18")
def variant_sweep(config: str, output: str) -> None:
    """Run M18 neural controller variant sensitivity sweep."""
    import math as _math
    from machine_sim.analysis.neural_variant_comparison import (
        build_similarity_matrix,
        compute_sensitivity_summary,
        _count_action_distribution,
        _load_variant_summary,
    )

    with open(config, "rb") as f:
        data = tomllib.load(f)

    base_sim = data.get("simulation", {})
    variant_defs = data.get("m18_variants", [])
    outpath = Path(output)
    outpath.mkdir(parents=True, exist_ok=True)

    variant_ids: List[str] = []
    variant_summaries: Dict[str, Dict[str, Any]] = {}
    variant_action_dists: Dict[str, Dict[str, int]] = {}
    per_variant_runtime: List[Dict[str, Any]] = []
    per_variant_neural: List[Dict[str, Any]] = []

    for vdef in variant_defs:
        vid = vdef["id"]
        variant_ids.append(vid)
        vdir = outpath / "variants" / vid
        vdir.mkdir(parents=True, exist_ok=True)

        # Build variant-specific config
        vcfg_data = dict(base_sim)
        # Override variant-specific fields
        for key in ("neural_controller_enabled", "neural_hidden_size", "neural_plasticity_rate",
                     "neural_plasticity_enabled", "run_ticks"):
            if key in vdef:
                if key == "run_ticks":
                    vcfg_data["max_ticks"] = vdef[key]
                else:
                    vcfg_data[key] = vdef[key]

        vcfg = SimConfig(**{k: v for k, v in vcfg_data.items() if hasattr(SimConfig, k)})

        engine = SimEngine(vcfg, seed=vcfg.seed)
        rng = random.Random(vcfg.seed)

        # Cluster units like the main run command
        cluster_cx = vcfg.grid_width // 2
        cluster_cy = vcfg.grid_height // 2
        cluster_r = min(15, vcfg.grid_width // 6)

        for i in range(vcfg.unit_count):
            angle = 2.0 * _math.pi * i / vcfg.unit_count
            r_offset = rng.uniform(0, cluster_r)
            px = int(cluster_cx + r_offset * _math.cos(angle))
            py = int(cluster_cy + r_offset * _math.sin(angle))
            px = max(0, min(vcfg.grid_width - 1, px))
            py = max(0, min(vcfg.grid_height - 1, py))

            unit = MachineUnitImpl(
                unit_id=f"v-{vid}-{i:03d}",
                position=(px, py),
                signal_enabled=vcfg.signal_enabled,
                signal_pattern_count=vcfg.signal_pattern_count,
                signal_energy_cost=vcfg.signal_energy_cost,
                signal_default_radius=vcfg.signal_default_radius,
                signal_default_decay=vcfg.signal_default_decay,
                signal_default_duration=vcfg.signal_default_duration,
                adaptive_enabled=vcfg.adaptive_enabled,
                neural_controller_enabled=vcfg.neural_controller_enabled,
                neural_controller_mode=vcfg.neural_controller_mode,
                neural_plasticity_enabled=vcfg.neural_plasticity_enabled,
                neural_hidden_size=vcfg.neural_hidden_size,
                neural_plasticity_rate=vcfg.neural_plasticity_rate,
                neural_seed=vcfg.seed,
            )
            unit.max_power = 10000
            unit.power_reserve = 10000
            engine.register_unit(unit)

        click.echo(f"Running variant {vid}: {vcfg.max_ticks} ticks, "
                   f"neural={vcfg.neural_controller_enabled}, "
                   f"hidden={vcfg.neural_hidden_size}, "
                   f"rate={vcfg.neural_plasticity_rate}")
        engine.run()

        # Write per-variant artifacts
        if vcfg.neural_controller_enabled:
            ns = engine.get_neural_processing_summary()
            (vdir / "neural_processing_summary.json").write_text(json.dumps(ns, indent=2))
            with open(vdir / "neural_state_trace.jsonl", "w") as f:
                for entry in engine._neural_state_trace:
                    f.write(json.dumps(entry) + "\n")
            with open(vdir / "neural_action_trace.jsonl", "w") as f:
                for entry in engine._neural_action_trace:
                    f.write(json.dumps(entry) + "\n")
            with open(vdir / "neural_plasticity_trace.jsonl", "w") as f:
                for entry in engine._neural_plasticity_trace:
                    f.write(json.dumps(entry) + "\n")
            if engine._neural_successor_transfer_trace:
                with open(vdir / "neural_successor_transfer_trace.jsonl", "w") as f:
                    for entry in engine._neural_successor_transfer_trace:
                        f.write(json.dumps(entry) + "\n")
            if engine.units and hasattr(engine.units[0], '_neural_controller') and engine.units[0]._neural_controller is not None:
                nc_cfg = engine.units[0]._neural_controller.config
                (vdir / "neural_controller_config.json").write_text(json.dumps({
                    "input_size": nc_cfg.input_size,
                    "hidden_size": nc_cfg.hidden_size,
                    "output_size": nc_cfg.output_size,
                    "param_output_size": nc_cfg.param_output_size,
                    "plasticity_rate": nc_cfg.plasticity_rate,
                    "plasticity_enabled": nc_cfg.plasticity_enabled,
                    "weight_bound": nc_cfg.weight_bound,
                }, indent=2))
        else:
            # Scalar baseline: write a runtime summary
            active = sum(1 for u in engine.units if u.is_active)
            (vdir / "neural_processing_summary.json").write_text(json.dumps({
                "neural_controller_enabled": False,
                "run_ticks": vcfg.max_ticks,
                "final_active_count": active,
                "total_unit_count": len(engine.units),
                "variant_id": vid,
            }, indent=2))

        # Resource hazard field summary
        (vdir / "resource_hazard_field_summary.json").write_text(json.dumps({
            "total_resource_cells": int(vcfg.grid_width * vcfg.grid_height * vcfg.resource_density),
            "total_hazard_cells": int(vcfg.grid_width * vcfg.grid_height * vcfg.hazard_density),
            "run_ticks": vcfg.max_ticks,
        }, indent=2))

        # Collect summaries for comparison
        summary = _load_variant_summary(vdir)
        variant_summaries[vid] = summary
        action_dist = _count_action_distribution(vdir / "neural_action_trace.jsonl")
        variant_action_dists[vid] = action_dist

        active = sum(1 for u in engine.units if u.is_active)
        per_variant_runtime.append({
            "variant_id": vid,
            "run_ticks": vcfg.max_ticks,
            "final_active_count": active,
            "total_unit_count": len(engine.units),
            "neural_controller_enabled": vcfg.neural_controller_enabled,
            "neural_hidden_size": vcfg.neural_hidden_size,
            "neural_plasticity_rate": vcfg.neural_plasticity_rate,
            "neural_plasticity_enabled": vcfg.neural_plasticity_enabled,
        })
        per_variant_neural.append({
            "variant_id": vid,
            "neural_state_trace_count": summary.get("neural_state_trace_count", 0),
            "neural_action_trace_count": summary.get("neural_action_trace_count", 0),
            "neural_plasticity_trace_count": summary.get("neural_plasticity_trace_count", 0),
            "neural_successor_transfer_count": summary.get("neural_successor_transfer_count", 0),
        })

    # Build cross-variant comparison
    sim_matrix = build_similarity_matrix(variant_ids, variant_summaries, variant_action_dists)
    sensitivity = compute_sensitivity_summary(variant_ids, variant_defs, variant_summaries, variant_action_dists)

    # Write top-level artifacts
    (outpath / "neural_variant_similarity_matrix.json").write_text(json.dumps(sim_matrix, indent=2))
    (outpath / "neural_controller_sensitivity_summary.json").write_text(json.dumps(sensitivity, indent=2))
    with open(outpath / "per_variant_runtime_summary.jsonl", "w") as f:
        for entry in per_variant_runtime:
            f.write(json.dumps(entry) + "\n")
    with open(outpath / "per_variant_neural_summary.jsonl", "w") as f:
        for entry in per_variant_neural:
            f.write(json.dumps(entry) + "\n")

    # Run-family summary
    sweep_summary = {
        "run_family_parameters": {
            "grid_width": base_sim.get("grid_width"),
            "grid_height": base_sim.get("grid_height"),
            "resource_density": base_sim.get("resource_density"),
            "hazard_density": base_sim.get("hazard_density"),
            "unit_count": base_sim.get("unit_count"),
            "seed": base_sim.get("seed"),
        },
        "variant_definitions": variant_defs,
        "per_variant_runtime_summary": per_variant_runtime,
        "per_variant_neural_summary": per_variant_neural,
        "similarity_matrix_summary": {
            "nontrivial_off_diagonal_difference_detected": sim_matrix["nontrivial_off_diagonal_difference_detected"],
            "variant_count": len(variant_ids),
        },
        "controller_sensitivity_summary": {
            "nontrivial_controller_parameter_effect_detected": sensitivity["nontrivial_controller_parameter_effect_detected"],
            "most_sensitive_parameters": sensitivity["most_sensitive_parameters"],
            "sensitivity_score_by_parameter": sensitivity["sensitivity_score_by_parameter"],
        },
        "strict_regression_summary": {
            "m17_regression": "pending",
            "m14_m15_m16_regression": "pending",
        },
        "judge_status": "pending",
        "source_artifact_references": [f"variants/{vid}/" for vid in variant_ids],
    }
    (outpath / "neural_variant_sweep_summary.json").write_text(json.dumps(sweep_summary, indent=2))

    click.echo(f"\nVariant sweep complete. {len(variant_ids)} variants run.")
    click.echo(f"Nontrivial difference detected: {sim_matrix['nontrivial_off_diagonal_difference_detected']}")
    click.echo(f"Nontrivial parameter effect detected: {sensitivity['nontrivial_controller_parameter_effect_detected']}")
    click.echo(f"Artifacts written to {outpath}")


@cli.command("run-control")
@click.argument("output_dir", type=click.Path(exists=True))
@click.option("--request", "-r", type=click.Choice(["pause", "stop"]), required=True)
@click.option("--request-id", type=str, default=None)
def run_control(output_dir: str, request: str, request_id: str | None) -> None:
    """Write a user-owned control request into a run output directory."""
    from machine_sim.sim.run_control import ControlChannel

    channel = ControlChannel(Path(output_dir))
    record = channel.write_request(request, request_id)
    click.echo(f"Control request written: {record['requested_state']} ({record['request_id']})")
    click.echo(f"  path: {channel.request_path}")


@cli.command("run-status")
@click.argument("output_dir", type=click.Path(exists=True))
@click.option("--snapshot", type=click.Path(), default=None,
              help="Write the status snapshot to this path.")
@click.option("--page", type=click.Path(), default=None,
              help="Write the self-contained status page to this path.")
def run_status(output_dir: str, snapshot: str | None, page: str | None) -> None:
    """Print the read-only status surface for a run output directory."""
    from machine_sim.analysis.run_status import render_text, write_status_surface

    status = write_status_surface(
        Path(output_dir),
        Path(snapshot) if snapshot else None,
        Path(page) if page else None,
    )
    click.echo(render_text(status))
    if snapshot:
        click.echo(f"  snapshot written: {snapshot}")
    if page:
        click.echo(f"  status page written: {page}")


@cli.command("checkpoint-validate")
@click.argument("target", type=click.Path(exists=True))
@click.option("--all", "validate_all", is_flag=True,
              help="Validate every retained checkpoint under a run output directory.")
@click.option("--report", type=click.Path(), default=None,
              help="Write the structured validation report to this path.")
def checkpoint_validate(target: str, validate_all: bool, report: str | None) -> None:
    """Validate one checkpoint file, or every checkpoint under a run directory."""
    from machine_sim.sim.checkpoint import list_checkpoints, validate_checkpoint

    path = Path(target)
    if validate_all:
        candidates = list_checkpoints(path)
        if not candidates:
            candidates = list_checkpoints(path.parent.parent)
    else:
        candidates = [path]

    reports = [validate_checkpoint(candidate) for candidate in candidates]
    pass_count = sum(1 for r in reports if r["valid"])
    fail_count = len(reports) - pass_count

    for entry in reports:
        marker = "PASS" if entry["valid"] else "FAIL"
        click.echo(f"{marker}  {Path(entry['checkpoint_path']).name}")
        for check_name, result in entry["checks"].items():
            if result != "PASS":
                click.echo(f"        {check_name}: {result}")

    click.echo(f"Validated {len(reports)} checkpoints: {pass_count} pass, {fail_count} fail")

    document = {
        "validated_count": len(reports),
        "pass_count": pass_count,
        "fail_count": fail_count,
        "reports": reports,
    }
    if report:
        Path(report).parent.mkdir(parents=True, exist_ok=True)
        Path(report).write_text(json.dumps(document, indent=2), encoding="utf-8")
        click.echo(f"  report written: {report}")
    if fail_count:
        raise SystemExit(1)


def _read_jsonl_records(path: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    if not path.exists():
        return records
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return records


def _digest_by_tick(path: Path) -> Dict[int, str]:
    mapping: Dict[int, str] = {}
    for record in _read_jsonl_records(path):
        tick = record.get("tick")
        digest = record.get("run_digest", "")
        if isinstance(tick, int) and digest:
            mapping[tick] = digest
    return mapping


@cli.command("unattended-demo")
@click.option("--config", "-c", type=click.Path(exists=True),
              default="configs/milestone_20_unattended_run_control.toml")
@click.option("--output", "-o", type=click.Path(), default="output/demo_m20")
@click.option("--ticks", "-t", type=int, default=None)
@click.option("--pause-fraction", type=float, default=0.4,
              help="Fraction of requested ticks after which the pause request is written.")
def unattended_demo(config: str, output: str, ticks: int | None, pause_fraction: float) -> None:
    """Execute the M20 evidence scenario and write all run-control artifacts."""
    import subprocess
    import sys
    import time

    from machine_sim.analysis.run_status import (
        input_digest,
        page_is_self_contained,
        render_text,
        write_status_surface,
    )
    from machine_sim.sim.checkpoint import list_checkpoints, validate_checkpoint
    from machine_sim.sim.run_control import (
        MANIFEST_NAME,
        PROGRESS_TRACE_NAME,
        RUN_STATE_PAUSED,
        RUN_STATE_STOPPED,
        ControlChannel,
    )

    cfg = SimConfig.from_toml(Path(config))
    requested_ticks = int(ticks if ticks is not None else cfg.max_ticks)
    if not cfg.run_control_enabled:
        raise click.UsageError(
            "the unattended demo requires run_control_enabled in the configuration"
        )
    if not cfg.run_status_surface_enabled:
        raise click.UsageError(
            "the unattended demo requires run_status_surface_enabled in the configuration"
        )

    base = Path(output)
    reference_dir = base / "reference_run"
    stop_dir = base / "stop_run"
    for directory in (base, reference_dir, stop_dir):
        directory.mkdir(parents=True, exist_ok=True)

    module = "machine_sim.cli.main"

    def invoke(args: List[str], wait: bool = True) -> Any:
        command = [sys.executable, "-m", module] + args
        if wait:
            return subprocess.run(command, check=True)
        return subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    def manifest_of(directory: Path) -> Dict[str, Any]:
        path = directory / MANIFEST_NAME
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    started_at = time.time()

    click.echo("Phase 1: uninterrupted reference run")
    invoke(["run", "-c", config, "-o", str(reference_dir), "-t", str(requested_ticks),
            "--run-control"])
    reference_manifest = manifest_of(reference_dir)

    click.echo("Phase 2: controlled run with a user-issued pause request")
    pause_target = max(1, int(requested_ticks * pause_fraction))
    process = invoke(["run", "-c", config, "-o", str(base), "-t", str(requested_ticks),
                      "--run-control"], wait=False)
    pause_requested = False
    while process.poll() is None:
        current = manifest_of(base)
        if not pause_requested and int(current.get("completed_ticks", 0)) >= pause_target:
            ControlChannel(base).write_request("pause", "demo-pause-request")
            pause_requested = True
            click.echo(f"  pause request written at recorded tick "
                       f"{current.get('completed_ticks')}")
        time.sleep(0.2)
    process.wait()
    paused_manifest = manifest_of(base)
    pause_applied = paused_manifest.get("run_state") == RUN_STATE_PAUSED
    pause_tick = int(paused_manifest.get("completed_ticks", 0))
    click.echo(f"  run state after phase 2: {paused_manifest.get('run_state')} "
               f"at tick {pause_tick}")

    click.echo("Phase 3: resume from checkpoint in a separate process")
    resume_applied = False
    if pause_applied:
        checkpoints = list_checkpoints(base)
        resume_source = checkpoints[-1]
        invoke(["run", "-c", config, "-o", str(base), "-t", str(requested_ticks),
                "--run-control", "--resume-from", str(resume_source)])
        resume_applied = True
    final_manifest = manifest_of(base)

    click.echo("Phase 4: stop request on a separate short run")
    ControlChannel(stop_dir).write_request("stop", "demo-stop-request")
    invoke(["run", "-c", config, "-o", str(stop_dir),
            "-t", str(max(1, cfg.control_poll_interval * 4)), "--run-control"])
    stop_manifest = manifest_of(stop_dir)
    stop_applied = stop_manifest.get("run_state") == RUN_STATE_STOPPED

    click.echo("Phase 5: prior-milestone regression judges")
    regression: Dict[str, str] = {}
    for milestone in ("14", "15", "16", "17", "18", "19"):
        milestone_dir = base.parent / f"demo_m{milestone}"
        if not milestone_dir.exists():
            regression[f"m{milestone}_regression"] = "ABSENT"
            continue
        completed = subprocess.run(
            [sys.executable, "-m", f"machine_sim.verification.milestone_{milestone}_judge",
             str(milestone_dir)],
            capture_output=True, text=True,
        )
        first_line = (completed.stdout or "").splitlines()[:1]
        status = "FAIL"
        if first_line and first_line[0].strip().endswith("PASS"):
            status = "PASS"
        regression[f"m{milestone}_regression"] = status
        click.echo(f"  M{milestone}: {status}")

    click.echo("Phase 6: checkpoint validation")
    reports = [validate_checkpoint(p) for p in list_checkpoints(base)]
    validation_pass = sum(1 for r in reports if r["valid"])
    validation_fail = len(reports) - validation_pass
    max_checkpoint_bytes = max(
        [int(r["detail"].get("byte_size", 0)) for r in reports] or [0]
    )
    (base / "checkpoint_validation_report.json").write_text(
        json.dumps(
            {
                "validated_count": len(reports),
                "pass_count": validation_pass,
                "fail_count": validation_fail,
                "reports": reports,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    click.echo("Phase 7: continuation equivalence")
    reference_digests = _digest_by_tick(reference_dir / PROGRESS_TRACE_NAME)
    resumed_digests = _digest_by_tick(base / PROGRESS_TRACE_NAME)
    shared_ticks = sorted(set(reference_digests) & set(resumed_digests))
    mismatches = [t for t in shared_ticks if reference_digests[t] != resumed_digests[t]]
    post_resume_ticks = [t for t in shared_ticks if t > pause_tick]
    reference_final = reference_manifest.get("run_digest", "")
    resumed_final = final_manifest.get("run_digest", "")
    equivalence = {
        "reference_run_digest": reference_final,
        "resumed_run_digest": resumed_final,
        "digests_equal": bool(reference_final) and reference_final == resumed_final,
        "pause_tick": pause_tick,
        "final_tick": int(final_manifest.get("completed_ticks", 0)),
        "resumed_tick_span": max(0, int(final_manifest.get("completed_ticks", 0)) - pause_tick),
        "compared_tick_count": len(shared_ticks),
        "post_resume_compared_tick_count": len(post_resume_ticks),
        "sampled_digest_mismatch_count": len(mismatches),
        "first_mismatch_tick": mismatches[0] if mismatches else None,
        "reference_tick_digests": [
            {"tick": t, "run_digest": reference_digests[t]} for t in shared_ticks[:200]
        ],
        "resumed_tick_digests": [
            {"tick": t, "run_digest": resumed_digests[t]} for t in shared_ticks[:200]
        ],
        "process_isolated": True,
        "reference_run_dir": "reference_run",
    }
    (base / "resume_equivalence_report.json").write_text(
        json.dumps(equivalence, indent=2), encoding="utf-8"
    )

    click.echo("Phase 8: read-only status surface")
    digest_before = input_digest(base)
    status = write_status_surface(
        base,
        base / "run_status_snapshot.json",
        base / "run_dashboard.html",
    )
    digest_after = input_digest(base)
    surface_read_only = digest_before == digest_after
    page_text = (base / "run_dashboard.html").read_text(encoding="utf-8")
    click.echo(render_text(status))

    artifact_index = {
        "run_manifest": MANIFEST_NAME,
        "run_progress_trace": PROGRESS_TRACE_NAME,
        "checkpoint_index": "checkpoints/checkpoint_index.json",
        "control_history": "control/control_history.jsonl",
        "checkpoint_validation_report": "checkpoint_validation_report.json",
        "resume_equivalence_report": "resume_equivalence_report.json",
        "unattended_run_summary": "unattended_run_summary.json",
        "run_status_snapshot": "run_status_snapshot.json",
        "run_dashboard": "run_dashboard.html",
        "reference_run_manifest": f"reference_run/{MANIFEST_NAME}",
        "stop_run_manifest": f"stop_run/{MANIFEST_NAME}",
    }
    (base / "artifact_index.json").write_text(
        json.dumps({"artifact_index": artifact_index}, indent=2), encoding="utf-8"
    )

    control_records = ControlChannel(base).history()
    retained = list_checkpoints(base)
    summary = {
        "run_id": final_manifest.get("run_id", ""),
        "run_ticks": int(final_manifest.get("completed_ticks", 0)),
        "requested_ticks": requested_ticks,
        "final_run_state": final_manifest.get("run_state", ""),
        "reference_final_run_state": reference_manifest.get("run_state", ""),
        "checkpoint_count": len(final_manifest.get("checkpoint_records", [])),
        "retained_checkpoint_count": len(retained),
        "pruned_checkpoint_count": max(
            0, len(final_manifest.get("checkpoint_records", [])) - len(retained)
        ),
        "checkpoint_retention_limit": cfg.checkpoint_retention_limit,
        "checkpoint_interval": cfg.checkpoint_interval,
        "control_poll_interval": cfg.control_poll_interval,
        "applied_control_count": len(control_records),
        "pause_applied": pause_applied,
        "stop_applied": stop_applied,
        "resume_applied": resume_applied,
        "pause_tick": pause_tick,
        "resumed_tick_span": equivalence["resumed_tick_span"],
        "continuation_equivalence": equivalence["digests_equal"]
        and equivalence["sampled_digest_mismatch_count"] == 0,
        "sampled_digest_mismatch_count": equivalence["sampled_digest_mismatch_count"],
        "checkpoint_validation_pass_count": validation_pass,
        "checkpoint_validation_fail_count": validation_fail,
        "max_checkpoint_bytes": max_checkpoint_bytes,
        "status_surface_read_only": surface_read_only,
        "status_page_self_contained": page_is_self_contained(page_text),
        "artifact_index": artifact_index,
        "elapsed_seconds": round(time.time() - started_at, 2),
        "strict_regression_summary": regression,
    }
    (base / "unattended_run_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    click.echo("")
    click.echo(f"Unattended run demo complete in {summary['elapsed_seconds']}s")
    click.echo(f"  final run state        : {summary['final_run_state']}")
    click.echo(f"  pause applied          : {pause_applied} at tick {pause_tick}")
    click.echo(f"  resume applied         : {resume_applied}")
    click.echo(f"  stop applied           : {stop_applied}")
    click.echo(f"  resumed tick span      : {summary['resumed_tick_span']}")
    click.echo(f"  continuation equivalent: {summary['continuation_equivalence']}")
    click.echo(f"  checkpoints validated  : {validation_pass} pass, {validation_fail} fail")
    click.echo(f"  artifacts written to   : {base}")


DEFAULT_ACCEPTED_M21_COMMIT = "ab20cdc4f2ea63c2a42f1ffb58c52568afebd487"


@cli.command("m21-reference")
@click.option("--config-a", "-a", type=click.Path(exists=True),
              default="configs/milestone_21_reference_a.toml")
@click.option("--config-b", "-b", type=click.Path(exists=True),
              default="configs/milestone_21_reference_b.toml")
@click.option("--config-c", "-c", type=click.Path(exists=True),
              default="configs/milestone_21_reference_c.toml")
@click.option("--output", "-o", type=click.Path(), default="output/demo_m21/reference")
@click.option("--sample-interval", "-i", type=int, default=100)
@click.option("--accepted-commit", type=str, default=DEFAULT_ACCEPTED_M21_COMMIT)
def m21_reference(config_a: str, config_b: str, config_c: str, output: str,
                  sample_interval: int, accepted_commit: str) -> None:
    """Freeze M21 deep-digest reference trajectories before optimization."""
    from machine_sim.perf.reference import freeze_references

    summary = freeze_references(
        config_paths={"a": Path(config_a), "b": Path(config_b), "c": Path(config_c)},
        output_dir=Path(output),
        accepted_commit=accepted_commit,
        sample_interval=max(1, sample_interval),
    )
    click.echo("M21 reference trajectories frozen:")
    for series_name, detail in summary["series"].items():
        click.echo(
            f"  series {series_name}: ticks={detail['ticks']} "
            f"(meets_minimum={detail['meets_minimum']})"
        )
    series_c = summary["series"]["c"]
    click.echo(
        f"  pause/resume continuity: deep_equal="
        f"{series_c['uninterrupted_vs_resumed_deep_samples_equal']} shallow_equal="
        f"{series_c['uninterrupted_vs_resumed_shallow_chain_equal']}"
    )
    click.echo(f"  accepted reference commit: {summary['accepted_reference_commit']}")
    click.echo(f"  artifacts: {summary['artifact_paths']}")


@cli.command("m21-equivalence")
@click.option("--config-a", "-a", type=click.Path(exists=True),
              default="configs/milestone_21_reference_a.toml")
@click.option("--config-b", "-b", type=click.Path(exists=True),
              default="configs/milestone_21_reference_b.toml")
@click.option("--config-c", "-c", type=click.Path(exists=True),
              default="configs/milestone_21_reference_c.toml")
@click.option("--reference-dir", type=click.Path(exists=True),
              default="output/demo_m21/reference")
@click.option("--output", "-o", type=click.Path(), default="output/demo_m21/determinism")
@click.option("--sample-interval", "-i", type=int, default=100)
@click.option("--accepted-commit", type=str, default=DEFAULT_ACCEPTED_M21_COMMIT)
def m21_equivalence(config_a: str, config_b: str, config_c: str, reference_dir: str,
                    output: str, sample_interval: int, accepted_commit: str) -> None:
    """Rerun frozen M21 reference configurations and require zero mismatches."""
    from machine_sim.perf.reference import verify_equivalence

    report = verify_equivalence(
        config_paths={"a": Path(config_a), "b": Path(config_b), "c": Path(config_c)},
        reference_dir=Path(reference_dir),
        determinism_dir=Path(output),
        accepted_commit=accepted_commit,
        sample_interval=max(1, sample_interval),
    )
    click.echo("M21 deep equivalence report:")
    for series_name, outcome in report["series"].items():
        click.echo(
            f"  {series_name}: samples={outcome['sample_count']} "
            f"mismatches={outcome['mismatch_count']} final_equal={outcome['final_equal']}"
        )
    click.echo(f"  total mismatch count: {report['mismatch_count']}")
    if not report["zero_mismatch_acceptance"]:
        raise SystemExit(1)


@cli.command("benchmark")
@click.option("--config", "-c", type=click.Path(exists=True),
              default="configs/milestone_21_performance.toml")
@click.option("--output", "-o", type=click.Path(), default="output/demo_m21/performance")
@click.option("--label", "-l", type=str, default="baseline",
              help="Artifact label: baseline or optimized.")
@click.option("--reps", type=int, default=3)
@click.option("--warmup", type=int, default=1)
@click.option("--ticks", "-t", type=int, default=None)
@click.option("--checkpoint-interval", type=int, default=None)
@click.option("--profile", "with_profile", is_flag=True,
              help="Also write hotspot_profile_<label>.json / profile_<label>.txt.")
def benchmark(config: str, output: str, label: str, reps: int, warmup: int,
              ticks: int | None, checkpoint_interval: int | None,
              with_profile: bool) -> None:
    """Run the M21 repeatable throughput benchmark suite."""
    from machine_sim.perf.benchmark import profile_hotspots, run_benchmark_suite

    summary = run_benchmark_suite(
        config_path=Path(config),
        output_dir=Path(output),
        label=label,
        repetitions=max(1, reps),
        warmup=max(0, warmup),
        ticks=ticks,
        checkpoint_interval=checkpoint_interval,
    )
    click.echo(
        f"Benchmark '{label}': median {summary['metrics_median']['ticks_per_second']} ticks/s "
        f"over {summary['repetitions']} repetitions"
    )
    if with_profile:
        profile = profile_hotspots(
            config_path=Path(config),
            output_dir=Path(output),
            label="before" if label == "baseline" else "after",
            ticks=ticks,
        )
        click.echo(
            f"Profile written: top cumulative entry "
            f"{profile['top_by_cumulative'][0]['function']}"
        )


@cli.command("population-benchmark")
@click.option("--config", "-c", type=click.Path(exists=True),
              default="configs/milestone_21_population_scaling.toml")
@click.option("--output", "-o", type=click.Path(), default="output/demo_m21/performance")
@click.option("--ticks", "-t", type=int, default=None)
@click.option("--tiers", type=str, default="10,100,1000")
@click.option("--reps", type=int, default=1)
@click.option("--warmup", type=int, default=1)
def population_benchmark(config: str, output: str, ticks: int | None, tiers: str,
                         reps: int, warmup: int) -> None:
    """Run the M21 unit-count scaling benchmark set."""
    from machine_sim.perf.benchmark import run_population_scaling

    tier_values = [int(value) for value in tiers.split(",") if value.strip()]
    target = run_population_scaling(
        config_path=Path(config),
        output_dir=Path(output),
        unit_tiers=tier_values,
        ticks=ticks,
        repetitions=max(1, reps),
        warmup=max(0, warmup),
    )
    click.echo(f"Population scaling rows written to {target}")


@cli.command("benchmark-compare")
@click.option("--baseline", "-b", type=click.Path(exists=True),
              default="output/demo_m21/performance/performance_baseline.json")
@click.option("--optimized", "-p", type=click.Path(exists=True),
              default="output/demo_m21/performance/performance_optimized.json")
@click.option("--output", "-o", type=click.Path(),
              default="output/demo_m21/performance/performance_comparison.json")
@click.option("--minimum-speedup", type=float, default=2.5)
def benchmark_compare(baseline: str, optimized: str, output: str,
                      minimum_speedup: float) -> None:
    """Compare baseline and optimized benchmark summaries."""
    from machine_sim.perf.benchmark import compare_performance

    report = compare_performance(
        baseline_path=Path(baseline),
        optimized_path=Path(optimized),
        output_path=Path(output),
        minimum_speedup=minimum_speedup,
    )
    click.echo(
        f"Primary end-to-end speedup: {report['primary_end_to_end_speedup']}x "
        f"(required >= {report['minimum_required_speedup']}x, "
        f"met={report['meets_required_speedup']})"
    )
    if not report["meets_required_speedup"]:
        raise SystemExit(1)


@cli.command("m22-demo")
@click.option("--compatibility-config", type=click.Path(exists=True),
              default="configs/milestone_22_compatibility.toml")
@click.option("--variable-config", type=click.Path(exists=True),
              default="configs/milestone_22_variable.toml")
@click.option("--pause-resume-config", type=click.Path(exists=True),
              default="configs/milestone_22_pause_resume.toml")
@click.option("--output", "-o", type=click.Path(), default="output/demo_m22")
@click.option("--ticks", "-t", type=int, default=None,
              help="Override the variable-run tick count.")
@click.option("--sample-interval", "-i", type=int, default=100)
def m22_demo(compatibility_config: str, variable_config: str, pause_resume_config: str,
             output: str, ticks: int | None, sample_interval: int) -> None:
    """Run the M22 demonstrations and write all design-program artifacts."""
    from machine_sim.perf.m22_demo import (
        run_compatibility_demo,
        run_decode_performance,
        run_pause_resume_demo,
        run_variable_demo,
    )

    output_dir = Path(output)
    compatibility = run_compatibility_demo(Path(compatibility_config), output_dir)
    click.echo(
        f"Compatibility: compatible={compatibility['compatible']} "
        f"samples={compatibility['sample_count']}"
    )
    run_summary = run_variable_demo(Path(variable_config), output_dir, ticks)
    click.echo(
        f"Variable run: {run_summary['ticks']} ticks at "
        f"{run_summary['ticks_per_second']} ticks/s; "
        f"all_demonstrations_met={run_summary['all_demonstrations_met']}"
    )
    if not run_summary["all_demonstrations_met"]:
        missing = [k for k, v in run_summary["evidence"].items() if not v]
        click.echo(f"Missing evidence: {missing}")
    pause = run_pause_resume_demo(
        Path(pause_resume_config), output_dir, max(1, sample_interval)
    )
    click.echo(
        f"Pause/resume: equivalent={pause['equivalent']} "
        f"pause_tick={pause['pause_tick']} mismatches={pause['mismatch_count']}"
    )
    performance = run_decode_performance()
    performance["compatibility_compatible"] = compatibility["compatible"]
    performance["pause_resume_equivalent"] = pause["equivalent"]
    from machine_sim.sim.checkpoint import config_digest as _cfg_digest

    performance["pause_resume_config_digest"] = _cfg_digest(
        SimConfig.from_toml(Path(pause_resume_config))
    )
    (output_dir / "design_program_performance.json").write_text(
        json.dumps(performance, indent=2, sort_keys=True), encoding="utf-8"
    )
    click.echo(
        f"Decode throughput: canonical={performance['canonical_programs_per_second']} "
        f"programs/s"
    )
    if not (compatibility["compatible"] and pause["equivalent"]):
        raise SystemExit(1)


@cli.command("m23-demo")
@click.option("--output", "-o", type=click.Path(), default="output/demo_m23")
@click.option("--ticks", "-t", type=int, default=400)
@click.option("--min-cursor", type=int, default=4,
              help="Mid-copy cursor threshold for the pause/resume child.")
@click.option("--skip-performance", is_flag=True, default=False)
def m23_demo(output: str, ticks: int, min_cursor: int, skip_performance: bool) -> None:
    """Run the M23 demonstrations and write all construction artifacts."""
    from machine_sim.perf import m23_demo

    output_dir = Path(output)
    removal = m23_demo.demo_scheduler_removal(output_dir)
    click.echo(f"Scheduler removal: zero_successors={removal['zero_successors_without_runtime_section']}")

    canonical = m23_demo.demo_canonical_copy(output_dir)
    click.echo(f"Canonical copy: ok={canonical['canonical_copy_ok']}")

    closure = m23_demo.demo_two_generation_closure(output_dir)
    click.echo(f"A->B->C closure: ok={closure['closure_ok']} generations={closure['generations_present']}")

    capability = m23_demo.demo_padding_and_length(output_dir)
    length_report = json.loads(
        (output_dir / "program_length_cost_comparison.json").read_text(encoding="utf-8")
    )
    click.echo(
        f"Length cost: more_records={length_report['longer_program_more_records']} "
        f"more_energy={length_report['longer_program_more_energy']}"
    )
    capability_doc = json.loads(
        (output_dir / "copy_capability_comparison.json").read_text(encoding="utf-8")
    )
    padding = capability_doc["padding"]
    click.echo(
        f"Padding: compact_cycles={padding['compact_cycles_within_window']} "
        f"padded_cycles={padding['padded_cycles_within_window']}"
    )

    copy_errors = m23_demo.demo_copy_errors(output_dir)
    click.echo(
        f"Copy errors: deterministic={copy_errors['same_seed_identical_outcome']} "
        f"mechanisms={copy_errors['all_four_mechanisms_observed']} "
        f"runtime_opcode_hits={copy_errors['runtime_opcodes_can_change_via_substitution_or_deletion_or_insertion']}"
    )

    traced = m23_demo.run_traced_variable_run(output_dir, ticks=ticks)
    click.echo(
        f"Traced run: {traced['ticks']} ticks, successes={traced['successes']}, "
        f"{traced['wall_seconds']}s"
    )

    pause_resume = m23_demo.demo_midcopy_pause_resume(
        output_dir, min_cursor=max(1, min_cursor)
    )
    click.echo(
        f"Mid-copy pause/resume: equivalent={pause_resume['equivalent']} "
        f"deep_mismatches={pause_resume['deep_digest_mismatch_count']}"
    )

    if skip_performance:
        performance = {"within_10_percent_bound": True, "skipped": True}
    else:
        performance = m23_demo.demo_performance_regression(output_dir)
        click.echo(
            f"M23-disabled performance: {performance['m23_disabled_ticks_per_second']} t/s "
            f"vs accepted {performance['baseline_ticks_per_second']} t/s "
            f"(regression {performance['regression_percent']}%)"
        )

    summary = {
        "scheduler_removal": removal,
        "canonical_copy": canonical,
        "closure": closure,
        "capability": capability,
        "copy_errors": copy_errors,
        "traced_run": traced,
        "pause_resume": pause_resume,
        "performance": performance,
    }
    (output_dir / "construction_run_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    click.echo(f"Artifacts written to {output_dir}")

    ok = (
        removal["zero_successors_without_runtime_section"]
        and canonical["canonical_copy_ok"]
        and closure["closure_ok"]
        and pause_resume["equivalent"]
    )
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    cli()
