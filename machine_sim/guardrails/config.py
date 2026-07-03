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
    "fabrication_enabled", "population_cap", "fabrication_interval",
    "fabrication_power_cost", "fabrication_material_cost", "fabrication_variation",
    "capsule_enabled", "telemetry_enabled", "reconciliation_enabled",
    "reconciliation_interval", "reconciliation_radius", "lineage_drift_enabled",
    "pressure_analysis_enabled", "signal_dynamics_enabled", "trace_compression_enabled",
    "trace_drift_enabled", "summary_consistency_enabled", "long_run_adaptation_enabled",
}

# Allowed memory event_type labels
ALLOWED_MEMORY_LABELS: Set[str] = {
    "move", "move_failed", "harvest", "harvest_empty",
    "scan", "collect", "collect_empty",
    "maintain", "maintain_failed", "idle",
    "movement_blocked", "emit_signal",
}
