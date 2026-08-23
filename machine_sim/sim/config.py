"""Simulation configuration."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

from machine_sim.guardrails.runtime import StateViolation, validate_config_keys


@dataclass
class SimConfig:
    grid_width: int = 20
    grid_height: int = 20
    resource_density: float = 0.3
    hazard_density: float = 0.05
    unit_count: int = 5
    power_drain_rate: float = 1.0
    max_ticks: int = 500
    seed: int = 42
    signal_enabled: bool = False
    signal_pattern_count: int = 3
    signal_energy_cost: float = 2.0
    signal_default_radius: int = 3
    signal_default_decay: float = 0.1
    signal_default_duration: int = 10
    signal_observation_window: int = 10
    adaptive_enabled: bool = False
    fabrication_enabled: bool = False
    unit_capacity: int = 20
    fabrication_interval: int = 25
    fabrication_power_cost: float = 30.0
    fabrication_material_cost: float = 5.0
    fabrication_variation: float = 0.1
    fabrication_min_power_ratio: float = 0.4
    fabrication_min_component_health: float = 0.3
    capsule_enabled: bool = False
    telemetry_enabled: bool = False
    reconciliation_enabled: bool = False
    reconciliation_interval: int = 5
    reconciliation_radius: int = 3
    lineage_drift_enabled: bool = False
    pressure_analysis_enabled: bool = False
    signal_dynamics_enabled: bool = False
    trace_compression_enabled: bool = False
    trace_drift_enabled: bool = False
    summary_consistency_enabled: bool = False
    long_run_adaptation_enabled: bool = False
    multi_generation_trace_enabled: bool = False
    component_degradation_scale: float = 1.0
    trajectory_compression_enabled: bool = False
    trajectory_compression_max_segments: int = 64
    neural_controller_enabled: bool = False
    neural_controller_mode: str = "replace"
    neural_plasticity_enabled: bool = True
    neural_hidden_size: int = 16
    neural_plasticity_rate: float = 0.01

    # M19: Architecture variation
    neural_architecture_variation_enabled: bool = False
    minimum_hidden_size: int = 8
    initial_hidden_size: int = 16
    maximum_hidden_size: int = 64
    minimum_recurrent_density: float = 0.15
    initial_recurrent_density: float = 1.0
    maximum_recurrent_density: float = 1.0
    minimum_plasticity_rate: float = 0.0
    maximum_plasticity_rate: float = 0.05
    initial_architecture_policy: str = "uniform_baseline"
    hidden_size_variation_probability: float = 0.5
    hidden_size_variation_max_step: int = 2
    recurrent_density_variation_probability: float = 0.5
    recurrent_density_variation_max_step: float = 0.10
    plasticity_rate_variation_probability: float = 0.3
    plasticity_rate_variation_max_step: float = 0.005
    neural_processing_base_cost: float = 0.05
    neural_hidden_unit_cost: float = 0.002
    neural_recurrent_connection_cost: float = 0.001
    neural_plastic_update_cost: float = 0.0005
    neural_fabrication_hidden_unit_cost: float = 0.5
    neural_fabrication_connection_cost: float = 0.02

    # M20: Run lifecycle control
    run_control_enabled: bool = False
    checkpoint_enabled: bool = False
    checkpoint_interval: int = 1000
    checkpoint_retention_limit: int = 6
    control_poll_interval: int = 100
    run_progress_interval: int = 500
    run_digest_enabled: bool = False
    run_status_surface_enabled: bool = False

    # M22: Executable per-unit design-program substrate
    design_program_enabled: bool = False
    program_execution_budget: int = 512
    program_min_length: int = 1
    program_max_length: int = 128
    program_base_cost: float = 0.5
    program_per_instruction_cost: float = 0.01
    program_substitution_probability: float = 0.0
    program_operand_mutation_probability: float = 0.0
    program_insertion_probability: float = 0.0
    program_deletion_probability: float = 0.0

    @classmethod
    def from_toml(cls, path: Path) -> SimConfig:
        with open(path, "rb") as f:
            data = tomllib.load(f)
        sim_data = data.get("simulation", {})
        validate_config_keys(set(sim_data.keys()))
        return cls(**sim_data)

    def to_dict(self) -> Dict[str, Any]:
        from dataclasses import asdict
        return asdict(self)
