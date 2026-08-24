"""Deep future-causal semantic-state digest for deterministic refactoring equivalence.

The M20 run digest (``run_control.tick_observation``) is intentionally shallow:
it observes unit identifier, position, power, mean component health, and active
state. Hidden neural state, weights, masks, adaptive scalars, resources,
hazards, signals, RNG state, and fabrication counters can all diverge while the
shallow observation stays equal.

This module provides a *deep* digest that covers every audited future-causal
state category of a ``SimEngine`` so an internal refactoring can be verified as
semantics-preserving: two engines with identical deep digests at the same tick
have identical observable futures up to RNG consumption, which is itself part
of the digest.

Canonicalization rules:

* the snapshot contains only ``None``, ``bool``, ``int``, ``float``, ``str``,
  lists, and string-keyed dicts — no sets, tuples, objects, or callables;
* floats are serialized through :mod:`json` shortest round-trip representation,
  so identical values produce identical text and no precision is masked;
* mapping keys are sorted at serialization time; list order is preserved because
  list order is observable by the tick loop (units, signals, sensor readings);
* no dependence on Python built-in ``hash()`` or on set iteration order;
* ``random.Random`` state is captured exactly via ``getstate()``.

Classification policy: every field below was classified by inspecting actual
engine reads in the tick loop, not by name. Fields that are read by the tick
loop, the decision path, or any code that can change future behavior are
included. Fields proven to be write-only within the run (output-only traces,
rendered summaries, wall-clock records) are excluded and declared in
:func:`semantic_state_schema`. When a field's classification was uncertain it
was treated as future-causal and included.
"""

from __future__ import annotations

import hashlib
import json
import random
from typing import Any, Dict, List, Optional

from machine_sim.sim.checkpoint import config_digest

DEEP_DIGEST_SCHEMA_VERSION = "1.0.0"


def _rng_snapshot(rng: random.Random) -> Dict[str, Any]:
    version, internal, gauss_next = rng.getstate()
    return {
        "version": int(version),
        "internal": [int(v) for v in internal],
        "gauss_next": gauss_next,
    }


def _world_snapshot(engine: Any) -> Dict[str, Any]:
    world = engine.world
    cells: Dict[str, Any] = {}
    for pos, cell in world.grid.items():
        if not (cell.resources or cell.hazards):
            continue
        cells[f"{pos[0]},{pos[1]}"] = {
            "resources": {
                name: {
                    "quantity": res.quantity,
                    "max_quantity": res.max_quantity,
                    "regrowth_rate": res.regrowth_rate,
                }
                for name, res in sorted(cell.resources.items())
            },
            "hazards": {
                name: {
                    "intensity": hz.intensity,
                    "decay_rate": hz.decay_rate,
                    "damage_per_tick": hz.damage_per_tick,
                }
                for name, hz in sorted(cell.hazards.items())
            },
        }
    signals = [
        {
            "signal_id": sig.signal_id,
            "source_unit_id": sig.source_unit_id,
            "pattern_id": sig.pattern_id,
            "position": [sig.position[0], sig.position[1]],
            "intensity": sig.intensity,
            "radius": sig.radius,
            "decay_rate": sig.decay_rate,
            "emitted_tick": sig.emitted_tick,
            "duration": sig.duration,
        }
        for sig in world.signals
    ]
    snapshot: Dict[str, Any] = {
        "width": world.width,
        "height": world.height,
        "next_signal_id": world._next_signal_id,
        "current_tick": world._current_tick,
        # M23: multi-tick construction reservations are future-causal (they
        # arbitrate placement and are preserved through checkpoint/resume).
        "reserved_cells": {
            f"{pos[0]},{pos[1]}": owner
            for pos, owner in sorted(world.reserved_cells.items())
        },
        # Unit occupancy is future-causal: movement, sensing, proximity, and
        # placement all read cell.unit_id.
        "occupied_cells": {
            f"{pos[0]},{pos[1]}": cell.unit_id
            for pos, cell in sorted(world.grid.items())
            if cell.unit_id is not None
        },
        "cells": cells,
        "signals": signals,
    }
    # The engine normally shares its RNG with the world; only capture a second
    # copy when the aliasing does not hold, so the digest never double-counts.
    if world.rng is not getattr(engine, "rng", None):
        snapshot["world_rng"] = _rng_snapshot(world.rng)
    return snapshot


