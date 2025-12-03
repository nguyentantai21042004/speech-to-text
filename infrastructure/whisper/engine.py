"""
Whisper.cpp transcriber interface (Legacy CLI wrapper).
Includes detailed logging and comprehensive error handling.
Auto-downloads models from MinIO if not present locally.

Note: This is the legacy CLI-based implementation.
Prefer WhisperLibraryAdapter for better performance.
"""

import subprocess
import os
import time
from typing import Optional

from core.config import get_settings
from core.logger import logger
from core.errors import (
    WhisperCrashError,
    TimeoutError as STTTimeoutError,
    FileNotFoundError as STTFileNotFoundError,
)
from infrastructure.whisper.model_downloader import get_model_downloader

settings = get_settings()


class WhisperTranscriber:
    """Interface to Whisper.cpp for audio transcription (CLI-based)."""

    def __init__(self):
        """Initialize Whisper transcriber."""
        self._validate_whisper_setup()
        self._model_path_cache: dict[str, str] = {}
        self._model_downloader = None

    def _validate_whisper_setup(self) -> None:
        """
        Validate Whisper executable and models exist.

        Raises:
            FileNotFoundError: If executable or model not found
        """
        try:

            # Check executable exists
            if not os.path.exists(settings.whisper_executable):
                error_msg = (
                    f"Whisper executable not found: {settings.whisper_executable}"
                )
                logger.error(f"{error_msg}")
                raise STTFileNotFoundError(error_msg)

            # Check executable is executable
            if not os.access(settings.whisper_executable, os.X_OK):
                error_msg = (
                    f"Whisper executable not executable: {settings.whisper_executable}"
                )
                logger.error(f"{error_msg}")
                raise PermissionError(error_msg)

            # Check models directory exists
            if not os.path.exists(settings.whisper_models_dir):
                error_msg = (
                    f"Whisper models directory not found: {settings.whisper_models_dir}"
                )
                logger.error(f"{error_msg}")
                raise STTFileNotFoundError(error_msg)

        except Exception as e:
            logger.error(f"Whisper setup validation failed: {e}")
            raise

    def transcribe(
        self,
        audio_path: str,
        language: str = "vi",
        model: str = "medium",
        timeout: Optional[int] = None,
    ) -> str:
        """
        Transcribe audio file using Whisper.cpp.

        Args:
            audio_path: Path to audio file
            language: Language code (en, vi, etc.)
            model: Whisper model to use
            timeout: Timeout in seconds

        Returns:
            Transcribed text

        Raises:
            FileNotFoundError: If audio file not found
            WhisperCrashError: If Whisper process crashes
            TimeoutError: If transcription times out
        """
        start_time = time.time()

        try:
            logger.info(
                f"Starting transcription: file={audio_path}, language={language}, model={model}"
            )

            # Validate audio file exists
            if not os.path.exists(audio_path):
                error_msg = f"Audio file not found: {audio_path}"
                logger.error(f"{error_msg}")
                raise STTFileNotFoundError(error_msg)

            # Build Whisper command
            command = self._build_command(audio_path, language, model)

            # Execute Whisper
            timeout = timeout or settings.chunk_timeout

            result = subprocess.run(
                command, capture_output=True, text=True, timeout=timeout, check=False
            )

            elapsed_time = time.time() - start_time

            # Check for errors
            if result.returncode != 0:
                error_msg = f"Whisper process failed with code {result.returncode}"
                logger.error(f"{error_msg}")
                logger.error(
                    f"Stderr: {result.stderr[:1000] if result.stderr else 'No stderr'}"
                )
                logger.error(
                    f"Stdout: {result.stdout[:500] if result.stdout else 'No stdout'}"
                )
                raise WhisperCrashError(error_msg)

            # Parse output
            transcription = self._parse_output(result.stdout, result.stderr, audio_path)

            logger.info(
                f"Transcription successful: length={len(transcription)} chars, time={elapsed_time:.2f}s"
            )

            # Log performance metrics
            chars_per_second = (
                len(transcription) / elapsed_time if elapsed_time > 0 else 0
            )
            logger.info(f"Performance: {chars_per_second:.2f} chars/sec")

            return transcription

        except subprocess.TimeoutExpired as e:
            elapsed_time = time.time() - start_time
            error_msg = f"Transcription timeout after {elapsed_time:.2f}s"
            logger.error(f"{error_msg}")
            logger.exception("Timeout error details:")
            raise STTTimeoutError(error_msg)

        except WhisperCrashError as e:
            elapsed_time = time.time() - start_time
            logger.error(f"Whisper crash after {elapsed_time:.2f}s: {e}")
            raise

        except STTFileNotFoundError as e:
            logger.error(f"File not found: {e}")
            raise

        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"Transcription failed after {elapsed_time:.2f}s: {e}")
            logger.exception("Transcription error details:")
            raise

    def _build_command(self, audio_path: str, language: str, model: str) -> list:
        """
        Build Whisper.cpp command.
        Auto-downloads model from MinIO if not present locally.
        """
        try:
            if model in self._model_path_cache:
                model_path = self._model_path_cache[model]
            else:
                if self._model_downloader is None:
                    self._model_downloader = get_model_downloader()

                model_path = self._model_downloader.ensure_model_exists(model)
                self._model_path_cache[model] = model_path

            command = [
                settings.whisper_executable,
                "-m",
                model_path,
                "-f",
                audio_path,
                "-l",
                language,
                "--no-timestamps",
                "--max-context",
                str(settings.whisper_max_context),
                "--suppress-nst",
                "--no-speech-thold",
                str(settings.whisper_no_speech_thold),
                "--entropy-thold",
                str(settings.whisper_entropy_thold),
                "--logprob-thold",
                str(settings.whisper_logprob_thold),
            ]

            if settings.whisper_no_fallback:
                command.append("--no-fallback")

            if settings.whisper_suppress_regex:
                command.extend(["--suppress-regex", settings.whisper_suppress_regex])

            return command

        except Exception as e:
            logger.error(f"Failed to build Whisper command: {e}")
            logger.exception("Command build error:")
            raise

    def _parse_output(self, stdout: str, stderr: str, audio_path: str = None) -> str:
        """Parse Whisper output to extract transcription."""
        try:
            transcription_text = ""

            if stdout and stdout.strip():
                transcription_text = stdout.strip()
            else:
                # Check if transcription is in stderr
                if stderr and stderr.strip():
                    stderr_lower = stderr.lower()
                    is_error = any(
                        word in stderr_lower
                        for word in ["error", "warning", "failed", "usage", "help"]
                    )

                    if not is_error and len(stderr.strip()) > 10:
                        transcription_text = stderr.strip()

            if not transcription_text:
                logger.warning("No transcription found in stdout or stderr")
                return ""

            transcription_text = transcription_text.strip()
            transcription_text = " ".join(transcription_text.split())

            return transcription_text

        except Exception as e:
            logger.error(f"Failed to parse Whisper output: {e}")
            logger.exception("Output parsing error:")
            return ""

    def transcribe_with_retry(
        self,
        audio_path: str,
        language: str = "vi",
        model: str = "medium",
        max_retries: int = 3,
        timeout: Optional[int] = None,
    ) -> str:
        """Transcribe with retry logic."""
        last_exception = None

        for attempt in range(max_retries):
            try:
                logger.info(f"Transcription attempt {attempt + 1}/{max_retries}")

                result = self.transcribe(audio_path, language, model, timeout)

                if result:
                    logger.info(f"Transcription successful on attempt {attempt + 1}")
                    return result
                else:
                    logger.warning(f"Empty transcription on attempt {attempt + 1}")
                    if attempt < max_retries - 1:
                        time.sleep(2**attempt)
                        continue

            except STTTimeoutError as e:
                last_exception = e
                logger.warning(f"Timeout on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    logger.info(f"Retrying after backoff...")
                    time.sleep(2**attempt)
                    continue
                else:
                    raise

            except WhisperCrashError as e:
                last_exception = e
                logger.warning(f"Whisper crash on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    logger.info(f"Retrying after backoff...")
                    time.sleep(2**attempt)
                    continue
                else:
                    raise

            except Exception as e:
                logger.error(f"Unexpected error on attempt {attempt + 1}: {e}")
                last_exception = e
                raise

        error_msg = f"All {max_retries} transcription attempts failed"
        logger.error(f"{error_msg}")
        if last_exception:
            raise last_exception
        else:
            raise Exception(error_msg)


# Global singleton instance
_whisper_transcriber: Optional[WhisperTranscriber] = None


def get_whisper_transcriber() -> WhisperTranscriber:
    """Get or create global WhisperTranscriber instance (singleton)."""
    global _whisper_transcriber

    try:
        if _whisper_transcriber is None:
            logger.info("Creating WhisperTranscriber instance...")
            _whisper_transcriber = WhisperTranscriber()
            logger.info("WhisperTranscriber singleton initialized")

        return _whisper_transcriber

    except Exception as e:
        logger.error(f"Failed to get whisper transcriber: {e}")
        logger.exception("WhisperTranscriber initialization error:")
        raise
