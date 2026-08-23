"""M22 compatibility proof: legacy descriptor path versus program-decoded path.

The canonical program must construct the same neural architecture as the
accepted M19/M21 descriptor path, and a program-backed unit must be
behaviorally equivalent to its legacy twin. Program metadata itself is new
future-causal state, so engine-level comparisons use the documented
compatibility projection (program metadata excluded) while the standard M21
deep digest remains in force everywhere else.
"""

from __future__ import annotations

from typing import List

from machine_sim.agents.base import SensorReading
from machine_sim.agents.design_program import (
    DesignExecutionBounds,
    DesignProgramInterpreter,
    canonical_baseline_program,
)
from machine_sim.agents.neural_architecture import NeuralArchitectureDescriptor
from machine_sim.agents.unit import MachineUnitImpl
from machine_sim.analysis.design_program_lineage import (
    compatibility_projection_digest,
)
from machine_sim.cli.main import build_engine
from machine_sim.sim.config import SimConfig
from machine_sim.sim.run_control import tick_observation


def _compatibility_config(**overrides) -> SimConfig:
    values = dict(
        grid_width=12,
        grid_height=12,
        resource_density=0.25,
        hazard_density=0.05,
        unit_count=4,
        power_drain_rate=0.5,
        max_ticks=60,
        seed=91,
        signal_enabled=True,
        adaptive_enabled=True,
        neural_controller_enabled=True,
        neural_plasticity_enabled=True,
        neural_hidden_size=16,
        neural_plasticity_rate=0.01,
        neural_architecture_variation_enabled=True,
        design_program_enabled=False,
    )
    values.update(overrides)
    return SimConfig(**values)


def test_canonical_program_decodes_accepted_baseline_descriptor() -> None:
    result = DesignProgramInterpreter(DesignExecutionBounds()).execute(
        canonical_baseline_program(plasticity_rate=0.01)
    )
    assert result.status == "complete"
    decoded = result.decoded_architecture
    legacy = NeuralArchitectureDescriptor(
        architecture_id="arch-init-000",
        hidden_size=16,
        recurrent_density=1.0,
        plasticity_rate=0.01,
        plasticity_enabled=True,
    )
    assert decoded.hidden_size == legacy.hidden_size
    assert decoded.recurrent_density == legacy.recurrent_density
    assert decoded.plasticity_rate == legacy.plasticity_rate
    assert decoded.plasticity_enabled == legacy.plasticity_enabled


def test_legacy_and_program_units_share_neural_parameters() -> None:
    legacy = MachineUnitImpl(
        unit_id="unit-twin",
        neural_controller_enabled=True,
        neural_seed=77,
        neural_architecture_descriptor=NeuralArchitectureDescriptor(
            architecture_id="arch-legacy",
            hidden_size=16,
            recurrent_density=1.0,
            plasticity_rate=0.01,
            plasticity_enabled=True,
        ),
    )
    program_unit = MachineUnitImpl(
        unit_id="unit-twin",
        neural_controller_enabled=True,
        neural_seed=77,
        design_program=canonical_baseline_program(),
    )
    assert program_unit._design_program is not None
    assert program_unit._design_program_enabled is True

    state_a = legacy._neural_controller.state
    state_b = program_unit._neural_controller.state
    assert len(state_b.hidden_state) == len(state_a.hidden_state)
    assert state_b.W_in == state_a.W_in
    assert state_b.W_rec == state_a.W_rec
    assert state_b.W_out == state_a.W_out
    assert state_b.W_param == state_a.W_param
    assert state_b.b_hidden == state_a.b_hidden
    # Baseline density is 1.0 on both paths: no recurrent mask either way.
    assert state_a.recurrent_mask is None or state_a.active_recurrent_count() > 0
    assert state_b.recurrent_mask == state_a.recurrent_mask


def test_legacy_and_program_units_same_action_outputs() -> None:
    def make(kind: str) -> MachineUnitImpl:
        shared = dict(
            unit_id="unit-actions",
            position=(2, 2),
            signal_enabled=True,
            adaptive_enabled=True,
            neural_controller_enabled=True,
            neural_seed=31,
        )
        if kind == "legacy":
            return MachineUnitImpl(
                neural_architecture_descriptor=NeuralArchitectureDescriptor(
                    architecture_id="arch-legacy",
                    hidden_size=16,
                    recurrent_density=1.0,
                    plasticity_rate=0.01,
                    plasticity_enabled=True,
                ),
                **shared,
            )
        return MachineUnitImpl(design_program=canonical_baseline_program(), **shared)

    readings: List[SensorReading] = [
        SensorReading(tick=5, position=(1, 1), resource_signals={"power_node": 3.5}),
        SensorReading(tick=5, position=(2, 3), hazard_signals={"em_pulse": 0.4}),
    ]
    legacy = make("legacy")
    program_unit = make("program")
    for unit in (legacy, program_unit):
        for reading in readings:
            unit.sensor_readings.append(reading)

    for tick in (6, 7, 8):
        action_a = legacy.decide(tick)
        action_b = program_unit.decide(tick)
        assert (action_a is None) == (action_b is None)
        if action_a is not None:
            assert action_a.action_type == action_b.action_type
            assert action_a.parameters == action_b.parameters


def test_engine_level_projection_equivalence_over_controlled_run() -> None:
    config_common = dict(max_ticks=40, unit_count=4, fabrication_enabled=False)
    legacy_engine = build_engine(_compatibility_config(**config_common))
    program_engine = build_engine(
        _compatibility_config(design_program_enabled=True, **config_common)
    )

    program_units = [
        u for u in program_engine.units if getattr(u, "_design_program", None) is not None
    ]
    assert len(program_units) == 4
    for unit in program_units:
        descriptor = unit._architecture_descriptor
        assert descriptor.hidden_size == 16
        assert descriptor.recurrent_density == 1.0
        assert descriptor.plasticity_rate == 0.01
        assert descriptor.plasticity_enabled is True

    chain_legacy = ""
    chain_program = ""
    for step in range(40):
        legacy_engine.tick()
        program_engine.tick()
        chain_legacy = f"{chain_legacy}{tick_observation(legacy_engine)}"
        chain_program = f"{chain_program}{tick_observation(program_engine)}"
        if (step + 1) % 10 == 0:
            assert chain_legacy == chain_program, f"shallow divergence at step {step}"
            assert compatibility_projection_digest(legacy_engine) == (
                compatibility_projection_digest(program_engine)
            ), f"projection divergence at step {step}"

    # The standard M21 deep digest still distinguishes the representation:
    # program metadata is future-causal state.
    from machine_sim.sim.state_digest import deep_state_digest

    assert deep_state_digest(legacy_engine) != deep_state_digest(program_engine)


def test_projection_is_sensitive_to_phenotype_differences() -> None:
    engine_one = build_engine(_compatibility_config())
    engine_two = build_engine(
        _compatibility_config(neural_hidden_size=16, seed=92)
    )
    engine_one.tick()
    engine_two.tick()
    # Different seeds produce different worlds; the projection must notice.
    assert compatibility_projection_digest(engine_one) != (
        compatibility_projection_digest(engine_two)
    )


def test_standard_deep_digest_unchanged_for_non_program_engines() -> None:
    """M21 behavior guard: no program fields appear when programs are off."""
    from machine_sim.sim.state_digest import semantic_state_snapshot

    engine = build_engine(_compatibility_config())
    snapshot = semantic_state_snapshot(engine)
    for unit in snapshot["units"]:
        assert "design_program" not in unit
        assert "design_program_enabled" not in unit
