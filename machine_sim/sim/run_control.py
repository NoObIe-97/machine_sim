"""User-owned run lifecycle control: manifest, control channel, digest chain.

A run is an inspectable object on disk. The manifest records lifecycle state and
progress, the control channel accepts user-written pause and stop requests, and
the per-tick digest chain lets a resumed run be compared against an
uninterrupted run of the same configuration and seed.

Nothing here starts a background process, schedules itself, or reaches the
network. The user starts a process, the user writes a control request, and the
user resumes a run.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from machine_sim.sim.checkpoint import (
    checkpoint_path,
    config_digest,
    list_checkpoints,
    prune_checkpoints,
    restore_from_checkpoint,
    write_checkpoint,
    write_checkpoint_index,
)

MANIFEST_SCHEMA_VERSION = "1.0.0"
MANIFEST_NAME = "run_manifest.json"
PROGRESS_TRACE_NAME = "run_progress_trace.jsonl"
CONTROL_DIR_NAME = "control"
CONTROL_REQUEST_NAME = "control_request.json"
CONTROL_HISTORY_NAME = "control_history.jsonl"

RUN_STATE_INITIALIZED = "initialized"
RUN_STATE_RUNNING = "running"
RUN_STATE_PAUSED = "paused"
RUN_STATE_STOPPED = "stopped"
RUN_STATE_COMPLETED = "completed"
RUN_STATE_FAILED = "failed"

RUN_STATES: Tuple[str, ...] = (
    RUN_STATE_INITIALIZED,
    RUN_STATE_RUNNING,
    RUN_STATE_PAUSED,
    RUN_STATE_STOPPED,
    RUN_STATE_COMPLETED,
    RUN_STATE_FAILED,
)

ALLOWED_TRANSITIONS: Dict[str, Tuple[str, ...]] = {
    RUN_STATE_INITIALIZED: (RUN_STATE_RUNNING,),
    RUN_STATE_RUNNING: (
        RUN_STATE_PAUSED,
        RUN_STATE_STOPPED,
        RUN_STATE_COMPLETED,
        RUN_STATE_FAILED,
    ),
    RUN_STATE_PAUSED: (RUN_STATE_RUNNING, RUN_STATE_STOPPED),
    RUN_STATE_STOPPED: (),
    RUN_STATE_COMPLETED: (),
    RUN_STATE_FAILED: (),
}

REQUESTABLE_STATES: Tuple[str, ...] = ("pause", "stop")

REQUEST_TO_RUN_STATE: Dict[str, str] = {
    "pause": RUN_STATE_PAUSED,
    "stop": RUN_STATE_STOPPED,
}

MAX_CONTROL_HISTORY_LINES = 10000
MAX_PROGRESS_TRACE_LINES = 50000


class RunControlViolation(Exception):
    """Raised on an illegal run-state transition or malformed control request."""


def derive_run_id(config_fingerprint: str, seed: int, requested_ticks: int) -> str:
    """Return a deterministic run identifier for a configuration and seed."""
    digest = hashlib.sha256(
        f"{config_fingerprint}|{seed}|{requested_ticks}".encode("utf-8")
    ).hexdigest()
    return f"run-{digest[:16]}"


def _quantize(value: float) -> str:
    return f"{float(value):.6f}"


def tick_observation(engine: Any) -> str:
    """Return the canonical per-tick observation text derived from live state."""
    parts: List[str] = [str(engine.tick_count)]
    active = [unit for unit in engine.units if unit.is_active]
    parts.append(str(len(active)))
    for unit in engine.units:
        health = 0.0
        if unit.components:
            health = sum(c.health for c in unit.components.values()) / len(unit.components)
        parts.append(
            "|".join(
                [
                    unit.unit_id,
                    str(unit.position[0]),
                    str(unit.position[1]),
                    _quantize(unit.power_reserve),
                    _quantize(health),
                    "1" if unit.is_active else "0",
                ]
            )
        )
    return ";".join(parts)


def initial_run_digest(run_id: str) -> str:
    return hashlib.sha256(run_id.encode("utf-8")).hexdigest()


def advance_run_digest(previous: str, observation: str) -> str:
    return hashlib.sha256(f"{previous}{observation}".encode("utf-8")).hexdigest()


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


class RunManifest:
    """Schema-versioned run lifecycle record with atomic persistence."""

    def __init__(
        self,
        output_dir: Path,
        run_id: str,
        config_fingerprint: str,
        seed: int,
        requested_ticks: int,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.path = self.output_dir / MANIFEST_NAME
        now = time.time()
        self.data: Dict[str, Any] = {
            "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
            "run_id": run_id,
            "run_state": RUN_STATE_INITIALIZED,
            "config_digest": config_fingerprint,
            "seed": int(seed),
            "requested_ticks": int(requested_ticks),
            "completed_ticks": 0,
            "progress_ratio": 0.0,
            "run_digest": initial_run_digest(run_id),
            "checkpoint_records": [],
            "control_records": [],
            "artifact_index": {},
            "created_at_unix": now,
            "updated_at_unix": now,
        }

    @classmethod
    def create(cls, output_dir: Path, config: Any, requested_ticks: Optional[int] = None) -> "RunManifest":
        fingerprint = config_digest(config)
        ticks = int(requested_ticks if requested_ticks is not None else config.max_ticks)
        run_id = derive_run_id(fingerprint, int(config.seed), ticks)
        manifest = cls(output_dir, run_id, fingerprint, int(config.seed), ticks)
        manifest.save()
        return manifest

    @classmethod
    def load(cls, output_dir: Path) -> "RunManifest":
        path = Path(output_dir) / MANIFEST_NAME
        if not path.exists():
            raise RunControlViolation(f"run manifest not present: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("manifest_schema_version") != MANIFEST_SCHEMA_VERSION:
            raise RunControlViolation(
                f"unsupported manifest schema version: {data.get('manifest_schema_version')}"
            )
        manifest = cls(
            Path(output_dir),
            data["run_id"],
            data["config_digest"],
            data["seed"],
            data["requested_ticks"],
        )
        manifest.data = data
        return manifest

    @property
    def run_state(self) -> str:
        return self.data["run_state"]

    @property
    def run_id(self) -> str:
        return self.data["run_id"]

    def transition(self, next_state: str) -> None:
        if next_state not in RUN_STATES:
            raise RunControlViolation(f"unrecognized run state: {next_state}")
        current = self.data["run_state"]
        if next_state not in ALLOWED_TRANSITIONS[current]:
            raise RunControlViolation(
                f"illegal run-state transition: {current} -> {next_state}"
            )
        self.data["run_state"] = next_state
        self.data["updated_at_unix"] = time.time()

    def set_progress(self, completed_ticks: int, run_digest: str = "") -> None:
        requested = max(1, int(self.data["requested_ticks"]))
        completed = int(completed_ticks)
        if completed < int(self.data["completed_ticks"]):
            raise RunControlViolation(
                f"progress must not decrease: {self.data['completed_ticks']} -> {completed}"
            )
        self.data["completed_ticks"] = completed
        self.data["progress_ratio"] = min(1.0, completed / requested)
        if run_digest:
            self.data["run_digest"] = run_digest
        self.data["updated_at_unix"] = time.time()

    def record_checkpoint(self, tick: int, path: Path, state_digest: str, byte_size: int) -> None:
        self.data["checkpoint_records"].append(
            {
                "tick": int(tick),
                "path": Path(path).name,
                "state_digest": state_digest,
                "byte_size": int(byte_size),
                "created_at_unix": time.time(),
            }
        )
        self.data["updated_at_unix"] = time.time()

    def record_control(self, record: Dict[str, Any]) -> None:
        self.data["control_records"].append(record)
        self.data["updated_at_unix"] = time.time()

    def set_artifact_index(self, index: Dict[str, str]) -> None:
        self.data["artifact_index"] = dict(sorted(index.items()))
        self.data["updated_at_unix"] = time.time()

    def save(self) -> Path:
        _atomic_write_text(self.path, json.dumps(self.data, indent=2, sort_keys=True))
        return self.path


class ControlChannel:
    """File-based user-owned control channel for a run output directory."""

    def __init__(self, output_dir: Path) -> None:
        self.directory = Path(output_dir) / CONTROL_DIR_NAME
        self.request_path = self.directory / CONTROL_REQUEST_NAME
        self.history_path = self.directory / CONTROL_HISTORY_NAME

    def write_request(self, requested_state: str, request_id: Optional[str] = None) -> Dict[str, Any]:
        if requested_state not in REQUESTABLE_STATES:
            raise RunControlViolation(
                f"unrecognized control request: {requested_state}"
            )
        now = time.time()
        record = {
            "request_id": request_id or f"req-{int(now * 1000):d}",
            "requested_state": requested_state,
            "requested_at_unix": now,
        }
        _atomic_write_text(self.request_path, json.dumps(record, indent=2, sort_keys=True))
        return record

    def read_request(self) -> Optional[Dict[str, Any]]:
        if not self.request_path.exists():
            return None
        try:
            record = json.loads(self.request_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(record, dict):
            return None
        if record.get("requested_state") not in REQUESTABLE_STATES:
            return None
        if not isinstance(record.get("request_id"), str):
            return None
        return record

    def clear_request(self) -> None:
        try:
            self.request_path.unlink()
        except OSError:
            pass

    def applied_request_ids(self) -> List[str]:
        return [record.get("request_id", "") for record in self.history()]

    def history(self) -> List[Dict[str, Any]]:
        if not self.history_path.exists():
            return []
        records: List[Dict[str, Any]] = []
        with open(self.history_path, "r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return records

    def append_history(self, record: Dict[str, Any]) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        if len(self.history()) >= MAX_CONTROL_HISTORY_LINES:
            return
        with open(self.history_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


class RunController:
    """Drives a `SimEngine` under manifest, checkpoint, and control policy."""

    def __init__(
        self,
        engine: Any,
        output_dir: Path,
        manifest: Optional[RunManifest] = None,
        checkpoint_enabled: Optional[bool] = None,
        checkpoint_interval: Optional[int] = None,
        checkpoint_retention_limit: Optional[int] = None,
        control_poll_interval: Optional[int] = None,
        run_progress_interval: Optional[int] = None,
        run_digest_enabled: Optional[bool] = None,
        deep_digest_interval: Optional[int] = None,
        deep_digest_path: Optional[Path] = None,
    ) -> None:
        self.engine = engine
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        config = engine.config
        self.manifest = manifest or RunManifest.create(self.output_dir, config)
        self.channel = ControlChannel(self.output_dir)
        self.checkpoint_enabled = (
            config.checkpoint_enabled if checkpoint_enabled is None else checkpoint_enabled
        )
        self.checkpoint_interval = max(
            1,
            int(
                config.checkpoint_interval
                if checkpoint_interval is None
                else checkpoint_interval
            ),
        )
        self.checkpoint_retention_limit = int(
            config.checkpoint_retention_limit
            if checkpoint_retention_limit is None
            else checkpoint_retention_limit
        )
        self.control_poll_interval = max(
            1,
            int(
                config.control_poll_interval
                if control_poll_interval is None
                else control_poll_interval
            ),
        )
        self.run_progress_interval = max(
            1,
            int(
                config.run_progress_interval
                if run_progress_interval is None
                else run_progress_interval
            ),
        )
        self.run_digest_enabled = (
            config.run_digest_enabled if run_digest_enabled is None else run_digest_enabled
        )
        self.progress_path = self.output_dir / PROGRESS_TRACE_NAME
        self._progress_lines = 0
        self._started_at = time.time()
        self._pruned_checkpoints: List[str] = []
        # M21 optional deep-digest sampling. Inactive unless both values are
        # provided; sampling writes an append-only JSONL record per sampled
        # tick and never touches simulation state.
        self.deep_digest_interval = (
            max(1, int(deep_digest_interval)) if deep_digest_interval else None
        )
        self.deep_digest_path = Path(deep_digest_path) if deep_digest_path else None

    @property
    def run_digest(self) -> str:
        return getattr(self.engine, "run_digest_value", "") or ""

    def _set_run_digest(self, value: str) -> None:
        self.engine.run_digest_value = value

    def start(self) -> None:
        """Initialize the world and mark the run as running."""
        if self.manifest.run_state == RUN_STATE_INITIALIZED:
            self.engine.initialize()
            if not self.run_digest:
                self._set_run_digest(initial_run_digest(self.manifest.run_id))
            self.manifest.transition(RUN_STATE_RUNNING)
            self.manifest.save()

    def _write_progress_record(self, elapsed: float) -> None:
        if self._progress_lines >= MAX_PROGRESS_TRACE_LINES:
            return
        record = {
            "tick": self.engine.tick_count,
            "run_state": self.manifest.run_state,
            "progress_ratio": round(
                min(1.0, self.engine.tick_count / max(1, self.manifest.data["requested_ticks"])), 6
            ),
            "active_unit_count": sum(1 for u in self.engine.units if u.is_active),
            "run_digest": self.run_digest,
            "elapsed_seconds": round(elapsed, 3),
        }
        with open(self.progress_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
        self._progress_lines += 1

    def create_checkpoint(self) -> Path:
        """Write a checkpoint at the current tick and refresh the index."""
        path = write_checkpoint(
            self.engine,
            self.output_dir,
            self.engine.tick_count,
            self.manifest.run_id,
            self.manifest.data["config_digest"],
        )
        document_digest = json.loads(path.read_text(encoding="utf-8"))["state_digest"]
        self.manifest.record_checkpoint(
            self.engine.tick_count, path, document_digest, path.stat().st_size
        )
        self._pruned_checkpoints.extend(
            prune_checkpoints(self.output_dir, self.checkpoint_retention_limit)
        )
        write_checkpoint_index(self.output_dir)
        return path

    @property
    def pruned_checkpoints(self) -> List[str]:
        return list(self._pruned_checkpoints)

    def _apply_control_request(self, request: Dict[str, Any]) -> str:
        next_state = REQUEST_TO_RUN_STATE[request["requested_state"]]
        checkpoint_file: Optional[Path] = None
        if self.checkpoint_enabled:
            checkpoint_file = self.create_checkpoint()
        record = {
            "request_id": request["request_id"],
            "requested_state": request["requested_state"],
            "requested_at_unix": request.get("requested_at_unix", 0.0),
            "applied_at_unix": time.time(),
            "applied_tick": self.engine.tick_count,
            "resulting_run_state": next_state,
            "checkpoint_path": checkpoint_file.name if checkpoint_file else "",
        }
        self.channel.append_history(record)
        self.manifest.record_control(record)
        self.manifest.transition(next_state)
        self.manifest.set_progress(self.engine.tick_count, self.run_digest)
        self.manifest.save()
        self.channel.clear_request()
        return next_state

    def poll_control(self) -> Optional[str]:
        """Read the control channel once and apply a pending request."""
        request = self.channel.read_request()
        if request is None:
            return None
        if request["request_id"] in self.channel.applied_request_ids():
            self.channel.clear_request()
            return None
        return self._apply_control_request(request)

    def _sample_deep_digest(self, tick: int) -> None:
        if not self.deep_digest_interval or self.deep_digest_path is None:
            return
        if tick % self.deep_digest_interval != 0:
            return
        from machine_sim.sim.state_digest import deep_state_digest

        record = {
            "tick": int(tick),
            "deep_digest": deep_state_digest(self.engine),
            "run_digest": self.run_digest,
        }
        self.deep_digest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.deep_digest_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")

    def advance(self, target_ticks: Optional[int] = None) -> str:
        """Run ticks until the target, a control request, or completion."""
        if self.manifest.run_state != RUN_STATE_RUNNING:
            raise RunControlViolation(
                f"run must be running to advance, current state: {self.manifest.run_state}"
            )
        target = int(target_ticks if target_ticks is not None else self.engine.max_ticks)
        while self.engine.tick_count < target:
            self.engine.tick()
            tick = self.engine.tick_count

            if self.run_digest_enabled:
                self._set_run_digest(
                    advance_run_digest(self.run_digest, tick_observation(self.engine))
                )

            self._sample_deep_digest(tick)

            if tick % self.run_progress_interval == 0:
                self._write_progress_record(time.time() - self._started_at)

            if self.checkpoint_enabled and tick % self.checkpoint_interval == 0:
                self.create_checkpoint()
                self.manifest.set_progress(tick, self.run_digest)
                self.manifest.save()

            if tick % self.control_poll_interval == 0:
                applied = self.poll_control()
                if applied is not None:
                    return applied

        self.manifest.set_progress(self.engine.tick_count, self.run_digest)
        self.manifest.transition(RUN_STATE_COMPLETED)
        self.manifest.save()
        return RUN_STATE_COMPLETED

    def finalize_artifact_index(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Record the location of every artifact this run produced."""
        index: Dict[str, str] = {"run_manifest": MANIFEST_NAME}
        if self.progress_path.exists():
            index["run_progress_trace"] = PROGRESS_TRACE_NAME
        if self.channel.history_path.exists():
            index["control_history"] = f"{CONTROL_DIR_NAME}/{CONTROL_HISTORY_NAME}"
        checkpoints = list_checkpoints(self.output_dir)
        if checkpoints:
            index["checkpoint_index"] = "checkpoints/checkpoint_index.json"
            index["latest_checkpoint"] = f"checkpoints/{checkpoints[-1].name}"
        for label, relative in (extra or {}).items():
            index[label] = relative
        self.manifest.set_artifact_index(index)
        self.manifest.save()
        return index


