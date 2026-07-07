"""Adaptive trajectory compression and offline analysis.

Read-only post-processing module that compresses multi-generation
adaptive-state transfer traces into bounded segments and computes
offline replay metrics and cross-trajectory similarity.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class CompressedSegment:
    """A bounded compressed segment of adaptive trajectory."""
    segment_index: int
    start_tick: int
    end_tick: int
    generation_index_min: int
    generation_index_max: int
    transfer_count: int
    avg_adaptive_state: Dict[str, float]
    adaptive_state_range: Dict[str, float]
    avg_transfer_delta: Dict[str, float]
    max_transfer_delta: Dict[str, float]
    action_distribution_summary: Dict[str, int]
    signal_parameter_summary: Dict[str, float]
    resource_response_summary: Dict[str, float]
    hazard_response_summary: Dict[str, float]
    feedback_event_summary: Dict[str, float]
    segment_signature: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "segment_index": self.segment_index,
            "start_tick": self.start_tick,
            "end_tick": self.end_tick,
            "generation_index_min": self.generation_index_min,
            "generation_index_max": self.generation_index_max,
            "transfer_count": self.transfer_count,
            "avg_adaptive_state": self.avg_adaptive_state,
            "adaptive_state_range": self.adaptive_state_range,
            "avg_transfer_delta": self.avg_transfer_delta,
            "max_transfer_delta": self.max_transfer_delta,
            "action_distribution_summary": self.action_distribution_summary,
            "signal_parameter_summary": self.signal_parameter_summary,
            "resource_response_summary": self.resource_response_summary,
            "hazard_response_summary": self.hazard_response_summary,
            "feedback_event_summary": self.feedback_event_summary,
            "segment_signature": self.segment_signature,
        }


class AdaptiveTrajectoryCompressor:
    """Compresses multi-generation adaptive-state traces into bounded segments.

    Read-only post-processor. Does not influence unit action selection.
    """

    def __init__(self, max_segments: int = 64) -> None:
        self.max_segments = max_segments
        self._segments: List[CompressedSegment] = []
        self._source_records: List[Dict[str, Any]] = []
        self._action_trace: List[Dict[str, Any]] = []
        self._feedback_trace: List[Dict[str, Any]] = []
        self._adaptive_state_trace: List[Dict[str, Any]] = []

    def load_transfer_records(self, records: List[Dict[str, Any]]) -> None:
        """Load generation-adaptive-state transfer records."""
        self._source_records = list(records)

    def load_action_trace(self, trace: List[Dict[str, Any]]) -> None:
        """Load action distribution trace records."""
        self._action_trace = list(trace)

    def load_feedback_trace(self, trace: List[Dict[str, Any]]) -> None:
        """Load local feedback trace records."""
        self._feedback_trace = list(trace)

    def load_adaptive_state_trace(self, trace: List[Dict[str, Any]]) -> None:
        """Load adaptive state snapshot trace records."""
        self._adaptive_state_trace = list(trace)

    def compress(self) -> List[CompressedSegment]:
        """Compress loaded traces into bounded segments.

        Divides transfer records into segments (up to max_segments),
        computing aggregate statistics for each segment.
        """
        if not self._source_records:
            self._segments = []
            return self._segments

        n_records = len(self._source_records)
        # Use fewer segments when there are few records to ensure compression
        n_segments = min(self.max_segments, max(1, min(n_records, max(2, n_records // 2))))

        # Divide records into segments
        seg_size = max(1, n_records // n_segments)
        segments = []

        for seg_idx in range(n_segments):
            start = seg_idx * seg_size
            end = min(start + seg_size, n_records)
            if seg_idx == n_segments - 1:
                end = n_records  # last segment gets remainder
            if start >= n_records:
                break

            seg_records = self._source_records[start:end]
            segment = self._build_segment(seg_idx, seg_records)
            segments.append(segment)

        self._segments = segments
        return self._segments

    def _build_segment(self, seg_idx: int, records: List[Dict[str, Any]]) -> CompressedSegment:
        """Build a compressed segment from a collection of transfer records."""
        ticks = [r.get("tick", 0) for r in records]
        start_tick = min(ticks)
        end_tick = max(ticks)

        gen_mins = [r.get("source_generation_index", 0) for r in records]
        gen_maxs = [r.get("successor_generation_index", 0) for r in records]
        gen_index_min = min(gen_mins + gen_maxs)
        gen_index_max = max(gen_mins + gen_maxs)

        # Aggregate adaptive states
        all_source_states = [r.get("source_adaptive_state_summary", {}) for r in records]
        all_successor_states = [r.get("successor_adaptive_state_summary", {}) for r in records]
        all_deltas = [r.get("adaptive_state_delta", {}) for r in records]

        avg_state = _avg_dict(all_source_states)
        state_range = _range_dict(all_source_states)
        avg_delta = _avg_dict(all_deltas)
        max_delta = _max_abs_dict(all_deltas)

        # Signal parameters from adaptive state
        signal_keys = [k for k in avg_state if "signal" in k]
        signal_summary = {k: avg_state.get(k, 0.0) for k in signal_keys}

        # Resource response from deltas
        resource_keys = [k for k in avg_delta if "resource" in k or "extract" in k]
        resource_summary = {k: avg_delta.get(k, 0.0) for k in resource_keys}

        # Hazard response from deltas
        hazard_keys = [k for k in avg_delta if "hazard" in k]
        hazard_summary = {k: avg_delta.get(k, 0.0) for k in hazard_keys}

        # Action distribution summary for this segment's tick range
        action_dist: Dict[str, int] = {}
        for a in self._action_trace:
            if start_tick <= a.get("tick", 0) <= end_tick:
                act = a.get("action", "unknown")
                action_dist[act] = action_dist.get(act, 0) + 1

        # Feedback event summary for this segment's tick range
        feedback_summary: Dict[str, float] = {}
        for f in self._feedback_trace:
            if start_tick <= f.get("tick", 0) <= end_tick:
                for k in ["power_delta", "hazard_exposure", "resource_extracted",
                          "signal_observed", "movement_blocked"]:
                    val = f.get(k, 0.0)
                    if abs(val) > 0.01:
                        feedback_summary[k] = feedback_summary.get(k, 0.0) + val

        # Segment signature: deterministic hash of key metrics
        sig_data = json.dumps({
            "gen_min": gen_index_min, "gen_max": gen_index_max,
            "n_transfers": len(records),
            "avg_delta": {k: round(v, 6) for k, v in avg_delta.items()},
        }, sort_keys=True)
        signature = hashlib.sha256(sig_data.encode()).hexdigest()[:16]

        return CompressedSegment(
            segment_index=seg_idx,
            start_tick=start_tick,
            end_tick=end_tick,
            generation_index_min=gen_index_min,
            generation_index_max=gen_index_max,
            transfer_count=len(records),
            avg_adaptive_state=avg_state,
            adaptive_state_range=state_range,
            avg_transfer_delta=avg_delta,
            max_transfer_delta=max_delta,
            action_distribution_summary=action_dist,
            signal_parameter_summary=signal_summary,
            resource_response_summary=resource_summary,
            hazard_response_summary=hazard_summary,
            feedback_event_summary=feedback_summary,
            segment_signature=signature,
        )

    def get_segments(self) -> List[CompressedSegment]:
        return list(self._segments)

    def get_trajectory_signature(self) -> Dict[str, Any]:
        """Compute an aggregate trajectory signature from all segments."""
        if not self._segments:
            return {"segment_count": 0, "signature_hash": ""}

        all_sigs = [s.segment_signature for s in self._segments]
        combined = "|".join(all_sigs)
        hash_val = hashlib.sha256(combined.encode()).hexdigest()[:32]

        # Aggregate across segments
        total_transfers = sum(s.transfer_count for s in self._segments)
        all_gen_mins = [s.generation_index_min for s in self._segments]
        all_gen_maxs = [s.generation_index_max for s in self._segments]

        return {
            "segment_count": len(self._segments),
            "signature_hash": hash_val,
            "total_transfer_count": total_transfers,
            "generation_index_span": max(all_gen_maxs) - min(all_gen_mins) + 1 if all_gen_mins else 0,
            "avg_transfer_delta_rms": _mean([_rms_dict(s.avg_transfer_delta) for s in self._segments]),
        }

    def get_replay_metrics(self) -> Dict[str, Any]:
        """Compute offline replay metrics from compressed segments.

        Estimates how well compressed segments approximate the source statistics.
        """
        if not self._segments or not self._source_records:
            return self._empty_replay_metrics()

        # Source-level statistics
        source_deltas = [r.get("adaptive_state_delta", {}) for r in self._source_records]
        source_avg_delta = _avg_dict(source_deltas)

        # Segment-level averages (what compression preserves)
        seg_avg_deltas = [s.avg_transfer_delta for s in self._segments]

        # Replay error: difference between source stats and segment-preserved stats
        # For each segment, compute how much its avg deviates from the source avg
        per_seg_errors = []
        for seg_avg in seg_avg_deltas:
            error_keys = set(source_avg_delta.keys()) | set(seg_avg.keys())
            errors = []
            for k in error_keys:
                errors.append(abs(source_avg_delta.get(k, 0.0) - seg_avg.get(k, 0.0)))
            per_seg_errors.append(_mean(errors) if errors else 0.0)

        avg_replay_error = _mean(per_seg_errors) if per_seg_errors else 0.0
        max_replay_error = max(per_seg_errors) if per_seg_errors else 0.0

        # Adaptive state replay error: per-key deviation
        source_states = [r.get("source_adaptive_state_summary", {}) for r in self._source_records]
        source_avg_state = _avg_dict(source_states)
        seg_avg_states = [s.avg_adaptive_state for s in self._segments]
        state_errors = []
        for seg_s in seg_avg_states:
            keys = set(source_avg_state.keys()) | set(seg_s.keys())
            errs = [abs(source_avg_state.get(k, 0.0) - seg_s.get(k, 0.0)) for k in keys]
            state_errors.append(_mean(errs) if errs else 0.0)
        state_replay_error = _mean(state_errors) if state_errors else 0.0

        # Action distribution replay error
        total_source_actions: Dict[str, int] = {}
        for a in self._action_trace:
            act = a.get("action", "unknown")
            total_source_actions[act] = total_source_actions.get(act, 0) + 1
        total_seg_actions: Dict[str, int] = {}
        for s in self._segments:
            for act, cnt in s.action_distribution_summary.items():
                total_seg_actions[act] = total_seg_actions.get(act, 0) + cnt
        action_keys = set(total_source_actions.keys()) | set(total_seg_actions.keys())
        if action_keys:
            source_total = sum(total_source_actions.values()) or 1
            seg_total = sum(total_seg_actions.values()) or 1
            action_errors = []
            for k in action_keys:
                src_pct = total_source_actions.get(k, 0) / source_total
                seg_pct = total_seg_actions.get(k, 0) / seg_total
                action_errors.append(abs(src_pct - seg_pct))
            action_replay_error = _mean(action_errors)
        else:
            action_replay_error = 0.0

        # Transfer delta replay error
        source_max_deltas = _max_abs_dict(source_deltas)
        seg_max_deltas_list = [s.max_transfer_delta for s in self._segments]
        seg_avg_max = _avg_dict(seg_max_deltas_list)
        td_keys = set(source_max_deltas.keys()) | set(seg_avg_max.keys())
        td_errors = [abs(source_max_deltas.get(k, 0.0) - seg_avg_max.get(k, 0.0)) for k in td_keys]
        transfer_delta_replay_error = _mean(td_errors) if td_errors else 0.0

        # Stability: low variance across segments
        seg_error_variance = _variance(per_seg_errors) if len(per_seg_errors) > 1 else 0.0
        replay_stability = max(0.0, 1.0 - seg_error_variance)

        return {
            "replay_window_count": len(self._segments),
            "avg_trajectory_replay_error": round(avg_replay_error, 6),
            "max_trajectory_replay_error": round(max_replay_error, 6),
            "adaptive_state_replay_error": round(state_replay_error, 6),
            "action_distribution_replay_error": round(action_replay_error, 6),
            "transfer_delta_replay_error": round(transfer_delta_replay_error, 6),
            "replay_stability_score": round(replay_stability, 6),
        }

    def get_compressed_size_estimate(self) -> Dict[str, Any]:
        """Estimate compressed artifact sizes."""
        if not self._segments:
            return {
                "source_trace_record_count": len(self._source_records),
                "compressed_segment_count": 0,
                "source_artifact_size_bytes": 0,
                "compressed_artifact_size_bytes": 0,
                "trajectory_compression_ratio": 1.0,
                "bounded_segment_limit": self.max_segments,
            }

        # Estimate source size (JSONL records)
        source_bytes = sum(len(json.dumps(r).encode()) for r in self._source_records)

        # Estimate compressed size
        compressed_bytes = sum(len(json.dumps(s.to_dict()).encode()) for s in self._segments)

        ratio = compressed_bytes / max(1, source_bytes)

        return {
            "source_trace_record_count": len(self._source_records),
            "compressed_segment_count": len(self._segments),
            "source_artifact_size_bytes": source_bytes,
            "compressed_artifact_size_bytes": compressed_bytes,
            "trajectory_compression_ratio": round(ratio, 6),
            "bounded_segment_limit": self.max_segments,
        }

    def _empty_replay_metrics(self) -> Dict[str, Any]:
        return {
            "replay_window_count": 0,
            "avg_trajectory_replay_error": 0.0,
            "max_trajectory_replay_error": 0.0,
            "adaptive_state_replay_error": 0.0,
            "action_distribution_replay_error": 0.0,
            "transfer_delta_replay_error": 0.0,
            "replay_stability_score": 1.0,
        }


def compare_trajectories(
    primary: AdaptiveTrajectoryCompressor,
    comparison: AdaptiveTrajectoryCompressor,
) -> Dict[str, Any]:
    """Compare compressed trajectory signatures from two compressors."""
    p_sig = primary.get_trajectory_signature()
    c_sig = comparison.get_trajectory_signature()

    p_segs = primary.get_segments()
    c_segs = comparison.get_segments()

    # Signature delta: difference in aggregate metrics
    sig_delta = abs(p_sig.get("avg_transfer_delta_rms", 0) - c_sig.get("avg_transfer_delta_rms", 0))

    # Adaptive state similarity: cosine similarity of avg states across segments
    p_avg_states = [s.avg_adaptive_state for s in p_segs]
    c_avg_states = [s.avg_adaptive_state for s in c_segs]
    p_state_agg = _avg_dict(p_avg_states) if p_avg_states else {}
    c_state_agg = _avg_dict(c_avg_states) if c_avg_states else {}
    state_sim = 1.0 - _cosine_distance(p_state_agg, c_state_agg)

    # Transfer delta similarity
    p_avg_deltas = [s.avg_transfer_delta for s in p_segs]
    c_avg_deltas = [s.avg_transfer_delta for s in c_segs]
    p_delta_agg = _avg_dict(p_avg_deltas) if p_avg_deltas else {}
    c_delta_agg = _avg_dict(c_avg_deltas) if c_avg_deltas else {}
    delta_sim = 1.0 - _cosine_distance(p_delta_agg, c_delta_agg)

    # Action distribution similarity
    p_actions: Dict[str, int] = {}
    c_actions: Dict[str, int] = {}
    for s in p_segs:
        for k, v in s.action_distribution_summary.items():
            p_actions[k] = p_actions.get(k, 0) + v
    for s in c_segs:
        for k, v in s.action_distribution_summary.items():
            c_actions[k] = c_actions.get(k, 0) + v
    action_sim = 1.0 - _cosine_distance(
        {k: float(v) for k, v in p_actions.items()},
        {k: float(v) for k, v in c_actions.items()},
    )

    # Signal response similarity
    p_signals = [s.signal_parameter_summary for s in p_segs]
    c_signals = [s.signal_parameter_summary for s in c_segs]
    p_sig_agg = _avg_dict(p_signals) if p_signals else {}
    c_sig_agg = _avg_dict(c_signals) if c_signals else {}
    sig_sim = 1.0 - _cosine_distance(p_sig_agg, c_sig_agg)

    # Overall similarity
    similarities = [state_sim, delta_sim, action_sim, sig_sim]
    overall = _mean(similarities)

    # Nontrivial difference: overall similarity < 0.99
    nontrivial = overall < 0.99

    return {
        "primary_segment_count": len(p_segs),
        "comparison_segment_count": len(c_segs),
        "trajectory_signature_delta": round(sig_delta, 6),
        "adaptive_state_similarity": round(state_sim, 6),
        "transfer_delta_similarity": round(delta_sim, 6),
        "action_distribution_similarity": round(action_sim, 6),
        "signal_response_similarity": round(sig_sim, 6),
        "overall_trajectory_similarity": round(overall, 6),
        "nontrivial_difference_detected": nontrivial,
    }


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Load a JSONL file into a list of dicts."""
    if not path.exists():
        return []
    records = []
    for line in path.read_text().strip().split("\n"):
        if line.strip():
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


