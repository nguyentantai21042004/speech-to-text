"""
Interface Layer - Abstract interfaces for dependency injection.

This layer defines contracts that infrastructure implementations must fulfill.
Services depend on these interfaces, not concrete implementations.
"""

from .transcriber import ITranscriber
from .audio_downloader import IAudioDownloader

__all__ = [
    "ITranscriber",
    "IAudioDownloader",
]
