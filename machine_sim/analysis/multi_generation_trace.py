"""Multi-generation adaptive-state trajectory tracking.

Read-only observer that records generation-indexed adaptive-state transfers
and computes trajectory comparison metrics.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class GenerationTransferRecord:
    """A single source-to-successor adaptive-state transfer."""
    tick: int
    source_unit_id: str
    successor_unit_id: str
    source_generation_index: int
    successor_generation_index: int
    source_adaptive_state: Dict[str, float]
    successor_adaptive_state: Dict[str, float]
    adaptive_state_delta: Dict[str, float]
    transfer_variation_summary: Dict[str, float]
    source_lifetime_ticks: int
    successor_initial_power_ratio: float
    local_feedback_context: Dict[str, float] = field(default_factory=dict)


class MultiGenerationTraceAnalyzer:
    """Tracks multi-generation adaptive-state trajectories.

    This is a read-only observer. It records transfer events and computes
    trajectory metrics but does not influence unit action selection.
    """

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self._transfer_records: List[GenerationTransferRecord] = []
        self._max_records = 10000

    def record_transfer(
        self,
        tick: int,
        source_unit_id: str,
        successor_unit_id: str,
        source_generation_index: int,
        successor_generation_index: int,
        source_adaptive_state: Dict[str, float],
        successor_adaptive_state: Dict[str, float],
        source_lifetime_ticks: int,
        successor_initial_power_ratio: float,
        local_feedback_context: Optional[Dict[str, float]] = None,
    ) -> None:
        """Record a generation-indexed adaptive-state transfer."""
        if not self.enabled:
            return

        # Compute delta
        delta = {}
        all_keys = set(source_adaptive_state.keys()) | set(successor_adaptive_state.keys())
        for k in all_keys:
            sv = source_adaptive_state.get(k, 0.0)
            ov = successor_adaptive_state.get(k, 0.0)
            delta[k] = round(ov - sv, 6)

        # Compute variation summary (absolute deltas grouped by category)
        weight_keys = [k for k in delta if "weight" in k]
        bias_keys = [k for k in delta if "bias" in k or "rate" in k or "threshold" in k]
        variation = {
            "weight_delta_rms": _rms([abs(delta[k]) for k in weight_keys]) if weight_keys else 0.0,
            "bias_delta_rms": _rms([abs(delta[k]) for k in bias_keys]) if bias_keys else 0.0,
            "max_abs_delta": max((abs(v) for v in delta.values()), default=0.0),
            "nonzero_delta_count": sum(1 for v in delta.values() if abs(v) > 1e-6),
        }

        record = GenerationTransferRecord(
            tick=tick,
            source_unit_id=source_unit_id,
            successor_unit_id=successor_unit_id,
            source_generation_index=source_generation_index,
            successor_generation_index=successor_generation_index,
            source_adaptive_state=dict(source_adaptive_state),
            successor_adaptive_state=dict(successor_adaptive_state),
            adaptive_state_delta=delta,
            transfer_variation_summary=variation,
            source_lifetime_ticks=source_lifetime_ticks,
            successor_initial_power_ratio=successor_initial_power_ratio,
            local_feedback_context=dict(local_feedback_context) if local_feedback_context else {},
        )

        self._transfer_records.append(record)
        if len(self._transfer_records) > self._max_records:
            self._transfer_records = self._transfer_records[-self._max_records:]

    def get_records(self) -> List[GenerationTransferRecord]:
        return list(self._transfer_records)

    def get_trajectory_comparison(self) -> Dict[str, Any]:
        """Compute trajectory comparison metrics across all transfers."""
        if not self._transfer_records:
            return self._empty_comparison()

        records = self._transfer_records
        transfer_count = len(records)

        # Generation index span
        gen_indices = set()
        for r in records:
            gen_indices.add(r.source_generation_index)
            gen_indices.add(r.successor_generation_index)
        generation_index_span = max(gen_indices) - min(gen_indices) + 1 if gen_indices else 0

        # Delta statistics
        all_deltas = [r.adaptive_state_delta for r in records]
        avg_delta = _avg_dict([d for d in all_deltas])
        max_delta = _max_abs_dict(all_deltas)

        # Similarity (1 - avg_abs_delta)
        avg_abs_delta_vals = []
        for d in all_deltas:
            avg_abs_delta_vals.append(_rms(list(d.values())))
        avg_similarity = 1.0 - _mean(avg_abs_delta_vals) if avg_abs_delta_vals else 1.0

        # Weight drift summary
        weight_deltas = []
        for d in all_deltas:
            w = {k: v for k, v in d.items() if "weight" in k}
            weight_deltas.append(w)
        weight_drift = _avg_dict(weight_deltas)

        # Signal parameter drift
        signal_deltas = []
        for d in all_deltas:
            s = {k: v for k, v in d.items() if "signal" in k}
            signal_deltas.append(s)
        signal_drift = _avg_dict(signal_deltas)

        # Resource response drift
        resource_deltas = []
        for d in all_deltas:
            r = {k: v for k, v in d.items() if "resource" in k or "extract" in k}
            resource_deltas.append(r)
        resource_drift = _avg_dict(resource_deltas)

        # Hazard response drift
        hazard_deltas = []
        for d in all_deltas:
            h = {k: v for k, v in d.items() if "hazard" in k}
            hazard_deltas.append(h)
        hazard_drift = _avg_dict(hazard_deltas)

        # Trajectory continuity: consecutive transfers with similar deltas
        continuity_scores = []
        for i in range(1, len(records)):
            prev = records[i - 1].adaptive_state_delta
            curr = records[i].adaptive_state_delta
            similarity = 1.0 - _cosine_distance(prev, curr)
            continuity_scores.append(max(0.0, similarity))
        trajectory_continuity = _mean(continuity_scores) if continuity_scores else 1.0

        return {
            "transfer_count": transfer_count,
            "generation_index_span": generation_index_span,
            "avg_transfer_delta": avg_delta,
            "max_transfer_delta": max_delta,
            "avg_source_successor_similarity": round(avg_similarity, 6),
            "adaptive_weight_drift_summary": weight_drift,
            "signal_parameter_drift_summary": signal_drift,
            "resource_response_drift_summary": resource_drift,
            "hazard_response_drift_summary": hazard_drift,
            "trajectory_continuity_score": round(trajectory_continuity, 6),
        }

    def get_trajectory_summary(self) -> Dict[str, Any]:
        """Compact summary for the adaptive_trajectory_summary.json artifact."""
        comparison = self.get_trajectory_comparison()
        records = self._transfer_records

        # Generation distribution
        gen_dist: Dict[int, int] = {}
        for r in records:
            gen = r.successor_generation_index
            gen_dist[gen] = gen_dist.get(gen, 0) + 1

        # Source lifetime stats at transfer time
        lifetimes = [r.source_lifetime_ticks for r in records]
        # Successor power ratio stats
        power_ratios = [r.successor_initial_power_ratio for r in records]

        return {
            "transfer_count": len(records),
            "generation_index_span": comparison["generation_index_span"],
            "generation_distribution": gen_dist,
            "avg_source_lifetime_at_transfer": round(_mean(lifetimes), 2) if lifetimes else 0,
            "avg_successor_initial_power_ratio": round(_mean(power_ratios), 4) if power_ratios else 0,
            "trajectory_continuity_score": comparison["trajectory_continuity_score"],
            "avg_transfer_delta_rms": round(_rms([comparison["avg_transfer_delta"].get(k, 0)
                                                   for k in comparison["avg_transfer_delta"]]), 6),
        }

    def get_comparison_with_reference(self, reference_records: List[GenerationTransferRecord]) -> Dict[str, Any]:
        """Compare transfer-enabled run against a reference (transfer-disabled) run."""
        enabled_comparison = self.get_trajectory_comparison()
        enabled_count = len(self._transfer_records)
        reference_count = len(reference_records)

        # Reference generation span
        ref_gen_indices = set()
        for r in reference_records:
            ref_gen_indices.add(r.source_generation_index)
            ref_gen_indices.add(r.successor_generation_index)
        ref_span = max(ref_gen_indices) - min(ref_gen_indices) + 1 if ref_gen_indices else 0

        enabled_span = enabled_comparison["generation_index_span"]

        # Delta comparison
        enabled_delta_rms = _rms([enabled_comparison["avg_transfer_delta"].get(k, 0)
                                   for k in enabled_comparison["avg_transfer_delta"]])
        ref_deltas = [r.adaptive_state_delta for r in reference_records]
        ref_delta_rms = _rms([v for d in ref_deltas for v in d.values()]) if ref_deltas else 0.0

        # Continuity comparison
        enabled_cont = enabled_comparison["trajectory_continuity_score"]
        ref_continuity_scores = []
        for i in range(1, len(reference_records)):
            prev = reference_records[i - 1].adaptive_state_delta
            curr = reference_records[i].adaptive_state_delta
            ref_continuity_scores.append(max(0.0, 1.0 - _cosine_distance(prev, curr)))
        ref_cont = _mean(ref_continuity_scores) if ref_continuity_scores else 1.0

        return {
            "transfer_enabled_count": enabled_count,
            "reference_transfer_count": reference_count,
            "adaptive_state_delta_enabled": round(enabled_delta_rms, 6),
            "adaptive_state_delta_reference": round(ref_delta_rms, 6),
            "signal_adaptation_delta": round(
                enabled_comparison["signal_parameter_drift_summary"].get("signal_emission_rate", 0.0), 6
            ),
            "late_active_delta": 0,  # Filled by CLI with actual active counts
            "generation_index_span_delta": enabled_span - ref_span,
            "trajectory_continuity_enabled": round(enabled_cont, 6),
            "trajectory_continuity_reference": round(ref_cont, 6),
        }

    def _empty_comparison(self) -> Dict[str, Any]:
        return {
            "transfer_count": 0,
            "generation_index_span": 0,
            "avg_transfer_delta": {},
            "max_transfer_delta": {},
            "avg_source_successor_similarity": 1.0,
            "adaptive_weight_drift_summary": {},
            "signal_parameter_drift_summary": {},
            "resource_response_drift_summary": {},
            "hazard_response_drift_summary": {},
            "trajectory_continuity_score": 1.0,
        }


def _mean(values: List[float]) -> float:
    return sum(values) / max(1, len(values))


def _rms(values: List[float]) -> float:
    if not values:
        return 0.0
    return math.sqrt(sum(v * v for v in values) / len(values))


def _rms_list(values: List[float]) -> float:
    return _rms(values)


def _avg_dict(dicts: List[Dict[str, float]]) -> Dict[str, float]:
    if not dicts:
        return {}
    keys = set()
    for d in dicts:
        keys.update(d.keys())
    result = {}
    for k in keys:
        vals = [d.get(k, 0.0) for d in dicts]
        result[k] = round(_mean(vals), 6)
    return result


def _max_abs_dict(dicts: List[Dict[str, float]]) -> Dict[str, float]:
    if not dicts:
        return {}
    keys = set()
    for d in dicts:
        keys.update(d.keys())
    result = {}
    for k in keys:
        vals = [abs(d.get(k, 0.0)) for d in dicts]
        result[k] = round(max(vals), 6)
    return result


def _cosine_distance(a: Dict[str, float], b: Dict[str, float]) -> float:
    """Cosine distance between two vectors represented as dicts."""
    keys = set(a.keys()) | set(b.keys())
    if not keys:
        return 0.0
    dot = sum(a.get(k, 0.0) * b.get(k, 0.0) for k in keys)
    norm_a = math.sqrt(sum(a.get(k, 0.0) ** 2 for k in keys))
    norm_b = math.sqrt(sum(b.get(k, 0.0) ** 2 for k in keys))
    if norm_a < 1e-12 or norm_b < 1e-12:
        return 0.0
    cos_sim = max(-1.0, min(1.0, dot / (norm_a * norm_b)))
    return 1.0 - cos_sim
