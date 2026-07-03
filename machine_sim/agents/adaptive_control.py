"""Internal adaptive state vector for machine units."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple


@dataclass
class AdaptiveStateVector:
    """Bounded adaptive state that modulates action selection from local feedback."""
    move_weight: float = 0.25
    scan_weight: float = 0.25
    extract_weight: float = 0.25
    signal_weight: float = 0.10
    conserve_weight: float = 0.15
    exploration_bias: float = 0.5
    resource_following_bias: float = 0.5
    hazard_avoidance_bias: float = 0.5
    signal_emission_rate: float = 0.3
    signal_pattern_bias: float = 0.0
    signal_radius_bias: float = 0.0
    scan_interval_bias: float = 0.0
    extract_threshold: float = 0.3
    fabrication_threshold: float = 0.6
    power_conservation_threshold: float = 0.2

    def to_dict(self) -> Dict[str, float]:
        return {
            "move_weight": self.move_weight,
            "scan_weight": self.scan_weight,
            "extract_weight": self.extract_weight,
            "signal_weight": self.signal_weight,
            "conserve_weight": self.conserve_weight,
            "exploration_bias": self.exploration_bias,
            "resource_following_bias": self.resource_following_bias,
            "hazard_avoidance_bias": self.hazard_avoidance_bias,
            "signal_emission_rate": self.signal_emission_rate,
            "signal_pattern_bias": self.signal_pattern_bias,
            "signal_radius_bias": self.signal_radius_bias,
            "scan_interval_bias": self.scan_interval_bias,
            "extract_threshold": self.extract_threshold,
            "fabrication_threshold": self.fabrication_threshold,
            "power_conservation_threshold": self.power_conservation_threshold,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, float]) -> AdaptiveStateVector:
        return cls(**{k: d[k] for k in d if hasattr(cls, k)})

    def copy(self) -> AdaptiveStateVector:
        return AdaptiveStateVector(**self.to_dict())


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


class AdaptiveController:
    """Updates adaptive state from local operational feedback."""

    def __init__(self, enabled: bool = True, learning_rate: float = 0.02,
                 variation_scale: float = 0.005, min_weight: float = 0.02,
                 max_weight: float = 0.8) -> None:
        self.enabled = enabled
        self.learning_rate = learning_rate
        self.variation_scale = variation_scale
        self.min_weight = min_weight
        self.max_weight = max_weight

    def compute_action_scores(self, state: AdaptiveStateVector,
                               power_ratio: float,
                               has_resource_nearby: bool,
                               has_hazard_nearby: bool) -> Dict[str, float]:
        """Compute action scores from adaptive state + local sensed state."""
        scores: Dict[str, float] = {}
        scores["move"] = state.move_weight * (1.0 + state.exploration_bias * 0.3)
        scores["scan"] = state.scan_weight * (1.0 + state.scan_interval_bias * 0.2)
        scores["harvest"] = state.extract_weight * (1.0 + state.resource_following_bias * 0.3)
        scores["signal"] = state.signal_weight * (1.0 + state.signal_emission_rate * 0.3)
        scores["idle"] = state.conserve_weight * (1.0 + state.power_conservation_threshold * 0.2)

        if has_resource_nearby:
            scores["harvest"] *= (1.0 + state.resource_following_bias)
        if has_hazard_nearby:
            scores["move"] *= (1.0 + state.hazard_avoidance_bias)
            scores["idle"] *= (1.0 + state.hazard_avoidance_bias * 0.5)
        if power_ratio < 0.3:
            scores["harvest"] *= 2.0
            scores["move"] *= 1.5
        elif power_ratio > 0.7:
            scores["scan"] *= 1.5
            scores["signal"] *= 1.5

        total = sum(scores.values()) or 1.0
        return {k: v / total for k, v in scores.items()}

    def update_from_feedback(self, state: AdaptiveStateVector,
                              feedback: Dict[str, float],
                              rng: random.Random) -> AdaptiveStateVector:
        """Update adaptive state from local operational feedback. Returns new state."""
        if not self.enabled:
            return state

        s = state.copy()
        lr = self.learning_rate

        # Power delta: positive -> more exploration, negative -> more conservation
        power_delta = feedback.get("power_delta", 0.0)
        if power_delta > 0:
            s.move_weight = _clamp(s.move_weight + lr * 0.5, self.min_weight, self.max_weight)
            s.exploration_bias = _clamp(s.exploration_bias + lr * 0.3, 0.0, 1.0)
        else:
            s.conserve_weight = _clamp(s.conserve_weight + lr * 0.5, self.min_weight, self.max_weight)
            s.power_conservation_threshold = _clamp(s.power_conservation_threshold + lr * 0.3, 0.0, 1.0)

        # Resource extracted: boost extraction and resource-following
        if feedback.get("resource_extracted", 0.0) > 0:
            s.extract_weight = _clamp(s.extract_weight + lr * 0.5, self.min_weight, self.max_weight)
            s.resource_following_bias = _clamp(s.resource_following_bias + lr * 0.3, 0.0, 1.0)
        elif feedback.get("resource_detected", 0.0) > 0:
            s.resource_following_bias = _clamp(s.resource_following_bias + lr * 0.2, 0.0, 1.0)

        # Hazard exposure: boost hazard avoidance
        if feedback.get("hazard_exposure", 0.0) > 0:
            s.hazard_avoidance_bias = _clamp(s.hazard_avoidance_bias + lr * 0.4, 0.0, 1.0)
            s.move_weight = _clamp(s.move_weight + lr * 0.3, self.min_weight, self.max_weight)

        # Movement blocked: increase exploration or scanning
        if feedback.get("movement_blocked", 0.0) > 0:
            s.scan_weight = _clamp(s.scan_weight + lr * 0.3, self.min_weight, self.max_weight)
            s.exploration_bias = _clamp(s.exploration_bias + lr * 0.2, 0.0, 1.0)

        # Signal observed: increase signal tendency
        if feedback.get("signal_observed", 0.0) > 0:
            s.signal_weight = _clamp(s.signal_weight + lr * 0.3, self.min_weight, self.max_weight)
            s.signal_emission_rate = _clamp(s.signal_emission_rate + lr * 0.2, 0.0, 1.0)

        # Signal emitted: successful emission boosts emission rate
        if feedback.get("signal_emitted", 0.0) > 0:
            s.signal_emission_rate = _clamp(s.signal_emission_rate + lr * 0.15, 0.0, 1.0)
        else:
            # Natural decay toward baseline when not emitting
            s.signal_emission_rate = _clamp(s.signal_emission_rate - lr * 0.05, 0.0, 1.0)

        # Scan results: more results boost scan tendency
        scan_results = feedback.get("scan_result_count", 0.0)
        if scan_results > 0:
            s.scan_weight = _clamp(s.scan_weight + lr * 0.2, self.min_weight, self.max_weight)

        # Component health delta: positive -> maintain exploration, negative -> conserve
        health_delta = feedback.get("component_health_delta", 0.0)
        if health_delta < 0:
            s.conserve_weight = _clamp(s.conserve_weight + lr * 0.3, self.min_weight, self.max_weight)

        # Normalize weights
        weight_sum = s.move_weight + s.scan_weight + s.extract_weight + s.signal_weight + s.conserve_weight
        if weight_sum > 0:
            s.move_weight /= weight_sum
            s.scan_weight /= weight_sum
            s.extract_weight /= weight_sum
            s.signal_weight /= weight_sum
            s.conserve_weight /= weight_sum

        # Add small deterministic variation
        s.move_weight = _clamp(s.move_weight + rng.gauss(0, self.variation_scale), self.min_weight, self.max_weight)
        s.scan_weight = _clamp(s.scan_weight + rng.gauss(0, self.variation_scale), self.min_weight, self.max_weight)
        s.extract_weight = _clamp(s.extract_weight + rng.gauss(0, self.variation_scale), self.min_weight, self.max_weight)
        s.signal_weight = _clamp(s.signal_weight + rng.gauss(0, self.variation_scale), self.min_weight, self.max_weight)
        s.conserve_weight = _clamp(s.conserve_weight + rng.gauss(0, self.variation_scale), self.min_weight, self.max_weight)

        # Re-normalize after variation
        weight_sum = s.move_weight + s.scan_weight + s.extract_weight + s.signal_weight + s.conserve_weight
        if weight_sum > 0:
            s.move_weight /= weight_sum
            s.scan_weight /= weight_sum
            s.extract_weight /= weight_sum
            s.signal_weight /= weight_sum
            s.conserve_weight /= weight_sum

        return s

    def transfer_to_successor(self, source: AdaptiveStateVector,
                               rng: random.Random,
                               variation: float = 0.05) -> AdaptiveStateVector:
        """Transfer bounded adaptive state to successor with variation."""
        s = source.copy()
        s.move_weight = _clamp(s.move_weight + rng.gauss(0, variation), self.min_weight, self.max_weight)
        s.scan_weight = _clamp(s.scan_weight + rng.gauss(0, variation), self.min_weight, self.max_weight)
        s.extract_weight = _clamp(s.extract_weight + rng.gauss(0, variation), self.min_weight, self.max_weight)
        s.signal_weight = _clamp(s.signal_weight + rng.gauss(0, variation), self.min_weight, self.max_weight)
        s.conserve_weight = _clamp(s.conserve_weight + rng.gauss(0, variation), self.min_weight, self.max_weight)
        s.exploration_bias = _clamp(s.exploration_bias + rng.gauss(0, variation), 0.0, 1.0)
        s.resource_following_bias = _clamp(s.resource_following_bias + rng.gauss(0, variation), 0.0, 1.0)
        s.hazard_avoidance_bias = _clamp(s.hazard_avoidance_bias + rng.gauss(0, variation), 0.0, 1.0)
        s.signal_emission_rate = _clamp(s.signal_emission_rate + rng.gauss(0, variation), 0.0, 1.0)

        weight_sum = s.move_weight + s.scan_weight + s.extract_weight + s.signal_weight + s.conserve_weight
        if weight_sum > 0:
            s.move_weight /= weight_sum
            s.scan_weight /= weight_sum
            s.extract_weight /= weight_sum
            s.signal_weight /= weight_sum
            s.conserve_weight /= weight_sum
        return s
