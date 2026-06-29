"""Simulation state snapshot."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from machine_sim.agents.base import MachineState
from machine_sim.sim.events import Event


@dataclass
class SimulationState:
    tick: int
    agents: List[MachineState]
    world: Dict[str, Any]
    events: List[Event]

    def to_dict(self) -> Dict[str, Any]:
        from dataclasses import asdict
        return asdict(self)
