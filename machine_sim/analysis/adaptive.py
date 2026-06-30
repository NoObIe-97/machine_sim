"""Local signal-field summary and adaptive signal control."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class SignalFieldSummary:
    """Bounded local statistics for a unit's signal environment."""
    recent_signal_count: int = 0
    pattern_frequency: Dict[int, int] = field(default_factory=dict)
    avg_received_intensity: float = 0.0
    local_hazard_density: float = 0.0
    local_proximity_count: int = 0
    recent_movement_blocks: int = 0
    emission_rate: float = 0.0
    scan_rate: float = 0.0


class LocalFieldTracker:
    """Maintains bounded local statistics per unit.

    Tracks recent signal observations, hazard encounters, proximity events,
    and movement constraints within a bounded window.
    """

    def __init__(self, window_size: int = 20) -> None:
        self.window_size = window_size
        self._signal_observations: deque = deque(maxlen=window_size)
        self._hazard_events: deque = deque(maxlen=window_size)
        self._proximity_events: deque = deque(maxlen=window_size)
        self._movement_blocks: deque = deque(maxlen=window_size)
        self._emission_ticks: deque = deque(maxlen=window_size)
        self._scan_ticks: deque = deque(maxlen=window_size)

    def record_signal_observation(self, tick: int, pattern_id: int,
                                  intensity: float) -> None:
        self._signal_observations.append((tick, pattern_id, intensity))

    def record_hazard_event(self, tick: int) -> None:
        self._hazard_events.append(tick)

    def record_proximity_event(self, tick: int, nearby_count: int) -> None:
        self._proximity_events.append((tick, nearby_count))

    def record_movement_block(self, tick: int) -> None:
        self._movement_blocks.append(tick)

    def record_emission(self, tick: int) -> None:
        self._emission_ticks.append(tick)

    def record_scan(self, tick: int) -> None:
        self._scan_ticks.append(tick)

    def get_summary(self, current_tick: int) -> SignalFieldSummary:
        """Compute bounded local statistics."""
        window_start = max(0, current_tick - self.window_size)

        # Signal density
        recent_signals = [s for s in self._signal_observations if s[0] >= window_start]
        pattern_freq: Dict[int, int] = {}
        intensity_sum = 0.0
        for _, pid, intensity in recent_signals:
            pattern_freq[pid] = pattern_freq.get(pid, 0) + 1
            intensity_sum += intensity
        avg_intensity = intensity_sum / len(recent_signals) if recent_signals else 0.0

        # Hazard density
        recent_hazards = [h for h in self._hazard_events if h >= window_start]

        # Proximity count
        recent_proximity = [p for p in self._proximity_events if p[0] >= window_start]
        avg_proximity = (
            sum(p[1] for p in recent_proximity) / len(recent_proximity)
            if recent_proximity else 0
        )

        # Movement blocks
        recent_blocks = [b for b in self._movement_blocks if b >= window_start]

        # Emission and scan rates
        recent_emissions = [e for e in self._emission_ticks if e >= window_start]
        recent_scans = [s for s in self._scan_ticks if s >= window_start]
        window_len = max(1, current_tick - window_start)

        return SignalFieldSummary(
            recent_signal_count=len(recent_signals),
            pattern_frequency=pattern_freq,
            avg_received_intensity=avg_intensity,
            local_hazard_density=len(recent_hazards) / window_len,
            local_proximity_count=int(avg_proximity),
            recent_movement_blocks=len(recent_blocks),
            emission_rate=len(recent_emissions) / window_len,
            scan_rate=len(recent_scans) / window_len,
        )


class AdaptiveEmissionPolicy:
    """Non-semantic adaptive emission control.

    Adjusts emission parameters based on local machine-native state.
    No symbolic interpretation is assigned to signals.
    """

    def __init__(
        self,
        base_interval: int = 5,
        base_intensity: float = 1.0,
        base_radius: int = 3,
        min_interval: int = 2,
        max_interval: int = 15,
        low_power_threshold: float = 0.3,
        high_density_threshold: float = 0.5,
    ) -> None:
        self.base_interval = base_interval
        self.base_intensity = base_intensity
        self.base_radius = base_radius
        self.min_interval = min_interval
        self.max_interval = max_interval
        self.low_power_threshold = low_power_threshold
        self.high_density_threshold = high_density_threshold

    def compute_interval(self, power_ratio: float,
                         field_summary: SignalFieldSummary) -> int:
        """Compute adaptive emission interval."""
        interval = self.base_interval

        # Reduce interval (emit more) when signal density is high
        if field_summary.recent_signal_count > 5:
            interval = max(self.min_interval, interval - 2)

        # Increase interval (emit less) when power is low
        if power_ratio < self.low_power_threshold:
            interval = min(self.max_interval, interval + 3)

        # Increase interval when hazard density is high
        if field_summary.local_hazard_density > self.high_density_threshold:
            interval = min(self.max_interval, interval + 2)

        return interval

    def compute_intensity(self, power_ratio: float,
                          field_summary: SignalFieldSummary) -> float:
        """Compute adaptive signal intensity."""
        intensity = self.base_intensity

        # Reduce intensity when power is low
        if power_ratio < self.low_power_threshold:
            intensity = max(0.3, intensity * 0.6)

        # Increase intensity when nearby signals are strong
        if field_summary.avg_received_intensity > 0.7:
            intensity = min(1.5, intensity * 1.2)

        return intensity

    def compute_radius(self, power_ratio: float,
                       field_summary: SignalFieldSummary) -> int:
        """Compute adaptive signal radius."""
        radius = self.base_radius

        # Reduce radius when power is low
        if power_ratio < self.low_power_threshold:
            radius = max(1, radius - 1)

        # Increase radius when few nearby signals
        if field_summary.recent_signal_count < 2:
            radius = min(6, radius + 1)

        return radius

    def compute_pattern_id(self, tick: int,
                           field_summary: SignalFieldSummary,
                           pattern_count: int) -> int:
        """Compute adaptive pattern_id selection."""
        # Base: cycle through patterns
        base_pattern = tick % pattern_count

        # If a pattern has high frequency locally, shift to a different one
        if field_summary.pattern_frequency:
            most_common = max(field_summary.pattern_frequency,
                              key=field_summary.pattern_frequency.get)
            freq = field_summary.pattern_frequency[most_common]
            if freq > 3 and most_common == base_pattern:
                return (base_pattern + 1) % pattern_count

        return base_pattern


class AdaptiveScanPolicy:
    """Non-semantic adaptive scan behavior."""

    def __init__(
        self,
        base_scan_interval: int = 3,
        min_scan_interval: int = 1,
        max_scan_interval: int = 8,
        low_power_threshold: float = 0.3,
    ) -> None:
        self.base_scan_interval = base_scan_interval
        self.min_scan_interval = min_scan_interval
        self.max_scan_interval = max_scan_interval
        self.low_power_threshold = low_power_threshold

    def compute_scan_interval(self, power_ratio: float,
                              field_summary: SignalFieldSummary) -> int:
        """Compute adaptive scan interval."""
        interval = self.base_scan_interval

        # Scan more frequently when signal density is high
        if field_summary.recent_signal_count > 5:
            interval = max(self.min_scan_interval, interval - 1)

        # Scan less frequently when power is low
        if power_ratio < self.low_power_threshold:
            interval = min(self.max_scan_interval, interval + 2)

        # Scan more frequently when hazard density is high
        if field_summary.local_hazard_density > 0.3:
            interval = max(self.min_scan_interval, interval - 1)

        return interval
