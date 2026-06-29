"""Machine-native decision primitives."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from machine_sim.agents.base import MemoryEntry, SensorReading


def threshold_gate(value: float, low: float, high: float) -> str:
    """Pure threshold logic: returns 'low', 'mid', or 'high'."""
    if value < low:
        return "low"
    elif value > high:
        return "high"
    return "mid"


def gradient_direction(
    position: Tuple[int, int],
    density_map: Dict[Tuple[int, int], float],
) -> Optional[Tuple[int, int]]:
    """Return the neighbor position with highest density, or None."""
    x, y = position
    neighbors = [
        (x + dx, y + dy)
        for dx in (-1, 0, 1)
        for dy in (-1, 0, 1)
        if (dx, dy) != (0, 0)
    ]
    best = None
    best_val = density_map.get(position, 0.0)
    for nx, ny in neighbors:
        val = density_map.get((nx, ny), 0.0)
        if val > best_val:
            best_val = val
            best = (nx, ny)
    return best


def correlation_detect(
    memory: List[MemoryEntry],
    pattern_type: str,
    window: int = 10,
) -> bool:
    """Check if a pattern_type appeared in recent memory entries."""
    recent = list(memory)[-window:]
    return any(e.event_type == pattern_type for e in recent)


def reinforcement_score(
    memory: List[MemoryEntry],
    action_label: str,
    window: int = 20,
) -> float:
    """Average outcome_delta for events matching action_label."""
    recent = list(memory)[-window:]
    matches = [e for e in recent if e.event_type == action_label]
    if not matches:
        return 0.0
    return sum(e.outcome_delta for e in matches) / len(matches)


def build_resource_map(readings: List[SensorReading]) -> Dict[Tuple[int, int], float]:
    """Aggregate sensor readings into local resource density map."""
    resource_map: Dict[Tuple[int, int], float] = {}
    for reading in readings:
        total = sum(reading.resource_signals.values())
        resource_map[reading.position] = total
    return resource_map
