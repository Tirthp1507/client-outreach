"""Turn word-level TTS timings into publish-quality animated subtitle files.

Phase 8 additions:
- Scene-aware caption grouping: captions never straddle scene boundaries, and
  each caption is tagged with the scene kind it belongs to.
- Per-scene-kinds caption styling (hook / main / cta "caption templates") so
  hooks and CTAs read larger and in brand accent colors.
- A separate scene-header ASS track (top of the 9:16 frame) showing section
  labels, giving viewers a visual sense of scene structure.
"""

from __future__ import annotations

import logging
from pathlib import Path
from textwrap import dedent

from generators.models import Scene
from voice.models import WordTiming

logger = logging.getLogger(__name__)

DEFAULT_MAX_LINE_CHARS = 28
DEFAULT_MAX_LINES = 2
HIGHLIGHT_COLOR = r"{\c&H0000FFFF&}"  # Vibrant Yellow in BGR ASS format
NORMAL_COLOR = r"{\c&H00FFFFFF&}"     # Clean White

# Per-scene-kind caption template styling.
# Key is the scene kind; value overrides applied on top of the base style.
SCENE_KIND_STYLES: dict[str, dict] = {
    "hook": {"font_scale": 1.35, "primary_colour": "&H0000FFFF", "bold": 1, "outline": 4},
    "main": {"font_scale": 1.0, "primary_colour": "&H00FFFFFF", "bold": 1, "outline": 3},
    "cta": {"font_scale": 1.15, "primary_colour": "&H00F040E0", "bold": 1, "outline": 4},
}

HEADER_STYLE = {
    "font_size": 96,
    "primary_colour": "&H00EEEEEE",
    "back_colour": "&H40222A55",
    "outline": 3,
    "bold": 1,
    "alignment": 8,  # top-centre
    "margin_v": 240,
    "spacing": 2,
}

_STYLE_FORMAT = (
    "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
    "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, "
    "ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
    "MarginR, MarginV, Encoding"
)


def scene_regions_from_timings(
    word_timings: list[WordTiming],
    scenes: list[Scene],
) -> list[dict]:
    """Map word timings onto scene regions scaled to the true audio length.

    Returns ``[{start, end, kind, label}]`` where label is a short section
    title ("HOOK 1", "POINT 2", ...) used for on-screen scene headers.
    """
    if not word_timings or not scenes:
        return []

    total_est = sum(max(0.1, s.estimated_duration) for s in scenes)
    audio_end = word_timings[-1].end
    regions: list[dict] = []
    cursor = 0.0
    for scene in scenes:
        fraction = max(0.1, scene.estimated_duration) / total_est if total_est else 1.0 / len(scenes)
        start = cursor
        cursor += fraction * audio_end
        regions.append(
            {
                "start": round(start, 3),
                "end": round(cursor, 3),
                "kind": scene.kind or "main",
                "label": f"{scene.kind.upper()} {scene.scene_index}",
            }
        )
    if regions:
        regions[-1]["end"] = round(audio_end, 3)
    return regions


def build_captions(
    word_timings: list[WordTiming],
    *,
    max_line_chars: int = DEFAULT_MAX_LINE_CHARS,
    max_lines: int = DEFAULT_MAX_LINES,
    scene_regions: list[dict] | None = None,
) -> list[dict]:
    """Group word timings into timed caption chunks with contained word lists.

    Returns a list of dicts:
    ``{"start", "end", "text", "words", "scene_kind"}``.
    Captions never straddle a scene-region boundary (scene-aware grouping).
    """
    if not word_timings:
        return []

    def region_kind_at(time: float) -> str | None:
        if not scene_regions:
            return None
        for region in scene_regions:
            if region["start"] - 1e-6 <= time <= region["end"] + 1e-6:
                return region["kind"]
        return None

    captions: list[dict] = []
    current: list[WordTiming] = []

    def flush() -> None:
        nonlocal current
        if not current:
            return
        kind = region_kind_at(current[0].start) or "main"
        captions.append(
            {
                "start": current[0].start,
                "end": current[-1].end,
                "text": " ".join(w.text for w in current),
                "words": list(current),
                "scene_kind": kind,
            }
        )
        current = []

    for word in word_timings:
        candidate_count = len(current) + 1
        candidate_chars = sum(len(w.text) for w in current) + len(word.text) + candidate_count - 1
        # Hard break at scene boundaries so no caption spans two scenes.
        boundary_hit = bool(
            scene_regions and current
            and region_kind_at(word.start) not in (None, region_kind_at(current[0].start))
        )
        if current and (
            candidate_chars > max_line_chars * max_lines
            or candidate_count > max_lines * 4
            or boundary_hit
        ):
            flush()
        current.append(word)
    flush()
    return captions


