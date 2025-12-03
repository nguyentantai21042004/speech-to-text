"""Centralized error and log message templates for STT processing."""


class ErrorMessages:
    """Centralized error message templates."""

    # Library errors
    LIBRARY_DIR_NOT_FOUND = (
        "Library directory not found: {path}. Run artifact download script first."
    )
    LIBRARY_LOAD_FAILED = "Failed to load Whisper libraries: {error}"
    LIBRARY_LOAD_UNEXPECTED = "Unexpected error loading libraries: {error}"

    # Model errors
    MODEL_NOT_FOUND = (
        "Model file not found: {path}. Run artifact download script first."
    )
    MODEL_INIT_NULL = (
        "whisper_init_from_file() returned NULL. Model file may be corrupted: {path}"
    )
    MODEL_INIT_FAILED = "Failed to initialize Whisper context: {error}"
    MODEL_UNSUPPORTED = "Unsupported model size: {size}. Must be one of {valid_sizes}"
    MODEL_INVALID_NAME = "Invalid model name: {name}. Valid models: {valid_models}"
    MODEL_SIZE_MISMATCH = "Downloaded file size too small: {actual}MB < {expected}MB"

    # Audio errors
    AUDIO_FILE_NOT_FOUND = "Audio file not found: {path}"
    AUDIO_EMPTY = "Audio file is empty or has zero duration"
    AUDIO_SILENT = (
        "Audio appears to be silent or very low volume (max={max:.4f} < {threshold})"
    )
    AUDIO_CONSTANT_NOISE = (
        "Audio appears to be constant noise (std={std:.6f} < {threshold})"
    )
    AUDIO_SPLIT_FAILED = "Audio splitting failed: {error}"
    AUDIO_TOO_MANY_CHUNKS = "Too many chunks calculated, possible infinite loop"

    # Transcription errors
    TRANSCRIPTION_FAILED = "Transcription failed: {error}"
    CHUNK_TRANSCRIPTION_FAILED = "Chunked transcription failed: {error}"
    FFPROBE_FAILED = "ffprobe failed: {error}"
    FFPROBE_PARSE_FAILED = "Failed to parse ffprobe output: {error}"
    FFMPEG_CHUNK_FAILED = "FFmpeg failed for chunk {index}"

    # Context errors
    CONTEXT_NULL = "Whisper context is None"
    CONTEXT_LIBRARY_NULL = "Whisper library is None"
    CONTEXT_INVALID = "Whisper context pointer is invalid"
    CONTEXT_HEALTH_FAILED = "Context health check failed: {error}"
    CONTEXT_RECOVERY_FAILED = "Context recovery failed: {error}"
    CONTEXT_REINIT_FAILED = "Context reinitialization failed: {error}"

    # HTTP errors
    HTTP_DOWNLOAD_FAILED = "Failed to download file: HTTP {status_code}"
    HTTP_FILE_TOO_LARGE = "File too large: {actual}MB > {max}MB"
    HTTP_FILE_TOO_LARGE_STREAMED = "File too large (streamed): > {max}MB"

    # MinIO errors
    MINIO_MODEL_NOT_FOUND = "Model not found in MinIO bucket '{bucket}': {path}"


