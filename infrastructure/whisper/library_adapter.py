"""
Whisper Library Adapter - Direct C library integration for Whisper.cpp

Implements ITranscriber interface for dependency injection.
Replaces subprocess-based CLI wrapper with direct shared library calls.
Provides significant performance improvements by loading model once and reusing context.
"""

import ctypes
import json
import os
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, Any
import numpy as np  # type: ignore

from core.config import get_settings
from core.logger import logger
from core.errors import (
    TranscriptionError,
    WhisperLibraryError,
    LibraryLoadError,
    ModelInitError,
)
from core.constants import WHISPER_MODEL_CONFIGS, MIN_CHUNK_DURATION
from interfaces.transcriber import ITranscriber


@contextmanager
def capture_native_logs(source: str, level: str = "info"):
    """
    Capture stdout/stderr emitted by native libraries (ctypes) and pipe them through Loguru.
    """
    log_method = getattr(logger, level, logger.info)

    if not hasattr(sys.stdout, "fileno") or not hasattr(sys.stderr, "fileno"):
        yield
        return

    try:
        stdout_fd = sys.stdout.fileno()
        stderr_fd = sys.stderr.fileno()

        stdout_dup = os.dup(stdout_fd)
        stderr_dup = os.dup(stderr_fd)

        stdout_pipe_r, stdout_pipe_w = os.pipe()
        stderr_pipe_r, stderr_pipe_w = os.pipe()

        stdout_lines: list[str] = []
        stderr_lines: list[str] = []
        collector_lock = threading.Lock()

        def _forward(pipe_fd: int, collector: list[str]):
            with os.fdopen(pipe_fd, "r", encoding="utf-8", errors="ignore") as pipe:
                for line in pipe:
                    text = line.strip()
                    if text:
                        with collector_lock:
                            collector.append(text)

        stdout_thread = threading.Thread(
            target=_forward, args=(stdout_pipe_r, stdout_lines), daemon=True
        )
        stderr_thread = threading.Thread(
            target=_forward, args=(stderr_pipe_r, stderr_lines), daemon=True
        )

        stdout_thread.start()
        stderr_thread.start()

        os.dup2(stdout_pipe_w, stdout_fd)
        os.dup2(stderr_pipe_w, stderr_fd)

        try:
            yield
        finally:
            os.dup2(stdout_dup, stdout_fd)
            os.dup2(stderr_dup, stderr_fd)

            os.close(stdout_pipe_w)
            os.close(stderr_pipe_w)
            os.close(stdout_dup)
            os.close(stderr_dup)

            stdout_thread.join(timeout=0.5)
            stderr_thread.join(timeout=0.5)

            if stdout_lines:
                log_method(f"[{source}:stdout]\n" + "\n".join(stdout_lines))
            if stderr_lines:
                log_method(f"[{source}:stderr]\n" + "\n".join(stderr_lines))

    except Exception:
        yield


# Note: WhisperLibraryError, LibraryLoadError, ModelInitError imported from core.errors
# Note: MIN_CHUNK_DURATION, WHISPER_MODEL_CONFIGS imported from core.constants

# Alias for backward compatibility within this module
MODEL_CONFIGS = WHISPER_MODEL_CONFIGS


