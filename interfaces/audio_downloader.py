"""
Audio Downloader Interface - Abstract interface for downloading audio from URLs.
"""

from abc import ABC, abstractmethod
from pathlib import Path


class IAudioDownloader(ABC):
    """
    Abstract interface for downloading audio files from URLs.

    Implementations:
    - infrastructure.http.audio_downloader.HttpAudioDownloader
    """

    @abstractmethod
    async def download(self, url: str, destination: Path) -> float:
        """
        Download audio file from URL to destination.

        Args:
            url: URL to download audio from
            destination: Local path to save the file

        Returns:
            File size in MB

        Raises:
            ValueError: If download fails or file too large
        """
        pass

    @abstractmethod
    def get_max_size_mb(self) -> int:
        """
        Get maximum allowed file size in MB.

        Returns:
            Maximum file size in MB
        """
        pass
