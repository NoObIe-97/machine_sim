"""Guardrail configuration — forbidden terms, allowed fields, allowed labels."""

from __future__ import annotations

from typing import Set

# Anthropomorphic / social / emotional / moral / institutional terms
# banned in runtime machine logic (agent code, environment interaction logic)
FORBIDDEN_LEXICAL_PATTERNS = [
    r"\b(goal|desire|want|wish|intend|aim|motivation|motivated)\b",
    r"\b(love|hate|fear|anger|joy|sadness|happy|angry|afraid|mood|temperament)\b",
    r"\b(moral|ethical|ethics|virtue|sin|guilt|shame|conscience)\b",
    r"\b(social|society|community|friend|enemy|ally|tribe|family|group)\b",
    r"\b(language|speak|word|sentence|communicate|talk|dialogue)\b",
    r"\b(consciousness|awareness|aware|sentient|sentience|experience)\b",
    r"\b(law|crime|trade|commerce|economy|government|leadership)\b",
    r"\b(personality|character|identity|ego)\b",
    r"\b(believe|faith|trust|doubt|hope)\b",
    r"\b(purpose|meaning|reason|why|motivation)\b",
]

# Allowed state fields in MachineState
ALLOWED_STATE_FIELDS: Set[str] = {
    "unit_id", "position", "power_reserve", "max_power",
    "components", "sensor_readings", "local_memory",
    "action_budget", "is_active", "unit_class",
}

# Allowed component names
ALLOWED_COMPONENT_NAMES: Set[str] = {
    "sensor", "actuator", "processor", "power_cell",
}

# Allowed action type names
ALLOWED_ACTION_NAMES: Set[str] = {
    "MOVE", "SCAN", "HARVEST", "COLLECT", "MAINTAIN", "IDLE", "EMIT_SIGNAL", "FABRICATE",
}

# Allowed event type labels
ALLOWED_EVENT_LABELS: Set[str] = {
    "tick_begin", "tick_end", "unit_action", "resource_harvest",
    "resource_depleted", "component_damage", "component_repair",
    "unit_deactivated", "hazard_encounter", "environment_update",
    # action result event types
    "move", "move_failed", "harvest", "harvest_empty",
    "scan", "collect", "collect_empty",
    "maintain", "maintain_failed", "idle",
    # Milestone 2 emitted interaction event types
    "movement_blocked", "unit_proximity",
    # Milestone 3 signal event types
    "emit_signal", "signal_emitted", "signal_received",
    # Milestone 6 fabrication event types
    "fabrication_attempted", "fabrication_succeeded", "fabrication_failed",
}

# Allowed config keys
ALLOWED_CONFIG_KEYS: Set[str] = {
    "grid_width", "grid_height", "resource_density", "hazard_density",
    "unit_count", "power_drain_rate", "max_ticks", "seed",
    "signal_enabled", "signal_pattern_count", "signal_energy_cost",
    "signal_default_radius", "signal_default_decay", "signal_default_duration",
    "signal_observation_window", "adaptive_enabled",
    "fabrication_enabled", "unit_capacity", "fabrication_interval",
    "fabrication_power_cost", "fabrication_material_cost", "fabrication_variation",
    "fabrication_min_power_ratio", "fabrication_min_component_health",
    "capsule_enabled", "telemetry_enabled", "reconciliation_enabled",
    "reconciliation_interval", "reconciliation_radius", "lineage_drift_enabled",
    "pressure_analysis_enabled", "signal_dynamics_enabled", "trace_compression_enabled",
    "trace_drift_enabled", "summary_consistency_enabled", "long_run_adaptation_enabled",
    "multi_generation_trace_enabled",
    "component_degradation_scale",
    "trajectory_compression_enabled",
    "trajectory_compression_max_segments",
    "neural_controller_enabled",
    "neural_controller_mode",
    "neural_plasticity_enabled",
    "neural_hidden_size",
    "neural_plasticity_rate",
    "neural_architecture_variation_enabled",
    "minimum_hidden_size",
    "initial_hidden_size",
    "maximum_hidden_size",
    "minimum_recurrent_density",
    "initial_recurrent_density",
    "maximum_recurrent_density",
    "minimum_plasticity_rate",
    "maximum_plasticity_rate",
    "initial_architecture_policy",
    "hidden_size_variation_probability",
    "hidden_size_variation_max_step",
    "recurrent_density_variation_probability",
    "recurrent_density_variation_max_step",
    "plasticity_rate_variation_probability",
    "plasticity_rate_variation_max_step",
    "neural_processing_base_cost",
    "neural_hidden_unit_cost",
    "neural_recurrent_connection_cost",
    "neural_plastic_update_cost",
    "neural_fabrication_hidden_unit_cost",
    "neural_fabrication_connection_cost",
    "run_control_enabled",
    "checkpoint_enabled",
    "checkpoint_interval",
    "checkpoint_retention_limit",
    "control_poll_interval",
    "run_progress_interval",
    "run_digest_enabled",
    "run_status_surface_enabled",
    # M22 design-program substrate
    "design_program_enabled",
    "program_execution_budget",
    "program_min_length",
    "program_max_length",
    "program_base_cost",
    "program_per_instruction_cost",
    "program_substitution_probability",
    "program_operand_mutation_probability",
    "program_insertion_probability",
    "program_deletion_probability",
}

# Allowed memory event_type labels
ALLOWED_MEMORY_LABELS: Set[str] = {
    "move", "move_failed", "harvest", "harvest_empty",
    "scan", "collect", "collect_empty",
    "maintain", "maintain_failed", "idle",
    "movement_blocked", "emit_signal",
}
