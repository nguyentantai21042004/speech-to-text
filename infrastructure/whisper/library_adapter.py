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
from core.errors import TranscriptionError
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

    except Exception as capture_error:
        logger.debug(f"Failed to capture native logs ({source}): {capture_error}")
        yield


class WhisperLibraryError(Exception):
    """Base exception for Whisper library errors"""
    pass


class LibraryLoadError(WhisperLibraryError):
    """Failed to load .so files"""
    pass


class ModelInitError(WhisperLibraryError):
    """Failed to initialize Whisper context"""
    pass


# Model configuration mapping
MODEL_CONFIGS = {
    "base": {
        "dir": "whisper_base_xeon",
        "model": "ggml-base-q5_1.bin",
        "size_mb": 60,
        "ram_mb": 1000,
    },
    "small": {
        "dir": "whisper_small_xeon",
        "model": "ggml-small-q5_1.bin",
        "size_mb": 181,
        "ram_mb": 500,
    },
    "medium": {
        "dir": "whisper_medium_xeon",
        "model": "ggml-medium-q5_1.bin",
        "size_mb": 1500,
        "ram_mb": 2000,
    },
}


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

        try:
            self._load_libraries()
            self._initialize_context()
            logger.info(
                f"WhisperLibraryAdapter initialized successfully (model={self.model_size})"
            )
        except Exception as e:
            logger.error(f"Failed to initialize WhisperLibraryAdapter: {e}")
            raise

    def _load_libraries(self) -> None:
        """Load Whisper shared libraries in correct dependency order."""
        try:
            logger.debug(f"Loading libraries from: {self.lib_dir}")

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
            logger.debug(f"Set LD_LIBRARY_PATH={new_ld_path}")

            # Load dependencies in correct order
            logger.debug("Loading libggml-base.so.0...")
            ctypes.CDLL(str(self.lib_dir / "libggml-base.so.0"), mode=ctypes.RTLD_GLOBAL)

            logger.debug("Loading libggml-cpu.so.0...")
            ctypes.CDLL(str(self.lib_dir / "libggml-cpu.so.0"), mode=ctypes.RTLD_GLOBAL)

            logger.debug("Loading libggml.so.0...")
            ctypes.CDLL(str(self.lib_dir / "libggml.so.0"), mode=ctypes.RTLD_GLOBAL)

            logger.debug("Loading libwhisper.so...")
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
            logger.debug(f"Initializing Whisper context from: {self.model_path}")

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
            logger.debug(f"Transcribing: {audio_path} (language={language})")

            if not os.path.exists(audio_path):
                raise TranscriptionError(f"Audio file not found: {audio_path}")

            settings = get_settings()
            duration = self.get_audio_duration(audio_path)
            logger.info(f"Audio duration: {duration:.2f}s")

            if settings.whisper_chunk_enabled and duration > settings.whisper_chunk_duration:
                logger.info(f"Using chunked transcription (duration > {settings.whisper_chunk_duration}s)")
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
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                audio_path
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)

            duration = float(data["format"]["duration"])
            logger.debug(f"Detected audio duration: {duration:.2f}s")

            return duration

        except subprocess.CalledProcessError as e:
            raise TranscriptionError(f"ffprobe failed: {e.stderr}")
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
        logger.debug(f"Transcription successful: {len(result['text'])} chars")
        return result["text"]

    def _transcribe_chunked(self, audio_path: str, language: str, duration: float) -> str:
        """Chunked transcription for long audio files."""
        settings = get_settings()
        chunk_duration = settings.whisper_chunk_duration
        chunk_overlap = settings.whisper_chunk_overlap

        logger.info(f"Starting chunked transcription: duration={duration:.2f}s, chunk_size={chunk_duration}s, overlap={chunk_overlap}s")

        try:
            chunk_files = self._split_audio(audio_path, duration, chunk_duration, chunk_overlap)
            logger.info(f"Audio split into {len(chunk_files)} chunks")

            chunk_texts = []
            for i, chunk_path in enumerate(chunk_files):
                try:
                    logger.info(f"Processing chunk {i+1}/{len(chunk_files)}")
                    chunk_text = self._transcribe_direct(chunk_path, language)
                    chunk_texts.append(chunk_text)
                    logger.debug(f"Chunk {i+1}/{len(chunk_files)} completed: {len(chunk_text)} chars")

                except Exception as e:
                    logger.error(f"Failed to process chunk {i+1}/{len(chunk_files)}: {e}")
                    chunk_texts.append("[inaudible]")

                finally:
                    try:
                        if os.path.exists(chunk_path):
                            os.remove(chunk_path)
                            logger.debug(f"Cleaned up chunk file: {chunk_path}")
                    except Exception as e:
                        logger.warning(f"Failed to cleanup chunk file: {e}")

            merged_text = self._merge_chunks(chunk_texts)
            logger.info(f"Chunked transcription complete: {len(chunk_texts)} chunks, {len(merged_text)} chars")

            return merged_text

        except Exception as e:
            logger.error(f"Chunked transcription failed: {e}")
            raise TranscriptionError(f"Chunked transcription failed: {e}")

    def _split_audio(self, audio_path: str, duration: float, chunk_duration: int, overlap: int) -> list[str]:
        """Split audio into chunks using FFmpeg."""
        try:
            logger.debug(f"Starting audio split: duration={duration}, chunk_duration={chunk_duration}, overlap={overlap}")

            chunks = []
            start = 0.0

            while start < duration:
                end = min(start + chunk_duration, duration)
                chunks.append((start, end))

                if end >= duration:
                    break

                next_start = end - overlap

                if next_start <= start:
                    logger.warning(f"Chunk calculation would not advance (start={start}, next={next_start}), breaking")
                    break

                start = next_start

                if len(chunks) > 1000:
                    raise TranscriptionError("Too many chunks calculated, possible infinite loop")

            logger.info(f"Calculated {len(chunks)} chunk boundaries")

            chunk_files = []
            base_path = Path(audio_path).parent
            base_name = Path(audio_path).stem

            for i, (start_time, end_time) in enumerate(chunks):
                chunk_path = base_path / f"{base_name}_chunk_{i}.wav"
                chunk_duration_actual = end_time - start_time

                cmd = [
                    "ffmpeg",
                    "-y",
                    "-loglevel", "error",
                    "-i", audio_path,
                    "-ss", str(start_time),
                    "-t", str(chunk_duration_actual),
                    "-ar", "16000",
                    "-ac", "1",
                    "-c:a", "pcm_s16le",
                    str(chunk_path)
                ]

                logger.info(f"Creating chunk {i+1}/{len(chunks)}: {start_time:.2f}s - {end_time:.2f}s")

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
        """Merge chunk transcriptions into final text."""
        merged = " ".join(text.strip() for text in chunk_texts if text.strip())
        logger.debug(f"Merged {len(chunk_texts)} chunks into {len(merged)} chars")
        return merged

    def _load_audio(self, audio_path: str) -> tuple[np.ndarray, float]:
        """Load audio file and convert to format expected by Whisper."""
        try:
            import librosa
            
            logger.debug(f"Loading audio file: {audio_path}")
            
            audio_data, sample_rate = librosa.load(
                audio_path,
                sr=16000,
                mono=True,
                dtype=np.float32,
            )
            
            duration = len(audio_data) / sample_rate
            
            if len(audio_data) == 0:
                raise TranscriptionError("Audio file is empty or has zero duration")
            
            max_val = np.abs(audio_data).max()
            if max_val > 1.0:
                logger.warning(f"Audio data exceeds [-1, 1] range, normalizing (max={max_val:.2f})")
                audio_data = audio_data / max_val
            
            logger.info(
                f"Audio loaded: duration={duration:.2f}s, samples={len(audio_data)}, "
                f"sample_rate={sample_rate}Hz, channels=mono"
            )
            
            return audio_data, duration

        except Exception as e:
            logger.error(f"Failed to load audio: {e}")
            raise TranscriptionError(f"Failed to load audio: {e}")

    def _call_whisper_full(
        self, audio_data: np.ndarray, language: str, audio_duration: float
    ) -> dict[str, Any]:
        """Call whisper_full() C function to perform transcription."""
        try:
            logger.debug(f"Starting Whisper inference (language={language})")
            
            class WhisperFullParamsPartial(ctypes.Structure):
                _fields_ = [
                    ("strategy", ctypes.c_int),
                    ("n_threads", ctypes.c_int),
                    ("n_max_text_ctx", ctypes.c_int),
                    ("offset_ms", ctypes.c_int),
                    ("duration_ms", ctypes.c_int),
                ]
            
            self.lib.whisper_full_default_params_by_ref.argtypes = [ctypes.c_int]
            self.lib.whisper_full_default_params_by_ref.restype = ctypes.POINTER(WhisperFullParamsPartial)
            
            self.lib.whisper_full.argtypes = [
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_float),
                ctypes.c_int,
            ]
            self.lib.whisper_full.restype = ctypes.c_int
            
            self.lib.whisper_free_params.argtypes = [ctypes.c_void_p]
            self.lib.whisper_free_params.restype = None
            
            self.lib.whisper_full_n_segments.argtypes = [ctypes.c_void_p]
            self.lib.whisper_full_n_segments.restype = ctypes.c_int
            
            self.lib.whisper_full_get_segment_text.argtypes = [ctypes.c_void_p, ctypes.c_int]
            self.lib.whisper_full_get_segment_text.restype = ctypes.c_char_p
            
            self.lib.whisper_full_get_segment_t0.argtypes = [ctypes.c_void_p, ctypes.c_int]
            self.lib.whisper_full_get_segment_t0.restype = ctypes.c_int64
            
            self.lib.whisper_full_get_segment_t1.argtypes = [ctypes.c_void_p, ctypes.c_int]
            self.lib.whisper_full_get_segment_t1.restype = ctypes.c_int64
            
            params_ptr = self.lib.whisper_full_default_params_by_ref(0)
            if not params_ptr:
                raise TranscriptionError("Failed to get default whisper params")
            
            settings = get_settings()
            n_threads = settings.whisper_n_threads
            
            if n_threads == 0:
                cpu_count = os.cpu_count() or 4
                n_threads = min(cpu_count, 8)
                logger.debug(f"Auto-detected {cpu_count} CPUs, using {n_threads} threads")
            else:
                logger.debug(f"Using configured WHISPER_N_THREADS={n_threads}")
            
            params_ptr.contents.n_threads = n_threads
            logger.info(f"Whisper inference configured with {n_threads} threads")
            
            n_samples = len(audio_data)
            audio_array = (ctypes.c_float * n_samples)(*audio_data)
            
            logger.debug(f"Calling whisper_full with {n_samples} samples (language={language})")
            start_time = time.time()
            
            try:
                result = self.lib.whisper_full(
                    self.ctx,
                    params_ptr,
                    audio_array,
                    n_samples,
                )
            finally:
                self.lib.whisper_free_params(params_ptr)
            
            inference_time = time.time() - start_time
            
            if result != 0:
                raise TranscriptionError(f"whisper_full returned error code: {result}")
            
            n_segments = self.lib.whisper_full_n_segments(self.ctx)
            logger.debug(f"Whisper inference completed: {n_segments} segments in {inference_time:.2f}s")
            
            if n_segments == 0:
                logger.warning("Whisper returned 0 segments - audio may be silent or invalid")
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
                
                segments.append({
                    "start": start_time_s,
                    "end": end_time_s,
                    "text": text.strip(),
                })
                
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
        if self.ctx and self.lib:
            try:
                logger.debug("Freeing Whisper context...")
                self.lib.whisper_free.argtypes = [ctypes.c_void_p]
                self.lib.whisper_free.restype = None
                self.lib.whisper_free(self.ctx)
                logger.debug("Whisper context freed")
            except Exception as e:
                logger.error(f"Error freeing Whisper context: {e}")


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
