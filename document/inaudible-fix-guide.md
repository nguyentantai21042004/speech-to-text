# Troubleshooting Guide: [inaudible] Chunks Issue

## Overview

This guide documents the fixes implemented to resolve the `[inaudible]` chunks issue in the transcription service, where long audio files would return `"[inaudible] [inaudible] [inaudible]..."` instead of actual transcription text.

## Root Cause

The issue was caused by multiple factors:
1. **Exception swallowing**: Chunk processing errors were logged but exceptions weren't captured with full tracebacks
2. **Thread safety**: Concurrent API requests could cause race conditions in the singleton Whisper context
3. **Silent audio handling**: Silent or invalid audio chunks would fail silently
4. **Chunk boundary issues**: Overlapping text at chunk boundaries caused duplicate words

## Configuration Options

### Chunking Settings (`.env` or environment variables)

| Variable | Default | Description |
|----------|---------|-------------|
| `WHISPER_CHUNK_ENABLED` | `true` | Enable chunked transcription for long audio |
| `WHISPER_CHUNK_DURATION` | `30` | Chunk duration in seconds |
| `WHISPER_CHUNK_OVERLAP` | `3` | Overlap between chunks in seconds (must be < duration/2) |

### Validation Rules

- `WHISPER_CHUNK_OVERLAP` must be less than half of `WHISPER_CHUNK_DURATION`
- Minimum chunk duration is 2 seconds (shorter chunks are merged with previous)

## Log Patterns for Debugging

### Audio Statistics (every transcription)
```
Audio stats: max=0.4523, mean=0.0234, std=0.1234, samples=480000
```

### Chunk Processing
```
Processing chunk 1/6: /tmp/audio_chunk_0.wav
Chunk 1/6 result: 245 chars, preview='Xin chào các bạn hôm nay...'
```

### Warnings

**Silent Audio:**
```
Audio appears to be silent or very low volume (max=0.0023 < 0.01). Transcription may return empty result.
```

**Constant Noise:**
```
Audio appears to be constant noise (std=0.0005 < 0.001). Transcription may return empty result.
```

**Empty Chunk Result:**
```
Chunk 2/6 returned empty text - may contain silence or invalid audio
```

### Chunk Summary
```
Chunked transcription summary: total=6, successful=5, failed=1
```

### Smart Merge
```
Smart merge: 6 chunks -> 1234 chars, 12 duplicate words removed
```

### Context Recovery
```
Context health check failed, attempting recovery...
Reinitializing Whisper context due to health check failure...
Whisper context reinitialized successfully
```

## Troubleshooting Steps

### 1. Check for Silent Audio
If you see many empty chunk results:
- Check audio file quality with `ffprobe`
- Verify audio has actual speech content
- Check audio levels (max amplitude should be > 0.01)

### 2. Check for Thread Safety Issues
If you see random failures under load:
- Verify `_lock` is being used (check logs for `lock_acquired=True`)
- Check for concurrent request patterns in logs

### 3. Check for Context Corruption
If you see context health check failures:
- Check memory usage on the server
- Look for "Context health check failed" in logs
- Verify model file integrity

### 4. Check Chunk Boundaries
If transcription has duplicate words:
- Increase `WHISPER_CHUNK_OVERLAP` (default: 3s)
- Check smart merge logs for duplicate word removal

## Performance Benchmarks

| Audio Duration | Processing Time | Realtime Factor |
|----------------|-----------------|-----------------|
| 30s | ~9s | 3.2x |
| 178s | ~95s | 1.9x |

## Files Modified

- `infrastructure/whisper/library_adapter.py` - Main transcription logic
- `core/config.py` - Configuration with validation
- `internal/api/routes/transcribe_routes.py` - API endpoints

## Test Files

- `tests/test_inaudible_fix.py` - Comprehensive unit tests
- `scripts/test_phase_features.py` - Feature verification tests
- `scripts/test_container_api.py` - Container API tests