# --- Helper functions ---

def _mean(values: List[float]) -> float:
    return sum(values) / max(1, len(values))


def _variance(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    return sum((v - m) ** 2 for v in values) / len(values)


def _rms(values: List[float]) -> float:
    if not values:
        return 0.0
    return math.sqrt(sum(v * v for v in values) / len(values))


def _rms_dict(d: Dict[str, float]) -> float:
    return _rms(list(d.values()))


def _avg_dict(dicts: List[Dict[str, Any]]) -> Dict[str, float]:
    if not dicts:
        return {}
    keys = set()
    for d in dicts:
        keys.update(d.keys())
    result = {}
    for k in keys:
        vals = [float(d.get(k, 0.0)) for d in dicts]
        result[k] = round(_mean(vals), 6)
    return result


def _range_dict(dicts: List[Dict[str, Any]]) -> Dict[str, float]:
    if not dicts:
        return {}
    keys = set()
    for d in dicts:
        keys.update(d.keys())
    result = {}
    for k in keys:
        vals = [float(d.get(k, 0.0)) for d in dicts]
        result[k] = round(max(vals) - min(vals), 6)
    return result


def _max_abs_dict(dicts: List[Dict[str, Any]]) -> Dict[str, float]:
    if not dicts:
        return {}
    keys = set()
    for d in dicts:
        keys.update(d.keys())
    result = {}
    for k in keys:
        vals = [abs(float(d.get(k, 0.0))) for d in dicts]
        result[k] = round(max(vals), 6)
    return result


def _cosine_distance(a: Dict[str, float], b: Dict[str, float]) -> float:
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
