"""Per-unit neural architecture descriptor, bounded successor variation, and dimension-changing transfer."""

from __future__ import annotations

import hashlib
import math
import random
import struct
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


def stable_seed(*parts: Any) -> int:
    """Deterministic seed derivation from arbitrary parts (SHA-256 based)."""
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


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


@dataclass
class NeuralArchitectureConfig:
    """Global bounds for neural architecture variation."""
    minimum_hidden_size: int = 8
    initial_hidden_size: int = 16
    maximum_hidden_size: int = 64
    minimum_recurrent_density: float = 0.15
    initial_recurrent_density: float = 1.0
    maximum_recurrent_density: float = 1.0
    minimum_plasticity_rate: float = 0.0
    initial_plasticity_rate: float = 0.01
    maximum_plasticity_rate: float = 0.05
    hidden_size_variation_probability: float = 0.5
    hidden_size_variation_max_step: int = 2
    recurrent_density_variation_probability: float = 0.5
    recurrent_density_variation_max_step: float = 0.10
    plasticity_rate_variation_probability: float = 0.3
    plasticity_rate_variation_max_step: float = 0.005
    architecture_variation_enabled: bool = True
    initial_architecture_policy: str = "uniform_baseline"  # or "bounded_seeded_distribution"

    # Cost coefficients
    neural_processing_base_cost: float = 0.05
    neural_hidden_unit_cost: float = 0.002
    neural_recurrent_connection_cost: float = 0.001
    neural_plastic_update_cost: float = 0.0005
    neural_fabrication_hidden_unit_cost: float = 0.5
    neural_fabrication_connection_cost: float = 0.02

    def validate(self) -> None:
        """Validate configuration bounds."""
        assert 1 <= self.minimum_hidden_size <= self.initial_hidden_size <= self.maximum_hidden_size
        assert 0.0 <= self.minimum_recurrent_density <= self.initial_recurrent_density <= self.maximum_recurrent_density <= 1.0
        assert 0.0 <= self.minimum_plasticity_rate <= self.initial_plasticity_rate <= self.maximum_plasticity_rate
        assert self.hidden_size_variation_max_step >= 0
        assert 0.0 <= self.recurrent_density_variation_max_step <= 1.0
        assert 0.0 <= self.plasticity_rate_variation_max_step
        assert self.neural_processing_base_cost >= 0
        assert self.neural_hidden_unit_cost >= 0
        assert self.neural_recurrent_connection_cost >= 0
        assert self.neural_plastic_update_cost >= 0
        assert self.neural_fabrication_hidden_unit_cost >= 0
        assert self.neural_fabrication_connection_cost >= 0


@dataclass
class NeuralArchitectureDescriptor:
    """Per-unit neural architecture descriptor."""
    architecture_id: str = "arch-0"
    hidden_size: int = 16
    recurrent_density: float = 1.0
    plasticity_rate: float = 0.01
    plasticity_enabled: bool = True

    def validate(self, bounds: Optional[NeuralArchitectureConfig] = None) -> None:
        """Validate descriptor values against bounds."""
        if bounds is None:
            bounds = NeuralArchitectureConfig()
        assert isinstance(self.hidden_size, int) and self.hidden_size >= 1
        assert isinstance(self.recurrent_density, float) and 0.0 <= self.recurrent_density <= 1.0
        assert isinstance(self.plasticity_rate, float) and math.isfinite(self.plasticity_rate)
        assert self.hidden_size >= bounds.minimum_hidden_size
        assert self.hidden_size <= bounds.maximum_hidden_size
        assert self.recurrent_density >= bounds.minimum_recurrent_density
        assert self.recurrent_density <= bounds.maximum_recurrent_density
        assert self.plasticity_rate >= bounds.minimum_plasticity_rate
        assert self.plasticity_rate <= bounds.maximum_plasticity_rate

    def active_recurrent_connections(self) -> int:
        """Number of active recurrent connections given density."""
        n = self.hidden_size
        total = n * n
        return max(1, int(total * self.recurrent_density))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "architecture_id": self.architecture_id,
            "hidden_size": self.hidden_size,
            "recurrent_density": round(self.recurrent_density, 6),
            "plasticity_rate": round(self.plasticity_rate, 6),
            "plasticity_enabled": self.plasticity_enabled,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> NeuralArchitectureDescriptor:
        return cls(
            architecture_id=d.get("architecture_id", "arch-0"),
            hidden_size=d.get("hidden_size", 16),
            recurrent_density=d.get("recurrent_density", 1.0),
            plasticity_rate=d.get("plasticity_rate", 0.01),
            plasticity_enabled=d.get("plasticity_enabled", True),
        )

    def copy(self) -> NeuralArchitectureDescriptor:
        return NeuralArchitectureDescriptor(
            architecture_id=self.architecture_id,
            hidden_size=self.hidden_size,
            recurrent_density=self.recurrent_density,
            plasticity_rate=self.plasticity_rate,
            plasticity_enabled=self.plasticity_enabled,
        )