def _components_snapshot(unit: Any) -> Dict[str, Any]:
    return {
        name: {
            "max_health": comp.max_health,
            "health": comp.health,
            "degradation_rate": comp.degradation_rate,
            "is_critical": comp.is_critical,
        }
        for name, comp in unit.components.items()
    }


def _sensor_readings_snapshot(unit: Any) -> List[Any]:
    readings = []
    for r in unit.sensor_readings:
        readings.append(
            {
                "tick": r.tick,
                "position": [r.position[0], r.position[1]],
                "resource_signals": dict(sorted(r.resource_signals.items())),
                "hazard_signals": dict(sorted(r.hazard_signals.items())),
                "nearby_units": list(r.nearby_units),
                "signal_strength": r.signal_strength,
            }
        )
    return readings


def _local_memory_snapshot(unit: Any) -> List[Any]:
    entries = []
    for m in unit.local_memory:
        entries.append(
            {
                "tick": m.tick,
                "event_type": m.event_type,
                "position": [m.position[0], m.position[1]],
                "outcome_delta": m.outcome_delta,
                "data": m.data,
            }
        )
    return entries


def _field_tracker_snapshot(unit: Any) -> Optional[Dict[str, Any]]:
    tracker = getattr(unit, "_field_tracker", None)
    if tracker is None:
        return None
    # Window deques and cumulative counters are both future-causal: they feed
    # get_summary(), which feeds action selection every tick.
    return {
        "window_size": tracker.window_size,
        "signal_observations": [list(item) for item in tracker._signal_observations],
        "hazard_events": list(tracker._hazard_events),
        "proximity_events": [list(item) for item in tracker._proximity_events],
        "movement_blocks": list(tracker._movement_blocks),
        "emission_ticks": list(tracker._emission_ticks),
        "scan_ticks": list(tracker._scan_ticks),
        "total_signals": tracker._total_signals,
        "total_hazards": tracker._total_hazards,
        "total_proximity": tracker._total_proximity,
        "total_movement_blocks": tracker._total_movement_blocks,
        "total_emissions": tracker._total_emissions,
        "total_scans": tracker._total_scans,
    }


def _adaptive_state_snapshot(unit: Any) -> Optional[Dict[str, Any]]:
    state = getattr(unit, "_adaptive_state", None)
    if state is None:
        return None
    return dict(sorted(state.to_dict().items()))


def _neural_controller_snapshot(unit: Any) -> Optional[Dict[str, Any]]:
    controller = getattr(unit, "_neural_controller", None)
    if controller is None:
        return None
    cfg = controller.config
    s = controller.state
    return {
        "config": {
            "input_size": cfg.input_size,
            "hidden_size": cfg.hidden_size,
            "output_size": cfg.output_size,
            "param_output_size": cfg.param_output_size,
            "plasticity_rate": cfg.plasticity_rate,
            "plasticity_enabled": cfg.plasticity_enabled,
            "weight_bound": cfg.weight_bound,
        },
        "state": {
            "hidden_state": list(s.hidden_state),
            "W_in": [list(row) for row in s.W_in],
            "W_rec": [list(row) for row in s.W_rec],
            "W_out": [list(row) for row in s.W_out],
            "W_param": [list(row) for row in s.W_param],
            "b_hidden": list(s.b_hidden),
            "c_action": list(s.c_action),
            "c_param": list(s.c_param),
            "recurrent_mask": (
                [list(row) for row in s.recurrent_mask]
                if s.recurrent_mask is not None
                else None
            ),
        },
    }


