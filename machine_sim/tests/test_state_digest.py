"""Tests for the M21 deep future-causal semantic-state digest oracle."""

from __future__ import annotations

import json
import random
import subprocess
import sys
from pathlib import Path

import pytest

from machine_sim.agents.unit import MachineUnitImpl
from machine_sim.sim.checkpoint import decode_state, encode_state
from machine_sim.sim.config import SimConfig
from machine_sim.sim.engine import SimEngine
from machine_sim.sim.state_digest import (
    DEEP_DIGEST_SCHEMA_VERSION,
    deep_state_digest,
    semantic_state_schema,
    semantic_state_snapshot,
)


def _neural_config() -> SimConfig:
    return SimConfig(
        grid_width=10,
        grid_height=10,
        resource_density=0.3,
        hazard_density=0.05,
        unit_count=3,
        max_ticks=50,
        seed=42,
        signal_enabled=True,
        adaptive_enabled=True,
        neural_controller_enabled=True,
        neural_architecture_variation_enabled=True,
    )


def _engine_with_ticks(config: SimConfig, ticks: int = 5) -> SimEngine:
    engine = SimEngine(config, seed=config.seed)
    for index in range(config.unit_count):
        engine.register_unit(
            MachineUnitImpl(
                unit_id=f"unit-{index:03d}",
                position=(index, index),
                signal_enabled=config.signal_enabled,
                signal_pattern_count=config.signal_pattern_count,
                signal_energy_cost=config.signal_energy_cost,
                signal_default_radius=config.signal_default_radius,
                signal_default_decay=config.signal_default_decay,
                signal_default_duration=config.signal_default_duration,
                adaptive_enabled=config.adaptive_enabled,
                neural_controller_enabled=config.neural_controller_enabled,
                neural_controller_mode=config.neural_controller_mode,
                neural_plasticity_enabled=config.neural_plasticity_enabled,
                neural_hidden_size=config.neural_hidden_size,
                neural_plasticity_rate=config.neural_plasticity_rate,
                neural_seed=config.seed,
            )
        )
    engine.initialize()
    for _ in range(ticks):
        engine.tick()
    return engine


# 1. Deterministic for identical independently created states.
def test_deep_digest_deterministic_for_independent_states() -> None:
    config = _neural_config()
    engine_a = _engine_with_ticks(config)
    engine_b = _engine_with_ticks(config)
    assert engine_a is not engine_b
    assert deep_state_digest(engine_a) == deep_state_digest(engine_b)


def test_snapshot_contains_only_json_types() -> None:
    engine = _engine_with_ticks(_neural_config())
    text = json.dumps(semantic_state_snapshot(engine), sort_keys=True, allow_nan=False)
    assert isinstance(text, str)


