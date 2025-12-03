"""
Transcription Service - Business logic for audio transcription.

This service orchestrates audio download and transcription using
dependency injection through interfaces.
"""

import os
import uuid
import asyncio
import time
from pathlib import Path
from typing import Dict, Any, Optional

from core.config import get_settings
from core.logger import logger
from interfaces.transcriber import ITranscriber
from interfaces.audio_downloader import IAudioDownloader

settings = get_settings()


class TranscribeService:
    """
    Stateless service to download audio from URL and transcribe it.

    Uses dependency injection through interfaces:
    - ITranscriber: For audio transcription
    - IAudioDownloader: For downloading audio from URLs
    """

    def __init__(
        self,
        transcriber: Optional[ITranscriber] = None,
        audio_downloader: Optional[IAudioDownloader] = None,
    ):
        """
        Initialize TranscribeService with optional dependencies.

        If dependencies are not provided, defaults are used from infrastructure layer.

        Args:
            transcriber: ITranscriber implementation (default: WhisperLibraryAdapter)
            audio_downloader: IAudioDownloader implementation (default: HttpAudioDownloader)
        """
        # Use provided dependencies or get defaults
        self.transcriber = transcriber or self._get_default_transcriber()
        self.audio_downloader = audio_downloader or self._get_default_audio_downloader()

        # Use configured temp dir
        self.temp_dir = Path(settings.temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"TranscribeService initialized "
            f"(transcriber={self.transcriber.__class__.__name__}, "
            f"downloader={self.audio_downloader.__class__.__name__})"
        )

    def _get_default_transcriber(self) -> ITranscriber:
        """Get default transcriber from infrastructure layer."""
        from infrastructure.whisper.library_adapter import get_whisper_library_adapter

        logger.info("Using WhisperLibraryAdapter (direct C library integration)")
        return get_whisper_library_adapter()

    def _get_default_audio_downloader(self) -> IAudioDownloader:
        """Get default audio downloader from infrastructure layer."""
        from infrastructure.http.audio_downloader import get_audio_downloader

        logger.info("Using HttpAudioDownloader")
        return get_audio_downloader()

    async def transcribe_from_url(
        self, audio_url: str, language: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Download audio from URL and transcribe it with timeout protection.
        Automatically uses chunking for audio > 30 seconds with adaptive timeout.

        Args:
            audio_url: URL to download audio from
            language: Optional language hint for transcription (overrides config)

        Returns:
            Dictionary containing transcription text and metadata

        Raises:
            asyncio.TimeoutError: If transcription exceeds configured timeout
            ValueError: If download fails or file too large
        """
        file_id = str(uuid.uuid4())
        temp_file_path = self.temp_dir / f"{file_id}.tmp"

        try:
            logger.info(f"Processing transcription request for URL: {audio_url}")

            # 1. Download file using IAudioDownloader
            start_download = time.time()
            file_size_mb = await self.audio_downloader.download(
                audio_url, temp_file_path
            )
            download_duration = time.time() - start_download
            logger.info(f"Downloaded {file_size_mb:.2f}MB in {download_duration:.2f}s")

            # 2. Detect audio duration for adaptive timeout using ITranscriber
            audio_duration = 0.0
            try:
                audio_duration = self.transcriber.get_audio_duration(
                    str(temp_file_path)
                )
                logger.info(f"Detected audio duration: {audio_duration:.2f}s")
            except Exception as e:
                logger.warning(f"Failed to detect audio duration: {e}")

            # 3. Calculate adaptive timeout
            base_timeout = settings.transcribe_timeout_seconds
            if audio_duration > 0:
                adaptive_timeout = max(base_timeout, int(audio_duration * 1.5))
            else:
                adaptive_timeout = base_timeout

            logger.info(
                f"Using adaptive timeout: {adaptive_timeout}s (base={base_timeout}s, audio={audio_duration:.2f}s)"
            )

            # 4. Transcribe with timeout using ITranscriber
            loop = asyncio.get_running_loop()
            start_transcribe = time.time()

            lang = language or settings.whisper_language
            model = settings.whisper_model

            logger.info(
                f"Starting transcription (language={lang}, timeout={adaptive_timeout}s)"
            )

            def _transcribe():
                return self.transcriber.transcribe(str(temp_file_path), lang)

            transcription_text = await asyncio.wait_for(
                loop.run_in_executor(None, _transcribe),
                timeout=adaptive_timeout,
            )

            transcribe_duration = time.time() - start_transcribe
            logger.info(f"Transcribed in {transcribe_duration:.2f}s")

            return {
                "text": transcription_text,
                "duration": transcribe_duration,
                "download_duration": download_duration,
                "file_size_mb": file_size_mb,
                "model": model,
                "language": lang,
                "audio_duration": audio_duration,
            }

        except asyncio.TimeoutError:
            logger.error(f"Transcription timeout after {adaptive_timeout}s")
            raise
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise
        finally:
            # Cleanup temp file
            if temp_file_path.exists():
                try:
                    os.remove(temp_file_path)
                except Exception as e:
                    logger.warning(f"Failed to clean up temp file: {e}")


# Global singleton instance
_transcribe_service: Optional[TranscribeService] = None


def get_transcribe_service(
    transcriber: Optional[ITranscriber] = None,
    audio_downloader: Optional[IAudioDownloader] = None,
) -> TranscribeService:
    """
    Get or create global TranscribeService instance (singleton).

    Args:
        transcriber: Optional ITranscriber implementation
        audio_downloader: Optional IAudioDownloader implementation

    Returns:
        TranscribeService instance
    """
    global _transcribe_service

    if _transcribe_service is None:
        logger.info("Creating TranscribeService instance...")
        _transcribe_service = TranscribeService(
            transcriber=transcriber,
            audio_downloader=audio_downloader,
        )

    return _transcribe_service
