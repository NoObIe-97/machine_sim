"""Signal pattern field dynamics analysis."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class PatternFrequency:
    """Cross-tick pattern frequency data."""
    pattern_id: int = 0
    total_count: int = 0
    active_ticks: int = 0
    tick_span: int = 0
    recurrence_score: float = 0.0


@dataclass
class DensityCluster:
    """Temporal signal-density cluster."""
    start_tick: int = 0
    end_tick: int = 0
    peak_density: float = 0.0
    avg_density: float = 0.0


@dataclass
class SignalGradient:
    """Spatial signal-gradient data."""
    cell_count: int = 0
    avg_gradient: float = 0.0
    max_gradient: float = 0.0


@dataclass
class PatternCorrelation:
    """Pattern-observation correlation score."""
    pattern_id: int = 0
    observation_count: int = 0
    avg_score: float = 0.0
    persistence_score: float = 0.0


class SignalFieldDynamics:
    """Analyzes cross-tick signal pattern field dynamics."""

    def __init__(self, enabled: bool = True, window: int = 50,
                 sample_interval: int = 5, max_records: int = 100) -> None:
        self.enabled = enabled
        self.window = window
        self.sample_interval = sample_interval
        self.max_records = max_records
        self._signal_history: List[Tuple[int, str, int, Dict[str, Any]]] = []
        self._observation_history: List[Tuple[int, str, str, Dict[str, Any]]] = []
        self._tick_count = 0
        self._last_gradient: Optional[SignalGradient] = None

    def record_signal(self, tick: int, unit_id: str, pattern_id: int,
                      data: Dict[str, Any]) -> None:
        """Record a signal emission for dynamics analysis."""
        self._signal_history.append((tick, unit_id, pattern_id, data))
        if len(self._signal_history) > self.max_records:
            self._signal_history = self._signal_history[-self.max_records:]

    def record_observation(self, tick: int, unit_id: str,
                           observation_type: str, data: Dict[str, Any]) -> None:
        """Record an observation for correlation analysis."""
        self._observation_history.append((tick, unit_id, observation_type, data))
        if len(self._observation_history) > self.max_records:
            self._observation_history = self._observation_history[-self.max_records:]

    def compute_pattern_frequency(self) -> List[PatternFrequency]:
        """Compute cross-tick pattern frequency."""
        pattern_data: Dict[int, Dict[str, Any]] = {}
        for tick, unit_id, pattern_id, data in self._signal_history:
            if pattern_id not in pattern_data:
                pattern_data[pattern_id] = {"ticks": set(), "count": 0}
            pattern_data[pattern_id]["ticks"].add(tick)
            pattern_data[pattern_id]["count"] += 1

        results = []
        for pid, pdata in pattern_data.items():
            ticks = sorted(pdata["ticks"])
            span = ticks[-1] - ticks[0] + 1 if len(ticks) > 1 else 1
            # Recurrence: ratio of active ticks to span
            recurrence = len(ticks) / max(1, span)
            results.append(PatternFrequency(
                pattern_id=pid,
                total_count=pdata["count"],
                active_ticks=len(ticks),
                tick_span=span,
                recurrence_score=recurrence,
            ))
        return results

    def compute_density_clusters(self) -> List[DensityCluster]:
        """Compute temporal signal-density clusters."""
        if not self._signal_history:
            return []

        # Group signals by tick
        tick_counts: Dict[int, int] = defaultdict(int)
        for tick, _, _, _ in self._signal_history:
            tick_counts[tick] += 1

        if not tick_counts:
            return []

        sorted_ticks = sorted(tick_counts.keys())
        clusters: List[DensityCluster] = []
        current_start = sorted_ticks[0]
        current_peak = tick_counts[sorted_ticks[0]]
        current_density_sum = tick_counts[sorted_ticks[0]]
        current_count = 1

        for i in range(1, len(sorted_ticks)):
            tick = sorted_ticks[i]
            if tick - sorted_ticks[i-1] <= 2:  # Cluster proximity
                current_peak = max(current_peak, tick_counts[tick])
                current_density_sum += tick_counts[tick]
                current_count += 1
            else:
                clusters.append(DensityCluster(
                    start_tick=current_start,
                    end_tick=sorted_ticks[i-1],
                    peak_density=current_peak,
                    avg_density=current_density_sum / current_count,
                ))
                current_start = tick
                current_peak = tick_counts[tick]
                current_density_sum = tick_counts[tick]
                current_count = 1

        clusters.append(DensityCluster(
            start_tick=current_start,
            end_tick=sorted_ticks[-1],
            peak_density=current_peak,
            avg_density=current_density_sum / current_count,
        ))

        return clusters

    def compute_signal_gradient(self, world: Any) -> SignalGradient:
        """Compute spatial signal-gradient from world state."""
        gradient_cells = 0
        total_gradient = 0.0
        max_gradient = 0.0

        for pos, cell in world.grid.items():
            if cell.unit_id is not None:
                # Signal gradient = sum of resource and hazard signals
                resource_signal = sum(r.quantity for r in cell.resources.values())
                hazard_signal = sum(h.intensity for h in cell.hazards.values())
                gradient = resource_signal * 0.1 + hazard_signal * 0.5
                total_gradient += gradient
                max_gradient = max(max_gradient, gradient)
                gradient_cells += 1

        avg_gradient = total_gradient / max(1, gradient_cells)
        return SignalGradient(
            cell_count=gradient_cells,
            avg_gradient=avg_gradient,
            max_gradient=max_gradient,
        )

    def compute_pattern_correlation(self) -> List[PatternCorrelation]:
        """Compute pattern-observation correlation scores."""
        # Group observations by tick
        obs_by_tick: Dict[int, List[str]] = defaultdict(list)
        for tick, unit_id, obs_type, data in self._observation_history:
            obs_by_tick[tick].append(obs_type)

        # For each signal, check if observations follow within window
        pattern_obs_counts: Dict[int, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        pattern_total: Dict[int, int] = defaultdict(int)

        for tick, unit_id, pattern_id, data in self._signal_history:
            pattern_total[pattern_id] = pattern_total.get(pattern_id, 0) + 1
            # Look for observations within window
            for obs_tick, obs_unit, obs_type, obs_data in self._observation_history:
                lag = obs_tick - tick
                if 0 < lag <= self.window and obs_unit == unit_id:
                    pattern_obs_counts[pattern_id][obs_type] = \
                        pattern_obs_counts[pattern_id].get(obs_type, 0) + 1

        results = []
        for pid, total in pattern_total.items():
            obs_counts = pattern_obs_counts.get(pid, {})
            total_obs = sum(obs_counts.values())
            avg_score = total_obs / max(1, total)
            # Persistence: ratio of observation types to total observations
            persistence = len(obs_counts) / max(1, total_obs) if total_obs > 0 else 0.0

            results.append(PatternCorrelation(
                pattern_id=pid,
                observation_count=total_obs,
                avg_score=avg_score,
                persistence_score=persistence,
            ))

        return results

    def record_gradient(self, gradient: SignalGradient) -> None:
        """Record the latest signal gradient for summary inclusion."""
        self._last_gradient = gradient

    def get_summary(self) -> Dict[str, Any]:
        """Get field dynamics summary."""
        patterns = self.compute_pattern_frequency()
        clusters = self.compute_density_clusters()
        correlations = self.compute_pattern_correlation()

        # Gradient metrics
        grad = self._last_gradient
        gradient_cells = grad.cell_count if grad else 0
        avg_gradient = grad.avg_gradient if grad else 0.0
        max_gradient = grad.max_gradient if grad else 0.0

        return {
            "total_signals": len(self._signal_history),
            "total_observations": len(self._observation_history),
            "pattern_count": len(patterns),
            "most_frequent_pattern": max(
                (p.pattern_id for p in patterns),
                default=None
            ) if patterns else None,
            "cluster_count": len(clusters),
            "peak_cluster_density": max(
                (c.peak_density for c in clusters),
                default=0.0
            ) if clusters else 0.0,
            "correlation_count": len(correlations),
            "avg_correlation_score": (
                sum(c.avg_score for c in correlations) / len(correlations)
                if correlations else 0.0
            ),
            "max_correlation_score": max(
                (c.avg_score for c in correlations),
                default=0.0
            ) if correlations else 0.0,
            "signal_gradient_cells": gradient_cells,
            "avg_signal_gradient": avg_gradient,
            "max_signal_gradient": max_gradient,
            "patterns": [
                {
                    "pattern_id": p.pattern_id,
                    "total_count": p.total_count,
                    "active_ticks": p.active_ticks,
                    "tick_span": p.tick_span,
                    "recurrence_score": p.recurrence_score,
                }
                for p in patterns
            ],
        }
