"""FFmpeg-based 9:16 video compositor with multi-scene support, audio mixing, and karaoke captions.

Combines per-scene background sequences (matched B-roll assets or themed scene
colors), voiceover track, ducked background music, burned-in animated ASS
subtitles, and a scene-header track into a 1080x1920 MP4 ready for publishing.

Phase 8: scene-level visual variety is now real — scenes passed into ``compose``
are rendered as individual background segments (concatenated) instead of one
static canvas, with a scene-header overlay showing section labels.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Sequence

from generators.models import Scene
from video.broll_manager import BrollManager
from video.ffmpeg_utils import FFmpegError, find_ffmpeg, has_ffmpeg, probe_duration, run_ffmpeg
from voice.audio_mixer import AudioMixer

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi"}

DEFAULT_BACKGROUND_COLOR = "0x0B0F19"  # Sleek modern dark slate


class MissingFFmpegError(Exception):
    """FFmpeg is required to render video but is not installed."""


class VideoCompositorError(Exception):
    """Video composition failed."""


class FFmpegCompositor:
    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}
        video_cfg = self.config.get("video", {})
        self.width = int(video_cfg.get("width", 1080))
        self.height = int(video_cfg.get("height", 1920))
        self.framerate = int(video_cfg.get("framerate", 30))
        self.background_mode = video_cfg.get("background_mode", "auto")
        self.background_color = video_cfg.get("background_color", DEFAULT_BACKGROUND_COLOR)
        self.background_asset_dir = Path(
            video_cfg.get("background_asset", "assets/backgrounds")
        )
        self.background_asset = video_cfg.get("background_asset_file")
        self.font_size = int(video_cfg.get("subtitle_font_size", 68))
        self.crop_background = bool(video_cfg.get("crop_background", True))
        self.show_scene_headers = bool(video_cfg.get("show_scene_headers", True))
        self.audio_mixer = AudioMixer(self.config)
        self.broll_manager = BrollManager(self.config)

    # -- helpers -----------------------------------------------------------

    def _resolve_background(self) -> tuple[str, list[str]]:
        """Return ``(mode, background_input_args)`` based on config + assets."""
        assets = self._list_background_assets()
        mode = self.background_mode
        if mode == "auto":
            mode = "asset" if assets else "solid"
        if mode == "asset":
            if not assets:
                raise VideoCompositorError(
                    f"background_mode=asset but no media found in {self.background_asset_dir}"
                )
            asset = assets[0]
            mode = "image" if asset.suffix.lower() in IMAGE_EXTENSIONS else "video"
            input_args = (
                ["-loop", "1", "-i", str(asset)]
                if mode == "image"
                else ["-stream_loop", "-1", "-i", str(asset)]
            )
            return mode, input_args

        return "solid", [
            "-f",
            "lavfi",
            "-i",
            f"color=c={self.background_color}:s={self.width}x{self.height}:r={self.framerate}:d=300",
        ]

    def _list_background_assets(self) -> list[Path]:
        if self.background_asset:
            path = Path(self.background_asset)
            return [path] if path.exists() else []
        if not self.background_asset_dir.exists():
            return []
        files = [
            f
            for f in sorted(self.background_asset_dir.iterdir())
            if f.is_file() and f.suffix.lower() in (IMAGE_EXTENSIONS | VIDEO_EXTENSIONS)
        ]
        return files

    def _background_vf(self, mode: str) -> str | None:
        """Return the video filter for scaling and cropping the chosen background."""
        if mode in ("video", "image"):
            return self._asset_cover_filter()
        return None  # Solid color needs no extra scaling filter

    def _asset_cover_filter(self) -> str:
        if self.crop_background:
            return (
                f"scale={self.width}:{self.height}:force_original_aspect_ratio=increase,"
                f"crop={self.width}:{self.height},fps={self.framerate},setsar=1,format=yuv420p"
            )
        return (
            f"scale={self.width}:{self.height}:force_original_aspect_ratio=decrease,"
            f"pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2:color={self.background_color},"
            f"fps={self.framerate},setsar=1,format=yuv420p"
        )

    def _build_scene_backgrounds(self, matches) -> tuple[list[str], str, str]:
        """Return ``(inputs, branch_filters, concat_filter)`` for scene segments.

        Each scene becomes one bounded background segment (trimmed to its
        duration), then all segments are concatenated. Testable without FFmpeg.
        """
        inputs: list[str] = []
        branch_filters: list[str] = []
        concat_inputs: list[str] = []
        concat_count = 0

        for i, match in enumerate(matches):
            duration = max(0.2, match.duration)
            if match.is_asset and match.asset_path is not None:
                asset = match.asset_path
                is_image = asset.suffix.lower() in IMAGE_EXTENSIONS
                inputs += (
                    ["-loop", "1", "-i", str(asset)]
                    if is_image
                    else ["-stream_loop", "-1", "-i", str(asset)]
                )
                if self.crop_background:
                    branch = (
                        f"[{i}:v]scale={self.width}:{self.height}:force_original_aspect_ratio=increase,"
                        f"crop={self.width}:{self.height},fps={self.framerate},"
                        f"trim=duration={duration:.3f},setpts=PTS-STARTPTS,setsar=1,format=yuv420p[v{i}]"
                    )
                else:
                    branch = (
                        f"[{i}:v]scale={self.width}:{self.height}:force_original_aspect_ratio=decrease,"
                        f"pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2:color={self.background_color},"
                        f"fps={self.framerate},trim=duration={duration:.3f},"
                        f"setpts=PTS-STARTPTS,setsar=1,format=yuv420p[v{i}]"
                    )
            else:
                color = match.color_hex or self.background_color
                inputs += [
                    "-f",
                    "lavfi",
                    "-i",
                    f"color=c={color}:s={self.width}x{self.height}:r={self.framerate}:d={duration:.3f}",
                ]
                branch = f"[{i}:v]settb=AVTB,setpts=PTS-STARTPTS[v{i}]"

            branch_filters.append(branch)
            concat_inputs.append(f"[v{i}]")
            concat_count += 1

        concat_filter = f"{''.join(concat_inputs)}concat=n={concat_count}:v=1:a=0[vg]"
        return inputs, branch_filters, concat_filter

    def _resolve_audio_duration(self, voice: Path, scenes) -> float:
        """Best-effort total timeline length (audio duration preferred)."""
        try:
            return float(probe_duration(voice))
        except (FFmpegError, ValueError):
            total_est = sum(max(0.1, s.estimated_duration) for s in scenes) if scenes else 0
            return total_est or 30.0

    # -- public API --------------------------------------------------------

    def compose(
        self,
        *,
        voice_path: str | Path,
        subtitle_path: str | Path,
        output_path: str | Path,
        scenes: Sequence[Scene] | None = None,
        header_path: str | Path | None = None,
        content_format: str = "default",
        total_duration: float | None = None,
    ) -> dict[str, Any]:
        """Render the publish-ready MP4 video with multi-scene visuals and return summary."""
        if not has_ffmpeg():
            raise MissingFFmpegError(
                "FFmpeg is required to render the final video but was not found.\n"
                "Install it once (e.g. `winget install Gyan.FFmpeg`) or set "
                "FFMPEG_BIN to the binary path, then re-run."
            )

        voice = Path(voice_path)
        subtitle = Path(subtitle_path)
        output = Path(output_path)
        if not voice.exists():
            raise VideoCompositorError(f"voiceover file not found: {voice}")
        if not subtitle.exists():
            raise VideoCompositorError(f"subtitle file not found: {subtitle}")
        output.parent.mkdir(parents=True, exist_ok=True)
        assert subtitle.suffix.lower() == ".ass"

        audio_duration = float(total_duration) if total_duration else self._resolve_audio_duration(voice, scenes)
        scenes_list = list(scenes) if scenes else []

        # Plan per-scene visuals (B-roll / themed colors).
        matches: list = []
        bg_inputs: list[str] = []
        video_filter: str = ""
        mode = "solid"

        if len(scenes_list) >= 2:
            matches = self.broll_manager.plan_scene_visuals(
                scenes_list,
                total_duration=audio_duration,
                content_format=content_format or "default",
            )
            if len(matches) >= 2:
                bg_inputs, branch_filters, concat_filter = self._build_scene_backgrounds(matches)
                video_filter = ";".join(branch_filters) + ";" + concat_filter
                mode = "scenes"

        if not video_filter:
            # Single static background fallback (existing behaviour).
            mode, bg_inputs = self._resolve_background()
            bg_filter = self._background_vf(mode)
            src = f"[0:v]"
            if bg_filter:
                video_filter = f"{src}{bg_filter}"
            else:
                video_filter = src

        # Burn in captions + scene header track.
        ass_filters = [f"ass=filename='{subtitle.name}'"]
        header = Path(header_path) if header_path else None
        if header and header.exists() and self.show_scene_headers:
            assert header.suffix.lower() == ".ass"
            ass_filters.append(f"ass=filename='{header.name}'")
        # The caption chain must bind directly onto a bare pad link (no comma),
        # otherwise FFmpeg sees an empty filter name. The scene concat output
        # ([vg]) additionally must be re-entered as its own chain segment.
        ass_chain = f"{','.join(ass_filters)}[vout]"
        if mode == "scenes" and video_filter.rstrip().endswith("[vg]"):
            video_filter = f"{video_filter};[vg]{ass_chain}"
        elif video_filter.rstrip().endswith("]"):
            video_filter = f"{video_filter}{ass_chain}"
        else:
            video_filter = f"{video_filter},{ass_chain}"

        # Audio mixing (BGM + voiceover ducking + loudnorm).
        voice_index = len(matches) or 1
        bgm_inputs, audio_filter_graph = self.audio_mixer.build_audio_inputs_and_filter(
            voice,
            voice_index=voice_index,
            voice_duration=audio_duration,
        )
        filter_complex = f"{video_filter};{audio_filter_graph}"

        args = [
            "-y",
            *bg_inputs,
            "-i",
            str(voice),
            *bgm_inputs,
            "-filter_complex",
            filter_complex,
            "-map",
            "[vout]",
            "-map",
            "[aout]",
            "-shortest",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "21",  # Crisp publish quality
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "44100",
            "-ac",
            "2",
            "-movflags",
            "+faststart",
            str(output),
        ]

        try:
            run_ffmpeg(args, cwd=subtitle.parent)
        except FFmpegError as exc:
            raise VideoCompositorError(str(exc)) from exc

        logger.info("Composited final video -> %s", output)
        return {
            "output_path": str(output),
            "mode": mode,
            "background_asset": (
                str(self._resolve_background_path(mode)) if mode in ("image", "video") else None
            ),
            "scenes_count": len(matches) or len(scenes_list) or 1,
            "scene_colors": [m.color_hex for m in matches] if matches else None,
            "has_bgm": len(bgm_inputs) > 0,
            "has_scene_headers": bool(header and header.exists() and self.show_scene_headers),
            "width": self.width,
            "height": self.height,
            "duration_seconds": round(audio_duration, 2),
        }

    def _resolve_background_path(self, mode: str) -> Path | None:
        if mode in ("solid", "scenes"):
            return None
        assets = self._list_background_assets()
        return assets[0] if assets else None