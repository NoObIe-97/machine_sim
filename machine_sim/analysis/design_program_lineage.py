"""Read-only design-program lineage analysis and compatibility projection (M22).

Every function here is pure with respect to runtime state: analyzers consume
engine trace lists and unit snapshots and produce bounded artifact structures.
Nothing writes into engines or units.

The compatibility projection answers the M22 core requirement: a program-
backed engine and a legacy descriptor engine that construct the same
phenotype must agree on everything future-causal *except* the representation-
only program metadata. The projection removes exactly that metadata from the
M21 semantic snapshot — per-unit design-program records and flags, program
execution status, the configuration flag enabling program mode, and the
architecture identifier string (naming metadata, not phenotype) — then
digests the remainder. The standard M21 deep digest itself is never weakened.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any, Dict, List, Optional

from machine_sim.sim.state_digest import semantic_state_snapshot


def compatibility_projection_snapshot(engine: Any) -> Dict[str, Any]:
    """Return the M21 semantic snapshot with representation-only program
    metadata removed."""
    snapshot = semantic_state_snapshot(engine)
    config = snapshot.get("config")
    if isinstance(config, dict):
        config.pop("design_program_enabled", None)
    for unit in snapshot.get("units", []):
        unit.pop("design_program", None)
        unit.pop("design_program_enabled", None)
        unit.pop("design_program_execution_status", None)
        descriptor = unit.get("architecture_descriptor")
        if isinstance(descriptor, dict):
            # Identity metadata only; phenotype fields are compared.
            descriptor["architecture_id"] = ""
    return snapshot


def compatibility_projection_digest(engine: Any) -> str:
    payload = json.dumps(
        compatibility_projection_snapshot(engine),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def collect_initial_program_state(engine: Any) -> List[Dict[str, Any]]:
    """Bounded initial-state records for every program-backed unit."""
    rows: List[Dict[str, Any]] = []
    for unit in getattr(engine, "units", []):
        program = getattr(unit, "_design_program", None)
        if program is None:
            continue
        descriptor = getattr(unit, "_architecture_descriptor", None)
        rows.append(
            {
                "unit_id": unit.unit_id,
                "program_digest": program.program_digest(),
                "program_length": program.length,
                "instruction_set_version": program.instruction_set_version,
                "opcode_frequency": dict(
                    sorted(Counter(
                        record.opcode for record in program.instructions
                    ).items())
                ),
                "decoded_hidden_size": (
                    descriptor.hidden_size if descriptor is not None else None
                ),
                "decoded_recurrent_density": (
                    round(descriptor.recurrent_density, 6)
                    if descriptor is not None else None
                ),
                "decoded_plasticity_rate": (
                    round(descriptor.plasticity_rate, 6)
                    if descriptor is not None else None
                ),
            }
        )
    return rows


def summarize_transfers(engine: Any) -> Dict[str, Any]:
    """Aggregate the engine's program transfer trace without mutating it."""
    transfers = list(getattr(engine, "_design_program_transfer_trace", []))
    successful = [t for t in transfers if t.get("execution_status") == "complete"]
    changed_content = [
        t for t in transfers
        if t.get("successor_program_digest") != t.get("source_program_digest")
    ]
    length_changed = [
        t for t in transfers
        if t.get("successor_program_length") != t.get("source_program_length")
    ]
    phenotype_changed = [t for t in transfers if t.get("phenotype_changed") is True]
    zero_change = [t for t in transfers if not (
        t.get("successor_program_digest") != t.get("source_program_digest")
    )]
    distinct_decoded = {
        (
            t.get("decoded_hidden_size"),
            t.get("decoded_recurrent_density"),
            t.get("decoded_plasticity_rate"),
            t.get("decoded_plasticity_enabled"),
        )
        for t in successful
    }
    return {
        "transfer_count": len(transfers),
        "successful_transfer_count": len(successful),
        "content_changed_transfer_count": len(changed_content),
        "length_changed_transfer_count": len(length_changed),
        "phenotype_changed_transfer_count": len(phenotype_changed),
        "zero_change_transfer_count": len(zero_change),
        "distinct_decoded_architecture_count": len(distinct_decoded),
        "out_of_bounds_decoded_count": sum(
            1
            for t in successful
            if t.get("decoded_hidden_size") is None
        ),
        "total_program_execution_cost": round(
            float(getattr(engine, "_total_program_execution_cost", 0.0)), 6
        ),
    }


def summarize_distribution_trace(engine: Any) -> List[Dict[str, Any]]:
    """Read-only copy of sampled program distribution snapshots."""
    return [
        dict(row) for row in getattr(engine, "_design_program_distribution_trace", [])
    ]


__all__ = [
    "collect_initial_program_state",
    "compatibility_projection_digest",
    "compatibility_projection_snapshot",
    "summarize_distribution_trace",
    "summarize_transfers",
]