class LogMessages:
    """Centralized log message templates."""

    # Initialization
    INIT_ADAPTER = "Initializing WhisperLibraryAdapter with model={model}"
    INIT_ADAPTER_SUCCESS = "WhisperLibraryAdapter initialized successfully (model={model}, thread_safe=True)"
    INIT_ADAPTER_FAILED = "Failed to initialize WhisperLibraryAdapter: {error}"
    INIT_CONTEXT = "Whisper context initialized (model={model}, ram~{ram}MB)"
    INIT_HTTP_CLIENT = "Created HTTP client with connection pooling"

    # Library loading
    LIBRARIES_LOADED = "All Whisper libraries loaded successfully"

    # Audio processing
    AUDIO_DURATION = "Audio duration: {duration:.2f}s"
    AUDIO_STATS = (
        "Audio stats: max={max:.4f}, mean={mean:.4f}, std={std:.4f}, samples={samples}"
    )
    AUDIO_LOADED = (
        "Audio loaded: duration={duration:.2f}s, samples={samples}, "
        "sample_rate={sample_rate}Hz, channels=mono"
    )
    AUDIO_NORMALIZE = "Audio data exceeds [-1, 1] range, normalizing (max={max:.2f})"
    AUDIO_VALIDATION_FAILED = (
        "Audio validation failed: {reason}. Returning empty transcription."
    )

    # Chunking
    CHUNK_START = (
        "Starting chunked transcription: duration={duration:.2f}s, "
        "chunk_size={chunk_size}s, overlap={overlap}s"
    )
    CHUNK_SPLIT = "Audio split into {count} chunks"
    CHUNK_BOUNDARIES = "Calculated {count} chunk boundaries"
    CHUNK_PROCESSING = "Processing chunk {current}/{total}: {path}"
    CHUNK_RESULT = "Chunk {current}/{total} result: {chars} chars, preview='{preview}'"
    CHUNK_EMPTY = "Chunk {current}/{total} returned empty text - may contain silence or invalid audio"
    CHUNK_FAILED = "Failed to process chunk {current}/{total} (path={path}, exception_type={exc_type}): {error}"
    CHUNK_CREATING = "Creating chunk {current}/{total}: {start:.2f}s - {end:.2f}s"
    CHUNK_CREATED = "Successfully created {count} chunk files"
    CHUNK_SUMMARY = "Chunked transcription summary: total={total}, successful={success}, failed={failed}"
    CHUNK_COMPLETE = "Chunked transcription complete: {count} chunks, {chars} chars"
    CHUNK_SHORT_SKIP = "Skipping chunk {index}: duration {duration:.2f}s < {min}s"
    CHUNK_SHORT_MERGE = (
        "Final chunk too short ({duration:.2f}s < {min}s), merging with previous chunk"
    )
    CHUNK_MERGED = "Merged final chunk, now {count} chunks"
    CHUNK_NO_ADVANCE = (
        "Chunk calculation would not advance (start={start}, next={next}), breaking"
    )

    # Merge
    MERGE_RESULT = "Smart merge: {chunks} chunks -> {chars} chars, {duplicates} duplicate words removed"
    MERGE_ALL_EMPTY = "All chunks were empty or inaudible"

    # Transcription
    TRANSCRIBE_CHUNKED = "Using chunked transcription (duration > {threshold}s)"
    TRANSCRIBE_DIRECT = "Using direct transcription (fast path)"

    # Context health
    CONTEXT_HEALTH_FAILED = "Context health check failed, attempting recovery..."
    CONTEXT_REINIT = "Reinitializing Whisper context due to health check failure..."
    CONTEXT_REINIT_SUCCESS = "Whisper context reinitialized successfully"
    CONTEXT_FREE_FAILED = "Failed to free old context (may already be invalid): {error}"

    # Model download
    MODEL_ENSURING = "Ensuring model exists: {model}"
    MODEL_EXISTS = "Model already exists and is valid: {path}"
    MODEL_DOWNLOADING = "Model not found or invalid, downloading from MinIO..."
    MODEL_READY = "Model ready: {path}"
    MODEL_DOWNLOAD_START = "Downloading model '{model}' from MinIO: {path}"
    MODEL_DOWNLOAD_SIZE = "Expected size: {size}MB"
    MODEL_DOWNLOAD_TO = "Downloading from bucket '{bucket}' to: {path}"
    MODEL_DOWNLOAD_COMPLETE = "Download complete: {size:.2f}MB"
    MODEL_DOWNLOAD_VALIDATED = "Model downloaded and validated: {model}"
    MODEL_SIZE_MISMATCH = "Model file size mismatch: {actual:.2f}MB < {expected}MB"
    MODEL_MD5_MISMATCH = "Model MD5 mismatch: {actual} != {expected}"

    # HTTP download
    HTTP_DOWNLOADING = "Downloading audio from: {url}"
    HTTP_DOWNLOADED = "Downloaded {size:.2f}MB to {destination}"
