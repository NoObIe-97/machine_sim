"""Event types and append-only event log."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional


class EventType(Enum):
    TICK_BEGIN = auto()
    TICK_END = auto()
    UNIT_ACTION = auto()
    RESOURCE_HARVEST = auto()
    RESOURCE_DEPLETED = auto()
    COMPONENT_DAMAGE = auto()
    COMPONENT_REPAIR = auto()
    UNIT_DEACTIVATED = auto()
    HAZARD_ENCOUNTER = auto()
    ENVIRONMENT_UPDATE = auto()
    MOVEMENT_BLOCKED = auto()
    UNIT_PROXIMITY = auto()
    SIGNAL_EMITTED = auto()
    SIGNAL_RECEIVED = auto()


@dataclass(frozen=True, slots=True)
class Event:
    tick: int
    event_type: EventType
    unit_id: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)


class EventLog:
    """Append-only event store for a simulation run."""

    def __init__(self) -> None:
        self._events: List[Event] = []

    def record(self, event: Event) -> None:
        self._events.append(event)

    def begin_tick(self, tick: int) -> None:
        self.record(Event(tick=tick, event_type=EventType.TICK_BEGIN))

    def end_tick(self, tick: int) -> None:
        self.record(Event(tick=tick, event_type=EventType.TICK_END))

    def all_events(self) -> List[Event]:
        return list(self._events)

    def events_for_tick(self, tick: int) -> List[Event]:
        return [e for e in self._events if e.tick == tick]

    def events_for_unit(self, unit_id: str) -> List[Event]:
        return [e for e in self._events if e.unit_id == unit_id]

    def to_json(self) -> str:
        import dataclasses

        def _default(obj):
            if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
                return dataclasses.asdict(obj)
            if isinstance(obj, Enum):
                return obj.name
            if isinstance(obj, (list, tuple)):
                return [_default(i) for i in obj]
            if isinstance(obj, dict):
                return {k: _default(v) for k, v in obj.items()}
            return obj

        return json.dumps(
            [_default(e) for e in self._events],
            indent=2,
            default=_default,
        )
