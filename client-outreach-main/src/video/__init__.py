"""Video compositing subpackage."""

from video.broll_manager import BrollManager, BrollMatch
from video.compositor import FFmpegCompositor, MissingFFmpegError, VideoCompositorError, has_ffmpeg
from video.ffmpeg_utils import FFmpegError, find_ffmpeg

__all__ = [
    "BrollManager",
    "BrollMatch",
    "FFmpegCompositor",
    "MissingFFmpegError",
    "VideoCompositorError",
    "has_ffmpeg",
    "FFmpegError",
    "find_ffmpeg",
]