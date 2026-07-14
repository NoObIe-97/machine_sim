"""Read-only neural architecture lineage and distribution analysis."""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List


def analyze_architecture_lineage(
    transfer_trace: List[Dict[str, Any]],
    distribution_trace: List[Dict[str, Any]],
    cost_trace: List[Dict[str, Any]],
    initial_descriptors: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Produce a read-only summary of architecture lineage and distribution.

    This analyzer does not mutate any runtime state.
    """
    # Transition counts
    increase_count = 0
    decrease_count = 0
    unchanged_count = 0
    total_transitions = len(transfer_trace)

    for t in transfer_trace:
        delta = t.get("hidden_size_delta", 0)
        if delta > 0:
            increase_count += 1
        elif delta < 0:
            decrease_count += 1
        else:
            unchanged_count += 1

    # Distinct architectures observed
    all_arch_ids = set()
    for d in initial_descriptors:
        all_arch_ids.add(d.get("architecture_id", ""))
    for t in transfer_trace:
        all_arch_ids.add(t.get("source_architecture_id", ""))
        all_arch_ids.add(t.get("successor_architecture_id", ""))

    # Hidden size distribution over time
    hidden_size_over_time = []
    for snap in distribution_trace:
        hidden_size_over_time.append({
            "tick": snap.get("tick", 0),
            "mean_hidden_size": snap.get("mean_hidden_size", 0),
            "distinct_count": snap.get("distinct_architecture_count", 0),
        })

    # Processing cost by hidden size bin
    cost_by_hidden: Dict[int, float] = {}
    for c in cost_trace:
        hs = c.get("hidden_size", 0)
        cost = c.get("processing_cost", 0)
        cost_by_hidden[hs] = cost_by_hidden.get(hs, 0.0) + cost

    # Successor production count by hidden size
    succ_by_hidden: Dict[int, int] = {}
    for t in transfer_trace:
        hs = t.get("successor_hidden_size", 0)
        succ_by_hidden[hs] = succ_by_hidden.get(hs, 0) + 1

    return {
        "total_transitions": total_transitions,
        "increase_transition_count": increase_count,
        "decrease_transition_count": decrease_count,
        "unchanged_transition_count": unchanged_count,
        "distinct_architecture_count": len(all_arch_ids),
        "hidden_size_distribution_over_time": hidden_size_over_time,
        "processing_cost_by_hidden_size": {str(k): round(v, 4) for k, v in cost_by_hidden.items()},
        "successor_count_by_hidden_size": succ_by_hidden,
        "architecture_extinction_events": _find_extinctions(distribution_trace),
    }


def _find_extinctions(distribution_trace: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Detect architecture extinction events (a hidden size that was present then disappeared)."""
    seen_sizes: set = set()
    extinctions = []
    for snap in distribution_trace:
        hs_hist = snap.get("hidden_size_histogram", {})
        current_sizes = set(int(k) for k in hs_hist.keys())
        vanished = seen_sizes - current_sizes
        for s in vanished:
            extinctions.append({
                "tick": snap.get("tick", 0),
                "extinct_hidden_size": s,
            })
        seen_sizes |= current_sizes
    return extinctions


def build_fixed_vs_variable_comparison(
    fixed_summary: Dict[str, Any],
    variable_summary: Dict[str, Any],
    fixed_transfer_count: int,
    variable_transfer_count: int,
    variable_increase: int,
    variable_decrease: int,
    variable_unchanged: int,
    fixed_descriptor_count: int,
    variable_descriptor_count: int,
    nontrivial: bool,
) -> Dict[str, Any]:
    """Build the fixed-vs-variable comparison artifact."""
    return {
        "fixed_run_ticks": fixed_summary.get("run_ticks", 0),
        "variable_run_ticks": variable_summary.get("run_ticks", 0),
        "fixed_final_active_count": fixed_summary.get("final_active_count", 0),
        "variable_final_active_count": variable_summary.get("final_active_count", 0),
        "fixed_successor_count": fixed_transfer_count,
        "variable_successor_count": variable_transfer_count,
        "fixed_total_processing_cost": fixed_summary.get("total_processing_cost", 0),
        "variable_total_processing_cost": variable_summary.get("total_processing_cost", 0),
        "fixed_total_fabrication_cost": fixed_summary.get("total_fabrication_cost", 0),
        "variable_total_fabrication_cost": variable_summary.get("total_fabrication_cost", 0),
        "fixed_architecture_descriptor_count": fixed_descriptor_count,
        "variable_architecture_descriptor_count": variable_descriptor_count,
        "variable_increase_transition_count": variable_increase,
        "variable_decrease_transition_count": variable_decrease,
        "variable_unchanged_transition_count": variable_unchanged,
        "architecture_distribution_delta_summary": {
            "hidden_size_range_delta": abs(
                variable_summary.get("max_hidden_size", 0) - fixed_summary.get("max_hidden_size", 0)),
        },
        "runtime_metric_delta_summary": {
            "active_count_delta": (variable_summary.get("final_active_count", 0)
                                   - fixed_summary.get("final_active_count", 0)),
        },
        "nontrivial_architecture_variation_detected": nontrivial,
    }
