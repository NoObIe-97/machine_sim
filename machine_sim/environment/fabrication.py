"""Machine-native fabrication, design inheritance, and lineage tracking."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class DesignTemplate:
    """Bounded machine-native design parameters for fabrication."""
    variant_name: str = "balanced"
    max_power: float = 100.0
    sensor_range: int = 3
    power_drain_rate: float = 1.0
    signal_enabled: bool = False
    signal_pattern_count: int = 3
    signal_energy_cost: float = 2.0
    signal_default_radius: int = 3
    signal_default_decay: float = 0.1
    signal_default_duration: int = 10
    adaptive_enabled: bool = False
    component_health_seed: float = 1.0


@dataclass
class LineageRecord:
    """Machine-native lineage metadata for fabrication continuity."""
    source_unit_id: str
    successor_unit_id: str
    source_generation: int
    successor_generation: int
    fabrication_tick: int
    design_distance: float = 0.0
    material_cost: float = 0.0
    power_cost: float = 0.0


@dataclass
class FabricationResult:
    """Outcome of a fabrication attempt."""
    success: bool
    successor_id: Optional[str] = None
    source_id: str = ""
    failure_cause: str = ""
    placement: Optional[Tuple[int, int]] = None
    template: Optional[DesignTemplate] = None
    capsule: Any = None  # CalibrationCapsule if capsule_enabled
    material_cost: float = 0.0
    power_cost: float = 0.0
    design_distance: float = 0.0


class FabricationEngine:
    """Machine-native fabrication process.

    Handles successor creation with resource constraints, placement rules,
    and deterministic design variation.
    """

    def __init__(
        self,
        population_cap: int = 20,
        fabrication_interval: int = 25,
        power_cost: float = 30.0,
        material_cost: float = 5.0,
        variation_factor: float = 0.1,
        min_power_ratio: float = 0.4,
        min_component_health: float = 0.3,
    ) -> None:
        self.population_cap = population_cap
        self.fabrication_interval = fabrication_interval
        self.power_cost = power_cost
        self.material_cost = material_cost
        self.variation_factor = variation_factor
        self.min_power_ratio = min_power_ratio
        self.min_component_health = min_component_health
        self._next_unit_id = 0
        self._lineage_records: List[LineageRecord] = []
        self._fabrication_attempts = 0
        self._fabrication_successes = 0
        self._fabrication_failures: Dict[str, int] = {}

    def can_fabricate(
        self,
        source_unit: Any,
        current_tick: int,
        world: Any,
        current_population: int,
    ) -> Tuple[bool, str]:
        """Check if source unit meets fabrication prerequisites."""
        # Population cap
        if current_population >= self.population_cap:
            return False, "population_capacity"

        # Power check
        if source_unit.power_reserve < self.power_cost:
            return False, "insufficient_power"

        power_ratio = source_unit.power_reserve / source_unit.max_power
        if power_ratio < self.min_power_ratio:
            return False, "insufficient_power"

        # Component health check
        avg_health = source_unit._avg_component_health()
        if avg_health < self.min_component_health:
            return False, "source_unstable"

        # Cooldown check — fabrication_interval controls attempt frequency
        last_fab_tick = getattr(source_unit, '_last_fabrication_tick', -999)
        last_attempt_tick = getattr(source_unit, '_last_fabrication_attempt_tick', -999)
        if current_tick - max(last_fab_tick, last_attempt_tick) < self.fabrication_interval:
            return False, "fabrication_cooldown"

        # Material check — look for any resource with sufficient quantity
        cell = world.grid.get(source_unit.position)
        if cell:
            total_material = sum(r.quantity for r in cell.resources.values())
            if total_material < self.material_cost:
                return False, "insufficient_material"

        # Placement check
        if not self._find_placement(source_unit.position, world):
            return False, "placement_unavailable"

        return True, "ok"

    def _find_placement(self, position: Tuple[int, int], world: Any) -> Optional[Tuple[int, int]]:
        """Find an empty adjacent cell for successor placement."""
        x, y = position
        candidates = []
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if (nx, ny) in world.grid:
                    cell = world.grid[(nx, ny)]
                    if cell.unit_id is None:
                        candidates.append((nx, ny))
        return candidates[0] if candidates else None

    def fabricate(
        self,
        source_unit: Any,
        current_tick: int,
        world: Any,
        current_population: int,
        rng: random.Random,
    ) -> FabricationResult:
        """Attempt to fabricate a successor unit."""
        self._fabrication_attempts += 1
        can_fab, cause = self.can_fabricate(
            source_unit, current_tick, world, current_population
        )
        # Track attempt tick AFTER cooldown check so next tick sees previous attempt
        source_unit._last_fabrication_attempt_tick = current_tick

        if not can_fab:
            self._fabrication_failures[cause] = \
                self._fabrication_failures.get(cause, 0) + 1
            return FabricationResult(
                success=False,
                source_id=source_unit.unit_id,
                failure_cause=cause,
            )

        # Immutable per-attempt cost tracking
        remaining_power_cost = self.power_cost
        remaining_material_cost = self.material_cost

        # Deduct power cost
        source_unit.power_reserve -= remaining_power_cost

        # Deduct material cost from local resources
        cell = world.grid.get(source_unit.position)
        if cell:
            for res in cell.resources.values():
                if remaining_material_cost <= 0:
                    break
                if res.quantity >= remaining_material_cost:
                    res.quantity -= remaining_material_cost
                    remaining_material_cost = 0.0
                    break
                else:
                    remaining_material_cost -= res.quantity
                    res.quantity = 0

        # Find placement
        placement = self._find_placement(source_unit.position, world)
        if not placement:
            self._fabrication_failures["placement_unavailable"] = \
                self._fabrication_failures.get("placement_unavailable", 0) + 1
            source_unit.power_reserve += remaining_power_cost
            return FabricationResult(
                success=False,
                source_id=source_unit.unit_id,
                failure_cause="placement_unavailable",
            )

        # Create design template with variation (single source of truth)
        template = self._create_template(source_unit, rng)

        # Generate successor ID
        self._next_unit_id += 1
        successor_id = f"unit-{self._next_unit_id:04d}"

        # Record lineage
        source_gen = getattr(source_unit, '_generation_index', 0)
        lineage = LineageRecord(
            source_unit_id=source_unit.unit_id,
            successor_unit_id=successor_id,
            source_generation=source_gen,
            successor_generation=source_gen + 1,
            fabrication_tick=current_tick,
            material_cost=self.material_cost,
            power_cost=self.power_cost,
        )
        self._lineage_records.append(lineage)

        # Mark source as having fabricated
        source_unit._last_fabrication_tick = current_tick

        self._fabrication_successes += 1

        return FabricationResult(
            success=True,
            successor_id=successor_id,
            source_id=source_unit.unit_id,
            placement=placement,
            template=template,
            material_cost=self.material_cost,
            power_cost=self.power_cost,
        )

    def _create_template(self, source_unit: Any, rng: random.Random) -> DesignTemplate:
        """Create a design template with deterministic variation."""
        vf = self.variation_factor

        def vary(value: float, low: float, high: float) -> float:
            noise = rng.uniform(-vf, vf)
            return max(low, min(high, value * (1 + noise)))

        return DesignTemplate(
            variant_name=getattr(source_unit, 'variant', None) and source_unit.variant.name or "balanced",
            max_power=vary(source_unit.max_power, 50.0, 200.0),
            sensor_range=max(1, int(vary(
                getattr(source_unit, 'SENSOR_RANGE', 3), 1, 8
            ))),
            power_drain_rate=vary(
                getattr(source_unit, 'variant', None) and source_unit.variant.power_drain_rate or 1.0,
                0.5, 2.0
            ),
            signal_enabled=getattr(source_unit, 'signal_enabled', False),
            signal_pattern_count=getattr(source_unit, 'signal_pattern_count', 3),
            signal_energy_cost=vary(
                getattr(source_unit, 'signal_energy_cost', 2.0), 1.0, 5.0
            ),
            signal_default_radius=max(1, int(vary(
                getattr(source_unit, 'signal_default_radius', 3), 1, 6
            ))),
            signal_default_decay=vary(
                getattr(source_unit, 'signal_default_decay', 0.1), 0.05, 0.3
            ),
            signal_default_duration=max(3, int(vary(
                getattr(source_unit, 'signal_default_duration', 10), 3, 20
            ))),
            adaptive_enabled=getattr(source_unit, 'adaptive_enabled', False),
            component_health_seed=vary(1.0, 0.7, 1.0),
        )

    def get_lineage_records(self) -> List[LineageRecord]:
        return list(self._lineage_records)

    def get_summary(self) -> Dict[str, Any]:
        """Get fabrication and lineage summary."""
        generations: Dict[int, int] = {}
        for record in self._lineage_records:
            gen = record.successor_generation
            generations[gen] = generations.get(gen, 0) + 1

        return {
            "total_attempts": self._fabrication_attempts,
            "total_successes": self._fabrication_successes,
            "failures_by_cause": dict(self._fabrication_failures),
            "total_lineage_records": len(self._lineage_records),
            "generation_distribution": generations,
            "max_generation": max(generations.keys()) if generations else 0,
            "lineage": [
                {
                    "source": r.source_unit_id,
                    "successor": r.successor_unit_id,
                    "source_gen": r.source_generation,
                    "successor_gen": r.successor_generation,
                    "tick": r.fabrication_tick,
                }
                for r in self._lineage_records
            ],
        }
