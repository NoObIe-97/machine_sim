"""Cross-variant neural controller comparison and sensitivity analysis."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _action_distribution_similarity(dist_a: Dict[str, int], dist_b: Dict[str, int]) -> float:
    """Compute similarity between two action distributions using cosine similarity."""
    all_actions = sorted(set(list(dist_a.keys()) + list(dist_b.keys())))
    if not all_actions:
        return 1.0
    vec_a = [dist_a.get(a, 0) for a in all_actions]
    vec_b = [dist_b.get(a, 0) for a in all_actions]
    return _cosine_similarity(vec_a, vec_b)


def _load_variant_summary(variant_dir: Path) -> Dict[str, Any]:
    """Load per-variant runtime summary from artifacts."""
    summary: Dict[str, Any] = {}

    summary_path = variant_dir / "neural_processing_summary.json"
    if summary_path.exists():
        summary.update(json.loads(summary_path.read_text()))

    config_path = variant_dir / "neural_controller_config.json"
    if config_path.exists():
        summary["neural_controller_config"] = json.loads(config_path.read_text())

    compare_path = variant_dir / "neural_vs_scalar_compare.json"
    if compare_path.exists():
        summary["neural_vs_scalar_compare"] = json.loads(compare_path.read_text())

    return summary


def _count_action_distribution(action_trace_path: Path) -> Dict[str, int]:
    """Count action occurrences from an action trace file."""
    counts: Dict[str, int] = {}
    if not action_trace_path.exists():
        return counts
    with open(action_trace_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                action = rec.get("action", "unknown")
                counts[action] = counts.get(action, 0) + 1
            except json.JSONDecodeError:
                continue
    return counts


def _neural_state_feature_vector(summary: Dict[str, Any]) -> List[float]:
    """Extract a compact feature vector from a variant's neural state summary."""
    features: List[float] = []

    # From neural processing summary
    features.append(float(summary.get("neural_state_trace_count", 0)))
    features.append(float(summary.get("neural_action_trace_count", 0)))
    features.append(float(summary.get("neural_plasticity_trace_count", 0)))
    features.append(float(summary.get("neural_successor_transfer_count", 0)))
    features.append(float(summary.get("final_active_count", 0)))

    # From controller config
    cfg = summary.get("neural_controller_config", {})
    features.append(float(cfg.get("hidden_size", 16)))
    features.append(float(cfg.get("plasticity_rate", 0.01)))
    features.append(1.0 if cfg.get("plasticity_enabled", True) else 0.0)

    return features


def build_similarity_matrix(
    variant_ids: List[str],
    variant_summaries: Dict[str, Dict[str, Any]],
    variant_action_dists: Dict[str, Dict[str, int]],
) -> Dict[str, Any]:
    """Build similarity matrices across variants."""
    n = len(variant_ids)

    # Action distribution similarity matrix
    action_sim: List[List[float]] = []
    for i in range(n):
        row = []
        for j in range(n):
            sim = _action_distribution_similarity(
                variant_action_dists.get(variant_ids[i], {}),
                variant_action_dists.get(variant_ids[j], {}),
            )
            row.append(round(sim, 6))
        action_sim.append(row)

    # Neural state similarity matrix
    state_vecs = {}
    for vid in variant_ids:
        state_vecs[vid] = _neural_state_feature_vector(variant_summaries.get(vid, {}))

    state_sim: List[List[float]] = []
    for i in range(n):
        row = []
        for j in range(n):
            sim = _cosine_similarity(
                state_vecs.get(variant_ids[i], []),
                state_vecs.get(variant_ids[j], []),
            )
            row.append(round(sim, 6))
        state_sim.append(row)

    # Runtime metric similarity (based on active count, transfer count)
    runtime_vecs: Dict[str, List[float]] = {}
    for vid in variant_ids:
        s = variant_summaries.get(vid, {})
        runtime_vecs[vid] = [
            float(s.get("final_active_count", 0)),
            float(s.get("neural_successor_transfer_count", 0)),
            float(s.get("neural_plasticity_trace_count", 0)),
        ]

    runtime_sim: List[List[float]] = []
    for i in range(n):
        row = []
        for j in range(n):
            sim = _cosine_similarity(
                runtime_vecs.get(variant_ids[i], []),
                runtime_vecs.get(variant_ids[j], []),
            )
            row.append(round(sim, 6))
        runtime_sim.append(row)

    # Check for nontrivial off-diagonal differences
    nontrivial = False
    for i in range(n):
        for j in range(i + 1, n):
            if action_sim[i][j] < 0.99 or state_sim[i][j] < 0.99 or runtime_sim[i][j] < 0.99:
                nontrivial = True
                break

    return {
        "variant_ids": variant_ids,
        "similarity_matrix": {
            "action_distribution": action_sim,
            "neural_state": state_sim,
            "runtime_metric": runtime_sim,
        },
        "nontrivial_off_diagonal_difference_detected": nontrivial,
    }