def _architecture_descriptor_snapshot(unit: Any) -> Optional[Dict[str, Any]]:
    descriptor = getattr(unit, "_architecture_descriptor", None)
    if descriptor is None:
        return None
    return {
        "architecture_id": descriptor.architecture_id,
        "hidden_size": descriptor.hidden_size,
        "recurrent_density": descriptor.recurrent_density,
        "plasticity_rate": descriptor.plasticity_rate,
        "plasticity_enabled": descriptor.plasticity_enabled,
    }


def _unit_snapshot(unit: Any) -> Dict[str, Any]:
    variant = getattr(unit, "variant", None)
    snapshot: Dict[str, Any] = {
        "unit_id": unit.unit_id,
        "unit_class": type(unit).__name__,
        "position": [unit.position[0], unit.position[1]],
        "power_reserve": unit.power_reserve,
        "max_power": unit.max_power,
        "is_active": unit.is_active,
        "action_budget": unit.action_budget,
        "sensor_range_setting": getattr(unit, "SENSOR_RANGE", None),
        "components": _components_snapshot(unit),
        "sensor_readings": _sensor_readings_snapshot(unit),
        "local_memory": _local_memory_snapshot(unit),
    }
    if variant is not None:
        snapshot["variant"] = {
            "name": variant.name,
            "max_power": variant.max_power,
            "power_drain_rate": variant.power_drain_rate,
            "sensor_range": variant.sensor_range,
        }
    for attr in (
        "signal_enabled",
        "signal_pattern_count",
        "signal_energy_cost",
        "signal_default_radius",
        "signal_default_decay",
        "signal_default_duration",
        "adaptive_enabled",
        "_neural_controller_enabled",
        "_neural_controller_mode",
        "_last_signal_tick",
        "_last_scan_tick",
        "_previous_action_name",
        "_generation_index",
        "_lifetime_ticks",
    ):
        if hasattr(unit, attr):
            key = attr.lstrip("_")
            snapshot[key] = getattr(unit, attr)
    field_tracker = _field_tracker_snapshot(unit)
    if field_tracker is not None:
        snapshot["field_tracker"] = field_tracker
    adaptive_state = _adaptive_state_snapshot(unit)
    if adaptive_state is not None:
        snapshot["adaptive_state"] = adaptive_state
    neural = _neural_controller_snapshot(unit)
    if neural is not None:
        snapshot["neural_controller"] = neural
    architecture = _architecture_descriptor_snapshot(unit)
    if architecture is not None:
        snapshot["architecture_descriptor"] = architecture
    # M22: the design program is future-causal hereditary state. Its schema,
    # canonical instruction sequence, and digest enter the snapshot.
    design_program = getattr(unit, "_design_program", None)
    if design_program is not None:
        snapshot["design_program"] = design_program.to_dict()
        snapshot["design_program_enabled"] = bool(
            getattr(unit, "_design_program_enabled", True)
        )
        execution_status = getattr(unit, "_design_program_execution_status", None)
        if execution_status is not None:
            snapshot["design_program_execution_status"] = str(execution_status)
    # M23: runtime construction state is future-causal (copy cursor/buffer/
    # RNG/reservation/costs drive successor construction across ticks).
    construction_state = getattr(unit, "_construction_state", None)
    if construction_state is not None:
        from machine_sim.sim.state_digest import _rng_snapshot

        snapshot["construction_runtime"] = {
            "construction_enabled": bool(construction_state.construction_enabled),
            "runtime_section_start": int(construction_state.runtime_section_start),
            "runtime_program_counter": int(construction_state.runtime_program_counter),
            "construction_phase": str(construction_state.construction_phase),
            "construction_cycle_index": int(construction_state.construction_cycle_index),
            "source_program_digest_at_begin": str(
                construction_state.source_program_digest_at_begin
            ),
            "source_cursor": int(construction_state.source_cursor),
            "target_copy_buffer": [
                [int(pair[0]), float(pair[1])]
                for pair in construction_state.target_copy_buffer
            ],
            "reserved_target_position": (
                list(construction_state.reserved_target_position)
                if construction_state.reserved_target_position is not None
                else None
            ),
            "provisional_successor_id": (
                str(construction_state.provisional_successor_id)
                if construction_state.provisional_successor_id is not None
                else None
            ),
            "copy_rng": (
                _rng_snapshot(construction_state.copy_rng)
                if construction_state.copy_rng is not None
                else None
            ),
            "cycle_start_tick": int(construction_state.cycle_start_tick),
            "executed_runtime_instruction_count": int(
                construction_state.executed_runtime_instruction_count
            ),
            "copied_record_count": int(construction_state.copied_record_count),
            "copy_error_count": int(construction_state.copy_error_count),
            "accumulated_copy_cost": float(construction_state.accumulated_copy_cost),
            "last_construction_fault": (
                str(construction_state.last_construction_fault)
                if construction_state.last_construction_fault is not None
                else None
            ),
        }
    return snapshot


