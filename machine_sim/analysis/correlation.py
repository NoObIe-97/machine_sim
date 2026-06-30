"""Signal correlation and statistical association analysis."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from machine_sim.sim.events import Event, EventType


@dataclass
class AssociationRecord:
    """A single temporal association between a signal pattern and a later observation."""
    signal_pattern: int
    signal_tick: int
    observation_type: str
    observation_tick: int
    lag: int
    unit_id: str
    observation_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PatternAssociation:
    """Aggregated association stats for a signal pattern."""
    pattern_id: int
    total_emissions: int = 0
    total_observations: int = 0
    observation_counts: Dict[str, int] = field(default_factory=dict)
    avg_lag: Dict[str, float] = field(default_factory=dict)
    co_occurrence_score: Dict[str, float] = field(default_factory=dict)
    # Improved metrics
    lag_weighted_score: Dict[str, float] = field(default_factory=dict)
    normalized_rate: Dict[str, float] = field(default_factory=dict)
    confidence: Dict[str, float] = field(default_factory=dict)


class SignalCorrelator:
    """Computes temporal associations between signal patterns and later observations.

    This is a neutral statistical measurement system. It only measures
    co-occurrence patterns within bounded windows.
    """

    def __init__(self, observation_window: int = 10) -> None:
        self.observation_window = observation_window
        self._signal_history: List[Tuple[int, str, int, Dict[str, Any]]] = []
        self._observation_history: List[Tuple[int, str, str, Dict[str, Any]]] = []
        self._associations: List[AssociationRecord] = []
        self._pattern_stats: Dict[int, PatternAssociation] = {}

    def record_signal_emission(self, tick: int, unit_id: str,
                               pattern_id: int, data: Dict[str, Any]) -> None:
        """Record a signal emission event."""
        self._signal_history.append((tick, unit_id, pattern_id, data))

    def record_observation(self, tick: int, unit_id: str,
                           observation_type: str, data: Dict[str, Any]) -> None:
        """Record a machine-native observation (hazard, resource, proximity, etc.)."""
        self._observation_history.append((tick, unit_id, observation_type, data))

    def compute_associations(self) -> List[AssociationRecord]:
        """Compute temporal associations between signals and later observations.

        For each signal emission, look forward within the observation window
        for observations at the same position or by the same unit.
        """
        self._associations.clear()

        for sig_tick, sig_unit, pattern_id, sig_data in self._signal_history:
            for obs_tick, obs_unit, obs_type, obs_data in self._observation_history:
                lag = obs_tick - sig_tick
                if lag <= 0 or lag > self.observation_window:
                    continue
                # Associate if same unit or nearby (within observation window)
                if obs_unit == sig_unit:
                    assoc = AssociationRecord(
                        signal_pattern=pattern_id,
                        signal_tick=sig_tick,
                        observation_type=obs_type,
                        observation_tick=obs_tick,
                        lag=lag,
                        unit_id=obs_unit,
                        observation_data=obs_data,
                    )
                    self._associations.append(assoc)

        return self._associations

    def get_pattern_stats(self) -> Dict[int, PatternAssociation]:
        """Get aggregated association statistics per pattern."""
        self._pattern_stats.clear()

        # Count emissions per pattern
        for _, _, pattern_id, _ in self._signal_history:
            if pattern_id not in self._pattern_stats:
                self._pattern_stats[pattern_id] = PatternAssociation(pattern_id=pattern_id)
            self._pattern_stats[pattern_id].total_emissions += 1

        # Aggregate observations
        for assoc in self._associations:
            stats = self._pattern_stats.get(assoc.signal_pattern)
            if stats is None:
                continue
            stats.total_observations += 1
            stats.observation_counts[assoc.observation_type] = \
                stats.observation_counts.get(assoc.observation_type, 0) + 1

        # Compute average lag and co-occurrence scores
        lag_sums: Dict[int, Dict[str, List[int]]] = defaultdict(lambda: defaultdict(list))
        for assoc in self._associations:
            lag_sums[assoc.signal_pattern][assoc.observation_type].append(assoc.lag)

        for pattern_id, type_lags in lag_sums.items():
            stats = self._pattern_stats.get(pattern_id)
            if stats is None:
                continue
            for obs_type, lags in type_lags.items():
                stats.avg_lag[obs_type] = sum(lags) / len(lags) if lags else 0.0
                obs_count = stats.observation_counts.get(obs_type, 0)

                # Co-occurrence score: observations per emission (capped 0-1)
                if stats.total_emissions > 0:
                    stats.co_occurrence_score[obs_type] = min(
                        1.0, obs_count / stats.total_emissions
                    )

                # Lag-weighted score: observations weighted by inverse lag
                if lags:
                    lag_weights = [1.0 / max(1, lag) for lag in lags]
                    stats.lag_weighted_score[obs_type] = min(
                        1.0, sum(lag_weights) / stats.total_emissions
                    )

                # Normalized rate: observations per emission per window tick
                if stats.total_emissions > 0 and self.observation_window > 0:
                    stats.normalized_rate[obs_type] = min(
                        1.0, obs_count / (stats.total_emissions * self.observation_window)
                    )

                # Confidence: based on sample count (log-scaled)
                import math
                stats.confidence[obs_type] = min(
                    1.0, math.log1p(obs_count) / math.log1p(max(1, stats.total_emissions))
                )

        return self._pattern_stats

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of all association data."""
        stats = self.get_pattern_stats()
        return {
            "observation_window": self.observation_window,
            "total_emissions": len(self._signal_history),
            "total_observations": len(self._observation_history),
            "total_associations": len(self._associations),
            "patterns": {
                pid: {
                    "emissions": s.total_emissions,
                    "observations": s.total_observations,
                    "observation_counts": dict(s.observation_counts),
                    "avg_lag": dict(s.avg_lag),
                    "co_occurrence_score": dict(s.co_occurrence_score),
                    "lag_weighted_score": dict(s.lag_weighted_score),
                    "normalized_rate": dict(s.normalized_rate),
                    "confidence": dict(s.confidence),
                }
                for pid, s in stats.items()
            },
        }

    def reset(self) -> None:
        """Clear all history and associations."""
        self._signal_history.clear()
        self._observation_history.clear()
        self._associations.clear()
        self._pattern_stats.clear()
