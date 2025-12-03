"""
System dependencies validation and FastAPI dependency injection.

This module provides:
- System dependency validation (ffmpeg, ffprobe, whisper)
- FastAPI dependency injection functions for routes
"""

import shutil
from pathlib import Path
from typing import Tuple, Optional

from core.logger import logger
from core.config import get_settings
from core.errors import MissingDependencyError


def check_ffmpeg() -> Tuple[bool, Optional[str]]:
    """
    Check if ffmpeg or ffprobe is installed and accessible.

    Returns:
        Tuple of (is_available, path)
        - is_available: True if ffmpeg/ffprobe found
        - path: Path to executable, or None if not found
    """
    ffprobe_path = shutil.which("ffprobe")
    if ffprobe_path:
        return True, ffprobe_path

    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        return True, ffmpeg_path

    logger.warning("ffmpeg/ffprobe not found in PATH")
    return False, None


def validate_dependencies(check_ffmpeg: bool = True) -> None:
    """
    Validate all required system dependencies for STT processing.

    Args:
        check_ffmpeg: If True, check for ffmpeg/ffprobe (required for Consumer service).
                     If False, skip ffmpeg check (for API service which doesn't need it).

    Raises:
        MissingDependencyError: If required dependencies are missing
    """
    logger.info("Validating system dependencies...")

    # Check ffmpeg/ffprobe (only if requested)
    if check_ffmpeg:
        ffmpeg_available, ffmpeg_path = check_ffmpeg()

        if not ffmpeg_available:
            error_msg = (
                "ffmpeg/ffprobe not installed. "
                "Install with: brew install ffmpeg (macOS) or apt-get install ffmpeg (Linux)"
            )
            logger.error(f"{error_msg}")
            raise MissingDependencyError(error_msg)

        logger.info(f"All dependencies validated: ffmpeg/ffprobe={ffmpeg_path}")

    # Check Whisper library artifacts (optional - warn only, don't fail)
    settings = get_settings()
    model_size = settings.whisper_model_size
    artifacts_dir = Path(settings.whisper_artifacts_dir)
    model_dir = artifacts_dir / f"whisper_{model_size}_xeon"
    model_file = model_dir / f"ggml-{model_size}-q5_1.bin"

    if model_file.exists():
        logger.info(f"Whisper model found: {model_file}")
    else:
        logger.warning(
            f"Whisper model not found: {model_file}. "
            f"Run: make setup-artifacts or download will happen on first request."
        )

    logger.info("System dependencies check passed")


# =============================================================================
# FastAPI Dependency Injection
# =============================================================================


def get_transcribe_service_dependency():
    """
    FastAPI dependency for TranscribeService.

    Usage in routes:
        @router.post("/transcribe")
        async def transcribe(
            service: TranscribeService = Depends(get_transcribe_service_dependency)
        ):
            ...

    Returns:
        TranscribeService instance with injected dependencies
    """
    from core.container import get_transcribe_service

    return get_transcribe_service()


def get_transcriber_dependency():
    """
    FastAPI dependency for ITranscriber.

    Usage in routes:
        @router.post("/transcribe")
        async def transcribe(
            transcriber: ITranscriber = Depends(get_transcriber_dependency)
        ):
            ...

    Returns:
        ITranscriber implementation
    """
    from core.container import get_transcriber

    return get_transcriber()


def get_audio_downloader_dependency():
    """
    FastAPI dependency for IAudioDownloader.

    Usage in routes:
        @router.post("/download")
        async def download(
            downloader: IAudioDownloader = Depends(get_audio_downloader_dependency)
        ):
            ...

    Returns:
        IAudioDownloader implementation
    """
    from core.container import get_audio_downloader

    return get_audio_downloader()
