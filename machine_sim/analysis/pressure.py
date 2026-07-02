"""Machine-native resource pressure and field perturbation analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ResourcePressureSample:
    """Bounded sample of resource pressure at a cell."""
    position: Tuple[int, int] = (0, 0)
    resource_density: float = 0.0
    extraction_events: int = 0
    pressure_score: float = 0.0


@dataclass
class ExtractionLoadRecord:
    """Bounded record of extraction activity near a cell."""
    position: Tuple[int, int] = (0, 0)
    extraction_count: int = 0
    load_score: float = 0.0
    depletion_rate: float = 0.0


@dataclass
class PressureSummary:
    """Aggregated pressure analysis summary."""
    resource_pressure_cells: int = 0
    avg_resource_pressure: float = 0.0
    max_resource_pressure: float = 0.0
    resource_depletion_rate: float = 0.0
    total_extraction_events: int = 0
    peak_cell_load: float = 0.0
    avg_load_per_active_unit: float = 0.0
    avg_proximity_pressure: float = 0.0
    max_proximity_pressure: float = 0.0
    active_unit_density: float = 0.0
    movement_block_pressure: float = 0.0
    blocked_motion_rate: float = 0.0
    signal_density: float = 0.0
    signal_observation_load: float = 0.0
    field_perturbation_score: float = 0.0
    total_ticks_sampled: int = 0


class PressureAnalyzer:
    """Computes resource pressure, extraction load, proximity pressure, and signal-field perturbation."""

    def __init__(self, enabled: bool = True, window: int = 20, sample_interval: int = 1,
                 radius: int = 3, max_records: int = 100) -> None:
        self.enabled = enabled
        self.window = window
        self.sample_interval = sample_interval
        self.radius = radius
        self.max_records = max_records
        self._resource_samples: List[ResourcePressureSample] = []
        self._extraction_records: List[ExtractionLoadRecord] = []
        self._pressure_history: List[PressureSummary] = []
        self._tick_count = 0

    def record_tick(self, world: Any, units: List[Any], tick: int,
                    signal_enabled: bool = False) -> None:
        """Record pressure metrics for this tick."""
        if not self.enabled:
            return
        if tick % self.sample_interval != 0:
            return

        self._tick_count += 1

        # Resource pressure: sample cells near active units
        active_units = [u for u in units if u.is_active]
        total_pressure = 0.0
        max_pressure = 0.0
        pressure_cells = 0
        total_extraction = 0

        for unit in active_units:
            cell = world.grid.get(unit.position)
            if not cell:
                continue

            # Resource pressure: inverse of local density (lower density = higher pressure)
            density = cell.resource_density
            pressure = max(0.0, 1.0 - density / 50.0)
            total_pressure += pressure
            max_pressure = max(max_pressure, pressure)
            pressure_cells += 1

            # Record resource pressure sample
            sample = ResourcePressureSample(
                position=unit.position,
                resource_density=density,
                pressure_score=pressure,
            )
            self._resource_samples.append(sample)

        # Extraction load: count recent harvest events in cells
        for unit in active_units:
            cell = world.grid.get(unit.position)
            if cell:
                # Count resources with depleted quantity as extraction indicator
                for res in cell.resources.values():
                    if res.quantity < res.max_quantity * 0.5:
                        total_extraction += 1
                        load = 1.0 - res.quantity / max(res.max_quantity, 1.0)
                        record = ExtractionLoadRecord(
                            position=unit.position,
                            extraction_count=1,
                            load_score=load,
                            depletion_rate=res.regrowth_rate,
                        )
                        self._extraction_records.append(record)

        # Proximity pressure
        total_proximity = 0.0
        max_proximity = 0.0
        block_count = 0
        for unit in active_units:
            nearby = world.count_nearby_units(unit.position, unit.radius if hasattr(unit, 'radius') else 3)
            proximity = min(1.0, nearby / 5.0)
            total_proximity += proximity
            max_proximity = max(max_proximity, proximity)
            # Count movement blocks from field tracker
            if hasattr(unit, '_field_tracker'):
                field_summary = unit._field_tracker.get_summary(tick)
                block_count += field_summary.total_movement_blocks

        avg_proximity = total_proximity / max(1, len(active_units))

        # Signal field metrics — use all units (not just active) for cumulative signal density
        signal_density = 0.0
        signal_load = 0.0
        if signal_enabled:
            for unit in units:
                if hasattr(unit, '_field_tracker'):
                    # Track both emitted and received signals
                    signal_density += unit._field_tracker._total_signals + unit._field_tracker._total_emissions
                    signal_load += unit._field_tracker._total_emissions

        # Build summary
        avg_pressure = total_pressure / max(1, pressure_cells)
        depletion_rate = 1.0 - avg_pressure  # higher depletion = lower pressure
        avg_load = total_extraction / max(1, len(active_units))
        blocked_rate = block_count / max(1, len(active_units))
        perturbation = signal_density * avg_proximity if signal_enabled else 0.0

        summary = PressureSummary(
            resource_pressure_cells=pressure_cells,
            avg_resource_pressure=avg_pressure,
            max_resource_pressure=max_pressure,
            resource_depletion_rate=depletion_rate,
            total_extraction_events=total_extraction,
            peak_cell_load=max(r.load_score for r in self._extraction_records[-10:]) if self._extraction_records else 0.0,
            avg_load_per_active_unit=avg_load,
            avg_proximity_pressure=avg_proximity,
            max_proximity_pressure=max_proximity,
            active_unit_density=len(active_units) / max(1, world.width * world.height),
            movement_block_pressure=blocked_rate,
            blocked_motion_rate=blocked_rate,
            signal_density=signal_density,
            signal_observation_load=signal_load,
            field_perturbation_score=perturbation,
            total_ticks_sampled=self._tick_count,
        )
        self._pressure_history.append(summary)

        # Bound storage
        if len(self._resource_samples) > self.max_records:
            self._resource_samples = self._resource_samples[-self.max_records:]
        if len(self._extraction_records) > self.max_records:
            self._extraction_records = self._extraction_records[-self.max_records:]
        if len(self._pressure_history) > self.max_records:
            self._pressure_history = self._pressure_history[-self.max_records:]

    def get_summary(self) -> Dict[str, Any]:
        """Get final pressure analysis summary."""
        if not self._pressure_history:
            return self._empty_summary()

        last = self._pressure_history[-1]
        return {
            "resource_pressure_cells": last.resource_pressure_cells,
            "avg_resource_pressure": last.avg_resource_pressure,
            "max_resource_pressure": last.max_resource_pressure,
            "resource_depletion_rate": last.resource_depletion_rate,
            "total_extraction_events": last.total_extraction_events,
            "peak_cell_load": last.peak_cell_load,
            "avg_load_per_active_unit": last.avg_load_per_active_unit,
            "avg_proximity_pressure": last.avg_proximity_pressure,
            "max_proximity_pressure": last.max_proximity_pressure,
            "active_unit_density": last.active_unit_density,
            "movement_block_pressure": last.movement_block_pressure,
            "blocked_motion_rate": last.blocked_motion_rate,
            "signal_density": last.signal_density,
            "signal_observation_load": last.signal_observation_load,
            "field_perturbation_score": last.field_perturbation_score,
            "total_ticks_sampled": last.total_ticks_sampled,
            "total_samples": len(self._resource_samples),
            "total_extraction_records": len(self._extraction_records),
        }

    def _empty_summary(self) -> Dict[str, Any]:
        return {k: 0 for k in [
            "resource_pressure_cells", "avg_resource_pressure",
            "max_resource_pressure", "resource_depletion_rate",
            "total_extraction_events", "peak_cell_load",
            "avg_load_per_active_unit", "avg_proximity_pressure",
            "max_proximity_pressure", "active_unit_density",
            "movement_block_pressure", "blocked_motion_rate",
            "signal_density", "signal_observation_load",
            "field_perturbation_score", "total_ticks_sampled",
            "total_samples", "total_extraction_records",
        ]}
