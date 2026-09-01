"""Background music discovery, narration ducking, and loudness normalization mixer."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from config import PROJECT_ROOT

logger = logging.getLogger(__name__)

AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}

# Loudness for Shorts/Reels (EBU R128 integrated loudness target in LUFS).
DEFAULT_LOUDNESS_TARGET = -14.0
DEFAULT_LOUDNESS_TP = -1.5
DEFAULT_LOUDNESS_LRA = 11

# Sidechain ducking defaults (compress BGM whenever narration is present).
DEFAULT_DUCK_THRESHOLD = 0.03
DEFAULT_DUCK_RATIO = 12
DEFAULT_DUCK_ATTACK = 5
DEFAULT_DUCK_RELEASE = 250


class AudioMixer:
    """Finds background music tracks and builds audio mixing filters with ducking."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        cfg = config or {}
        voice_cfg = cfg.get("voice", {})
        music_cfg = cfg.get("music", {})

        self.music_dir = Path(music_cfg.get("music_dir", "assets/music"))
        if not self.music_dir.is_absolute():
            self.music_dir = PROJECT_ROOT / self.music_dir

        self.music_file = music_cfg.get("music_file")
        self.music_volume = float(music_cfg.get("volume", 0.12))
        self.enabled = bool(music_cfg.get("enabled", True))

        # Loudness normalization (disabled when target is falsy).
        raw_target = voice_cfg.get("loudness_target", DEFAULT_LOUDNESS_TARGET)
        if raw_target is None or raw_target is False or str(raw_target).lower() in ("none", "off", "false", "0"):
            self.loudness_enabled = False
            self.loudness_target = None
        else:
            self.loudness_enabled = True
            self.loudness_target = float(raw_target)
        self.loudness_tp = float(voice_cfg.get("loudness_tp", DEFAULT_LOUDNESS_TP))
        self.loudness_lra = float(voice_cfg.get("loudness_lra", DEFAULT_LOUDNESS_LRA))

        # Sidechain ducking.
        self.ducking_enabled = bool(music_cfg.get("ducking", True))
        self.duck_threshold = float(music_cfg.get("duck_threshold", DEFAULT_DUCK_THRESHOLD))
        self.duck_ratio = float(music_cfg.get("duck_ratio", DEFAULT_DUCK_RATIO))
        self.duck_attack = int(music_cfg.get("duck_attack", DEFAULT_DUCK_ATTACK))
        self.duck_release = int(music_cfg.get("duck_release", DEFAULT_DUCK_RELEASE))

    def find_music_track(self) -> Path | None:
        """Locate a valid background music track if available."""
        if not self.enabled:
            return None

        if self.music_file:
            custom_path = Path(self.music_file)
            if not custom_path.is_absolute():
                custom_path = PROJECT_ROOT / custom_path
            if custom_path.exists():
                return custom_path

        if not self.music_dir.exists():
            return None

        tracks = [
            f for f in sorted(self.music_dir.iterdir())
            if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS
        ]
        return tracks[0] if tracks else None

    def build_voice_filter(self) -> str:
        """Normalization filter applied to the voice stream."""
        if not self.loudness_enabled:
            return "volume=1.0"
        return (
            f"loudnorm=I={self.loudness_target:.1f}:TP={self.loudness_tp:.1f}:"
            f"LRA={self.loudness_lra:.0f}"
        )

    def build_audio_inputs_and_filter(
        self,
        voice_path: Path | str,
        *,
        voice_index: int = 1,
        voice_duration: float | None = None,
    ) -> tuple[list[str], str]:
        """Return FFmpeg input arguments and filter graph for mixing voice + ducked music.

        Stream layout used in the graph:
          ``[voice_index:a]`` voiceover (possibly normalized to publish loudness),
          ``[voice_index+1:a]`` background music (ducked under narration).

        Args:
            voice_path: path to the narration audio (used for logging).
            voice_index: 0-based input index of the voice stream.
            voice_duration: narration length in seconds; when provided the music
                fades out smoothly over its final 2 seconds.

        Returns:
            (extra_input_args, filter_complex_fragment)
        """
        music_track = self.find_music_track()
        voice_chain = self.build_voice_filter()
        if music_track is None:
            # Pure voiceover without background music.
            return [], f"[{voice_index}:a]{voice_chain}[aout]"

        bgm_index = voice_index + 1
        extra_inputs = ["-stream_loop", "-1", "-i", str(music_track)]

        bgm_chain = f"[{bgm_index}:a]volume={self.music_volume:.2f},aloop=-1:size=2e+09"
        if voice_duration and voice_duration > 3.0:
            fade_start = max(0.5, voice_duration - 2.0)
            bgm_chain += f",afade=t=out:st={fade_start:.2f}:d=2.0"

        if self.ducking_enabled:
            # Real sidechain ducking: compress BGM whenever the voice is active.
            # Use asplit to fork the normalized voice for the sidechain detector and main mix.
            filter_graph = (
                f"[{voice_index}:a]{voice_chain},asplit=2[voice_main][voice_sc];"
                f"{bgm_chain}[bgm];"
                f"[bgm][voice_sc]sidechaincompress="
                f"threshold={self.duck_threshold:.2f}:ratio={self.duck_ratio:.0f}:"
                f"attack={self.duck_attack}:release={self.duck_release}[ducked_bgm];"
                f"[voice_main][ducked_bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]"
            )
        else:
            # Simple static blend without ducking.
            filter_graph = (
                f"[{voice_index}:a]{voice_chain}[voice_norm];"
                f"{bgm_chain}[bgm];"
                f"[voice_norm][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]"
            )

        logger.info(
            "Mixing background music: %s (vol=%.2f, duck=%s, loudnorm=%s)",
            music_track.name, self.music_volume, self.ducking_enabled, self.loudness_enabled,
        )
        return extra_inputs, filter_graph