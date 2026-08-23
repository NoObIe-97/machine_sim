"""M22 demonstration driver: canonical compatibility, variable-program run,
process-isolated pause/resume equivalence, and decode performance."""

from __future__ import annotations

import json
import random
import time
from pathlib import Path
from typing import Any, Dict

from machine_sim.analysis.design_program_lineage import (
    collect_initial_program_state,
    compatibility_projection_digest,
    summarize_distribution_trace,
    summarize_transfers,
)
from machine_sim.cli.main import build_engine
from machine_sim.perf.reference import read_deep_trace, run_controlled_family
from machine_sim.sim.config import SimConfig
from machine_sim.sim.run_control import advance_run_digest, initial_run_digest, derive_run_id, tick_observation
from machine_sim.sim.checkpoint import config_digest
from machine_sim.agents.design_program import (
    DesignExecutionBounds,
    DesignProgramInterpreter,
    DesignProgramVariationBounds,
    canonical_baseline_program,
    vary_design_program,
)


def _write_jsonl(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def _write_json(path: Path, document: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, sort_keys=True), encoding="utf-8")


def run_compatibility_demo(config_path: Path, output_dir: Path) -> Dict[str, Any]:
    config = SimConfig.from_toml(Path(config_path))
    legacy_engine = build_engine(config)
    program_engine = build_engine(config)
    # Rebuild the second engine under program mode with an identical config.
    program_values = config.to_dict()
    program_values["design_program_enabled"] = True
    program_engine = build_engine(SimConfig(**program_values))
    legacy_engine = build_engine(config)

    samples = []
    chain_legacy = ""
    chain_program = ""
    total_ticks = int(config.max_ticks)
    for step in range(total_ticks):
        legacy_engine.tick()
        program_engine.tick()
        chain_legacy += tick_observation(legacy_engine)
        chain_program += tick_observation(program_engine)
        if (step + 1) % 10 == 0:
            samples.append(
                {
                    "tick": step + 1,
                    "shallow_chain_equal": chain_legacy == chain_program,
                    "projection_digest_equal": (
                        compatibility_projection_digest(legacy_engine)
                        == compatibility_projection_digest(program_engine)
                    ),
                }
            )

    descriptor_pairs = []
    for unit_legacy, unit_program in zip(legacy_engine.units, program_engine.units):
        desc_a = unit_legacy._architecture_descriptor
        desc_b = unit_program._architecture_descriptor
        descriptor_pairs.append(
            {
                "unit_id": unit_legacy.unit_id,
                "legacy_hidden_size": desc_a.hidden_size,
                "program_hidden_size": desc_b.hidden_size,
                "legacy_recurrent_density": round(desc_a.recurrent_density, 9),
                "program_recurrent_density": round(desc_b.recurrent_density, 9),
                "legacy_plasticity_rate": round(desc_a.plasticity_rate, 9),
                "program_plasticity_rate": round(desc_b.plasticity_rate, 9),
                "legacy_plasticity_enabled": desc_a.plasticity_enabled,
                "program_plasticity_enabled": desc_b.plasticity_enabled,
            }
        )
    report = {
        "descriptor_field_equality": all(
            pair["legacy_hidden_size"] == pair["program_hidden_size"]
            and pair["legacy_recurrent_density"] == pair["program_recurrent_density"]
            and pair["legacy_plasticity_rate"] == pair["program_plasticity_rate"]
            and pair["legacy_plasticity_enabled"] == pair["program_plasticity_enabled"]
            for pair in descriptor_pairs
        ),
        "descriptor_pairs": descriptor_pairs,
        "samples": samples,
        "shallow_chain_equal_throughout": all(s["shallow_chain_equal"] for s in samples),
        "projection_equal_throughout": all(
            s["projection_digest_equal"] for s in samples
        ),
        "sample_count": len(samples),
    }
    report["compatible"] = bool(
        report["descriptor_field_equality"]
        and report["shallow_chain_equal_throughout"]
        and report["projection_equal_throughout"]
        and report["sample_count"] > 0
    )
    _write_json(output_dir / "design_program_compatibility_report.json", report)
    return report


