"""
MinIO Audio Downloader - Downloads audio files directly from MinIO.

Supports both:
- minio://bucket/path URLs (direct MinIO access)
- http:// URLs (fallback to HTTP download)
"""

from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from minio import Minio  # type: ignore

from core.config import get_settings
from core.logger import logger
from interfaces.audio_downloader import IAudioDownloader


class MinioAudioDownloader(IAudioDownloader):
    """
    MinIO-based audio downloader with HTTP fallback.

    Supports:
    - minio://bucket/path → Direct MinIO download (fast, internal network)
    - http://... → HTTP download via presigned URL
    """

    def __init__(self, max_size_mb: Optional[int] = None):
        settings = get_settings()
        self._max_size_mb = max_size_mb or settings.max_upload_size_mb
        self._minio_client: Optional[Minio] = None
        self._http_downloader = None  # Lazy load

    def _get_minio_client(self) -> Minio:
        """Get or create MinIO client."""
        if self._minio_client is None:
            settings = get_settings()
            # Parse endpoint to get host:port
            endpoint = settings.minio_endpoint.replace("http://", "").replace(
                "https://", ""
            )
            secure = settings.minio_endpoint.startswith("https://")

            self._minio_client = Minio(
                endpoint,
                access_key=settings.minio_access_key,
                secret_key=settings.minio_secret_key,
                secure=secure,
            )
            logger.info(f"MinIO client created: {endpoint}")
        return self._minio_client

    def _get_http_downloader(self):
        """Lazy load HTTP downloader for fallback."""
        if self._http_downloader is None:
            from infrastructure.http.audio_downloader import HttpAudioDownloader

            self._http_downloader = HttpAudioDownloader(self._max_size_mb)
        return self._http_downloader

    def _parse_minio_url(self, url: str) -> tuple[str, str]:
        """
        Parse minio:// URL to bucket and object path.

        Args:
            url: minio://bucket/path/to/file.mp3

        Returns:
            (bucket, object_path)
        """
        parsed = urlparse(url)
        bucket = parsed.netloc
        object_path = parsed.path.lstrip("/")
        return bucket, object_path

    async def download(self, url: str, destination: Path) -> float:
        """
        Download audio file from MinIO or HTTP URL.

        Args:
            url: minio://bucket/path or http://... URL
            destination: Local path to save file

        Returns:
            File size in MB
        """
        if url.startswith("minio://"):
            return await self._download_from_minio(url, destination)
        else:
            # Fallback to HTTP download
            return await self._get_http_downloader().download(url, destination)

    async def _download_from_minio(self, url: str, destination: Path) -> float:
        """Download directly from MinIO using S3 API."""
        bucket, object_path = self._parse_minio_url(url)
        logger.info(f"Downloading from MinIO: bucket={bucket}, object={object_path}")

        client = self._get_minio_client()

        # Get object info first to check size
        stat = client.stat_object(bucket, object_path)
        size_mb = stat.size / (1024 * 1024)

        if size_mb > self._max_size_mb:
            raise ValueError(f"File too large: {size_mb:.2f}MB > {self._max_size_mb}MB")

        # Download file
        client.fget_object(bucket, object_path, str(destination))

        logger.info(f"Downloaded {size_mb:.2f}MB from MinIO to {destination}")
        return size_mb

    def get_max_size_mb(self) -> int:
        return self._max_size_mb


# Global singleton
_minio_downloader: Optional[MinioAudioDownloader] = None


def get_minio_audio_downloader() -> MinioAudioDownloader:
    """Get or create MinioAudioDownloader singleton."""
    global _minio_downloader
    if _minio_downloader is None:
        logger.info("Creating MinioAudioDownloader instance...")
        _minio_downloader = MinioAudioDownloader()
    return _minio_downloader
