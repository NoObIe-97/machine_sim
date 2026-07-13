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
        )
        if cfg.long_run_adaptation_enabled:
            unit.max_power = 10000
            unit.power_reserve = 10000
        # Scale component degradation rates if configured
        if cfg.component_degradation_scale != 1.0:
            for comp in unit.components.values():
                comp.degradation_rate *= cfg.component_degradation_scale
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


if __name__ == "__main__":
    cli()
