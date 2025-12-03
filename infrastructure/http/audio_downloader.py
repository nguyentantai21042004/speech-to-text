"""
HTTP Audio Downloader - Downloads audio files from URLs.

Implements IAudioDownloader interface for dependency injection.
"""

from pathlib import Path
from typing import Optional
import httpx  # type: ignore

from core.config import get_settings
from core.logger import logger
from interfaces.audio_downloader import IAudioDownloader


class HttpAudioDownloader(IAudioDownloader):
    """
    HTTP-based audio downloader.

    Implements IAudioDownloader interface for dependency injection.
    Downloads audio files from URLs with streaming and size validation.
    """

    def __init__(self, max_size_mb: Optional[int] = None):
        """
        Initialize HTTP audio downloader.

        Args:
            max_size_mb: Maximum file size in MB (defaults to settings)
        """
        settings = get_settings()
        self._max_size_mb = max_size_mb or settings.max_upload_size_mb

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

        async with httpx.AsyncClient() as client:
            async with client.stream("GET", url, follow_redirects=True) as response:
                if response.status_code != 200:
                    raise ValueError(
                        f"Failed to download file: HTTP {response.status_code}"
                    )

                # Check content-length if available
                content_length = response.headers.get("content-length")
                if (
                    content_length
                    and int(content_length) > self._max_size_mb * 1024 * 1024
                ):
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
