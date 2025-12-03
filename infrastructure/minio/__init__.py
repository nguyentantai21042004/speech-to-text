"""MinIO infrastructure module."""

from infrastructure.minio.audio_downloader import (
    MinioAudioDownloader,
    get_minio_audio_downloader,
)

__all__ = ["MinioAudioDownloader", "get_minio_audio_downloader"]