def resume_controller(
    output_dir: Path,
    checkpoint_file: Optional[Path] = None,
    target_ticks: Optional[int] = None,
) -> RunController:
    """Rebuild a controller from a checkpoint and mark the run as running."""
    output_dir = Path(output_dir)
    manifest = RunManifest.load(output_dir)
    if checkpoint_file is None:
        available = list_checkpoints(output_dir)
        if not available:
            raise RunControlViolation(f"no checkpoint available under {output_dir}")
        checkpoint_file = available[-1]
    engine, document = restore_from_checkpoint(Path(checkpoint_file))
    if document.get("run_id") != manifest.run_id:
        raise RunControlViolation(
            f"checkpoint run identifier does not match manifest: "
            f"{document.get('run_id')} != {manifest.run_id}"
        )
    if target_ticks is not None:
        engine.max_ticks = int(target_ticks)
    controller = RunController(engine, output_dir, manifest=manifest)
    manifest.transition(RUN_STATE_RUNNING)
    manifest.save()
    return controller


def latest_checkpoint_file(output_dir: Path) -> Optional[Path]:
    available = list_checkpoints(output_dir)
    return available[-1] if available else None


def checkpoint_file_for_tick(output_dir: Path, tick: int) -> Path:
    return checkpoint_path(Path(output_dir), tick)
