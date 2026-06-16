"""Phase narration helpers (load + render templates from ``narratives.yaml``).

Ported from ``crawler_agent/src/graph/narrative.py``. The YAML it reads has
moved alongside this module (``app/agents/core/narratives.yaml``).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

CANONICAL_LABEL = "Datahash Canonical"

INTENT_STEP_TOTAL = 3
CANONICAL_STEP_TOTAL = 2
PROJECTION_STEP_TOTAL = 2

INTENT_STEP_INDEX: dict[str, int] = {
    "requirements": 0,
    "source": 1,
    "object": 2,
    "destination": 3,
}

CANONICAL_STEP_INDEX: dict[str, int] = {
    "bridge": 1,
    "map": 2,
}

PROJECTION_STEP_INDEX: dict[str, int] = {
    "setup": 1,
    "map": 2,
}

_NARRATIVES_PATH = Path(__file__).resolve().parent / "narratives.yaml"


@lru_cache(maxsize=1)
def _load_narrative() -> dict[str, Any]:
    """Parse ``narratives.yaml`` once and cache the result."""
    raw = yaml.safe_load(_NARRATIVES_PATH.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else {}


def get_template(phase: str, step: str, status: str) -> str:
    """Look up the template string for ``(phase, step, status)`` — empty if missing."""
    phase_block = _load_narrative().get(phase, {})
    if not isinstance(phase_block, dict):
        return ""
    step_block = phase_block.get(step, {})
    if isinstance(step_block, dict):
        return str(step_block.get(status, "") or "")
    return str(step_block) if status == "message" else ""


def render_template(template: str, labels: dict[str, str]) -> str:
    """Format ``template`` with ``labels``; return the raw template on KeyError."""
    if not template:
        return ""
    try:
        return template.format(**labels)
    except KeyError:
        return template
