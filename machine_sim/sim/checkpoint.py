"""Deterministic, inspectable checkpoint capture and restore for simulation runs.

The encoder writes a JSON document that round-trips the live object graph of a
`SimEngine` without any third-party dependency and without a binary pickle
stream. Object reconstruction on load is restricted to an explicit module
prefix allowlist, so a checkpoint file cannot cause an arbitrary class to be
imported or constructed.

Encoding rules:

* primitives (``None``, ``bool``, ``int``, ``float``, ``str``) are emitted as-is
* every other node is a tagged mapping carrying a ``$`` type tag
* mappings are emitted with sorted keys, sets are emitted in canonical order,
  and floats use the shortest round-trip representation, so identical state
  always produces byte-identical output
* shared objects are emitted once and referenced afterwards, so aliasing such as
  ``engine.rng is engine.world.rng`` survives a restore
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import time
from collections import deque
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

CHECKPOINT_SCHEMA_VERSION = "1.0.0"

ALLOWED_MODULE_PREFIXES: Tuple[str, ...] = ("machine_sim.",)

CHECKPOINT_FILE_PATTERN = "checkpoint_[0-9]*.json"
CHECKPOINT_INDEX_NAME = "checkpoint_index.json"

# Attributes deliberately left out of the captured payload. The append-only
# event store is an output artifact rather than live tick-loop state: the tick
# loop only reads the per-tick buffer, which is captured.
FIELD_EXCLUSIONS: Dict[str, Set[str]] = {
    "machine_sim.sim.events:EventLog": {"_events"},
}

# Rebuilt values for excluded attributes when a payload is decoded.
FIELD_DEFAULTS: Dict[str, Dict[str, Callable[[], Any]]] = {
    "machine_sim.sim.events:EventLog": {"_events": list},
}


class CheckpointError(Exception):
    """Raised when a checkpoint cannot be encoded, decoded, or validated."""


def _type_key(cls: type) -> str:
    return f"{cls.__module__}:{cls.__qualname__}"


def _is_allowed_type_key(key: str) -> bool:
    module_name = key.split(":", 1)[0]
    return any(module_name.startswith(prefix) for prefix in ALLOWED_MODULE_PREFIXES)


def _resolve_type_key(key: str) -> Any:
    if not _is_allowed_type_key(key):
        raise CheckpointError(f"type key outside the allowlist: {key}")
    module_name, _, qual_name = key.partition(":")
    import importlib

    module = importlib.import_module(module_name)
    target: Any = module
    for part in qual_name.split("."):
        target = getattr(target, part, None)
        if target is None:
            raise CheckpointError(f"unresolvable type key: {key}")
    return target


def _member_order_key(value: Any) -> Optional[str]:
    """Return a canonical ordering key for a set member, or None if unsupported.

    Set iteration order depends on insertion history, so members are emitted in
    a canonical order. Integers are zero-padded so lexical ordering matches
    numeric ordering. Mappings keep their insertion order instead, because
    mapping order is observable by the tick loop.
    """
    if value is None:
        return "0:"
    if isinstance(value, bool):
        return f"1:{int(value)}"
    if isinstance(value, int):
        return f"2:{value:+021d}"
    if isinstance(value, float):
        return f"3:{value:+030.9f}"
    if isinstance(value, str):
        return f"4:{value}"
    if isinstance(value, bytes):
        return f"5:{value.hex()}"
    if isinstance(value, Enum):
        return f"6:{_type_key(type(value))}.{value.name}"
    if isinstance(value, (tuple, list)):
        member_keys = [_member_order_key(item) for item in value]
        if any(k is None for k in member_keys):
            return None
        return "7:[" + ",".join(k for k in member_keys if k is not None) + "]"
    return None


def _canonical_member_order(members: List[Any]) -> List[Any]:
    keys = [_member_order_key(member) for member in members]
    if any(key is None for key in keys):
        return members
    return [member for _, member in sorted(zip(keys, members), key=lambda pair: pair[0])]


def _object_fields(obj: Any) -> Dict[str, Any]:
    if hasattr(obj, "__dict__"):
        return dict(vars(obj))
    fields: Dict[str, Any] = {}
    for slot_name in getattr(type(obj), "__slots__", ()):  # slotted dataclasses
        if hasattr(obj, slot_name):
            fields[slot_name] = getattr(obj, slot_name)
    return fields


class _Encoder:
    """Depth-first encoder with shared-object memoization."""

    def __init__(self) -> None:
        self._seen: Dict[int, int] = {}
        self._active: Set[int] = set()
        self._next_ref = 0
        self._keepalive: List[Any] = []

    def encode(self, obj: Any) -> Any:
        if obj is None or isinstance(obj, (bool, int, float, str)):
            return obj

        obj_id = id(obj)
        if obj_id in self._seen:
            return {"$": "ref", "i": self._seen[obj_id]}
        if obj_id in self._active:
            raise CheckpointError(
                f"cyclic reference through {type(obj).__name__} is not encodable"
            )

        self._active.add(obj_id)
        try:
            node = self._encode_node(obj)
        finally:
            self._active.discard(obj_id)

        ref_id = self._next_ref
        self._next_ref += 1
        node["i"] = ref_id
        self._seen[obj_id] = ref_id
        self._keepalive.append(obj)
        return node

    def _encode_node(self, obj: Any) -> Dict[str, Any]:
        if isinstance(obj, Enum):
            return {"$": "enum", "c": _type_key(type(obj)), "n": obj.name}
        if isinstance(obj, bytes):
            return {"$": "bytes", "v": obj.hex()}
        if isinstance(obj, deque):
            return {
                "$": "deque",
                "maxlen": obj.maxlen,
                "v": [self.encode(item) for item in obj],
            }
        if isinstance(obj, list):
            return {"$": "list", "v": [self.encode(item) for item in obj]}
        if isinstance(obj, tuple):
            return {"$": "tuple", "v": [self.encode(item) for item in obj]}
        if isinstance(obj, (set, frozenset)):
            return {
                "$": "frozenset" if isinstance(obj, frozenset) else "set",
                "v": [self.encode(item) for item in _canonical_member_order(list(obj))],
            }
        if isinstance(obj, dict):
            if all(isinstance(k, str) for k in obj):
                return {
                    "$": "smap",
                    "v": [[k, self.encode(value)] for k, value in obj.items()],
                }
            return {
                "$": "map",
                "v": [[self.encode(k), self.encode(v)] for k, v in obj.items()],
            }
        if isinstance(obj, random.Random):
            version, internal, gauss_next = obj.getstate()
            return {
                "$": "rng",
                "version": version,
                "internal": list(internal),
                "gauss_next": gauss_next,
            }
        if callable(obj) and hasattr(obj, "__module__") and hasattr(obj, "__qualname__"):
            key = f"{obj.__module__}:{obj.__qualname__}"
            if "<locals>" in key or "<lambda>" in key:
                raise CheckpointError(f"non-addressable callable is not encodable: {key}")
            return {"$": "fn", "c": key}

        type_key = _type_key(type(obj))
        if not _is_allowed_type_key(type_key):
            raise CheckpointError(f"type outside the allowlist: {type_key}")
        excluded = FIELD_EXCLUSIONS.get(type_key, frozenset())
        fields = _object_fields(obj)
        return {
            "$": "obj",
            "c": type_key,
            "f": [
                [name, self.encode(value)]
                for name, value in fields.items()
                if name not in excluded
            ],
        }


class _Decoder:
    def __init__(self) -> None:
        self._refs: Dict[int, Any] = {}

    def decode(self, node: Any) -> Any:
        if node is None or isinstance(node, (bool, int, float, str)):
            return node
        if not isinstance(node, dict) or "$" not in node:
            raise CheckpointError(f"unrecognized payload node: {type(node).__name__}")

        tag = node["$"]
        if tag == "ref":
            ref_id = node.get("i")
            if ref_id not in self._refs:
                raise CheckpointError(f"unresolved reference: {ref_id}")
            return self._refs[ref_id]

        value = self._decode_node(tag, node)
        if "i" in node:
            self._refs[node["i"]] = value
        return value

    def _decode_node(self, tag: str, node: Dict[str, Any]) -> Any:
        if tag == "enum":
            enum_cls = _resolve_type_key(node["c"])
            return enum_cls[node["n"]]
        if tag == "bytes":
            return bytes.fromhex(node["v"])
        if tag == "list":
            return [self.decode(item) for item in node["v"]]
        if tag == "tuple":
            return tuple(self.decode(item) for item in node["v"])
        if tag == "set":
            return {self.decode(item) for item in node["v"]}
        if tag == "frozenset":
            return frozenset(self.decode(item) for item in node["v"])
        if tag == "deque":
            return deque((self.decode(item) for item in node["v"]), maxlen=node.get("maxlen"))
        if tag == "smap":
            return {k: self.decode(v) for k, v in node["v"]}
        if tag == "map":
            return {self.decode(k): self.decode(v) for k, v in node["v"]}
        if tag == "rng":
            generator = random.Random()
            generator.setstate(
                (node["version"], tuple(node["internal"]), node["gauss_next"])
            )
            return generator
        if tag == "fn":
            return _resolve_type_key(node["c"])
        if tag == "obj":
            type_key = node["c"]
            cls = _resolve_type_key(type_key)
            instance = object.__new__(cls)
            fields = {name: self.decode(v) for name, v in node["f"]}
            for name, factory in FIELD_DEFAULTS.get(type_key, {}).items():
                fields.setdefault(name, factory())
            if hasattr(instance, "__dict__"):
                instance.__dict__.update(fields)
            else:
                for name, field_value in fields.items():
                    object.__setattr__(instance, name, field_value)
            return instance
        raise CheckpointError(f"unrecognized payload tag: {tag}")


def encode_state(obj: Any) -> Any:
    """Encode an arbitrary in-project object graph into a JSON-able payload."""
    return _Encoder().encode(obj)


def decode_state(payload: Any) -> Any:
    """Decode a payload produced by :func:`encode_state`."""
    return _Decoder().decode(payload)


def canonical_text(payload: Any) -> str:
    """Return the canonical serialized text used for digesting."""
    return _canonical_text(payload)


def _canonical_text(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def payload_digest(payload: Any) -> str:
    """Return the sha256 digest of the canonical serialization of a payload."""
    return hashlib.sha256(_canonical_text(payload).encode("utf-8")).hexdigest()


def config_digest(config: Any) -> str:
    """Return a stable digest of a simulation configuration mapping."""
    if hasattr(config, "to_dict"):
        mapping = config.to_dict()
    elif isinstance(config, dict):
        mapping = config
    else:
        mapping = dict(vars(config))
    return hashlib.sha256(
        json.dumps(mapping, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def event_type_counts(engine: Any) -> Dict[str, int]:
    """Return the per-label counts of the append-only event store."""
    counts: Dict[str, int] = {}
    for event in getattr(engine.event_log, "_events", []):
        label = event.event_type.name.lower()
        counts[label] = counts.get(label, 0) + 1
    return counts


def capture_engine_state(engine: Any) -> Dict[str, Any]:
    """Encode the live engine object graph into a checkpoint payload."""
    return {
        "engine": encode_state(engine),
        "event_type_counts": event_type_counts(engine),
        "recorded_event_count": len(getattr(engine.event_log, "_events", [])),
    }


def restore_engine_state(payload: Dict[str, Any]) -> Any:
    """Rebuild a `SimEngine` from a checkpoint payload."""
    if "engine" not in payload:
        raise CheckpointError("payload has no engine section")
    return decode_state(payload["engine"])


def checkpoint_path(output_dir: Path, tick: int) -> Path:
    return Path(output_dir) / "checkpoints" / f"checkpoint_{tick:09d}.json"


def write_checkpoint(
    engine: Any,
    output_dir: Path,
    tick: int,
    run_id: str,
    config_fingerprint: str,
) -> Path:
    """Write a checkpoint for the current engine state and return its path."""
    payload = capture_engine_state(engine)
    document = {
        "checkpoint_schema_version": CHECKPOINT_SCHEMA_VERSION,
        "run_id": run_id,
        "tick": int(tick),
        "created_at_unix": time.time(),
        "config_digest": config_fingerprint,
        "state_digest": payload_digest(payload),
        "payload": payload,
    }
    target = checkpoint_path(output_dir, tick)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".json.partial")
    temporary.write_text(
        json.dumps(document, sort_keys=True, separators=(",", ":")), encoding="utf-8"
    )
    os.replace(temporary, target)
    return target


def load_checkpoint(path: Path) -> Dict[str, Any]:
    """Read and structurally check a checkpoint document."""
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CheckpointError(f"checkpoint file not present: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CheckpointError(f"checkpoint file is not parseable: {path}") from exc
    if document.get("checkpoint_schema_version") != CHECKPOINT_SCHEMA_VERSION:
        raise CheckpointError(
            f"unsupported checkpoint schema version: "
            f"{document.get('checkpoint_schema_version')}"
        )
    return document


def restore_from_checkpoint(path: Path) -> Tuple[Any, Dict[str, Any]]:
    """Load a checkpoint file and rebuild the engine it captured."""
    document = load_checkpoint(path)
    recorded = document.get("state_digest")
    recomputed = payload_digest(document.get("payload", {}))
    if recorded != recomputed:
        raise CheckpointError(
            f"checkpoint state digest mismatch: recorded={recorded} recomputed={recomputed}"
        )
    engine = restore_engine_state(document["payload"])
    return engine, document


REQUIRED_CHECKPOINT_FIELDS = (
    "checkpoint_schema_version",
    "run_id",
    "tick",
    "created_at_unix",
    "config_digest",
    "state_digest",
    "payload",
)


def validate_checkpoint(path: Path) -> Dict[str, Any]:
    """Return a structured validation report for a checkpoint file.

    The validator never runs the simulation and never modifies the file.
    """
    path = Path(path)
    checks: Dict[str, str] = {}
    detail: Dict[str, Any] = {"path": str(path)}

    document: Optional[Dict[str, Any]] = None
    try:
        raw = path.read_text(encoding="utf-8")
        checks["file_readable_check"] = "PASS"
    except OSError:
        checks["file_readable_check"] = "FAIL"
        raw = ""

    if checks.get("file_readable_check") == "PASS":
        try:
            document = json.loads(raw)
            checks["json_parseable_check"] = "PASS"
        except json.JSONDecodeError:
            checks["json_parseable_check"] = "FAIL"
    else:
        checks["json_parseable_check"] = "FAIL"

    if isinstance(document, dict):
        checks["schema_version_check"] = (
            "PASS"
            if document.get("checkpoint_schema_version") == CHECKPOINT_SCHEMA_VERSION
            else "FAIL"
        )
        missing = [f for f in REQUIRED_CHECKPOINT_FIELDS if f not in document]
        checks["required_fields_check"] = "PASS" if not missing else "FAIL"
        detail["missing_fields"] = missing

        tick_value = document.get("tick")
        checks["tick_bounds_check"] = (
            "PASS" if isinstance(tick_value, int) and tick_value >= 0 else "FAIL"
        )
        detail["tick"] = tick_value

        checks["config_digest_present_check"] = (
            "PASS" if isinstance(document.get("config_digest"), str) else "FAIL"
        )

        recomputed = payload_digest(document.get("payload", {}))
        checks["state_digest_check"] = (
            "PASS" if recomputed == document.get("state_digest") else "FAIL"
        )
        detail["recorded_state_digest"] = document.get("state_digest")
        detail["recomputed_state_digest"] = recomputed

        try:
            restore_engine_state(document.get("payload", {}))
            checks["payload_decodable_check"] = "PASS"
        except (CheckpointError, KeyError, TypeError, ValueError) as exc:
            checks["payload_decodable_check"] = "FAIL"
            detail["decode_failure"] = str(exc)
        detail["byte_size"] = len(raw.encode("utf-8"))
    else:
        for name in (
            "schema_version_check",
            "required_fields_check",
            "tick_bounds_check",
            "config_digest_present_check",
            "state_digest_check",
            "payload_decodable_check",
        ):
            checks[name] = "FAIL"
        detail["byte_size"] = len(raw.encode("utf-8"))

    failed = [name for name, result in checks.items() if result != "PASS"]
    return {
        "checkpoint_path": str(path),
        "checks": checks,
        "failed_checks": failed,
        "valid": not failed,
        "detail": detail,
    }


def list_checkpoints(output_dir: Path) -> List[Path]:
    """Return retained checkpoint files ordered by tick."""
    directory = Path(output_dir) / "checkpoints"
    if not directory.exists():
        return []
    return sorted(directory.glob(CHECKPOINT_FILE_PATTERN))


def prune_checkpoints(output_dir: Path, retention_limit: int) -> List[str]:
    """Remove oldest checkpoints beyond the retention limit.

    The most recent checkpoint is never removed.
    """
    if retention_limit <= 0:
        return []
    files = list_checkpoints(output_dir)
    if len(files) <= retention_limit:
        return []
    removable = files[: len(files) - retention_limit]
    pruned: List[str] = []
    for candidate in removable:
        if candidate == files[-1]:
            continue
        try:
            candidate.unlink()
            pruned.append(str(candidate))
        except OSError:
            continue
    return pruned


def write_checkpoint_index(output_dir: Path) -> Path:
    """Write the index of retained checkpoints and return its path."""
    entries: List[Dict[str, Any]] = []
    for file_path in list_checkpoints(output_dir):
        try:
            document = json.loads(file_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        entries.append(
            {
                "tick": document.get("tick"),
                "path": file_path.name,
                "state_digest": document.get("state_digest"),
                "byte_size": file_path.stat().st_size,
                "created_at_unix": document.get("created_at_unix"),
            }
        )
    entries.sort(key=lambda item: (item["tick"] is None, item["tick"]))
    index_path = Path(output_dir) / "checkpoints" / CHECKPOINT_INDEX_NAME
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps({"checkpoints": entries}, indent=2), encoding="utf-8")
    return index_path
