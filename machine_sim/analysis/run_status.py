"""Read-only local status surface over a run output directory.

Everything here reads the manifest, the checkpoint index, and the control
history. Nothing here advances a run, mutates a manifest, writes into the
control channel, or touches the network. Rendered output is written only to a
caller-supplied path outside those inputs.
"""

from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

STATUS_SNAPSHOT_NAME = "run_status_snapshot.json"
STATUS_PAGE_NAME = "run_dashboard.html"

READ_ONLY_INPUT_NAMES = (
    "run_manifest.json",
    "run_progress_trace.jsonl",
    "control/control_history.jsonl",
    "control/control_request.json",
    "checkpoints/checkpoint_index.json",
)


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    try:
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return records


def input_digest(output_dir: Path) -> str:
    """Digest the status-surface inputs, for confirming read-only behaviour."""
    output_dir = Path(output_dir)
    accumulator = hashlib.sha256()
    for relative in READ_ONLY_INPUT_NAMES:
        candidate = output_dir / relative
        accumulator.update(relative.encode("utf-8"))
        if candidate.exists():
            accumulator.update(candidate.read_bytes())
        else:
            accumulator.update(b"absent")
    checkpoint_dir = output_dir / "checkpoints"
    if checkpoint_dir.exists():
        for checkpoint_file in sorted(checkpoint_dir.glob("checkpoint_[0-9]*.json")):
            accumulator.update(checkpoint_file.name.encode("utf-8"))
            accumulator.update(str(checkpoint_file.stat().st_size).encode("utf-8"))
    return accumulator.hexdigest()


def collect_status(output_dir: Path) -> Dict[str, Any]:
    """Read the run surface and return a status snapshot mapping."""
    output_dir = Path(output_dir)
    manifest = _read_json(output_dir / "run_manifest.json")
    index = _read_json(output_dir / "checkpoints" / "checkpoint_index.json")
    control_records = _read_jsonl(output_dir / "control" / "control_history.jsonl")
    progress_records = _read_jsonl(output_dir / "run_progress_trace.jsonl")

    checkpoints = index.get("checkpoints", [])
    total_bytes = sum(int(entry.get("byte_size", 0)) for entry in checkpoints)
    last_checkpoint_tick = checkpoints[-1]["tick"] if checkpoints else None

    artifact_index: Dict[str, str] = {}
    for label, relative in (manifest.get("artifact_index") or {}).items():
        artifact_index[label] = str((output_dir / relative).resolve())

    return {
        "output_dir": str(output_dir.resolve()),
        "run_id": manifest.get("run_id", ""),
        "run_state": manifest.get("run_state", "unknown"),
        "manifest_schema_version": manifest.get("manifest_schema_version", ""),
        "seed": manifest.get("seed"),
        "requested_ticks": manifest.get("requested_ticks", 0),
        "completed_ticks": manifest.get("completed_ticks", 0),
        "progress_ratio": manifest.get("progress_ratio", 0.0),
        "run_digest": manifest.get("run_digest", ""),
        "checkpoint_count": len(checkpoints),
        "retained_checkpoint_bytes": total_bytes,
        "last_checkpoint_tick": last_checkpoint_tick,
        "checkpoints": checkpoints,
        "control_record_count": len(control_records),
        "last_control_record": control_records[-1] if control_records else {},
        "control_records": control_records,
        "progress_record_count": len(progress_records),
        "last_progress_record": progress_records[-1] if progress_records else {},
        "artifact_index": artifact_index,
        "input_digest": input_digest(output_dir),
    }


def render_text(status: Dict[str, Any]) -> str:
    """Render the status snapshot as plain text."""
    lines: List[str] = []
    lines.append("Run status surface (read-only)")
    lines.append(f"  output directory : {status['output_dir']}")
    lines.append(f"  run identifier   : {status['run_id']}")
    lines.append(f"  run state        : {status['run_state']}")
    lines.append(
        f"  progress         : {status['completed_ticks']}/{status['requested_ticks']} ticks "
        f"({status['progress_ratio'] * 100:.2f}%)"
    )
    lines.append(f"  run digest       : {status['run_digest'][:32]}")
    lines.append(
        f"  checkpoints      : {status['checkpoint_count']} retained, "
        f"{status['retained_checkpoint_bytes']} bytes, "
        f"last at tick {status['last_checkpoint_tick']}"
    )
    lines.append(f"  control records  : {status['control_record_count']}")
    last_control = status.get("last_control_record") or {}
    if last_control:
        lines.append(
            f"    last request   : {last_control.get('requested_state')} "
            f"at tick {last_control.get('applied_tick')} "
            f"-> {last_control.get('resulting_run_state')}"
        )
    lines.append("  artifact locations:")
    for label, location in sorted(status["artifact_index"].items()):
        lines.append(f"    {label}: {location}")
    return "\n".join(lines)


