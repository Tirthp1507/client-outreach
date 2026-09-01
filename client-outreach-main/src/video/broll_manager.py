"""B-roll and visual intelligence asset manager for multi-scene video composition."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Sequence

from config import PROJECT_ROOT
from generators.models import Scene

logger = logging.getLogger(__name__)

MEDIA_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".png", ".jpg", ".jpeg", ".webp"}

FORMAT_THEME_PALETTES: dict[str, list[str]] = {
    "news": ["0x1A0B10", "0x0B0F19", "0x1A1420", "0x0E1A2B"],
    "list": ["0x0A1F2C", "0x0E1A2B", "0x122B3D", "0x09222E"],
    "tutorial": ["0x0A261D", "0x0D3327", "0x0A2026", "0x113D2F"],
    "explainer": ["0x0B0F19", "0x131838", "0x0E1A2B", "0x1A1429"],
    "comparison": ["0x1B1828", "0x0E1A2B", "0x201524", "0x0B0F19"],
    "default": ["0x0B0F19", "0x0E1A2B", "0x132238", "0x0A2026", "0x1A1429"],
}


class BrollMatch:
    """Represents the assigned visual media or procedural background for a scene."""

    def __init__(
        self,
        scene_index: int,
        start_time: float,
        end_time: float,
        asset_path: Path | None = None,
        color_hex: str = "0x0B0F19",
        visual_style: str = "",
    ) -> None:
        self.scene_index = scene_index
        self.start_time = start_time
        self.end_time = end_time
        self.asset_path = asset_path
        self.color_hex = color_hex
        self.visual_style = visual_style

    @property
    def is_asset(self) -> bool:
        return self.asset_path is not None and self.asset_path.exists()

    @property
    def duration(self) -> float:
        return max(0.1, self.end_time - self.start_time)


class BrollManager:
    """Manages visual media discovery, keyword matching, and multi-scene background layout."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        cfg = config or {}
        video_cfg = cfg.get("video", {})
        self.asset_dir = Path(video_cfg.get("background_asset", "assets/backgrounds"))
        if not self.asset_dir.is_absolute():
            self.asset_dir = PROJECT_ROOT / self.asset_dir

        self.broll_dir = PROJECT_ROOT / "assets" / "broll"

    def list_available_assets(self) -> list[Path]:
        """List all video/image files in background and B-roll directories."""
        found: list[Path] = []
        for directory in (self.asset_dir, self.broll_dir):
            if directory.exists():
                for f in sorted(directory.iterdir()):
                    if f.is_file() and f.suffix.lower() in MEDIA_EXTENSIONS:
                        found.append(f)
        return found

    def find_best_asset_for_scene(self, scene: Scene, available: Sequence[Path]) -> Path | None:
        """Find the best matching visual asset for a scene based on keywords and description."""
        if not available:
            return None

        # Build search query terms
        search_terms = [k.lower() for k in scene.broll_keywords]
        desc_words = [w.lower() for w in re.findall(r"\b\w{4,}\b", scene.visual_description)]
        narr_words = [w.lower() for w in re.findall(r"\b\w{4,}\b", scene.narration)]
        all_terms = search_terms + desc_words + narr_words

        for term in all_terms:
            for asset in available:
                if term in asset.stem.lower():
                    return asset

        # Fallback: cycle available assets
        idx = (scene.scene_index - 1) % len(available)
        return available[idx]

    def plan_scene_visuals(
        self,
        scenes: Sequence[Scene],
        total_duration: float,
        content_format: str = "default",
    ) -> list[BrollMatch]:
        """Calculate scene timestamp boundaries and assign matching B-roll or procedural visuals."""
        if not scenes:
            palette = FORMAT_THEME_PALETTES.get(content_format, FORMAT_THEME_PALETTES["default"])
            return [BrollMatch(scene_index=1, start_time=0.0, end_time=total_duration, color_hex=palette[0])]

        total_est = sum(max(0.1, s.estimated_duration) for s in scenes)
        if total_est <= 0:
            total_est = total_duration

        available_assets = self.list_available_assets()
        palette = FORMAT_THEME_PALETTES.get(content_format, FORMAT_THEME_PALETTES["default"])
        matches: list[BrollMatch] = []
        current_time = 0.0

        for i, scene in enumerate(scenes):
            proportion = (
                max(0.1, scene.estimated_duration) / total_est if total_est > 0 else 1.0 / len(scenes)
            )
            scene_dur = proportion * total_duration
            start_t = current_time
            end_t = total_duration if i == len(scenes) - 1 else current_time + scene_dur
            current_time = end_t

            matched_asset = (
                self.find_best_asset_for_scene(scene, available_assets) if available_assets else None
            )
            color_hex = palette[i % len(palette)]

            matches.append(
                BrollMatch(
                    scene_index=scene.scene_index,
                    start_time=start_t,
                    end_time=end_t,
                    asset_path=matched_asset,
                    color_hex=color_hex,
                    visual_style=scene.visual_description,
                )
            )

        return matches