def compute_sensitivity_summary(
    variant_ids: List[str],
    variant_defs: List[Dict[str, Any]],
    variant_summaries: Dict[str, Dict[str, Any]],
    variant_action_dists: Dict[str, Dict[str, int]],
) -> Dict[str, Any]:
    """Compute parameter sensitivity summary across variants."""
    # Find the M17 baseline variant
    baseline_id = None
    for vd in variant_defs:
        if vd.get("neural_hidden_size") == 16 and vd.get("neural_plasticity_rate") == 0.01 and vd.get("neural_plasticity_enabled", True):
            baseline_id = vd["id"]
            break
    if baseline_id is None and len(variant_ids) > 1:
        baseline_id = variant_ids[1]  # fallback to second variant (first neural)

    baseline_summary = variant_summaries.get(baseline_id, {}) if baseline_id else {}
    baseline_actions = variant_action_dists.get(baseline_id, {}) if baseline_id else {}

    # Compute sensitivity by parameter
    varied_params: List[str] = ["hidden_size", "plasticity_rate", "plasticity_enabled"]
    sensitivity_scores: Dict[str, float] = {}
    hidden_size_effects: List[Dict[str, Any]] = []
    plasticity_effects: List[Dict[str, Any]] = []

    for vid in variant_ids:
        if vid == baseline_id:
            continue
        vd = next((v for v in variant_defs if v["id"] == vid), {})
        vs = variant_summaries.get(vid, {})
        va = variant_action_dists.get(vid, {})

        # Compute delta from baseline
        action_sim = _action_distribution_similarity(baseline_actions, va)
        active_delta = abs(vs.get("final_active_count", 0) - baseline_summary.get("final_active_count", 0))
        transfer_delta = abs(vs.get("neural_successor_transfer_count", 0) - baseline_summary.get("neural_successor_transfer_count", 0))
        plasticity_delta = abs(vs.get("neural_plasticity_trace_count", 0) - baseline_summary.get("neural_plasticity_trace_count", 0))

        # Overall variant sensitivity (bounded 0-1)
        variant_sensitivity = min(1.0, (1.0 - action_sim) * 0.5 + active_delta * 0.1 + transfer_delta * 0.1 + plasticity_delta * 0.001)

        # Attribute to specific parameters
        hidden_diff = vd.get("neural_hidden_size", 16) - 16
        rate_diff = vd.get("neural_plasticity_rate", 0.01) - 0.01
        plasticity_disabled = not vd.get("neural_plasticity_enabled", True)

        if hidden_diff != 0:
            sensitivity_scores["hidden_size"] = max(sensitivity_scores.get("hidden_size", 0.0), min(1.0, abs(hidden_diff) / 32.0 * variant_sensitivity))
            hidden_size_effects.append({
                "variant_id": vid,
                "hidden_size": vd.get("neural_hidden_size", 16),
                "sensitivity": round(variant_sensitivity, 6),
                "action_similarity_to_baseline": round(action_sim, 6),
                "active_count_delta": active_delta,
            })

        if rate_diff != 0 or plasticity_disabled:
            rate_sensitivity = min(1.0, abs(rate_diff) / 0.05 * variant_sensitivity if not plasticity_disabled else variant_sensitivity)
            sensitivity_scores["plasticity_rate"] = max(sensitivity_scores.get("plasticity_rate", 0.0), rate_sensitivity)
            plasticity_effects.append({
                "variant_id": vid,
                "plasticity_rate": vd.get("neural_plasticity_rate", 0.01),
                "plasticity_enabled": vd.get("neural_plasticity_enabled", True),
                "sensitivity": round(variant_sensitivity, 6),
                "action_similarity_to_baseline": round(action_sim, 6),
                "plasticity_event_count_delta": plasticity_delta,
            })

    # Determine most/least sensitive
    if sensitivity_scores:
        most_sensitive = max(sensitivity_scores, key=sensitivity_scores.get)
        least_sensitive = min(sensitivity_scores, key=sensitivity_scores.get)
    else:
        most_sensitive = "none"
        least_sensitive = "none"

    nontrivial_effect = any(v > 0.01 for v in sensitivity_scores.values())

    return {
        "variant_count": len(variant_ids),
        "varied_parameters": varied_params,
        "sensitivity_score_by_parameter": {k: round(v, 6) for k, v in sensitivity_scores.items()},
        "most_sensitive_parameters": [most_sensitive] if sensitivity_scores else [],
        "least_sensitive_parameters": [least_sensitive] if sensitivity_scores else [],
        "plasticity_effect_summary": plasticity_effects,
        "hidden_size_effect_summary": hidden_size_effects,
        "nontrivial_controller_parameter_effect_detected": nontrivial_effect,
    }
