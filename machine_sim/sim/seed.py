"""Deterministic seeding utilities."""

from __future__ import annotations

import random
from typing import Optional


def create_rng(seed: Optional[int] = None) -> random.Random:
    """Create an isolated random number generator instance."""
    return random.Random(seed)
