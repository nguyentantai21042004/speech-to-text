"""
Infrastructure Layer - External system integrations.

This layer contains implementations of interfaces defined in the interfaces/ layer.
Each subdirectory groups implementations by external dependency.

Structure:
- whisper/  - Whisper.cpp transcription integration
- http/     - HTTP client implementations
"""

from .whisper import WhisperLibraryAdapter, get_whisper_library_adapter
from .http import HttpAudioDownloader, get_audio_downloader

__all__ = [
    # Whisper transcription
    "WhisperLibraryAdapter",
    "get_whisper_library_adapter",
    # HTTP audio download
    "HttpAudioDownloader",
    "get_audio_downloader",
]