# 2. Stable across subprocess boundary.
def test_deep_digest_stable_across_subprocess(tmp_path: Path) -> None:
    engine = _engine_with_ticks(_neural_config())
    local_digest = deep_state_digest(engine)

    child_script = tmp_path / "digest_child.py"
    child_script.write_text(
        "\n".join(
            [
                "import json",
                "import sys",
                "from machine_sim.agents.unit import MachineUnitImpl",
                "from machine_sim.sim.config import SimConfig",
                "from machine_sim.sim.engine import SimEngine",
                "from machine_sim.sim.state_digest import deep_state_digest",
                "config = SimConfig(**json.loads(sys.argv[1]))",
                "engine = SimEngine(config, seed=config.seed)",
                "for index in range(config.unit_count):",
                "    engine.register_unit(MachineUnitImpl(",
                "        unit_id=f'unit-{index:03d}',",
                "        position=(index, index),",
                "        signal_enabled=True,",
                "        adaptive_enabled=True,",
                "        neural_controller_enabled=True,",
                "        neural_seed=config.seed,",
                "    ))",
                "engine.initialize()",
                "for _ in range(5):",
                "    engine.tick()",
                "print(deep_state_digest(engine))",
            ]
        ),
        encoding="utf-8",
    )
    import os

    repo_root = str(Path(__file__).resolve().parents[2])
    environment = dict(os.environ)
    environment["PYTHONPATH"] = repo_root + os.pathsep + environment.get("PYTHONPATH", "")
    completed = subprocess.run(
        [sys.executable, str(child_script), json.dumps(_neural_config().to_dict())],
        capture_output=True,
        text=True,
        cwd=repo_root,
        env=environment,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == local_digest


# 3. Stable across checkpoint encode/decode.
def test_deep_digest_stable_across_checkpoint_round_trip() -> None:
    engine = _engine_with_ticks(_neural_config(), ticks=7)
    before = deep_state_digest(engine)
    restored = decode_state(encode_state(engine))
    after = deep_state_digest(restored)
    assert before == after


def test_restored_engine_continues_identically() -> None:
    config = _neural_config()
    engine = _engine_with_ticks(config, ticks=7)
    restored = decode_state(encode_state(engine))
    for _ in range(6):
        engine.tick()
        restored.tick()
    assert deep_state_digest(engine) == deep_state_digest(restored)


# 4. Sensitivity: the digest changes for every representative future-causal field.
def _mutated_digest(mutator) -> str:
    engine = _engine_with_ticks(_neural_config(), ticks=4)
    mutator(engine)
    return deep_state_digest(engine)


def test_digest_sensitive_to_resource_quantity() -> None:
    baseline = _mutated_digest(lambda e: None)

    def mutate(engine: SimEngine) -> None:
        for cell in engine.world.grid.values():
            for resource in cell.resources.values():
                resource.quantity += 1.5
                return

    assert _mutated_digest(mutate) != baseline


def test_digest_sensitive_to_resource_regrowth_parameter() -> None:
    baseline = _mutated_digest(lambda e: None)

    def mutate(engine: SimEngine) -> None:
        for cell in engine.world.grid.values():
            for resource in cell.resources.values():
                resource.regrowth_rate += 0.01
                return

    assert _mutated_digest(mutate) != baseline


def test_digest_sensitive_to_hazard_intensity() -> None:
    baseline = _mutated_digest(lambda e: None)

    def mutate(engine: SimEngine) -> None:
        for cell in engine.world.grid.values():
            for hazard in cell.hazards.values():
                hazard.intensity += 0.25
                return

    assert _mutated_digest(mutate) != baseline


def test_digest_sensitive_to_signal_state() -> None:
    baseline = _mutated_digest(lambda e: None)
    assert _mutated_digest(
        lambda e: e.world.signals[0].__setattr__("intensity", e.world.signals[0].intensity + 0.1)
        if e.world.signals
        else e.world.emit_signal("unit-000", (0, 0), 1, 0.75, 3, 0.1, e.tick_count),
    ) != baseline


def test_digest_sensitive_to_unit_power() -> None:
    baseline = _mutated_digest(lambda e: None)
    assert _mutated_digest(lambda e: e.units[0].__setattr__("power_reserve", e.units[0].power_reserve - 3.0)) != baseline


def test_digest_sensitive_to_component_health() -> None:
    baseline = _mutated_digest(lambda e: None)
    assert _mutated_digest(
        lambda e: e.units[0].components["sensor"].__setattr__("health", 0.42)
    ) != baseline


def test_digest_sensitive_to_neural_hidden_state() -> None:
    baseline = _mutated_digest(lambda e: None)

    def mutate(engine: SimEngine) -> None:
        state = engine.units[0]._neural_controller.state
        state.hidden_state[0] += 0.05

    assert _mutated_digest(mutate) != baseline


def test_digest_sensitive_to_neural_weight() -> None:
    baseline = _mutated_digest(lambda e: None)

    def mutate(engine: SimEngine) -> None:
        state = engine.units[0]._neural_controller.state
        state.W_out[0][0] += 0.03

    assert _mutated_digest(mutate) != baseline


def test_digest_sensitive_to_recurrent_mask() -> None:
    baseline = _mutated_digest(lambda e: None)

    def mutate(engine: SimEngine) -> None:
        controller = engine.units[0]._neural_controller
        if controller.state.recurrent_mask is None:
            size = len(controller.state.hidden_state)
            controller.state.recurrent_mask = [[1.0] * size for _ in range(size)]
        else:
            controller.state.recurrent_mask[0][0] = 1.0 - controller.state.recurrent_mask[0][0]

    assert _mutated_digest(mutate) != baseline


def test_digest_sensitive_to_architecture_descriptor() -> None:
    baseline = _mutated_digest(lambda e: None)

    def mutate(engine: SimEngine) -> None:
        descriptor = engine.units[0]._architecture_descriptor
        if descriptor is None:
            from machine_sim.agents.neural_architecture import NeuralArchitectureDescriptor

            descriptor = NeuralArchitectureDescriptor(
                architecture_id="arch-test-000",
                hidden_size=engine.units[0]._neural_controller.config.hidden_size,
                recurrent_density=1.0,
                plasticity_rate=0.01,
                plasticity_enabled=True,
            )
            engine.units[0]._architecture_descriptor = descriptor
        else:
            descriptor.hidden_size += 1

    assert _mutated_digest(mutate) != baseline


def test_digest_sensitive_to_adaptive_scalar_state() -> None:
    baseline = _mutated_digest(lambda e: None)

    def mutate(engine: SimEngine) -> None:
        engine.units[0]._adaptive_state.move_weight += 0.01

    assert _mutated_digest(mutate) != baseline


def test_digest_sensitive_to_rng_state() -> None:
    baseline = _mutated_digest(lambda e: None)
    assert _mutated_digest(lambda e: e.rng.random()) != baseline


def test_digest_sensitive_to_fabrication_next_id_counter() -> None:
    baseline = _mutated_digest(lambda e: None)
    assert _mutated_digest(
        lambda e: setattr(e.fabrication_engine, "_next_unit_id", e.fabrication_engine._next_unit_id + 7)
    ) != baseline


def test_digest_sensitive_to_world_occupancy_change() -> None:
    baseline = _mutated_digest(lambda e: None)

    def mutate(engine: SimEngine) -> None:
        source = engine.units[0]
        target = None
        for pos, cell in engine.world.grid.items():
            if cell.unit_id is None:
                target = pos
                break
        engine.world.grid[source.position].unit_id = None
        source.position = target
        engine.world.grid[target].unit_id = source.unit_id

    assert _mutated_digest(mutate) != baseline


# 5. Insensitive to output-only trace appends.
def test_digest_unchanged_by_output_only_trace_appends() -> None:
    engine = _engine_with_ticks(_neural_config(), ticks=4)
    before = deep_state_digest(engine)

    engine._adaptive_state_snapshots.append({"tick": 999, "unit_id": "unit-000"})
    engine._neural_state_trace.append({"tick": 999, "unit_id": "unit-000"})
    engine._neural_action_trace.append({"tick": 999, "action_logits": [0.1] * 7})
    engine._neural_plasticity_trace.append({"tick": 999, "w_out_delta": 0.001})
    engine._neural_successor_transfer_trace.append({"tick": 999})
    engine._architecture_transfer_trace.append({"tick": 999})
    engine._architecture_distribution_trace.append({"tick": 999})
    engine._architecture_cost_trace.append({"tick": 999})
    engine._local_feedback_trace = getattr(engine, "_local_feedback_trace", [])
    engine._local_feedback_trace.append({"tick": 999})
    engine._total_processing_cost += 12.34
    engine.correlator._signal_history.append((9999, "unit-000", 1, {}))
    engine.fabrication_engine._lineage_records.append(object())
    engine.capsule_manager._capsules.append(object())
    engine.capsule_manager._capsule_count += 1
    engine.event_log._events.append(
        engine.event_log._events[-1] if engine.event_log._events else None
    )

    assert deep_state_digest(engine) == before


def test_digest_unchanged_by_tick_event_buffer_content() -> None:
    engine = _engine_with_ticks(_neural_config(), ticks=4)
    before = deep_state_digest(engine)
    from machine_sim.sim.events import Event, EventType

    engine.event_log._tick_events.append(
        Event(tick=engine.tick_count, event_type=EventType.TICK_BEGIN)
    )
    assert deep_state_digest(engine) == before


# Schema declaration.
def test_semantic_state_schema_present_and_declared() -> None:
    schema = semantic_state_schema()
    assert schema["schema_version"] == DEEP_DIGEST_SCHEMA_VERSION
    assert schema["included"] and schema["excluded"]
    excluded_fields = json.dumps(schema["excluded"])
    for required_exclusion in (
        "_neural_action_trace",
        "_lineage_records",
        "_capsules",
        "wall-clock timestamps",
        "benchmark performance counters",
    ):
        assert required_exclusion in excluded_fields


def test_schema_artifact_writer(tmp_path: Path) -> None:
    from machine_sim.sim.state_digest import write_schema_artifact

    target = write_schema_artifact(tmp_path / "deep_state_digest_schema.json")
    document = json.loads(target.read_text(encoding="utf-8"))
    assert document["schema_version"] == DEEP_DIGEST_SCHEMA_VERSION
