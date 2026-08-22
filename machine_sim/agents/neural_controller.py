"""Internal neural processing unit for machine units."""

from __future__ import annotations

import hashlib
import math
import random
import struct
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


def stable_seed(*parts: Any) -> int:
    """Deterministic seed derivation from arbitrary parts.

    Replaces Python hash() which is randomized per process (PYTHONHASHSEED).
    Uses SHA-256 over a canonical byte representation to guarantee identical
    seeds across processes, platforms, and Python invocations.
    """
    h = hashlib.sha256()
    for p in parts:
        if isinstance(p, int):
            h.update(struct.pack("<q", p))
        elif isinstance(p, str):
            h.update(p.encode("utf-8"))
        elif isinstance(p, bytes):
            h.update(p)
        else:
            h.update(str(p).encode("utf-8"))
    return int.from_bytes(h.digest()[:8], "little") & 0xFFFFFFFF


def _clamp(v: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _tanh(x: float) -> float:
    return math.tanh(x)


def _softmax(values: List[float]) -> List[float]:
    max_v = max(values)
    exps = [math.exp(v - max_v) for v in values]
    total = sum(exps)
    if total == 0:
        n = len(values)
        return [1.0 / n] * n
    return [e / total for e in exps]


ACTION_NAMES = ["MOVE", "SCAN", "HARVEST", "EMIT_SIGNAL", "IDLE", "MAINTAIN", "FABRICATE"]
SENSOR_INPUT_SIZE = 16


@dataclass
class NeuralProcessingConfig:
    """Configuration for the internal neural processing unit."""
    input_size: int = SENSOR_INPUT_SIZE
    hidden_size: int = 16
    output_size: int = 7  # number of action types
    param_output_size: int = 3  # signal intensity, scan interval, extraction threshold
    plasticity_rate: float = 0.01
    plasticity_enabled: bool = True
    weight_bound: float = 2.0


@dataclass
class NeuralProcessingState:
    """Bounded internal state of the neural processing unit."""
    hidden_state: List[float] = field(default_factory=lambda: [0.0] * 16)
    W_in: List[List[float]] = field(default_factory=list)
    W_rec: List[List[float]] = field(default_factory=list)
    W_out: List[List[float]] = field(default_factory=list)
    W_param: List[List[float]] = field(default_factory=list)
    b_hidden: List[float] = field(default_factory=list)
    c_action: List[float] = field(default_factory=list)
    c_param: List[float] = field(default_factory=list)
    recurrent_mask: Optional[List[List[float]]] = field(default=None)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "hidden_state": [round(v, 6) for v in self.hidden_state],
            "W_in": [[round(v, 6) for v in row] for row in self.W_in],
            "W_rec": [[round(v, 6) for v in row] for row in self.W_rec],
            "W_out": [[round(v, 6) for v in row] for row in self.W_out],
            "W_param": [[round(v, 6) for v in row] for row in self.W_param],
            "b_hidden": [round(v, 6) for v in self.b_hidden],
            "c_action": [round(v, 6) for v in self.c_action],
            "c_param": [round(v, 6) for v in self.c_param],
        }
        if self.recurrent_mask is not None:
            d["recurrent_mask"] = [[int(v) for v in row] for row in self.recurrent_mask]
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> NeuralProcessingState:
        mask_data = d.get("recurrent_mask")
        mask = [[float(v) for v in row] for row in mask_data] if mask_data else None
        return cls(
            hidden_state=list(d.get("hidden_state", [])),
            W_in=[list(row) for row in d.get("W_in", [])],
            W_rec=[list(row) for row in d.get("W_rec", [])],
            W_out=[list(row) for row in d.get("W_out", [])],
            W_param=[list(row) for row in d.get("W_param", [])],
            b_hidden=list(d.get("b_hidden", [])),
            c_action=list(d.get("c_action", [])),
            c_param=list(d.get("c_param", [])),
            recurrent_mask=mask,
        )

    def copy(self) -> NeuralProcessingState:
        return NeuralProcessingState(
            hidden_state=list(self.hidden_state),
            W_in=[list(row) for row in self.W_in],
            W_rec=[list(row) for row in self.W_rec],
            W_out=[list(row) for row in self.W_out],
            W_param=[list(row) for row in self.W_param],
            b_hidden=list(self.b_hidden),
            c_action=list(self.c_action),
            c_param=list(self.c_param),
            recurrent_mask=[list(row) for row in self.recurrent_mask] if self.recurrent_mask is not None else None,
        )

    def active_recurrent_count(self) -> int:
        """Count active recurrent connections."""
        if self.recurrent_mask is None:
            return len(self.W_rec) * len(self.W_rec) if self.W_rec else 0
        return sum(int(v) for row in self.recurrent_mask for v in row)

    def recurrent_density(self) -> float:
        """Current recurrent density."""
        n = len(self.hidden_state)
        total = n * n
        if total == 0:
            return 0.0
        return self.active_recurrent_count() / total


