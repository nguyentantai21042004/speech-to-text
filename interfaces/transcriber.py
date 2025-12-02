"""
Transcriber Interface - Abstract interface for speech-to-text transcription.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class ITranscriber(ABC):
    """
    Abstract interface for audio transcription.

    Implementations:
    - infrastructure.whisper.library_adapter.WhisperLibraryAdapter
    - infrastructure.whisper.engine.WhisperEngine (legacy CLI)
    """

    @abstractmethod
    def transcribe(self, audio_path: str, language: str = "vi", **kwargs) -> str:
        """
        Transcribe audio file to text.

        Args:
            audio_path: Path to audio file
            language: Language code (e.g., 'vi', 'en')
            **kwargs: Additional implementation-specific parameters

        Returns:
            Transcribed text

        Raises:
            TranscriptionError: If transcription fails
        """
        pass

    @abstractmethod
    def get_audio_duration(self, audio_path: str) -> float:
        """
        Get duration of audio file in seconds.

        Args:
            audio_path: Path to audio file

        Returns:
            Duration in seconds

        Raises:
            TranscriptionError: If duration detection fails
        """
        pass
