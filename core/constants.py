"""Constants for STT worker."""

from enum import Enum


class JobStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Language(str, Enum):
    ENGLISH = "en"
    VIETNAMESE = "vi"


# Supported audio formats
SUPPORTED_FORMATS = [
    ".mp3",
    ".wav",
    ".m4a",
    ".mp4",
    ".aac",
    ".ogg",
    ".flac",
    ".wma",
    ".webm",
    ".mkv",
    ".avi",
    ".mov",
]

# Queue names
QUEUE_HIGH_PRIORITY = "stt_jobs_high"
QUEUE_NORMAL = "stt_jobs"
QUEUE_LOW_PRIORITY = "stt_jobs_low"
QUEUE_DEAD_LETTER = "stt_jobs_dlq"

# Processing constants
MAX_CHUNK_SIZE_SECONDS = 60
MIN_CHUNK_SIZE_SECONDS = 5
DEFAULT_SAMPLE_RATE = 16000


# =============================================================================
# Audio Processing Constants
# =============================================================================

# Minimum chunk duration in seconds - chunks shorter than this will be skipped or merged
MIN_CHUNK_DURATION = 2.0

# Audio validation thresholds
AUDIO_SILENCE_THRESHOLD = 0.01  # Max amplitude below this is considered silent
AUDIO_NOISE_THRESHOLD = 0.001  # Std deviation below this is considered constant noise


# =============================================================================
# HTTP Client Constants
# =============================================================================

# Connection pool limits for production performance
HTTP_MAX_KEEPALIVE_CONNECTIONS = 10  # Keep 10 connections alive
HTTP_MAX_CONNECTIONS = 20  # Max 20 concurrent connections
HTTP_KEEPALIVE_EXPIRY = 30.0  # Keep connections alive for 30s

# Timeout configuration for audio downloads (in seconds)
HTTP_CONNECT_TIMEOUT = 10.0  # Time to establish connection
HTTP_READ_TIMEOUT = 60.0  # Time to read response (large files)
HTTP_WRITE_TIMEOUT = 10.0  # Time to write request
HTTP_POOL_TIMEOUT = 5.0  # Time to acquire connection from pool


# =============================================================================
# Whisper Model Configurations
# =============================================================================

# Model configuration for library adapter (optimized builds)
WHISPER_MODEL_CONFIGS = {
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

# Model configuration for downloader (standard models from MinIO)
WHISPER_DOWNLOAD_CONFIGS = {
    "tiny": {
        "filename": "ggml-tiny.bin",
        "minio_path": "models/ggml-tiny.bin",
        "size_mb": 75,
        "md5": None,
    },
    "base": {
        "filename": "ggml-base.bin",
        "minio_path": "models/ggml-base.bin",
        "size_mb": 142,
        "md5": None,
    },
    "small": {
        "filename": "ggml-small.bin",
        "minio_path": "models/ggml-small.bin",
        "size_mb": 466,
        "md5": None,
    },
    "medium": {
        "filename": "ggml-medium.bin",
        "minio_path": "models/ggml-medium.bin",
        "size_mb": 1500,
        "md5": None,
    },
    "large": {
        "filename": "ggml-large.bin",
        "minio_path": "models/ggml-large.bin",
        "size_mb": 2900,
        "md5": None,
    },
}


# =============================================================================
# Benchmark/Profiling Constants
# =============================================================================

# Default benchmark iterations
BENCHMARK_DEFAULT_ITERATIONS = 3

# CPU scaling test configurations
BENCHMARK_CPU_COUNTS = [1, 2, 4, 8]

# Profiling output directory
PROFILING_OUTPUT_DIR = "profiling_results"