class NeuralController:
    """Compact recurrent neural controller for local action selection.

    Consume local sensor/feedback features, maintain recurrent processing
    state, emit action logits/preferences, and update from local feedback.
    """

    def __init__(self, config: Optional[NeuralProcessingConfig] = None,
                 unit_id: str = "u-0", seed: int = 42) -> None:
        self.config = config or NeuralProcessingConfig()
        self.state = self._initialize_state(unit_id, seed)
        self._last_action_output: Dict[str, Any] = {}
        # M21 benchmark counter: observation-only, never read by runtime logic.
        self.forward_evaluations = 0

    def _make_rng(self, unit_id: str, seed: int) -> random.Random:
        combined = stable_seed("neural_init", unit_id, seed)
        return random.Random(combined)

    def _initialize_state(self, unit_id: str, seed: int) -> NeuralProcessingState:
        cfg = self.config
        rng = self._make_rng(unit_id, seed)
        scale = 1.0 / math.sqrt(cfg.input_size)

        # W_in: maps input_size -> hidden_size, shape [hidden_size][input_size]
        W_in = [[rng.gauss(0, scale) for _ in range(cfg.input_size)]
                for _ in range(cfg.hidden_size)]
        # W_rec: hidden -> hidden, shape [hidden_size][hidden_size]
        W_rec = [[rng.gauss(0, scale) for _ in range(cfg.hidden_size)]
                 for _ in range(cfg.hidden_size)]
        # W_out: maps hidden_size -> output_size, shape [output_size][hidden_size]
        W_out = [[rng.gauss(0, scale) for _ in range(cfg.hidden_size)]
                 for _ in range(cfg.output_size)]
        # W_param: maps hidden_size -> param_output_size, shape [param_output_size][hidden_size]
        W_param = [[rng.gauss(0, scale) for _ in range(cfg.hidden_size)]
                   for _ in range(cfg.param_output_size)]
        b_hidden = [rng.gauss(0, 0.01) for _ in range(cfg.hidden_size)]
        c_action = [0.0] * cfg.output_size
        c_param = [0.0] * cfg.param_output_size

        return NeuralProcessingState(
            hidden_state=[0.0] * cfg.hidden_size,
            W_in=W_in, W_rec=W_rec, W_out=W_out, W_param=W_param,
            b_hidden=b_hidden, c_action=c_action, c_param=c_param,
        )

    def build_sensor_input(self, power_ratio: float, avg_component_health: float,
                           has_resource: bool, resource_strength: float,
                           has_hazard: bool, hazard_strength: float,
                           signal_observed: bool, signal_emitted: bool,
                           movement_blocked: bool, resource_extracted: bool,
                           scan_result_count: float,
                           previous_action: str, time_since_signal: float,
                           fabrication_ready: bool = False) -> List[float]:
        """Build a fixed-size sensor input vector from local runtime values only."""
        action_enc = [0.0] * 4
        action_map = {"MOVE": 0, "SCAN": 1, "HARVEST": 2, "EMIT_SIGNAL": 3}
        if previous_action in action_map:
            action_enc[action_map[previous_action]] = 1.0

        return [
            _clamp(power_ratio, 0.0, 1.0),
            _clamp(avg_component_health, 0.0, 1.0),
            1.0 if has_resource else 0.0,
            _clamp(resource_strength, 0.0, 1.0),
            1.0 if has_hazard else 0.0,
            _clamp(hazard_strength, 0.0, 1.0),
            1.0 if signal_observed else 0.0,
            1.0 if signal_emitted else 0.0,
            1.0 if movement_blocked else 0.0,
            1.0 if resource_extracted else 0.0,
            _clamp(scan_result_count, 0.0, 1.0),
            action_enc[0],
            action_enc[1],
            action_enc[2],
            action_enc[3],
            _clamp(time_since_signal, 0.0, 1.0),
        ]

    def _matvec(self, W: List[List[float]], x: List[float]) -> List[float]:
        """Matrix-vector multiply: W @ x."""
        return [sum(W[i][j] * x[j] for j in range(len(x))) for i in range(len(W))]

    def _vecadd(self, a: List[float], b: List[float]) -> List[float]:
        return [a[i] + b[i] for i in range(len(a))]

    def _masked_matvec(self, W: List[List[float]], x: List[float],
                       mask: Optional[List[List[float]]] = None) -> List[float]:
        """Matrix-vector multiply with optional mask: (W * mask) @ x."""
        if mask is None:
            return self._matvec(W, x)
        return [sum(W[i][j] * mask[i][j] * x[j] for j in range(len(x)))
                for i in range(len(W))]

    def forward(self, sensor_input: List[float]) -> Tuple[List[float], List[float], List[float], List[float]]:
        """Forward pass through the neural controller.

        Returns:
            action_logits: raw action output values
            action_preferences: softmax-normalized action probabilities
            param_biases: bounded parameter output values
            new_hidden: updated hidden state
        """
        s = self.state
        cfg = self.config
        self.forward_evaluations += 1

        # h_t = tanh(W_in @ x + (W_rec * mask) @ h_prev + b_hidden)
        h_in = self._matvec(s.W_in, sensor_input)
        h_rec = self._masked_matvec(s.W_rec, s.hidden_state, s.recurrent_mask)
        h_combined = self._vecadd(self._vecadd(h_in, h_rec), s.b_hidden)
        new_hidden = [_tanh(v) for v in h_combined]

        # action_logits = W_out @ h + c_action
        action_logits = self._vecadd(self._matvec(s.W_out, new_hidden), s.c_action)
        action_preferences = _softmax(action_logits)

        # param_biases = clamp(W_param @ h + c_param)
        param_raw = self._vecadd(self._matvec(s.W_param, new_hidden), s.c_param)
        param_biases = [_clamp(v, -1.0, 1.0) for v in param_raw]

        return action_logits, action_preferences, param_biases, new_hidden

    def select_action(self, sensor_input: List[float],
                      rng: random.Random) -> Tuple[str, List[float], List[float]]:
        """Select an action from sensor input.

        Returns:
            action_name: chosen action string
            param_biases: parameter biases for the chosen action
            raw_logits: full action logits for tracing
        """
        action_logits, action_preferences, param_biases, new_hidden = self.forward(sensor_input)
        self.state.hidden_state = new_hidden

        # Weighted random selection
        roll = rng.random()
        cumul = 0.0
        chosen_idx = len(ACTION_NAMES) - 1
        for i, p in enumerate(action_preferences):
            cumul += p
            if roll < cumul:
                chosen_idx = i
                break

        self._last_action_output = {
            "action_name": ACTION_NAMES[chosen_idx],
            "action_logits": [round(v, 6) for v in action_logits],
            "action_preferences": [round(v, 6) for v in action_preferences],
            "param_biases": [round(v, 6) for v in param_biases],
        }

        return ACTION_NAMES[chosen_idx], param_biases, action_logits

    def update_from_feedback(self, sensor_input: List[float], selected_action: str,
                             feedback: Dict[str, float], rng: random.Random) -> None:
        """Update plastic parameters from local feedback.

        Uses eligibility trace: W_out += plasticity_rate * delta * outer(h, a_onehot)
        """
        if not self.config.plasticity_enabled:
            return

        cfg = self.config
        s = self.state

        # Recompute forward to get current hidden state
        _, _, _, new_hidden = self.forward(sensor_input)
        s.hidden_state = new_hidden

        # Compute reward-like delta from local feedback
        power_delta = feedback.get("power_delta", 0.0)
        resource_extracted = feedback.get("resource_extracted", 0.0)
        hazard_exposure = feedback.get("hazard_exposure", 0.0)
        signal_observed = feedback.get("signal_observed", 0.0)
        movement_blocked = feedback.get("movement_blocked", 0.0)

        delta = 0.0
        if power_delta > 0:
            delta += 0.3
        elif power_delta < 0:
            delta -= 0.1
        if resource_extracted > 0:
            delta += 0.4
        if hazard_exposure > 0:
            delta -= 0.3
        if signal_observed > 0:
            delta += 0.1
        if movement_blocked > 0:
            delta -= 0.1

        # Clamp delta
        delta = max(-1.0, min(1.0, delta))

        # One-hot encoding of selected action
        action_idx = ACTION_NAMES.index(selected_action) if selected_action in ACTION_NAMES else 4
        a_onehot = [0.0] * cfg.output_size
        a_onehot[action_idx] = 1.0

        # Eligibility: outer(h, a_onehot)
        # W_out has shape [output_size][hidden_size]
        # W_out[j][i] += plasticity_rate * delta * h[i] * a_onehot[j]
        for j in range(cfg.output_size):
            for i in range(cfg.hidden_size):
                eligibility = new_hidden[i] * a_onehot[j]
                s.W_out[j][i] += cfg.plasticity_rate * delta * eligibility
                s.W_out[j][i] = _clamp(s.W_out[j][i], -cfg.weight_bound, cfg.weight_bound)

        # Also adapt hidden bias slightly
        for i in range(cfg.hidden_size):
            s.b_hidden[i] += cfg.plasticity_rate * delta * new_hidden[i] * 0.1
            s.b_hidden[i] = _clamp(s.b_hidden[i], -cfg.weight_bound, cfg.weight_bound)

    def transfer_to_successor(self, rng: random.Random,
                              variation: float = 0.05) -> NeuralProcessingState:
        """Transfer bounded neural state to successor with variation."""
        s = self.state.copy()
        cfg = self.config

        # Add bounded noise to weights
        for i in range(len(s.hidden_state)):
            s.hidden_state[i] = _clamp(
                s.hidden_state[i] + rng.gauss(0, variation),
                -1.0, 1.0
            )

        def _noisy_matrix(mat: List[List[float]]) -> List[List[float]]:
            return [[_clamp(v + rng.gauss(0, variation), -cfg.weight_bound, cfg.weight_bound)
                     for v in row] for row in mat]

        s.W_in = _noisy_matrix(s.W_in)
        s.W_rec = _noisy_matrix(s.W_rec)
        s.W_out = _noisy_matrix(s.W_out)
        s.W_param = _noisy_matrix(s.W_param)
        s.b_hidden = [_clamp(v + rng.gauss(0, variation), -cfg.weight_bound, cfg.weight_bound)
                      for v in s.b_hidden]
        s.c_action = [_clamp(v + rng.gauss(0, variation * 0.5), -cfg.weight_bound, cfg.weight_bound)
                      for v in s.c_action]
        s.c_param = [_clamp(v + rng.gauss(0, variation * 0.5), -cfg.weight_bound, cfg.weight_bound)
                     for v in s.c_param]

        return s

    def set_state(self, new_state: NeuralProcessingState) -> None:
        """Replace the internal state (used after dimension-changing transfer)."""
        self.state = new_state
        # Update config hidden_size to match
        self.config.hidden_size = len(new_state.hidden_state)
        self.config.output_size = len(new_state.W_out) if new_state.W_out else self.config.output_size
        self.config.param_output_size = len(new_state.W_param) if new_state.W_param else self.config.param_output_size

    def set_recurrent_mask(self, mask: List[List[float]]) -> None:
        """Set the recurrent connection mask."""
        self.state.recurrent_mask = mask

    def get_state_snapshot(self) -> Dict[str, Any]:
        """Snapshot the current neural state for trace writing."""
        s = self.state
        return {
            "hidden_state_summary": {
                "mean": round(sum(s.hidden_state) / len(s.hidden_state), 6) if s.hidden_state else 0.0,
                "max": round(max(s.hidden_state), 6) if s.hidden_state else 0.0,
                "min": round(min(s.hidden_state), 6) if s.hidden_state else 0.0,
            },
            "w_out_norm": round(sum(sum(v**2 for v in row) ** 0.5
                                    for row in s.W_out), 6),
            "w_rec_norm": round(sum(sum(v**2 for v in row) ** 0.5
                                    for row in s.W_rec), 6),
        }

    def get_parameter_delta(self, other: NeuralProcessingState) -> Dict[str, Any]:
        """Compute parameter delta between current state and another state."""
        s = self.state

        def _matrix_delta(a: List[List[float]], b: List[List[float]]) -> float:
            total = 0.0
            rows = min(len(a), len(b))
            for i in range(rows):
                cols = min(len(a[i]), len(b[i]))
                for j in range(cols):
                    total += abs(a[i][j] - b[i][j])
            return total

        hidden_delta = sum(abs(s.hidden_state[i] - other.hidden_state[i])
                           for i in range(min(len(s.hidden_state), len(other.hidden_state))))

        return {
            "hidden_state_delta": round(hidden_delta, 6),
            "W_out_delta": round(_matrix_delta(s.W_out, other.W_out), 6),
            "W_rec_delta": round(_matrix_delta(s.W_rec, other.W_rec), 6),
            "b_hidden_delta": round(sum(abs(s.b_hidden[i] - other.b_hidden[i])
                                       for i in range(min(len(s.b_hidden), len(other.b_hidden)))), 6),
        }
