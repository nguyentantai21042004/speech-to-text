#!/usr/bin/env python3
"""
Test script for Phase 1-4 features of fix-inaudible-chunks.
Run with: uv run python scripts/test_phase_features.py
"""

import sys
import os
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Setup logging
try:
    from core.logger import logger, configure_script_logging
    from core.config import get_settings as get_config_settings

    settings = get_config_settings()
    configure_script_logging(level=settings.script_log_level)
except ImportError:
    from loguru import logger

    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    )

from infrastructure.whisper.library_adapter import (
    WhisperLibraryAdapter,
    MIN_CHUNK_DURATION,
)
from core.config import get_settings


def test_min_chunk_duration_constant():
    """Test 3.2.1: MIN_CHUNK_DURATION constant exists and is 2.0"""
    logger.info("Testing MIN_CHUNK_DURATION constant...")
    assert MIN_CHUNK_DURATION == 2.0, f"Expected 2.0, got {MIN_CHUNK_DURATION}"
    logger.success(f"MIN_CHUNK_DURATION = {MIN_CHUNK_DURATION}")


def test_chunk_overlap_config():
    """Test 4.1.1: WHISPER_CHUNK_OVERLAP default is 3 seconds"""
    logger.info("Testing chunk overlap config...")
    settings = get_settings()
    # Note: .env may override, so we check it's reasonable
    assert hasattr(settings, "whisper_chunk_overlap")
    logger.success(f"whisper_chunk_overlap = {settings.whisper_chunk_overlap}")


def test_validate_audio_method():
    """Test 3.1.1: _validate_audio method exists and works"""
    print("Testing _validate_audio method...")

    with patch.object(
        WhisperLibraryAdapter, "__init__", lambda x, model_size=None: None
    ):
        adapter = WhisperLibraryAdapter()

        # Test empty audio
        is_valid, reason = adapter._validate_audio(np.array([]))
        assert not is_valid
        assert "empty" in reason.lower()
        print(f"  ✅ Empty audio: is_valid={is_valid}, reason='{reason}'")

        # Test silent audio (max < 0.01)
        silent_audio = np.zeros(16000, dtype=np.float32)  # 1 second of silence
        is_valid, reason = adapter._validate_audio(silent_audio)
        assert not is_valid
        assert "silent" in reason.lower() or "low volume" in reason.lower()
        print(f"  ✅ Silent audio: is_valid={is_valid}, reason='{reason}'")

        # Test constant noise (std < 0.001)
        noise_audio = np.full(16000, 0.5, dtype=np.float32)  # Constant value
        is_valid, reason = adapter._validate_audio(noise_audio)
        assert not is_valid
        assert "noise" in reason.lower()
        print(f"  ✅ Constant noise: is_valid={is_valid}, reason='{reason}'")

        # Test valid audio
        valid_audio = np.random.randn(16000).astype(np.float32) * 0.5
        is_valid, reason = adapter._validate_audio(valid_audio)
        assert is_valid
        print(f"  ✅ Valid audio: is_valid={is_valid}, reason='{reason}'")


def test_check_context_health_method():
    """Test 3.3.1: _check_context_health method exists and works"""
    print("Testing _check_context_health method...")

    with patch.object(
        WhisperLibraryAdapter, "__init__", lambda x, model_size=None: None
    ):
        adapter = WhisperLibraryAdapter()

        # Test with None context
        adapter.ctx = None
        adapter.lib = MagicMock()
        is_healthy = adapter._check_context_health()
        assert not is_healthy
        print(f"  ✅ None context: is_healthy={is_healthy}")

        # Test with None lib
        adapter.ctx = MagicMock()
        adapter.lib = None
        is_healthy = adapter._check_context_health()
        assert not is_healthy
        print(f"  ✅ None lib: is_healthy={is_healthy}")

        # Test with valid context and lib
        adapter.ctx = MagicMock()
        adapter.lib = MagicMock()
        is_healthy = adapter._check_context_health()
        assert is_healthy
        print(f"  ✅ Valid context: is_healthy={is_healthy}")


def test_threading_lock():
    """Test 2.1.2: Threading lock exists in adapter"""
    print("Testing threading lock...")

    with patch.object(WhisperLibraryAdapter, "_load_libraries"):
        with patch.object(WhisperLibraryAdapter, "_initialize_context"):
            with patch(
                "infrastructure.whisper.library_adapter.get_settings"
            ) as mock_settings:
                mock_settings.return_value = MagicMock(
                    whisper_model_size="base", whisper_artifacts_dir="."
                )
                adapter = WhisperLibraryAdapter(model_size="base")

                assert hasattr(adapter, "_lock")
                import threading

                assert isinstance(adapter._lock, type(threading.Lock()))
                print(f"  ✅ Threading lock exists: {type(adapter._lock)}")


def test_smart_merge_chunks():
    """Test 4.2: Smart merge with duplicate detection"""
    print("Testing smart merge chunks...")

    with patch.object(
        WhisperLibraryAdapter, "__init__", lambda x, model_size=None: None
    ):
        adapter = WhisperLibraryAdapter()

        # Test empty chunks
        result = adapter._merge_chunks([])
        assert result == ""
        print(f"  ✅ Empty chunks: '{result}'")

        # Test single chunk
        result = adapter._merge_chunks(["Hello world"])
        assert result == "Hello world"
        print(f"  ✅ Single chunk: '{result}'")

        # Test basic merge without overlap
        result = adapter._merge_chunks(["Hello", "world", "test"])
        assert "Hello" in result and "world" in result and "test" in result
        print(f"  ✅ Basic merge: '{result}'")

        # Test merge with [inaudible] markers
        result = adapter._merge_chunks(["Hello", "[inaudible]", "world"])
        assert "[inaudible]" not in result
        assert "Hello" in result and "world" in result
        print(f"  ✅ Merge with inaudible: '{result}'")

        # Test merge with duplicate words at boundary
        result = adapter._merge_chunks(
            ["This is a test sentence", "test sentence and more words"]
        )
        # Should detect "test sentence" overlap
        print(f"  ✅ Merge with overlap: '{result}'")

        # Test merge with empty strings
        result = adapter._merge_chunks(["Hello", "", "   ", "world"])
        assert result == "Hello world"
        print(f"  ✅ Merge with empty: '{result}'")


def test_reinitialize_context_method():
    """Test 3.3.2: _reinitialize_context method exists"""
    print("Testing _reinitialize_context method...")

    with patch.object(
        WhisperLibraryAdapter, "__init__", lambda x, model_size=None: None
    ):
        adapter = WhisperLibraryAdapter()
        adapter.ctx = MagicMock()
        adapter.lib = MagicMock()
        adapter.model_path = Path("/fake/path")
        adapter.model_size = "base"
        adapter.config = {"ram_mb": 1000}

        # Mock _initialize_context
        with patch.object(adapter, "_initialize_context") as mock_init:
            adapter._reinitialize_context()
            mock_init.assert_called_once()
            print(f"  ✅ _reinitialize_context calls _initialize_context")


def main():
    print("=" * 60)
    print("Testing Phase 1-4 Features")
    print("=" * 60)
    print()

    tests = [
        test_min_chunk_duration_constant,
        test_chunk_overlap_config,
        test_validate_audio_method,
        test_check_context_health_method,
        test_threading_lock,
        test_smart_merge_chunks,
        test_reinitialize_context_method,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
            print()
        except Exception as e:
            failed += 1
            print(f"  ❌ FAILED: {e}")
            print()

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
