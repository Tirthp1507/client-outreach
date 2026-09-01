"""Visual & template diversity rotation for consecutive generated videos.

Phase 10 "content quality & diversity": rotates a deterministic set of visual
variants (palette + pacing + header/template family) so consecutive generated
videos never reuse the immediately-previous look. The rotation index is
persisted to ``output/analytics/rotation_state.json`` so variety survives
daemon restarts. The strategy layer consumes one variant per generated video;
selection/scoring passes never advance the rotation.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from config import PROJECT_ROOT, get_config

logger = logging.getLogger(__name__)

# Deterministic, curated set of visual variants. Each entry describes the
# palette, scene pacing and header/template family applied to scene plans.
VARIANTS: list[dict[str, str]] = [
    {
        "tag": "neon_kinetic",
        "palette": "neon accent on deep navy",
        "pace": "fast",
        "template": "bold kinetic type",
    },
    {
        "tag": "documentary_warm",
        "palette": "warm neutral cinematic",
        "pace": "steady",
        "template": "serif documentary lower-third",
    },
    {
        "tag": "vibrant_rapid",
        "palette": "high-contrast saturated",
        "pace": "fast",
        "template": "energetic chunky gradients",
    },
    {
        "tag": "minimal_haute",
        "palette": "monochrome high-contrast",
        "pace": "steady",
        "template": "minimal editorial typography",
    },
]


class TemplateRotation:
    """Deterministic visual-variant rotator with persisted, restart-safe state."""

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        state_path: Path | str | None = None,
    ) -> None:
        self.config = config or get_config()
        state_path = self._state_path(state_path)
        self.state_path = Path(state_path)
        self.state: dict[str, Any] = {"index": 0, "turns": 0, "last_tag": None}
        self._load()

    def _state_path(self, override: Path | str | None) -> Path | str:
        if override is not None:
            return Path(override)
        out = self.config.get("pipeline", {}).get("output_dir", "output")
        base = Path(out) if Path(out).is_absolute() else PROJECT_ROOT / out
        return base / "analytics" / "rotation_state.json"

    def _load(self) -> None:
        try:
            if self.state_path.exists():
                raw = json.loads(self.state_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    for key in ("index", "turns", "last_tag"):
                        if key in raw:
                            self.state[key] = raw[key]
        except Exception as exc:
            logger.warning("TemplateRotation could not load state %s: %s", self.state_path, exc)

    @property
    def last_tag(self) -> str | None:
        return self.state.get("last_tag")

    def next_variant(self) -> dict[str, str]:
        """Advance the rotation once and return the variant for the next video."""
        variants = list(VARIANTS)
        idx = int(self.state.get("index", 0)) % len(variants)
        variant = variants[idx]
        if len(variants) > 1 and variant["tag"] == self.state.get("last_tag"):
            idx = (idx + 1) % len(variants)
            variant = variants[idx]
        self.state["index"] = (idx + 1) % len(variants)
        self.state["last_tag"] = variant["tag"]
        self.state["turns"] = int(self.state.get("turns", 0)) + 1
        self._persist()
        return variant

    def _persist(self) -> None:
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(json.dumps(self.state, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.warning("TemplateRotation could not persist state: %s", exc)

    def reset(self) -> None:
        self.state = {"index": 0, "turns": 0, "last_tag": None}
        self._persist()