_PAGE_STYLE = """
body { font: 14px monospace; background: #101418; color: #d7dde3; margin: 0; padding: 24px; }
h1 { font-size: 18px; letter-spacing: 1px; color: #7fd1b9; margin: 0 0 16px 0; }
h2 { font-size: 14px; color: #7fd1b9; margin: 24px 0 8px 0; }
table { border-collapse: collapse; width: 100%; max-width: 1100px; }
td, th { border: 1px solid #2a333c; padding: 6px 10px; text-align: left; font-size: 13px; }
th { background: #172029; color: #9fb3c8; }
.bar { background: #172029; border: 1px solid #2a333c; height: 18px; max-width: 1100px; }
.bar span { display: block; height: 100%; background: #4f9d7e; }
.small { color: #8a99a8; font-size: 12px; }
"""


def render_page(status: Dict[str, Any]) -> str:
    """Render a self-contained local page with no external reference."""
    def esc(value: Any) -> str:
        return html.escape(str(value))

    percent = max(0.0, min(100.0, float(status["progress_ratio"]) * 100.0))

    checkpoint_rows = "".join(
        f"<tr><td>{esc(entry.get('tick'))}</td><td>{esc(entry.get('path'))}</td>"
        f"<td>{esc(entry.get('byte_size'))}</td>"
        f"<td>{esc(str(entry.get('state_digest', ''))[:24])}</td></tr>"
        for entry in status.get("checkpoints", [])
    ) or "<tr><td colspan='4'>none retained</td></tr>"

    control_rows = "".join(
        f"<tr><td>{esc(entry.get('applied_tick'))}</td>"
        f"<td>{esc(entry.get('requested_state'))}</td>"
        f"<td>{esc(entry.get('resulting_run_state'))}</td>"
        f"<td>{esc(entry.get('checkpoint_path'))}</td></tr>"
        for entry in status.get("control_records", [])
    ) or "<tr><td colspan='4'>none applied</td></tr>"

    artifact_rows = "".join(
        f"<tr><td>{esc(label)}</td><td>{esc(location)}</td></tr>"
        for label, location in sorted(status.get("artifact_index", {}).items())
    ) or "<tr><td colspan='2'>none recorded</td></tr>"

    summary_rows = "".join(
        f"<tr><th>{esc(label)}</th><td>{esc(value)}</td></tr>"
        for label, value in (
            ("run identifier", status["run_id"]),
            ("run state", status["run_state"]),
            ("seed", status["seed"]),
            ("completed ticks", status["completed_ticks"]),
            ("requested ticks", status["requested_ticks"]),
            ("run digest", status["run_digest"]),
            ("checkpoint count", status["checkpoint_count"]),
            ("retained checkpoint bytes", status["retained_checkpoint_bytes"]),
            ("control record count", status["control_record_count"]),
            ("progress record count", status["progress_record_count"]),
            ("output directory", status["output_dir"]),
        )
    )

    return (
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<title>machine-sim run status</title>\n"
        f"<style>{_PAGE_STYLE}</style>\n</head>\n<body>\n"
        "<h1>machine-sim run status surface</h1>\n"
        f"<div class=\"bar\"><span style=\"width: {percent:.2f}%\"></span></div>\n"
        f"<p class=\"small\">{percent:.2f}% of requested ticks completed. "
        "This page is a read-only local rendering; it does not control the run.</p>\n"
        f"<h2>Run record</h2>\n<table>{summary_rows}</table>\n"
        "<h2>Retained checkpoints</h2>\n<table>"
        "<tr><th>tick</th><th>file</th><th>bytes</th><th>state digest</th></tr>"
        f"{checkpoint_rows}</table>\n"
        "<h2>Applied control records</h2>\n<table>"
        "<tr><th>tick</th><th>request</th><th>resulting state</th><th>checkpoint</th></tr>"
        f"{control_rows}</table>\n"
        "<h2>Artifact locations</h2>\n<table>"
        "<tr><th>label</th><th>path</th></tr>"
        f"{artifact_rows}</table>\n"
        "</body>\n</html>\n"
    )


def write_status_surface(
    output_dir: Path,
    snapshot_path: Optional[Path] = None,
    page_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Collect status and write the snapshot and page to explicit paths."""
    status = collect_status(output_dir)
    if snapshot_path is not None:
        snapshot_path = Path(snapshot_path)
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_text(json.dumps(status, indent=2, sort_keys=True), encoding="utf-8")
    if page_path is not None:
        page_path = Path(page_path)
        page_path.parent.mkdir(parents=True, exist_ok=True)
        page_path.write_text(render_page(status), encoding="utf-8")
    return status


EXTERNAL_REFERENCE_MARKERS = (
    "http://",
    "https://",
    "//cdn",
    "src=\"//",
    "href=\"//",
    "@import",
    "fetch(",
    "XMLHttpRequest",
    "WebSocket",
)


def page_is_self_contained(page_text: str) -> bool:
    """Return True when a rendered page carries no external reference."""
    lowered = page_text.lower()
    return not any(marker.lower() in lowered for marker in EXTERNAL_REFERENCE_MARKERS)