def _make_descriptor_id(source_id: str, tick: int, index: int) -> str:
    """Generate a deterministic architecture ID for a successor."""
    h = hashlib.sha256()
    h.update(f"{source_id}:{tick}:{index}".encode("utf-8"))
    short = h.hexdigest()[:8]
    return f"arch-{short}"


def vary_architecture(
    source: NeuralArchitectureDescriptor,
    bounds: NeuralArchitectureConfig,
    rng: random.Random,
    tick: int,
    index: int = 0,
) -> NeuralArchitectureDescriptor:
    """Create a successor architecture descriptor with bounded variation."""
    if not bounds.architecture_variation_enabled:
        return source.copy()

    new_hidden = source.hidden_size
    new_density = source.recurrent_density
    new_rate = source.plasticity_rate

    # Hidden size variation
    if rng.random() < bounds.hidden_size_variation_probability:
        step = rng.randint(-bounds.hidden_size_variation_max_step, bounds.hidden_size_variation_max_step)
        new_hidden = _clamp(source.hidden_size + step, bounds.minimum_hidden_size, bounds.maximum_hidden_size)
        new_hidden = int(new_hidden)

    # Recurrent density variation
    if rng.random() < bounds.recurrent_density_variation_probability:
        delta = rng.uniform(-bounds.recurrent_density_variation_max_step, bounds.recurrent_density_variation_max_step)
        new_density = _clamp(source.recurrent_density + delta, bounds.minimum_recurrent_density, bounds.maximum_recurrent_density)

    # Plasticity rate variation
    if rng.random() < bounds.plasticity_rate_variation_probability:
        delta = rng.uniform(-bounds.plasticity_rate_variation_max_step, bounds.plasticity_rate_variation_max_step)
        new_rate = _clamp(source.plasticity_rate + delta, bounds.minimum_plasticity_rate, bounds.maximum_plasticity_rate)

    new_id = _make_descriptor_id(source.architecture_id, tick, index)
    return NeuralArchitectureDescriptor(
        architecture_id=new_id,
        hidden_size=new_hidden,
        recurrent_density=new_density,
        plasticity_rate=new_rate,
        plasticity_enabled=source.plasticity_enabled,
    )


def compute_recurrence_mask(hidden_size: int, density: float, rng: random.Random) -> List[List[float]]:
    """Create a binary mask for recurrent connections at the given density."""
    mask = [[0.0] * hidden_size for _ in range(hidden_size)]
    total = hidden_size * hidden_size
    active_count = max(1, int(total * density))
    # Flatten indices and sample
    indices = list(range(total))
    rng.shuffle(indices)
    for idx in indices[:active_count]:
        i = idx // hidden_size
        j = idx % hidden_size
        mask[i][j] = 1.0
    return mask


def compute_processing_cost(
    descriptor: NeuralArchitectureDescriptor,
    bounds: NeuralArchitectureConfig,
    changed_parameter_count: int = 0,
) -> float:
    """Compute per-decision processing cost."""
    active_conn = descriptor.active_recurrent_connections()
    cost = (
        bounds.neural_processing_base_cost
        + bounds.neural_hidden_unit_cost * descriptor.hidden_size
        + bounds.neural_recurrent_connection_cost * active_conn
    )
    if descriptor.plasticity_enabled:
        cost += bounds.neural_plastic_update_cost * changed_parameter_count
    return cost


def compute_fabrication_cost(
    descriptor: NeuralArchitectureDescriptor,
    bounds: NeuralArchitectureConfig,
) -> float:
    """Compute architecture-dependent fabrication complexity cost."""
    active_conn = descriptor.active_recurrent_connections()
    return (
        bounds.neural_fabrication_hidden_unit_cost * descriptor.hidden_size
        + bounds.neural_fabrication_connection_cost * active_conn
    )


