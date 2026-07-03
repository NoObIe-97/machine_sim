"""Compressed summary cross-unit consistency and windowed retention stability analysis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple
from itertools import combinations


@dataclass
class SummaryConsistencySummary:
    """Full M13 summary."""
    unit_summary_count: int = 0
    unit_pair_count: int = 0
    avg_unit_summary_delta: float = 0.0
    max_unit_summary_delta: float = 0.0
    avg_power_ratio_delta: float = 0.0
    avg_sensor_health_delta: float = 0.0
    avg_signal_trace_delta: float = 0.0
    avg_replay_error_delta: float = 0.0
    summary_consistency_score: float = 0.0
    retention_window_count: int = 0
    retention_window_span: int = 0
    avg_retention_variance: float = 0.0
    max_retention_variance: float = 0.0
    retention_stability_score: float = 0.0
    retention_drop_rate: float = 0.0
    compression_window_count: int = 0
    avg_compression_ratio: float = 0.0
    compression_ratio_delta: float = 0.0
    compression_ratio_variance: float = 0.0
    compression_convergence_score: float = 0.0
    compression_convergence_window_span: int = 0
    cross_generation_envelope_count: int = 0
    generation_index_span: int = 0
    generation_envelope_width: float = 0.0
    generation_delta_floor: float = 0.0
    generation_delta_ceiling: float = 0.0
    generation_envelope_stability: float = 0.0
    combined_window_count: int = 0
    combined_consistency_score: float = 0.0
    combined_stability_score: float = 0.0
    combined_delta_score: float = 0.0
    combined_record_count: int = 0


class SummaryConsistencyAnalyzer:
    """Analyzes cross-unit diagnostic summary consistency and retention stability."""

    def __init__(self, enabled: bool = True, max_records: int = 100,
                 window: int = 50, sample_interval: int = 5) -> None:
        self.enabled = enabled
        self.max_records = max_records
        self.window = window
        self.sample_interval = sample_interval
        self._unit_summaries: List[Dict[str, Any]] = []
        self._retention_records: List[Dict[str, Any]] = []
        self._compression_ratios: List[float] = []
        self._generation_deltas: List[Dict[str, Any]] = []

    def record_unit_summary(self, data: Dict[str, Any]) -> None:
        """Record a per-unit diagnostic summary."""
        self._unit_summaries.append(data)
        if len(self._unit_summaries) > self.max_records:
            self._unit_summaries = self._unit_summaries[-self.max_records:]

    def record_retention(self, data: Dict[str, Any]) -> None:
        """Record a retention window observation."""
        self._retention_records.append(data)
        if len(self._retention_records) > self.max_records:
            self._retention_records = self._retention_records[-self.max_records:]

    def record_compression_ratio(self, ratio: float) -> None:
        """Record a compression ratio observation."""
        self._compression_ratios.append(ratio)
        if len(self._compression_ratios) > self.max_records:
            self._compression_ratios = self._compression_ratios[-self.max_records:]

    def record_generation_delta(self, data: Dict[str, Any]) -> None:
        """Record a generation-indexed delta observation."""
        self._generation_deltas.append(data)
        if len(self._generation_deltas) > self.max_records:
            self._generation_deltas = self._generation_deltas[-self.max_records:]

    def analyze(self) -> SummaryConsistencySummary:
        """Compute full M13 summary."""
        # Cross-unit summary comparison
        units = self._unit_summaries
        unit_count = len(units)
        pair_count = 0
        deltas: List[float] = []
        pwr_deltas: List[float] = []
        sen_deltas: List[float] = []
        sig_deltas: List[float] = []
        rep_deltas: List[float] = []

        if unit_count >= 2:
            for a, b in combinations(units, 2):
                pair_count += 1
                pwr_d = abs(a.get("power_ratio", 0.0) - b.get("power_ratio", 0.0))
                sen_d = abs(a.get("sensor_health", 0.0) - b.get("sensor_health", 0.0))
                sig_raw = abs(a.get("signal_count", 0.0) - b.get("signal_count", 0.0))
                sig_d = min(1.0, sig_raw / 100.0)
                rep_d = abs(a.get("replay_error", 0.0) - b.get("replay_error", 0.0))
                overall = (pwr_d + sen_d + sig_d + rep_d) / 4.0
                deltas.append(overall)
                pwr_deltas.append(pwr_d)
                sen_deltas.append(sen_d)
                sig_deltas.append(sig_raw)
                rep_deltas.append(rep_d)

        avg_delta = sum(deltas) / len(deltas) if deltas else 0.0
        max_delta = max(deltas) if deltas else 0.0
        avg_pwr = sum(pwr_deltas) / len(pwr_deltas) if pwr_deltas else 0.0
        avg_sen = sum(sen_deltas) / len(sen_deltas) if sen_deltas else 0.0
        avg_sig = sum(sig_deltas) / len(sig_deltas) if sig_deltas else 0.0
        avg_rep = sum(rep_deltas) / len(rep_deltas) if rep_deltas else 0.0
        consistency = max(0.0, 1.0 - min(1.0, avg_delta)) if pair_count >= 1 else 0.0

        # Windowed retention stability
        ret = self._retention_records
        ret_count = len(ret)
        ret_span = 0
        avg_var = 0.0
        max_var = 0.0
        ret_stability = 0.0
        drop_rate = 0.0

        if ret_count > 0:
            ticks = [r.get("tick", 0) for r in ret]
            ret_span = max(ticks) - min(ticks) if len(ticks) > 1 else 0
            variances = [r.get("variance", 0.0) for r in ret]
            if variances:
                avg_var = sum(variances) / len(variances)
                max_var = max(variances)
            ret_stability = max(0.0, 1.0 - min(1.0, (max_var ** 0.5) / 20.0)) if variances else 0.0
            drops = [r.get("dropped", 0) for r in ret]
            total_records = [r.get("total", 0) for r in ret]
            if total_records:
                total_d = sum(drops)
                total_t = sum(total_records)
                drop_rate = total_d / max(1, total_t)

        # Compression ratio convergence
        ratios = self._compression_ratios
        comp_count = len(ratios)
        avg_ratio = 0.0
        comp_delta = 0.0
        comp_var = 0.0
        comp_score = 0.0
        comp_span = 0

        if comp_count > 0:
            avg_ratio = sum(ratios) / len(ratios)
            if len(ratios) > 1:
                comp_delta = max(ratios) - min(ratios)
                comp_span = len(ratios)
                mean_r = avg_ratio
                comp_var = sum((r - mean_r) ** 2 for r in ratios) / len(ratios)
            comp_score = 1.0 - comp_delta if comp_count > 1 else 1.0

        # Cross-generation diagnostic envelope
        gen_deltas = self._generation_deltas
        gen_count = len(gen_deltas)
        gen_span = 0
        gen_width = 0.0
        gen_floor = 0.0
        gen_ceiling = 0.0
        gen_stability = 0.0

        if gen_count > 1:
            gens = [d.get("generation_index", 0) for d in gen_deltas]
            gen_span = max(gens) - min(gens)
            delta_vals = [d.get("delta", 0.0) for d in gen_deltas]
            gen_floor = min(delta_vals)
            gen_ceiling = max(delta_vals)
            gen_width = gen_ceiling - gen_floor
            mean_d = sum(delta_vals) / len(delta_vals)
            gen_stability = 1.0 - gen_width if delta_vals else 0.0

        # Combined stability
        combined_windows = max(comp_count, ret_count, gen_count)
        combined_consistency = consistency
        combined_stability = max(0.0, (ret_stability + comp_score + gen_stability) / 3.0)
        combined_delta = (avg_delta + avg_var + comp_delta) / 3.0
        combined_records = unit_count + ret_count + comp_count + gen_count

        return SummaryConsistencySummary(
            unit_summary_count=unit_count,
            unit_pair_count=pair_count,
            avg_unit_summary_delta=avg_delta,
            max_unit_summary_delta=max_delta,
            avg_power_ratio_delta=avg_pwr,
            avg_sensor_health_delta=avg_sen,
            avg_signal_trace_delta=avg_sig,
            avg_replay_error_delta=avg_rep,
            summary_consistency_score=consistency,
            retention_window_count=ret_count,
            retention_window_span=ret_span,
            avg_retention_variance=avg_var,
            max_retention_variance=max_var,
            retention_stability_score=ret_stability,
            retention_drop_rate=drop_rate,
            compression_window_count=comp_count,
            avg_compression_ratio=avg_ratio,
            compression_ratio_delta=comp_delta,
            compression_ratio_variance=comp_var,
            compression_convergence_score=comp_score,
            compression_convergence_window_span=comp_span,
            cross_generation_envelope_count=gen_count,
            generation_index_span=gen_span,
            generation_envelope_width=gen_width,
            generation_delta_floor=gen_floor,
            generation_delta_ceiling=gen_ceiling,
            generation_envelope_stability=gen_stability,
            combined_window_count=combined_windows,
            combined_consistency_score=combined_consistency,
            combined_stability_score=combined_stability,
            combined_delta_score=combined_delta,
            combined_record_count=combined_records,
        )

    def get_summary(self) -> Dict[str, Any]:
        s = self.analyze()
        return {
            "cross_unit": {
                "unit_summary_count": s.unit_summary_count,
                "unit_pair_count": s.unit_pair_count,
                "avg_unit_summary_delta": s.avg_unit_summary_delta,
                "max_unit_summary_delta": s.max_unit_summary_delta,
                "avg_power_ratio_delta": s.avg_power_ratio_delta,
                "avg_sensor_health_delta": s.avg_sensor_health_delta,
                "avg_signal_trace_delta": s.avg_signal_trace_delta,
                "avg_replay_error_delta": s.avg_replay_error_delta,
                "summary_consistency_score": s.summary_consistency_score,
            },
            "retention_stability": {
                "retention_window_count": s.retention_window_count,
                "retention_window_span": s.retention_window_span,
                "avg_retention_variance": s.avg_retention_variance,
                "max_retention_variance": s.max_retention_variance,
                "retention_stability_score": s.retention_stability_score,
                "retention_drop_rate": s.retention_drop_rate,
            },
            "compression_convergence": {
                "compression_window_count": s.compression_window_count,
                "avg_compression_ratio": s.avg_compression_ratio,
                "compression_ratio_delta": s.compression_ratio_delta,
                "compression_ratio_variance": s.compression_ratio_variance,
                "compression_convergence_score": s.compression_convergence_score,
                "compression_convergence_window_span": s.compression_convergence_window_span,
            },
            "cross_generation_envelope": {
                "cross_generation_envelope_count": s.cross_generation_envelope_count,
                "generation_index_span": s.generation_index_span,
                "generation_envelope_width": s.generation_envelope_width,
                "generation_delta_floor": s.generation_delta_floor,
                "generation_delta_ceiling": s.generation_delta_ceiling,
                "generation_envelope_stability": s.generation_envelope_stability,
            },
            "combined": {
                "combined_window_count": s.combined_window_count,
                "combined_consistency_score": s.combined_consistency_score,
                "combined_stability_score": s.combined_stability_score,
                "combined_delta_score": s.combined_delta_score,
                "combined_record_count": s.combined_record_count,
            },
        }
