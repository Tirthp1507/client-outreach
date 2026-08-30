"""Publishing, metadata generation, and platform formatting."""

from publishers.base import BasePublisher, PublishResult
from publishers.instagram_publisher import InstagramPublisher
from publishers.metadata_generator import (
    InstagramMetadata,
    MetadataGenerator,
    PlatformMetadataPackage,
    YouTubeMetadata,
)
from publishers.publisher_service import PublisherService, PublishingGateError
from publishers.youtube_publisher import YouTubePublisher

__all__ = [
    "BasePublisher",
    "InstagramMetadata",
    "InstagramPublisher",
    "MetadataGenerator",
    "PlatformMetadataPackage",
    "PublishResult",
    "PublisherService",
    "PublishingGateError",
    "YouTubeMetadata",
    "YouTubePublisher",
]