def _fabrication_snapshot(engine: Any) -> Dict[str, Any]:
    fabricator = getattr(engine, "fabrication_engine", None)
    if fabricator is None:
        return {}
    # _next_unit_id determines successor identity and is strictly future-causal.
    # Attempt/successor/failure counters were audited as summary-only today but
    # are included deliberately: they are cheap, and treating them as causal
    # makes the digest strictly more sensitive to unintended behavior drift.
    return {
        "next_unit_id": fabricator._next_unit_id,
        "fabrication_attempts": fabricator._fabrication_attempts,
        "fabrication_successes": fabricator._fabrication_successes,
        "fabrication_failures": dict(sorted(fabricator._fabrication_failures.items())),
    }


def semantic_state_snapshot(engine: Any) -> Dict[str, Any]:
    """Return the canonical JSON-compatible deep semantic state of ``engine``."""
    snapshot: Dict[str, Any] = {
        "deep_digest_schema_version": DEEP_DIGEST_SCHEMA_VERSION,
        "tick_count": engine.tick_count,
        "max_ticks": engine.max_ticks,
        "run_digest_value": engine.run_digest_value,
        "config": engine.config.to_dict(),
        "rng": _rng_snapshot(engine.rng),
        "world": _world_snapshot(engine),
        "units": [_unit_snapshot(unit) for unit in engine.units],
        "fabrication": _fabrication_snapshot(engine),
    }
    return snapshot