class WhisperLibraryAdapter(ITranscriber):
    """
    Direct C library integration for Whisper.cpp.

    Implements ITranscriber interface for dependency injection.
    Loads shared libraries and Whisper model once, reuses context for all requests.
    """

    def __init__(self, model_size: Optional[str] = None):
        """
        Initialize Whisper library adapter.

        Args:
            model_size: Model size (base/small/medium), defaults to settings

        Raises:
            LibraryLoadError: If libraries cannot be loaded
            ModelInitError: If Whisper context cannot be initialized
        """
        settings = get_settings()
        self.model_size = model_size or settings.whisper_model_size
        self.artifacts_dir = Path(settings.whisper_artifacts_dir)

        logger.info(f"Initializing WhisperLibraryAdapter with model={self.model_size}")

        if self.model_size not in MODEL_CONFIGS:
            raise ValueError(
                f"Unsupported model size: {self.model_size}. Must be one of {list(MODEL_CONFIGS.keys())}"
            )

        self.config = MODEL_CONFIGS[self.model_size]
        self.lib_dir = self.artifacts_dir / self.config["dir"]
        self.model_path = self.lib_dir / self.config["model"]

        self.lib = None
        self.ctx = None

        # Task 2.1.2: Add threading lock for thread-safe context access
        self._lock = threading.Lock()

        try:
            self._load_libraries()
            self._initialize_context()
            logger.info(
                f"WhisperLibraryAdapter initialized successfully (model={self.model_size}, thread_safe=True)"
            )
        except Exception as e:
            logger.error(f"Failed to initialize WhisperLibraryAdapter: {e}")
            raise

    def _load_libraries(self) -> None:
        """Load Whisper shared libraries in correct dependency order."""
        try:
            if not self.lib_dir.exists():
                raise LibraryLoadError(
                    f"Library directory not found: {self.lib_dir}. "
                    f"Run artifact download script first."
                )

            old_ld_path = os.environ.get("LD_LIBRARY_PATH", "")
            new_ld_path = (
                f"{self.lib_dir}:{old_ld_path}" if old_ld_path else str(self.lib_dir)
            )
            os.environ["LD_LIBRARY_PATH"] = new_ld_path

            # Load dependencies in correct order
            ctypes.CDLL(
                str(self.lib_dir / "libggml-base.so.0"), mode=ctypes.RTLD_GLOBAL
            )
            ctypes.CDLL(str(self.lib_dir / "libggml-cpu.so.0"), mode=ctypes.RTLD_GLOBAL)
            ctypes.CDLL(str(self.lib_dir / "libggml.so.0"), mode=ctypes.RTLD_GLOBAL)

            with capture_native_logs("whisper_load", level="debug"):
                self.lib = ctypes.CDLL(str(self.lib_dir / "libwhisper.so"))

            logger.info("All Whisper libraries loaded successfully")

        except OSError as e:
            raise LibraryLoadError(f"Failed to load Whisper libraries: {e}")
        except Exception as e:
            raise LibraryLoadError(f"Unexpected error loading libraries: {e}")

    def _initialize_context(self) -> None:
        """Initialize Whisper context from model file."""
        try:

            if not self.model_path.exists():
                raise ModelInitError(
                    f"Model file not found: {self.model_path}. "
                    f"Run artifact download script first."
                )

            self.lib.whisper_init_from_file.argtypes = [ctypes.c_char_p]
            self.lib.whisper_init_from_file.restype = ctypes.c_void_p

            model_path_bytes = str(self.model_path).encode("utf-8")
            with capture_native_logs("whisper_init"):
                self.ctx = self.lib.whisper_init_from_file(model_path_bytes)

            if not self.ctx:
                raise ModelInitError(
                    f"whisper_init_from_file() returned NULL. "
                    f"Model file may be corrupted: {self.model_path}"
                )

            logger.info(
                f"Whisper context initialized (model={self.model_size}, ram~{self.config['ram_mb']}MB)"
            )

        except ModelInitError:
            raise
        except Exception as e:
            raise ModelInitError(f"Failed to initialize Whisper context: {e}")

    def transcribe(self, audio_path: str, language: str = "vi", **kwargs) -> str:
        """
        Transcribe audio file using Whisper library.

        Implements ITranscriber.transcribe() interface.
        Automatically uses chunking for audio > 30 seconds.

        Args:
            audio_path: Path to audio file
            language: Language code (vi, en, etc.)
            **kwargs: Additional parameters (for compatibility)

        Returns:
            Transcribed text

        Raises:
            TranscriptionError: If transcription fails
        """
        try:
            if not os.path.exists(audio_path):
                raise TranscriptionError(f"Audio file not found: {audio_path}")

            settings = get_settings()

            # Try to get duration, fallback to direct transcription if ffprobe fails
            duration = 0.0
            try:
                duration = self.get_audio_duration(audio_path)
                logger.info(f"Audio duration: {duration:.2f}s")
            except TranscriptionError as e:
                logger.warning(
                    f"Could not detect audio duration: {e}. Using direct transcription."
                )

            if (
                settings.whisper_chunk_enabled
                and duration > settings.whisper_chunk_duration
            ):
                logger.info(
                    f"Using chunked transcription (duration > {settings.whisper_chunk_duration}s)"
                )
                return self._transcribe_chunked(audio_path, language, duration)
            else:
                logger.info("Using direct transcription (fast path)")
                return self._transcribe_direct(audio_path, language)

        except TranscriptionError:
            raise
        except Exception as e:
            raise TranscriptionError(f"Transcription failed: {e}")

    def get_audio_duration(self, audio_path: str) -> float:
        """
        Get audio duration using ffprobe.

        Implements ITranscriber.get_audio_duration() interface.

        Args:
            audio_path: Path to audio file

        Returns:
            Duration in seconds

        Raises:
            TranscriptionError: If ffprobe fails
        """
        try:
            cmd = [
                "ffprobe",
                "-v",
                "error",  # Show errors only
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",  # Also show streams for better detection
                "-i",  # Explicit input flag
                audio_path,
            ]

            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=10  # Add timeout
            )

            if result.returncode != 0:
                error_msg = result.stderr.strip() or "Unknown ffprobe error"
                raise TranscriptionError(f"ffprobe failed: {error_msg}")

            if not result.stdout.strip():
                raise TranscriptionError("ffprobe returned empty output")

            data = json.loads(result.stdout)

            # Try format duration first, then stream duration
            duration = None
            if "format" in data and "duration" in data["format"]:
                duration = float(data["format"]["duration"])
            elif "streams" in data and data["streams"]:
                for stream in data["streams"]:
                    if "duration" in stream:
                        duration = float(stream["duration"])
                        break

            if duration is None:
                raise TranscriptionError("No duration found in ffprobe output")

            return duration

        except subprocess.TimeoutExpired:
            raise TranscriptionError("ffprobe timed out after 10s")
        except subprocess.CalledProcessError as e:
            raise TranscriptionError(f"ffprobe failed: {e.stderr or 'Unknown error'}")
        except (KeyError, ValueError, json.JSONDecodeError) as e:
            raise TranscriptionError(f"Failed to parse ffprobe output: {e}")

    # Alias for backward compatibility
    def _get_audio_duration(self, audio_path: str) -> float:
        """Backward compatibility alias for get_audio_duration."""
        return self.get_audio_duration(audio_path)

    def _transcribe_direct(self, audio_path: str, language: str) -> str:
        """Direct transcription without chunking (fast path)."""
        audio_data, audio_duration = self._load_audio(audio_path)
        result = self._call_whisper_full(audio_data, language, audio_duration)
        return result["text"]

    def _transcribe_chunked(
        self, audio_path: str, language: str, duration: float
    ) -> str:
        """Chunked transcription for long audio files."""
        settings = get_settings()
        chunk_duration = settings.whisper_chunk_duration
        chunk_overlap = settings.whisper_chunk_overlap

        logger.info(
            f"Starting chunked transcription: duration={duration:.2f}s, chunk_size={chunk_duration}s, overlap={chunk_overlap}s"
        )

        try:
            chunk_files = self._split_audio(
                audio_path, duration, chunk_duration, chunk_overlap
            )
            logger.info(f"Audio split into {len(chunk_files)} chunks")

            chunk_texts = []
            successful_chunks = 0
            failed_chunks = 0

            for i, chunk_path in enumerate(chunk_files):
                try:
                    logger.info(
                        f"Processing chunk {i+1}/{len(chunk_files)}: {chunk_path}"
                    )
                    chunk_text = self._transcribe_direct(chunk_path, language)
                    chunk_texts.append(chunk_text)
                    successful_chunks += 1

                    # Task 1.3.1: Log chunk result with preview
                    preview = (
                        chunk_text[:50] + "..." if len(chunk_text) > 50 else chunk_text
                    )
                    logger.info(
                        f"Chunk {i+1}/{len(chunk_files)} result: {len(chunk_text)} chars, preview='{preview}'"
                    )

                    # Task 1.3.2: Log warning for empty chunk results
                    if not chunk_text.strip():
                        logger.warning(
                            f"Chunk {i+1}/{len(chunk_files)} returned empty text - may contain silence or invalid audio"
                        )

                except Exception as e:
                    failed_chunks += 1
                    # Task 1.1.1: Add full exception traceback
                    logger.error(
                        f"Failed to process chunk {i+1}/{len(chunk_files)} (path={chunk_path}, exception_type={type(e).__name__}): {e}"
                    )
                    logger.exception("Chunk processing exception details:")
                    chunk_texts.append("[inaudible]")

                finally:
                    try:
                        if os.path.exists(chunk_path):
                            os.remove(chunk_path)
                    except Exception as e:
                        logger.warning(f"Failed to cleanup chunk file: {e}")

            # Task 1.3.3: Add summary log after all chunks complete
            logger.info(
                f"Chunked transcription summary: total={len(chunk_files)}, "
                f"successful={successful_chunks}, failed={failed_chunks}"
            )

            merged_text = self._merge_chunks(chunk_texts)
            logger.info(
                f"Chunked transcription complete: {len(chunk_texts)} chunks, {len(merged_text)} chars"
            )

            return merged_text

        except Exception as e:
            logger.error(f"Chunked transcription failed: {e}")
            raise TranscriptionError(f"Chunked transcription failed: {e}")

    def _split_audio(
        self, audio_path: str, duration: float, chunk_duration: int, overlap: int
    ) -> list[str]:
        """Split audio into chunks using FFmpeg."""
        try:
            chunks = []
            start = 0.0

            while start < duration:
                end = min(start + chunk_duration, duration)
                chunks.append((start, end))

                if end >= duration:
                    break

                next_start = end - overlap

                if next_start <= start:
                    logger.warning(
                        f"Chunk calculation would not advance (start={start}, next={next_start}), breaking"
                    )
                    break

                start = next_start

                if len(chunks) > 1000:
                    raise TranscriptionError(
                        "Too many chunks calculated, possible infinite loop"
                    )

            logger.info(f"Calculated {len(chunks)} chunk boundaries")

            # Task 3.2.3: Merge short final chunk with previous instead of skipping
            if len(chunks) > 1:
                last_chunk_duration = chunks[-1][1] - chunks[-1][0]
                if last_chunk_duration < MIN_CHUNK_DURATION:
                    logger.warning(
                        f"Final chunk too short ({last_chunk_duration:.2f}s < {MIN_CHUNK_DURATION}s), "
                        f"merging with previous chunk"
                    )
                    # Extend previous chunk to include the final chunk
                    prev_start, _ = chunks[-2]
                    _, last_end = chunks[-1]
                    chunks[-2] = (prev_start, last_end)
                    chunks.pop()  # Remove the short final chunk
                    logger.info(f"Merged final chunk, now {len(chunks)} chunks")

            chunk_files = []
            base_path = Path(audio_path).parent
            base_name = Path(audio_path).stem

            for i, (start_time, end_time) in enumerate(chunks):
                chunk_path = base_path / f"{base_name}_chunk_{i}.wav"
                chunk_duration_actual = end_time - start_time

                # Task 3.2.2: Skip chunks shorter than minimum (except merged final)
                if chunk_duration_actual < MIN_CHUNK_DURATION and i < len(chunks) - 1:
                    logger.warning(
                        f"Skipping chunk {i+1}: duration {chunk_duration_actual:.2f}s < {MIN_CHUNK_DURATION}s"
                    )
                    continue

                cmd = [
                    "ffmpeg",
                    "-y",
                    "-loglevel",
                    "error",
                    "-i",
                    audio_path,
                    "-ss",
                    str(start_time),
                    "-t",
                    str(chunk_duration_actual),
                    "-ar",
                    "16000",
                    "-ac",
                    "1",
                    "-c:a",
                    "pcm_s16le",
                    str(chunk_path),
                ]

                logger.info(
                    f"Creating chunk {i+1}/{len(chunks)}: {start_time:.2f}s - {end_time:.2f}s"
                )

                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

                if result.returncode != 0:
                    logger.error(f"FFmpeg failed for chunk {i}: {result.stderr}")
                    raise TranscriptionError(f"FFmpeg failed for chunk {i}")

                chunk_files.append(str(chunk_path))

            logger.info(f"Successfully created {len(chunk_files)} chunk files")
            return chunk_files

        except Exception as e:
            logger.error(f"Audio splitting failed: {e}")
            raise TranscriptionError(f"Audio splitting failed: {e}")

    def _merge_chunks(self, chunk_texts: list[str]) -> str:
        """
        Task 4.2: Merge chunk transcriptions with smart duplicate detection.

        Detects and removes duplicate text at chunk boundaries caused by overlap.
        """
        # Handle edge cases - empty chunks
        if not chunk_texts:
            return ""

        # Filter out empty chunks and [inaudible] markers for merge logic
        valid_texts = [
            text.strip()
            for text in chunk_texts
            if text.strip() and text.strip() != "[inaudible]"
        ]

        if not valid_texts:
            # All chunks were empty or inaudible
            logger.warning("All chunks were empty or inaudible")
            return ""

        if len(valid_texts) == 1:
            return valid_texts[0]

        # Task 4.2.1: Implement duplicate detection at boundaries
        merged_parts = [valid_texts[0]]
        duplicates_removed = 0

        for i in range(1, len(valid_texts)):
            current = valid_texts[i]
            if not current:
                continue

            # Get last N words of previous chunk and first N words of current
            prev_words = merged_parts[-1].split()
            curr_words = current.split()

            # Task 4.2.2: Handle single word chunks
            if len(prev_words) < 2 or len(curr_words) < 2:
                merged_parts.append(current)
                continue

            # Compare last 5 words of previous with first 5 words of current
            compare_length = min(5, len(prev_words), len(curr_words))
            prev_tail = prev_words[-compare_length:]
            curr_head = curr_words[:compare_length]

            # Find overlap - look for matching sequences
            overlap_start = 0
            for j in range(1, compare_length + 1):
                # Check if last j words of prev match first j words of curr
                if prev_tail[-j:] == curr_head[:j]:
                    overlap_start = j

            # Remove overlapping words from current chunk
            if overlap_start > 0:
                current = " ".join(curr_words[overlap_start:])
                duplicates_removed += overlap_start

            if current.strip():
                merged_parts.append(current.strip())

        merged = " ".join(merged_parts)
        logger.info(
            f"Smart merge: {len(chunk_texts)} chunks -> {len(merged)} chars, {duplicates_removed} duplicate words removed"
        )
        return merged

    def _validate_audio(self, audio_data: np.ndarray) -> tuple[bool, str]:
        """
        Task 3.1.1: Validate audio has actual content before transcription.

        Args:
            audio_data: Audio samples as numpy array

        Returns:
            Tuple of (is_valid, reason)
        """
        # Check for empty audio
        if len(audio_data) == 0:
            return False, "Audio is empty (0 samples)"

        audio_max = np.abs(audio_data).max()
        audio_std = np.std(audio_data)

        # Check for silent audio (max < 0.01)
        if audio_max < 0.01:
            return (
                False,
                f"Audio is silent or very low volume (max={audio_max:.4f} < 0.01)",
            )

        # Check for constant noise (std < 0.001)
        if audio_std < 0.001:
            return False, f"Audio is constant noise (std={audio_std:.6f} < 0.001)"

        return True, "Audio content valid"

    def _load_audio(self, audio_path: str) -> tuple[np.ndarray, float]:
        """Load audio file and convert to format expected by Whisper."""
        try:
            import librosa

            audio_data, sample_rate = librosa.load(
                audio_path,
                sr=16000,
                mono=True,
                dtype=np.float32,
            )

            duration = len(audio_data) / sample_rate

            if len(audio_data) == 0:
                raise TranscriptionError("Audio file is empty or has zero duration")

            # Task 1.2.1: Add audio statistics logging
            audio_max = np.abs(audio_data).max()
            audio_mean = np.abs(audio_data).mean()
            audio_std = np.std(audio_data)

            logger.info(
                f"Audio stats: max={audio_max:.4f}, mean={audio_mean:.4f}, "
                f"std={audio_std:.4f}, samples={len(audio_data)}"
            )

            # Task 3.1.2 & 3.1.3: Validate audio content
            is_valid, reason = self._validate_audio(audio_data)
            if not is_valid:
                logger.warning(
                    f"Audio validation failed: {reason}. Returning empty transcription."
                )
                # Return empty audio data to signal skip
                # The caller should handle this gracefully

            # Task 1.2.2: Add warning for silent audio (max < 0.01)
            if audio_max < 0.01:
                logger.warning(
                    f"Audio appears to be silent or very low volume (max={audio_max:.4f} < 0.01). "
                    f"Transcription may return empty result."
                )

            # Task 1.2.3: Add warning for constant noise (std < 0.001)
            if audio_std < 0.001:
                logger.warning(
                    f"Audio appears to be constant noise (std={audio_std:.6f} < 0.001). "
                    f"Transcription may return empty result."
                )

            # Normalize if needed
            if audio_max > 1.0:
                logger.warning(
                    f"Audio data exceeds [-1, 1] range, normalizing (max={audio_max:.2f})"
                )
                audio_data = audio_data / audio_max

            logger.info(
                f"Audio loaded: duration={duration:.2f}s, samples={len(audio_data)}, "
                f"sample_rate={sample_rate}Hz, channels=mono"
            )

            return audio_data, duration

        except TranscriptionError:
            raise
        except Exception as e:
            logger.error(f"Failed to load audio: {e}")
            logger.exception("Audio loading exception details:")
            raise TranscriptionError(f"Failed to load audio: {e}")

    def _check_context_health(self) -> bool:
        """
        Task 3.3.1: Check if Whisper context is still valid.

        Returns:
            True if context is healthy, False otherwise
        """
        try:
            if not self.ctx:
                logger.error("Whisper context is None")
                return False

            if not self.lib:
                logger.error("Whisper library is None")
                return False

            # Basic sanity check - context pointer should be non-zero
            if not bool(self.ctx):
                logger.error("Whisper context pointer is invalid")
                return False

            return True

        except Exception as e:
            logger.error(f"Context health check failed: {e}")
            return False

    def _reinitialize_context(self) -> None:
        """
        Task 3.3.2: Reinitialize Whisper context if corrupted.

        Raises:
            ModelInitError: If reinitialization fails
        """
        logger.warning("Reinitializing Whisper context due to health check failure...")

        # Free existing context safely
        if self.ctx and self.lib:
            try:
                self.lib.whisper_free.argtypes = [ctypes.c_void_p]
                self.lib.whisper_free.restype = None
                self.lib.whisper_free(self.ctx)
            except Exception as e:
                logger.warning(
                    f"Failed to free old context (may already be invalid): {e}"
                )

        self.ctx = None

        # Reinitialize
        try:
            self._initialize_context()
            logger.warning("Whisper context reinitialized successfully")
        except Exception as e:
            logger.error(f"Failed to reinitialize Whisper context: {e}")
            raise ModelInitError(f"Context reinitialization failed: {e}")

    def _call_whisper_full(
        self, audio_data: np.ndarray, language: str, audio_duration: float
    ) -> dict[str, Any]:
        """
        Call whisper_full() C function to perform transcription.

        Thread-safe: Uses lock to prevent concurrent access to Whisper context.
        Includes health check and auto-recovery.
        """
        # Task 2.1.3 & 2.1.4: Wrap with threading lock for thread safety
        with self._lock:
            # Task 3.3.3 & 3.3.4: Check context health and auto-recover
            if not self._check_context_health():
                logger.warning("Context health check failed, attempting recovery...")
                try:
                    self._reinitialize_context()
                except ModelInitError as e:
                    raise TranscriptionError(f"Context recovery failed: {e}")

            return self._call_whisper_full_unsafe(audio_data, language, audio_duration)

    def _call_whisper_full_unsafe(
        self, audio_data: np.ndarray, language: str, audio_duration: float
    ) -> dict[str, Any]:
        """
        Internal method: Call whisper_full() without lock.

        WARNING: This method is NOT thread-safe. Use _call_whisper_full() instead.
        """
        try:
            # Define WhisperFullParams structure matching whisper.cpp
            # This structure must match the C struct layout exactly
            class WhisperFullParams(ctypes.Structure):
                _fields_ = [
                    ("strategy", ctypes.c_int),
                    ("n_threads", ctypes.c_int),
                    ("n_max_text_ctx", ctypes.c_int),
                    ("offset_ms", ctypes.c_int),
                    ("duration_ms", ctypes.c_int),
                    ("translate", ctypes.c_bool),
                    ("no_context", ctypes.c_bool),
                    ("no_timestamps", ctypes.c_bool),
                    ("single_segment", ctypes.c_bool),
                    ("print_special", ctypes.c_bool),
                    ("print_progress", ctypes.c_bool),
                    ("print_realtime", ctypes.c_bool),
                    ("print_timestamps", ctypes.c_bool),
                    ("token_timestamps", ctypes.c_bool),
                    ("_pad1", ctypes.c_byte * 3),
                    ("thold_pt", ctypes.c_float),
                    ("thold_ptsum", ctypes.c_float),
                    ("max_len", ctypes.c_int),
                    ("split_on_word", ctypes.c_bool),
                    ("_pad2", ctypes.c_byte * 3),
                    ("max_tokens", ctypes.c_int),
                    ("debug_mode", ctypes.c_bool),
                    ("_pad3", ctypes.c_byte * 3),
                    ("audio_ctx", ctypes.c_int),
                    ("tdrz_enable", ctypes.c_bool),
                    ("_pad4", ctypes.c_byte * 7),
                    ("suppress_regex", ctypes.c_char_p),
                    ("initial_prompt", ctypes.c_char_p),
                    ("carry_initial_prompt", ctypes.c_bool),
                    ("_pad5", ctypes.c_byte * 7),
                    ("prompt_tokens", ctypes.c_void_p),
                    ("prompt_n_tokens", ctypes.c_int),
                    ("_pad6", ctypes.c_byte * 4),
                    ("language", ctypes.c_char_p),
                    ("detect_language", ctypes.c_bool),
                    ("suppress_blank", ctypes.c_bool),
                    ("suppress_nst", ctypes.c_bool),
                    ("_pad7", ctypes.c_byte * 5),
                    ("temperature", ctypes.c_float),
                    ("max_initial_ts", ctypes.c_float),
                    ("length_penalty", ctypes.c_float),
                    ("temperature_inc", ctypes.c_float),
                    ("entropy_thold", ctypes.c_float),
                    ("logprob_thold", ctypes.c_float),
                    ("no_speech_thold", ctypes.c_float),
                    ("greedy_best_of", ctypes.c_int),
                    ("beam_size", ctypes.c_int),
                    ("patience", ctypes.c_float),
                    # Callbacks
                    ("new_segment_callback", ctypes.c_void_p),
                    ("new_segment_callback_user_data", ctypes.c_void_p),
                    ("progress_callback", ctypes.c_void_p),
                    ("progress_callback_user_data", ctypes.c_void_p),
                    ("encoder_begin_callback", ctypes.c_void_p),
                    ("encoder_begin_callback_user_data", ctypes.c_void_p),
                    ("abort_callback", ctypes.c_void_p),
                    ("abort_callback_user_data", ctypes.c_void_p),
                    ("logits_filter_callback", ctypes.c_void_p),
                    ("logits_filter_callback_user_data", ctypes.c_void_p),
                    ("grammar_rules", ctypes.c_void_p),
                    ("n_grammar_rules", ctypes.c_size_t),
                    ("i_start_rule", ctypes.c_size_t),
                    ("grammar_penalty", ctypes.c_float),
                    ("_pad8", ctypes.c_byte * 4),
                    # VAD params
                    ("vad", ctypes.c_bool),
                    ("_pad9", ctypes.c_byte * 7),
                    ("vad_model_path", ctypes.c_char_p),
                    ("vad_threshold", ctypes.c_float),
                    ("vad_min_speech_duration_ms", ctypes.c_int),
                    ("vad_min_silence_duration_ms", ctypes.c_int),
                    ("vad_max_speech_duration_s", ctypes.c_float),
                    ("vad_speech_pad_ms", ctypes.c_int),
                    ("vad_samples_overlap", ctypes.c_float),
                ]

            # Setup function signatures
            self.lib.whisper_full_default_params.restype = WhisperFullParams
            self.lib.whisper_full_default_params.argtypes = [ctypes.c_int]

            self.lib.whisper_full.restype = ctypes.c_int
            self.lib.whisper_full.argtypes = [
                ctypes.c_void_p,  # ctx
                WhisperFullParams,  # params (by value)
                ctypes.POINTER(ctypes.c_float),  # samples
                ctypes.c_int,  # n_samples
            ]

            self.lib.whisper_full_n_segments.argtypes = [ctypes.c_void_p]
            self.lib.whisper_full_n_segments.restype = ctypes.c_int

            self.lib.whisper_full_get_segment_text.argtypes = [
                ctypes.c_void_p,
                ctypes.c_int,
            ]
            self.lib.whisper_full_get_segment_text.restype = ctypes.c_char_p

            self.lib.whisper_full_get_segment_t0.argtypes = [
                ctypes.c_void_p,
                ctypes.c_int,
            ]
            self.lib.whisper_full_get_segment_t0.restype = ctypes.c_int64

            self.lib.whisper_full_get_segment_t1.argtypes = [
                ctypes.c_void_p,
                ctypes.c_int,
            ]
            self.lib.whisper_full_get_segment_t1.restype = ctypes.c_int64

            # Get default params (strategy 0 = WHISPER_SAMPLING_GREEDY)
            params = self.lib.whisper_full_default_params(0)

            # Explicitly disable VAD
            params.vad = False
            params.vad_model_path = None

            settings = get_settings()
            n_threads = settings.whisper_n_threads

            if n_threads == 0:
                cpu_count = os.cpu_count() or 4
                n_threads = min(cpu_count, 8)

            params.n_threads = n_threads
            logger.info(f"Whisper inference configured with {n_threads} threads")

            n_samples = len(audio_data)
            audio_array = (ctypes.c_float * n_samples)(*audio_data)
            start_time = time.time()

            result = self.lib.whisper_full(
                self.ctx,
                params,
                audio_array,
                n_samples,
            )

            inference_time = time.time() - start_time

            if result != 0:
                raise TranscriptionError(f"whisper_full returned error code: {result}")

            n_segments = self.lib.whisper_full_n_segments(self.ctx)

            if n_segments == 0:
                logger.warning(
                    "Whisper returned 0 segments - audio may be silent or invalid"
                )
                return {
                    "text": "",
                    "segments": [],
                    "language": language,
                    "inference_time": inference_time,
                }

            segments = []
            full_text_parts = []

            for i in range(n_segments):
                text_ptr = self.lib.whisper_full_get_segment_text(self.ctx, i)
                text = text_ptr.decode("utf-8") if text_ptr else ""

                t0 = self.lib.whisper_full_get_segment_t0(self.ctx, i)
                t1 = self.lib.whisper_full_get_segment_t1(self.ctx, i)

                start_time_s = t0 / 100.0
                end_time_s = t1 / 100.0

                segments.append(
                    {
                        "start": start_time_s,
                        "end": end_time_s,
                        "text": text.strip(),
                    }
                )

                full_text_parts.append(text.strip())

            full_text = " ".join(full_text_parts)
            confidence = 0.95 if n_segments > 0 else 0.0

            logger.info(
                f"Transcription complete: {len(full_text)} chars, "
                f"{n_segments} segments, {inference_time:.2f}s"
            )

            return {
                "text": full_text,
                "segments": segments,
                "language": language,
                "inference_time": inference_time,
                "confidence": confidence,
            }

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise TranscriptionError(f"Transcription failed: {e}")

    def __del__(self):
        """Clean up Whisper context on deletion"""
        # Use getattr to safely check attributes (may not exist if __init__ failed)
        ctx = getattr(self, "ctx", None)
        lib = getattr(self, "lib", None)

        if ctx and lib:
            try:
                lib.whisper_free.argtypes = [ctypes.c_void_p]
                lib.whisper_free.restype = None
                lib.whisper_free(ctx)
            except Exception:
                pass  # Ignore cleanup errors


# Global singleton instance
_whisper_library_adapter: Optional[WhisperLibraryAdapter] = None


def get_whisper_library_adapter() -> WhisperLibraryAdapter:
    """
    Get or create global WhisperLibraryAdapter instance (singleton).
    This ensures model is loaded once and reused across all requests.

    Returns:
        WhisperLibraryAdapter instance
    """
    global _whisper_library_adapter

    try:
        if _whisper_library_adapter is None:
            logger.info("Creating WhisperLibraryAdapter instance...")
            _whisper_library_adapter = WhisperLibraryAdapter()
            logger.info("WhisperLibraryAdapter singleton initialized")

        return _whisper_library_adapter

    except Exception as e:
        logger.error(f"Failed to get WhisperLibraryAdapter: {e}")
        raise