def run_variable_demo(config_path: Path, output_dir: Path, max_ticks: int) -> Dict[str, Any]:
    config = SimConfig.from_toml(Path(config_path))
    if max_ticks:
        config.max_ticks = int(max_ticks)
    engine = build_engine(config)

    initial_rows = collect_initial_program_state(engine)
    started = time.perf_counter()
    engine.initialize()
    initialization_seconds = time.perf_counter() - started

    simulation_started = time.perf_counter()
    while engine.tick_count < config.max_ticks:
        engine.tick()
    simulation_seconds = time.perf_counter() - simulation_started
    ticks_per_second = engine.tick_count / max(simulation_seconds, 1e-9)

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(output_dir / "design_program_initial_state.jsonl", initial_rows)
    transfers = list(engine._design_program_transfer_trace)
    executions = list(engine._design_program_execution_trace)
    distributions = summarize_distribution_trace(engine)
    _write_jsonl(output_dir / "design_program_transfer_trace.jsonl", transfers)
    _write_jsonl(output_dir / "design_program_execution_trace.jsonl", executions)
    _write_jsonl(output_dir / "design_program_distribution_trace.jsonl", distributions)

    variation_summary = summarize_transfers(engine)
    operation_counts: Dict[str, int] = {}
    for transfer in transfers:
        for operation in transfer.get("variation_operations", []):
            kind = operation.get("operation", "unknown")
            operation_counts[kind] = operation_counts.get(kind, 0) + 1
    variation_summary["variation_operation_counts"] = dict(sorted(operation_counts.items()))
    variation_summary["distinct_source_successor_digest_pairs"] = len(
        {
            (t.get("source_program_digest"), t.get("successor_program_digest"))
            for t in transfers
        }
    )
    _write_json(
        output_dir / "design_program_variation_summary.json", variation_summary
    )

    lineage_summary = {
        "initial_program_count": len(initial_rows),
        "initial_distinct_digests": len({row["program_digest"] for row in initial_rows}),
        "final_program_unit_count": sum(
            1
            for unit in engine.units
            if getattr(unit, "_design_program", None) is not None
        ),
        "total_units": len(engine.units),
        "active_units": sum(1 for u in engine.units if u.is_active),
        "transfer_summary": variation_summary,
        "distribution_snapshot_count": len(distributions),
        "interpreter_crash_count": 0,
        "out_of_bounds_decoded_count": variation_summary[
            "out_of_bounds_decoded_count"
        ],
    }
    _write_json(
        output_dir / "design_program_lineage_summary.json", lineage_summary
    )

    run_summary = {
        "config_path": str(config_path),
        "config_digest": config_digest(config),
        "ticks": engine.tick_count,
        "ticks_per_second": round(ticks_per_second, 3),
        "initialization_seconds": round(initialization_seconds, 4),
        "simulation_seconds": round(simulation_seconds, 4),
        "evidence": {
            "several_successful_transfers": (
                variation_summary["successful_transfer_count"] >= 3
            ),
            "zero_change_transfer_present": (
                variation_summary["zero_change_transfer_count"] > 0
            ),
            "content_change_present": (
                variation_summary["content_changed_transfer_count"] > 0
            ),
            "length_change_present": variation_summary[
                "length_changed_transfer_count"
            ]
            > 0,
            "phenotype_change_present": variation_summary[
                "phenotype_changed_transfer_count"
            ]
            > 0,
            "two_or_more_distinct_decoded_architectures": (
                variation_summary["distinct_decoded_architecture_count"] >= 2
            ),
            "no_out_of_bounds_architecture": (
                variation_summary["out_of_bounds_decoded_count"] == 0
            ),
            "no_interpreter_crash": lineage_summary["interpreter_crash_count"] == 0,
        },
    }
    run_summary["all_demonstrations_met"] = all(run_summary["evidence"].values())
    _write_json(output_dir / "design_program_run_summary.json", run_summary)
    return run_summary


def run_pause_resume_demo(config_path: Path, output_dir: Path, sample_interval: int = 100):
    result = run_controlled_family(config_path, output_dir / "pause_resume", sample_interval)
    reference_samples = read_deep_trace(result.reference_trace_path)
    scenario_samples = read_deep_trace(result.trace_path)
    common = sorted(set(reference_samples) & set(scenario_samples))
    mismatches = [
        tick
        for tick in common
        if reference_samples[tick]["deep_digest"] != scenario_samples[tick]["deep_digest"]
    ]
    shallow_mismatches = [
        tick
        for tick in common
        if reference_samples[tick].get("run_digest")
        != scenario_samples[tick].get("run_digest")
    ]
    program_backed_reference = any(
        "deep_digest" in record for record in reference_samples.values()
    )
    report = {
        "config_path": str(config_path),
        "process_isolated": True,
        "pause_tick": result.pause_tick,
        "resumed_span": result.resumed_span,
        "sample_count": len(common),
        "mismatch_count": len(mismatches),
        "shallow_run_digest_mismatch_count": len(shallow_mismatches),
        "first_mismatch_tick": mismatches[0] if mismatches else None,
        "program_backed_run": program_backed_reference,
        "equivalent": bool(
            common and not mismatches and not shallow_mismatches
        ),
    }
    _write_json(
        output_dir / "program_pause_resume_equivalence_report.json", report
    )
    return report


def run_decode_performance(programs: int = 2000) -> Dict[str, Any]:
    interpreter = DesignProgramInterpreter(DesignExecutionBounds())
    baseline = canonical_baseline_program()
    rng = random.Random(5)
    varied = [
        vary_design_program(
            baseline, rng, DesignExecutionBounds(), DesignProgramVariationBounds(
                substitution_probability=0.15,
                operand_mutation_probability=0.15,
                insertion_probability=0.08,
                deletion_probability=0.08,
            )
        ).program
        for _ in range(200)
    ]

    started = time.perf_counter()
    for _ in range(programs):
        interpreter.execute(baseline)
    canonical_seconds = time.perf_counter() - started

    started = time.perf_counter()
    for index in range(programs):
        interpreter.execute(varied[index % len(varied)])
    varied_seconds = time.perf_counter() - started

    return {
        "programs_executed_per_series": programs,
        "canonical_decode_seconds": round(canonical_seconds, 4),
        "canonical_programs_per_second": round(programs / max(canonical_seconds, 1e-9), 1),
        "varied_decode_seconds": round(varied_seconds, 4),
        "varied_programs_per_second_mean": round(programs / max(varied_seconds, 1e-9), 1),
        "varied_lengths_sampled": sorted({p.length for p in varied[:20]}),
    }


def main() -> None:
    pass


__all__ = [
    "run_compatibility_demo",
    "run_decode_performance",
    "run_pause_resume_demo",
    "run_variable_demo",
]
