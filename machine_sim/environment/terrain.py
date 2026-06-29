"""Terrain types."""

from __future__ import annotations

from enum import Enum


class TerrainType(Enum):
    PLAIN = "plain"
    ROUGH = "rough"
    BLOCKED = "blocked"