def resize_state_for_successor(
    source_hidden: List[float],
    source_W_in: List[List[float]],
    source_W_rec: List[List[float]],
    source_W_out: List[List[float]],
    source_W_param: List[List[float]],
    source_b_hidden: List[float],
    source_mask: Optional[List[List[float]]],
    successor_descriptor: NeuralArchitectureDescriptor,
    source_descriptor: NeuralArchitectureDescriptor,
    rng: random.Random,
    weight_bound: float = 2.0,
) -> Tuple[List[float], List[List[float]], List[List[float]], List[List[float]], List[List[float]], List[float], List[List[float]], List[int]]:
    """Resize neural state for successor with different hidden_size.

    Returns (new_hidden, new_W_in, new_W_rec, new_W_out, new_W_param, new_b_hidden, new_mask, retained_indices).
    """
    old_h = source_descriptor.hidden_size
    new_h = successor_descriptor.hidden_size
    input_size = len(source_W_in[0]) if source_W_in else 16
    output_size = len(source_W_out) if source_W_out else 7
    param_size = len(source_W_param) if source_W_param else 3
    scale = 1.0 / math.sqrt(input_size)

    if new_h == old_h:
        # No size change — just return copies
        return (
            list(source_hidden),
            [list(row) for row in source_W_in],
            [list(row) for row in source_W_rec],
            [list(row) for row in source_W_out],
            [list(row) for row in source_W_param],
            list(source_b_hidden),
            [list(row) for row in source_mask] if source_mask else compute_recurrence_mask(new_h, successor_descriptor.recurrent_density, rng),
            list(range(old_h)),
        )

    retained_indices: List[int] = []
    new_hidden: List[float] = []
    new_W_in: List[List[float]] = []
    new_W_rec: List[List[float]] = []
    new_W_out: List[List[float]] = []
    new_W_param: List[List[float]] = []
    new_b_hidden: List[float] = []

    if new_h > old_h:
        # Expansion: keep all old, add new with deterministic init
        retained_indices = list(range(old_h))
        new_hidden = list(source_hidden)
        new_W_in = [list(row) for row in source_W_in]
        new_W_rec = [list(row) for row in source_W_rec]
        new_W_out = [list(row) for row in source_W_out]
        new_W_param = [list(row) for row in source_W_param]
        new_b_hidden = list(source_b_hidden)

        for _ in range(new_h - old_h):
            new_hidden.append(_clamp(rng.gauss(0, 0.1), -1.0, 1.0))
            new_W_in.append([rng.gauss(0, scale) for _ in range(input_size)])
            # New row in W_rec: mostly zero except for connections from existing neurons
            new_rec_row = [0.0] * old_h + [rng.gauss(0, scale) for _ in range(new_h - old_h)]
            new_W_rec.append(new_rec_row)
            # Extend existing W_rec rows with new columns
            for row in new_W_rec[:old_h]:
                row.append(rng.gauss(0, scale))
            # Extend W_out and W_param with new columns
            for row in new_W_out:
                row.append(rng.gauss(0, scale))
            for row in new_W_param:
                row.append(rng.gauss(0, scale))
            new_b_hidden.append(rng.gauss(0, 0.01))

    else:
        # Contraction: select retained indices deterministically
        all_indices = list(range(old_h))
        rng.shuffle(all_indices)
        retained_indices = sorted(all_indices[:new_h])
        retained_set = set(retained_indices)

        new_hidden = [source_hidden[i] for i in retained_indices]
        new_W_in = [list(source_W_in[i]) for i in retained_indices]
        new_W_rec = [[source_W_rec[i][j] for j in retained_indices] for i in retained_indices]
        new_W_out = [[row[i] for i in retained_indices] for row in source_W_out]
        new_W_param = [[row[i] for i in retained_indices] for row in source_W_param]
        new_b_hidden = [source_b_hidden[i] for i in retained_indices]

    # Create new recurrent mask
    new_mask = compute_recurrence_mask(new_h, successor_descriptor.recurrent_density, rng)

    return new_hidden, new_W_in, new_W_rec, new_W_out, new_W_param, new_b_hidden, new_mask, retained_indices


@dataclass
class NeuralArchitectureTransition:
    """Record of an architecture transition during successor creation."""
    tick: int = 0
    source_unit_id: str = ""
    successor_unit_id: str = ""
    source_generation: int = 0
    successor_generation: int = 0
    source_architecture_id: str = ""
    successor_architecture_id: str = ""
    source_hidden_size: int = 16
    successor_hidden_size: int = 16
    hidden_size_delta: int = 0
    source_recurrent_density: float = 1.0
    successor_recurrent_density: float = 1.0
    recurrent_density_delta: float = 0.0
    source_plasticity_rate: float = 0.01
    successor_plasticity_rate: float = 0.01
    plasticity_rate_delta: float = 0.0
    retained_hidden_count: int = 0
    added_hidden_count: int = 0
    removed_hidden_count: int = 0
    active_recurrent_connection_delta: int = 0
    processing_cost_estimate: float = 0.0
    fabrication_complexity_cost: float = 0.0
    variation_applied: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tick": self.tick,
            "source_unit_id": self.source_unit_id,
            "successor_unit_id": self.successor_unit_id,
            "source_generation": self.source_generation,
            "successor_generation": self.successor_generation,
            "source_architecture_id": self.source_architecture_id,
            "successor_architecture_id": self.successor_architecture_id,
            "source_hidden_size": self.source_hidden_size,
            "successor_hidden_size": self.successor_hidden_size,
            "hidden_size_delta": self.hidden_size_delta,
            "source_recurrent_density": round(self.source_recurrent_density, 6),
            "successor_recurrent_density": round(self.successor_recurrent_density, 6),
            "recurrent_density_delta": round(self.recurrent_density_delta, 6),
            "source_plasticity_rate": round(self.source_plasticity_rate, 6),
            "successor_plasticity_rate": round(self.successor_plasticity_rate, 6),
            "plasticity_rate_delta": round(self.plasticity_rate_delta, 6),
            "retained_hidden_count": self.retained_hidden_count,
            "added_hidden_count": self.added_hidden_count,
            "removed_hidden_count": self.removed_hidden_count,
            "active_recurrent_connection_delta": self.active_recurrent_connection_delta,
            "processing_cost_estimate": round(self.processing_cost_estimate, 6),
            "fabrication_complexity_cost": round(self.fabrication_complexity_cost, 6),
            "variation_applied": self.variation_applied,
        }