def deep_state_digest(engine: Any) -> str:
    """Return the sha256 hex digest of the engine's deep semantic state."""
    payload = json.dumps(
        semantic_state_snapshot(engine),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def semantic_state_schema() -> Dict[str, Any]:
    """Declare which state categories the deep digest includes and excludes.

    Every exclusion records the inspection evidence that justified treating the
    field as output-only rather than future-causal.
    """
    return {
        "schema_version": DEEP_DIGEST_SCHEMA_VERSION,
        "canonicalization": {
            "serialization": "json.dumps(sort_keys=True, separators=(',',':'), ensure_ascii=True)",
            "float_representation": "shortest round-trip repr, unrounded",
            "hash_dependence": "none (sha256 over canonical text only)",
            "set_dependence": "none (sets never enter the snapshot)",
            "ordering": "dict keys sorted, list order preserved (observable)",
        },
        "included": [
            "engine tick_count / max_ticks",
            "engine run_digest_value (M20 continuation chain value carried across checkpoints)",
            "full SimConfig mapping (every runtime-affecting configuration value)",
            "engine RNG state (random.Random getstate; shared with World by construction)",
            "world width/height, next_signal_id, current_tick",
            "world unit-occupancy map (cell.unit_id per occupied cell)",
            "per-cell resource quantity/max_quantity/regrowth_rate (non-inert cells only)",
            "per-cell hazard intensity/decay_rate/damage_per_tick (non-inert cells only)",
            "active signals with all future-causal parameters, in list order",
            "unit identifier, class, deterministic list order",
            "unit position, power_reserve, max_power, is_active, action_budget",
            "unit SENSOR_RANGE setting and hardware-variant parameters",
            "component health/max_health/degradation_rate/is_critical per unit",
            "bounded sensor-reading window contents per unit",
            "bounded local_memory window contents per unit",
            "signal/timer state (_last_signal_tick, _last_scan_tick, previous action name)",
            "generation index and lifetime ticks",
            "scalar adaptive-control state vector (all 15 fields)",
            "field-tracker bounded windows and cumulative counters (feed action selection)",
            "neural processing config, hidden/recurrent state, all weight matrices, biases, context vectors, recurrent mask",
            "neural architecture descriptor (id, hidden size, recurrent density, plasticity rate/enabled)",
            "fabrication next_unit_id counter plus attempt/success/failure counters",
            "per-unit design program: schema version, instruction-set version, canonical instruction sequence, program digest, program-enabled flag, recorded execution status",
            "capsule generator static bounds are covered by the config mapping",
        ],
        "excluded": [
            {
                "field": "EventLog._events and EventLog._tick_events",
                "basis": "append-only observation store and per-tick buffer; the tick loop clears _tick_events before any read each tick and never reads either across ticks",
            },
            {
                "field": "engine trace accumulators (_adaptive_state_snapshots, _neural_state_trace, _neural_action_trace, _neural_plasticity_trace, _neural_successor_transfer_trace, _architecture_transfer_trace, _architecture_distribution_trace, _architecture_cost_trace, _architecture_initial_descriptors, _descendant_transfer_trace, _local_feedback_trace)",
                "basis": "output-only sampled history written after decisions; no tick-loop read",
            },
            {
                "field": "engine cost accumulators (_total_processing_cost, _total_fabrication_cost)",
                "basis": "summary-only accumulators; no tick-loop read",
            },
            {
                "field": "analysis-module internal histories (correlator, telemetry_tracker, reconciliation_engine records, lineage_drift, pressure_analyzer, field_dynamics, trace_compressor, trace_drift, summary_consistency, multi_gen_trace)",
                "basis": "post-run analysis buffers; their outputs are consumed only by artifact writers and later analysis phases, never by action selection or environment updates",
            },
            {
                "field": "FabricationEngine._lineage_records",
                "basis": "unbounded output-only fabrication history; reads are confined to trace writers and summaries",
            },
            {
                "field": "CapsuleManager._capsules / _capsule_count",
                "basis": "unbounded output-only capsule archive; warm starts use freshly generated capsules, never archived ones",
            },
            {
                "field": "unit._last_action_output on NeuralController",
                "basis": "cached rendering of the last forward pass; read only by trace writers",
            },
            {
                "field": "unit._capsule_applied / _capsule_warm_start_effect",
                "basis": "telemetry annotations recorded during fabrication; read only by telemetry summaries and post-run comparisons",
            },
            {
                "field": "unit._emission_policy / _scan_policy",
                "basis": "static parameter objects constructed once and never read by the decision path (decide() uses inline logic); verified no mutation after __init__",
            },
            {
                "field": "unit._action_counts / _last_feedback",
                "basis": "initialized empty and never mutated or read anywhere in the runtime",
            },
            {
                "field": "Cell.terrain",
                "basis": "constant 'plain' since construction; no runtime reader",
            },
            {
                "field": "World._active_cells",
                "basis": "implementation-level index of non-inert cells, fully derivable from the captured cell map; not itself consulted by behavior",
            },
            {
                "field": "wall-clock timestamps, file paths, rendered status output, run-manifest timestamps, benchmark performance counters",
                "basis": "observation metadata with no influence on simulation futures",
            },
        ],
        "uncertainty_policy": "fields whose classification was uncertain were included until inspection proved them output-only",
    }


def write_schema_artifact(path: Any) -> Any:
    """Write the schema declaration as JSON and return the resolved path."""
    from pathlib import Path

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(semantic_state_schema(), indent=2), encoding="utf-8")
    return target


__all__ = [
    "DEEP_DIGEST_SCHEMA_VERSION",
    "config_digest",
    "deep_state_digest",
    "semantic_state_schema",
    "semantic_state_snapshot",
    "write_schema_artifact",
]