def _srt_ts(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    hh, rem = divmod(ms, 3_600_000)
    mm, rem = divmod(rem, 60_000)
    ss, ms = divmod(rem, 1000)
    return f"{hh:02d}:{mm:02d}:{ss:02d},{ms:03d}"


def _ass_ts(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    hh, rem = divmod(ms, 3_600_000)
    mm, rem = divmod(rem, 60_000)
    ss, rem = divmod(rem, 1000)
    cs = rem // 10
    return f"{hh}:{mm:02d}:{ss:02d}.{cs:02d}"


def _style_row(
    name: str,
    *,
    font_size: int,
    font_color: str,
    outline_color: str,
    bold: int = 1,
    margin_v: int = 420,
    outline: int = 3,
    shadow: int = 2,
    alignment: int = 2,
    back_colour: str = "&H80000000",
    spacing: int = 0,
) -> str:
    return (
        f"Style: {name}," + ",".join(
            str(v)
            for v in (
                "Arial",
                font_size,
                font_color,
                "&H00FFFFFF",
                outline_color,
                back_colour,
                bold,
                0,
                0,
                0,
                100,
                100,
                spacing,
                0,
                1,
                outline,
                shadow,
                alignment,
                60,
                60,
                margin_v,
                1,
            )
        )
    )


def to_srt(captions: list[dict]) -> str:
    """Generate standard SRT subtitle format."""
    blocks = []
    for index, cap in enumerate(captions, start=1):
        start = cap["start"]
        end = max(cap["end"], start + 0.3)
        blocks.append(
            f"{index}\n{_srt_ts(start)} --> {_srt_ts(end)}\n{cap['text']}"
        )
    return "\n\n".join(blocks) + "\n"


def to_ass(
    captions: list[dict],
    *,
    width: int = 1080,
    height: int = 1920,
    margin_v: int = 420,
    font_size: int = 68,
    font_color: str = "&H00FFFFFF",
    highlight_color: str = "&H0000FFFF",  # Bright yellow in BGR
    outline_color: str = "&H00000000",
    font_name: str = "Arial",
    animated_highlight: bool = True,
    scene_kind_styles: dict | None = None,
) -> str:
    """Generate styled ASS subtitles with word-by-word karaoke pop highlighting.

    When ``scene_kind_styles`` is provided, captions tagged with a scene kind
    (hook/main/cta) render in that style's font scale and accent color.
    """
    styles = scene_kind_styles or SCENE_KIND_STYLES

    # Build the set of styles actually used by the captions.
    used_kinds = sorted({c.get("scene_kind", "main") for c in captions if scene_kind_styles or c.get("scene_kind")})

    header = dedent(
        f"""
        [Script Info]
        ScriptType: v4.00+
        PlayResX: {width}
        PlayResY: {height}
        WrapStyle: 2

        [V4+ Styles]
        {_STYLE_FORMAT}
        """
    ).lstrip("\n")
    header += _style_row(
        "Default",
        font_size=font_size,
        font_color=font_color,
        outline_color=outline_color,
        margin_v=margin_v,
    ) + "\n"
    for kind in used_kinds:
        if kind == "main":
            continue
        override = styles.get(kind, {})
        header += _style_row(
            _style_name(kind),
            font_size=max(
                28, int(font_size * float(override.get("font_scale", 1.0)))
            ),
            font_color=override.get("primary_colour", font_color),
            outline_color=outline_color,
            margin_v=margin_v,
            bold=int(override.get("bold", 1)),
            outline=int(override.get("outline", 3)),
        ) + "\n"

    header += "\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Text\n"

    events: list[str] = []

    for cap in captions:
        words: list[WordTiming] = cap.get("words", [])
        style = _style_name(cap.get("scene_kind", "main")) if scene_kind_styles or cap.get("scene_kind") else "Default"
        base_color = _primary_colour(style, styles, font_color)
        active_color = highlight_color

        if not animated_highlight or not words:
            start = _ass_ts(cap["start"])
            end = _ass_ts(max(cap["end"], cap["start"] + 0.3))
            escaped = cap["text"].replace("{", r"\{").replace("}", r"\}")
            events.append(f"Dialogue: 0,{start},{end},{style},,0,0,0,,{escaped}")
            continue

        # Generate word-by-word highlighted segments for the active phrase
        for i, current_word in enumerate(words):
            word_start = _ass_ts(current_word.start)
            word_end = _ass_ts(max(current_word.end, current_word.start + 0.15))

            line_parts = []
            for j, w in enumerate(words):
                clean_w = w.text.replace("{", r"\{").replace("}", r"\}")
                if i == j:
                    line_parts.append(rf"{{\c{active_color}&}}{clean_w}{{\c{base_color}&}}")
                else:
                    line_parts.append(clean_w)

            highlighted_line = " ".join(line_parts)
            events.append(f"Dialogue: 0,{word_start},{word_end},{style},,0,0,0,,{highlighted_line}")

    return header + "\n".join(events) + "\n"


def _style_name(kind: str) -> str:
    return "Default" if kind in (None, "main") else kind.capitalize()


def _primary_colour(style: str, styles: dict, fallback: str) -> str:
    for kind, override in styles.items():
        if _style_name(kind) == style:
            return override.get("primary_colour", fallback)
    return fallback


def to_scene_headers_ass(
    regions: list[dict],
    *,
    width: int = 1080,
    height: int = 1920,
    include_visual_style: bool = True,
) -> str:
    """Generate a scene-header ASS track showing section labels at the top."""
    if not regions:
        return ""

    header = dedent(
        f"""
        [Script Info]
        ScriptType: v4.00+
        PlayResX: {width}
        PlayResY: {height}
        WrapStyle: 2

        [V4+ Styles]
        {_STYLE_FORMAT}
        """
    ).lstrip("\n")
    header += _style_row(
        "SceneHeader",
        font_size=int(HEADER_STYLE["font_size"]),
        font_color=HEADER_STYLE["primary_colour"],
        outline_color="&H00000000",
        back_colour=HEADER_STYLE["back_colour"],
        margin_v=HEADER_STYLE["margin_v"],
        outline=HEADER_STYLE["outline"],
        bold=HEADER_STYLE["bold"],
        alignment=HEADER_STYLE["alignment"],
        spacing=HEADER_STYLE["spacing"],
    ) + "\n"
    header += "\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Text\n"

    events = []
    for region in regions:
        start = _ass_ts(region["start"])
        end = _ass_ts(max(region["end"], region["start"] + 0.3))
        label = region.get("label", region.get("kind", ""))
        events.append(
            f"Dialogue: 0,{start},{end},SceneHeader,,0,0,0,,{label}"
        )
    return header + "\n".join(events) + "\n"


def write_subtitle_files(
    captions: list[dict],
    output_stem: Path,
    *,
    width: int = 1080,
    height: int = 1920,
    font_size: int = 68,
    animated_highlight: bool = True,
    scene_regions: list[dict] | None = None,
    write_headers: bool = True,
) -> dict[str, str]:
    """Write .srt, animated .ass, and optional scene-header .ass files.

    Returns ``{"srt", "ass", "headers"}`` (headers key only when written).
    """
    srt_path = output_stem.with_suffix(".srt")
    ass_path = output_stem.with_suffix(".ass")
    headers_path = output_stem.with_name(f"{output_stem.name}.headers.ass")
    srt_path.write_text(to_srt(captions), encoding="utf-8")
    ass_path.write_text(
        to_ass(
            captions,
            width=width,
            height=height,
            font_size=font_size,
            animated_highlight=animated_highlight,
            scene_kind_styles=SCENE_KIND_STYLES if scene_regions else None,
        ),
        encoding="utf-8",
    )
    result = {"srt": str(srt_path), "ass": str(ass_path)}
    if write_headers:
        headers_path.write_text(
            to_scene_headers_ass(scene_regions or [], width=width, height=height),
            encoding="utf-8",
        )
        result["headers"] = str(headers_path)
    return result