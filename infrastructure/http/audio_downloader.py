"""
HTTP Audio Downloader - Downloads audio files from URLs.

Implements IAudioDownloader interface for dependency injection.
Optimized with connection pooling for production performance.
"""

from pathlib import Path
from typing import Optional
import httpx  # type: ignore

from core.config import get_settings
from core.logger import logger
from interfaces.audio_downloader import IAudioDownloader


# Connection pool limits for production performance
# These are shared across all requests to reuse TCP connections
HTTP_LIMITS = httpx.Limits(
    max_keepalive_connections=10,  # Keep 10 connections alive
    max_connections=20,  # Max 20 concurrent connections
    keepalive_expiry=30.0,  # Keep connections alive for 30s
)

# Timeout configuration for audio downloads
HTTP_TIMEOUT = httpx.Timeout(
    connect=10.0,  # 10s to establish connection
    read=60.0,  # 60s to read response (large files)
    write=10.0,  # 10s to write request
    pool=5.0,  # 5s to acquire connection from pool
)


class HttpAudioDownloader(IAudioDownloader):
    """
    HTTP-based audio downloader with connection pooling.

    Implements IAudioDownloader interface for dependency injection.
    Downloads audio files from URLs with streaming and size validation.
    Uses connection pooling for better performance in production.
    """

    def __init__(self, max_size_mb: Optional[int] = None):
        """
        Initialize HTTP audio downloader with connection pool.

        Args:
            max_size_mb: Maximum file size in MB (defaults to settings)
        """
        settings = get_settings()
        self._max_size_mb = max_size_mb or settings.max_upload_size_mb
        # Reusable client with connection pooling
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create reusable HTTP client with connection pooling."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                limits=HTTP_LIMITS,
                timeout=HTTP_TIMEOUT,
                follow_redirects=True,
            )
            logger.info("Created HTTP client with connection pooling")
        return self._client

    async def download(self, url: str, destination: Path) -> float:
        """
        Download audio file from URL to destination.

        Implements IAudioDownloader.download() interface.

        Args:
            url: URL to download audio from
            destination: Local path to save the file

        Returns:
            File size in MB

        Raises:
            ValueError: If download fails or file too large
        """
        logger.info(f"Downloading audio from: {url}")

        client = await self._get_client()
        async with client.stream("GET", url) as response:
            if response.status_code != 200:
                raise ValueError(
                    f"Failed to download file: HTTP {response.status_code}"
                )

            # Check content-length if available
            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > self._max_size_mb * 1024 * 1024:
                raise ValueError(
                    f"File too large: {int(content_length)/1024/1024:.2f}MB > {self._max_size_mb}MB"
                )

            size_bytes = 0
            with open(destination, "wb") as f:
                async for chunk in response.aiter_bytes():
                    f.write(chunk)
                    size_bytes += len(chunk)
                    if size_bytes > self._max_size_mb * 1024 * 1024:
                        raise ValueError(
                            f"File too large (streamed): > {self._max_size_mb}MB"
                        )

            file_size_mb = size_bytes / (1024 * 1024)
            logger.info(f"Downloaded {file_size_mb:.2f}MB to {destination}")
            return file_size_mb

    def get_max_size_mb(self) -> int:
        """
        Get maximum allowed file size in MB.

        Implements IAudioDownloader.get_max_size_mb() interface.

        Returns:
            Maximum file size in MB
        """
        return self._max_size_mb


# Global singleton instance
_audio_downloader: Optional[HttpAudioDownloader] = None


def get_audio_downloader() -> HttpAudioDownloader:
    """
    Get or create global HttpAudioDownloader instance (singleton).

    Returns:
        HttpAudioDownloader instance
    """
    global _audio_downloader

    if _audio_downloader is None:
        logger.info("Creating HttpAudioDownloader instance...")
        _audio_downloader = HttpAudioDownloader()

    return _audio_downloader
