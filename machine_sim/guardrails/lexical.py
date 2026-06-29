"""Lexical scan for forbidden anthropomorphic terms."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Tuple

from machine_sim.guardrails.config import FORBIDDEN_LEXICAL_PATTERNS

FORBIDDEN_RE = re.compile("|".join(FORBIDDEN_LEXICAL_PATTERNS), re.IGNORECASE)


def scan_file(filepath: Path) -> List[Tuple[int, str, str]]:
    """Scan a Python file for forbidden terms. Returns [(line_no, term, line_text)]."""
    violations: List[Tuple[int, str, str]] = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            matches = FORBIDDEN_RE.findall(line)
            for match in matches:
                violations.append((line_no, match, line.strip()))
    return violations


def scan_directory(
    directory: Path,
    exclude_patterns: List[str] | None = None,
) -> Dict[str, List[Tuple[int, str, str]]]:
    """Scan all Python files in directory. Returns {filepath: violations}."""
    exclude = exclude_patterns or ["tests/", "docs/", "__pycache__", "guardrails/", "cli/"]
    results: Dict[str, List[Tuple[int, str, str]]] = {}
    for py_file in directory.rglob("*.py"):
        rel = py_file.relative_to(directory).as_posix()
        if any(ex in rel for ex in exclude):
            continue
        violations = scan_file(py_file)
        if violations:
            results[str(py_file)] = violations
    return results
