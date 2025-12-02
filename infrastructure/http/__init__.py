"""
HTTP Infrastructure - HTTP client implementations.

This module provides:
- HttpAudioDownloader: Async audio downloader (implements IAudioDownloader)
"""

from .audio_downloader import HttpAudioDownloader, get_audio_downloader

__all__ = [
    "HttpAudioDownloader",
    "get_audio_downloader",
]
