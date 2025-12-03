"""
Unit tests for TranscribeService.

Tests the transcription service business logic using mock dependencies.
The service uses dependency injection, so we can test it without real
Whisper libraries or network calls.
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

from services.transcription import TranscribeService, get_transcribe_service
from interfaces.transcriber import ITranscriber
from interfaces.audio_downloader import IAudioDownloader


class MockTranscriber(ITranscriber):
    """Mock transcriber for testing"""

    def __init__(self, transcription_text: str = "Test transcription"):
        self.transcription_text = transcription_text
        self.transcribe_called = False
        self.last_audio_path = None
        self.last_language = None

    def transcribe(self, audio_path: str, language: str = "vi") -> str:
        self.transcribe_called = True
        self.last_audio_path = audio_path
        self.last_language = language
        return self.transcription_text

    def get_audio_duration(self, audio_path: str) -> float:
        return 30.0  # Return 30 seconds by default


class MockAudioDownloader(IAudioDownloader):
    """Mock audio downloader for testing"""

    def __init__(
        self,
        file_size_mb: float = 5.0,
        should_fail: bool = False,
        max_size_mb: int = 100,
    ):
        self.file_size_mb = file_size_mb
        self.should_fail = should_fail
        self._max_size_mb = max_size_mb
        self.download_called = False
        self.last_url = None
        self.last_path = None

    async def download(self, url: str, destination: Path) -> float:
        self.download_called = True
        self.last_url = url
        self.last_path = destination

        if self.should_fail:
            raise ValueError("Download failed")

        # Create a dummy file
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.touch()

        return self.file_size_mb

    def get_max_size_mb(self) -> int:
        return self._max_size_mb


class TestTranscribeService:
    """Tests for TranscribeService"""

    @pytest.mark.asyncio
    async def test_transcribe_from_url_success(self, tmp_path):
        """Test successful transcription from URL"""
        # Setup mocks
        mock_transcriber = MockTranscriber(transcription_text="Hello world")
        mock_downloader = MockAudioDownloader(file_size_mb=2.5)

        # Create service with mocks
        with patch("services.transcription.settings") as mock_settings:
            mock_settings.temp_dir = str(tmp_path)
            mock_settings.whisper_language = "vi"
            mock_settings.whisper_model = "small"
            mock_settings.transcribe_timeout_seconds = 30

            service = TranscribeService(
                transcriber=mock_transcriber, audio_downloader=mock_downloader
            )

            # Execute
            result = await service.transcribe_from_url("https://example.com/audio.mp3")

            # Verify
            assert result["text"] == "Hello world"
            assert result["file_size_mb"] == 2.5
            assert result["model"] == "small"
            assert result["language"] == "vi"
            assert "duration" in result
            assert "download_duration" in result

            # Verify mocks were called
            assert mock_downloader.download_called
            assert mock_transcriber.transcribe_called

    @pytest.mark.asyncio
    async def test_transcribe_from_url_with_language_override(self, tmp_path):
        """Test transcription with language override"""
        mock_transcriber = MockTranscriber()
        mock_downloader = MockAudioDownloader()

        with patch("services.transcription.settings") as mock_settings:
            mock_settings.temp_dir = str(tmp_path)
            mock_settings.whisper_language = "vi"
            mock_settings.whisper_model = "small"
            mock_settings.transcribe_timeout_seconds = 30

            service = TranscribeService(
                transcriber=mock_transcriber, audio_downloader=mock_downloader
            )

            # Execute with language override
            result = await service.transcribe_from_url(
                "https://example.com/audio.mp3", language="en"
            )

            # Verify language was overridden
            assert result["language"] == "en"
            assert mock_transcriber.last_language == "en"

    @pytest.mark.asyncio
    async def test_transcribe_from_url_download_failure(self, tmp_path):
        """Test handling of download failure"""
        mock_transcriber = MockTranscriber()
        mock_downloader = MockAudioDownloader(should_fail=True)

        with patch("services.transcription.settings") as mock_settings:
            mock_settings.temp_dir = str(tmp_path)
            mock_settings.whisper_language = "vi"
            mock_settings.whisper_model = "small"
            mock_settings.transcribe_timeout_seconds = 30

            service = TranscribeService(
                transcriber=mock_transcriber, audio_downloader=mock_downloader
            )

            # Execute and expect failure
            with pytest.raises(ValueError, match="Download failed"):
                await service.transcribe_from_url("https://example.com/audio.mp3")

    @pytest.mark.asyncio
    async def test_transcribe_from_url_timeout(self, tmp_path):
        """Test handling of transcription timeout"""

        # Create a slow transcriber
        class SlowTranscriber(ITranscriber):
            def transcribe(self, audio_path: str, language: str = "vi") -> str:
                import time

                time.sleep(3)  # Sleep longer than timeout
                return "Should not reach here"

            def get_audio_duration(self, audio_path: str) -> float:
                # Return 0 to prevent adaptive timeout from extending
                return 0.0

        mock_downloader = MockAudioDownloader()

        with patch("services.transcription.settings") as mock_settings:
            mock_settings.temp_dir = str(tmp_path)
            mock_settings.whisper_language = "vi"
            mock_settings.whisper_model = "small"
            mock_settings.transcribe_timeout_seconds = 1  # Very short timeout

            service = TranscribeService(
                transcriber=SlowTranscriber(), audio_downloader=mock_downloader
            )

            # Execute and expect timeout
            with pytest.raises(asyncio.TimeoutError):
                await service.transcribe_from_url("https://example.com/audio.mp3")

    @pytest.mark.asyncio
    async def test_temp_file_cleanup(self, tmp_path):
        """Test that temp files are cleaned up after transcription"""
        mock_transcriber = MockTranscriber()
        mock_downloader = MockAudioDownloader()

        with patch("services.transcription.settings") as mock_settings:
            mock_settings.temp_dir = str(tmp_path)
            mock_settings.whisper_language = "vi"
            mock_settings.whisper_model = "small"
            mock_settings.transcribe_timeout_seconds = 30

            service = TranscribeService(
                transcriber=mock_transcriber, audio_downloader=mock_downloader
            )

            # Execute
            await service.transcribe_from_url("https://example.com/audio.mp3")

            # Verify temp file was cleaned up
            temp_files = list(tmp_path.glob("*.tmp"))
            assert len(temp_files) == 0

    @pytest.mark.asyncio
    async def test_adaptive_timeout_calculation(self, tmp_path):
        """Test that adaptive timeout is calculated based on audio duration"""

        class DurationTrackingTranscriber(ITranscriber):
            def __init__(self, audio_duration: float):
                self._audio_duration = audio_duration

            def transcribe(self, audio_path: str, language: str = "vi") -> str:
                return "Test"

            def get_audio_duration(self, audio_path: str) -> float:
                return self._audio_duration

        mock_downloader = MockAudioDownloader()

        with patch("services.transcription.settings") as mock_settings:
            mock_settings.temp_dir = str(tmp_path)
            mock_settings.whisper_language = "vi"
            mock_settings.whisper_model = "small"
            mock_settings.transcribe_timeout_seconds = 30

            # Test with long audio (120 seconds)
            service = TranscribeService(
                transcriber=DurationTrackingTranscriber(120.0),
                audio_downloader=mock_downloader,
            )

            result = await service.transcribe_from_url("https://example.com/audio.mp3")

            # Verify audio duration is returned
            assert result["audio_duration"] == 120.0


class TestTranscribeServiceDependencyInjection:
    """Tests for dependency injection in TranscribeService"""

    def test_service_accepts_custom_transcriber(self, tmp_path):
        """Test that service accepts custom transcriber"""
        mock_transcriber = MockTranscriber()

        with patch("services.transcription.settings") as mock_settings:
            mock_settings.temp_dir = str(tmp_path)

            service = TranscribeService(transcriber=mock_transcriber)

            assert service.transcriber is mock_transcriber

    def test_service_accepts_custom_downloader(self, tmp_path):
        """Test that service accepts custom audio downloader"""
        mock_downloader = MockAudioDownloader()

        with patch("services.transcription.settings") as mock_settings:
            mock_settings.temp_dir = str(tmp_path)

            # Need to mock the default transcriber since we're not providing one
            with patch.object(
                TranscribeService, "_get_default_transcriber"
            ) as mock_get:
                mock_get.return_value = MockTranscriber()
                service = TranscribeService(audio_downloader=mock_downloader)

            assert service.audio_downloader is mock_downloader
