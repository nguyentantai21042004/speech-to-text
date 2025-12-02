"""
Whisper Infrastructure - Whisper.cpp integration implementations.

This module provides:
- WhisperLibraryAdapter: Direct C library integration (primary, implements ITranscriber)
- WhisperTranscriber: Legacy CLI wrapper (fallback)
- ModelDownloader: MinIO model downloader
"""

from .library_adapter import WhisperLibraryAdapter, get_whisper_library_adapter
from .engine import WhisperTranscriber, get_whisper_transcriber
from .model_downloader import ModelDownloader, get_model_downloader

__all__ = [
    # Primary adapter (implements ITranscriber)
    "WhisperLibraryAdapter",
    "get_whisper_library_adapter",
    # Legacy CLI wrapper
    "WhisperTranscriber",
    "get_whisper_transcriber",
    # Model downloader
    "ModelDownloader",
    "get_model_downloader",
]
