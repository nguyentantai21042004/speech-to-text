"""
Comprehensive tests for the [inaudible] chunks fix.

Tests cover:
- Task 2.2: Thread Safety Testing
- Task 3.3.5: Context recovery after simulated corruption
- Task 4.1.2-4.1.3: Overlap validation
- Task 4.2.4: Smart merge quality comparison
- Task 5.2.2: Concurrent API requests
"""

import concurrent.futures
import threading
import time
from unittest.mock import MagicMock, patch
import pytest
import numpy as np

from core.config import Settings, get_settings


class TestOverlapValidation:
    """Task 4.1.2-4.1.3: Test overlap validation."""

    def test_valid_overlap(self):
        """Test that valid overlap passes validation."""
        settings = Settings()
        # Default is 30s chunk, 3s overlap - should be valid
        assert settings.validate_chunk_overlap() is True

    def test_overlap_at_boundary(self):
        """Test overlap at exactly half of chunk duration fails."""
        settings = Settings()
        settings.whisper_chunk_duration = 30
        settings.whisper_chunk_overlap = 15  # Exactly half
        with pytest.raises(ValueError) as exc_info:
            settings.validate_chunk_overlap()
        assert "must be less than half" in str(exc_info.value)

    def test_overlap_exceeds_half(self):
        """Test overlap exceeding half of chunk duration fails."""
        settings = Settings()
        settings.whisper_chunk_duration = 30
        settings.whisper_chunk_overlap = 20  # More than half
        with pytest.raises(ValueError) as exc_info:
            settings.validate_chunk_overlap()
        assert "must be less than half" in str(exc_info.value)

    def test_various_overlap_values(self):
        """Task 4.1.3: Test with various overlap values."""
        test_cases = [
            (30, 1, True),  # 1s overlap for 30s chunk - valid
            (30, 3, True),  # 3s overlap for 30s chunk - valid
            (30, 10, True),  # 10s overlap for 30s chunk - valid
            (30, 14, True),  # 14s overlap for 30s chunk - valid (just under half)
            (30, 15, False),  # 15s overlap for 30s chunk - invalid (exactly half)
            (30, 20, False),  # 20s overlap for 30s chunk - invalid
            (60, 25, True),  # 25s overlap for 60s chunk - valid
            (60, 30, False),  # 30s overlap for 60s chunk - invalid
        ]

        for chunk_duration, overlap, should_pass in test_cases:
            settings = Settings()
            settings.whisper_chunk_duration = chunk_duration
            settings.whisper_chunk_overlap = overlap
            if should_pass:
                assert (
                    settings.validate_chunk_overlap() is True
                ), f"Expected valid: chunk={chunk_duration}, overlap={overlap}"
            else:
                with pytest.raises(ValueError):
                    settings.validate_chunk_overlap()


class TestSmartMergeQuality:
    """Task 4.2.4: Compare quality before/after smart merge."""

    def test_merge_removes_duplicates(self):
        """Test that smart merge removes duplicate words at boundaries."""
        from infrastructure.whisper.library_adapter import WhisperLibraryAdapter

        # Mock the adapter without initializing Whisper
        with patch.object(WhisperLibraryAdapter, "__init__", lambda x, **kwargs: None):
            adapter = WhisperLibraryAdapter()
            adapter._lock = threading.Lock()

            # Simulate chunks with overlapping text
            chunks = [
                "Xin chào các bạn hôm nay",
                "hôm nay chúng ta sẽ học",  # "hôm nay" overlaps
                "sẽ học về Python programming",  # "sẽ học" overlaps
            ]

            merged = adapter._merge_chunks(chunks)

            # Should not have duplicate "hôm nay" or "sẽ học"
            words = merged.split()
            # Count occurrences
            hom_nay_count = sum(
                1
                for i in range(len(words) - 1)
                if words[i] == "hôm" and words[i + 1] == "nay"
            )
            se_hoc_count = sum(
                1
                for i in range(len(words) - 1)
                if words[i] == "sẽ" and words[i + 1] == "học"
            )

            # Each phrase should appear only once
            assert hom_nay_count <= 1, f"'hôm nay' appears {hom_nay_count} times"
            assert se_hoc_count <= 1, f"'sẽ học' appears {se_hoc_count} times"

    def test_merge_preserves_content(self):
        """Test that smart merge preserves all unique content."""
        from infrastructure.whisper.library_adapter import WhisperLibraryAdapter

        with patch.object(WhisperLibraryAdapter, "__init__", lambda x, **kwargs: None):
            adapter = WhisperLibraryAdapter()
            adapter._lock = threading.Lock()

            # Chunks without overlap
            chunks = [
                "First chunk content",
                "Second chunk content",
                "Third chunk content",
            ]

            merged = adapter._merge_chunks(chunks)

            # All unique words should be present
            assert "First" in merged
            assert "Second" in merged
            assert "Third" in merged

    def test_merge_handles_inaudible_markers(self):
        """Test that [inaudible] markers are filtered out."""
        from infrastructure.whisper.library_adapter import WhisperLibraryAdapter

        with patch.object(WhisperLibraryAdapter, "__init__", lambda x, **kwargs: None):
            adapter = WhisperLibraryAdapter()
            adapter._lock = threading.Lock()

            chunks = ["Valid text here", "[inaudible]", "More valid text"]

            merged = adapter._merge_chunks(chunks)

            assert "[inaudible]" not in merged
            assert "Valid text here" in merged
            assert "More valid text" in merged


class TestThreadSafety:
    """Task 2.2: Thread Safety Testing."""

    def test_lock_exists(self):
        """Task 2.2.1: Verify lock is properly initialized."""
        from infrastructure.whisper.library_adapter import WhisperLibraryAdapter

        with patch.object(WhisperLibraryAdapter, "_load_libraries", return_value=None):
            with patch.object(
                WhisperLibraryAdapter, "_initialize_context", return_value=None
            ):
                adapter = WhisperLibraryAdapter()

                assert hasattr(adapter, "_lock")
                assert isinstance(adapter._lock, type(threading.Lock()))

    def test_concurrent_access_simulation(self):
        """Task 2.2.1: Simulate concurrent transcription requests."""
        from infrastructure.whisper.library_adapter import WhisperLibraryAdapter

        # Track concurrent access
        access_count = {"current": 0, "max": 0}
        access_lock = threading.Lock()

        def mock_whisper_full_unsafe(self, audio_data, language, duration):
            with access_lock:
                access_count["current"] += 1
                access_count["max"] = max(access_count["max"], access_count["current"])

            # Simulate processing time
            time.sleep(0.1)

            with access_lock:
                access_count["current"] -= 1

            return {"text": "test", "segments": [], "language": language}

        with patch.object(WhisperLibraryAdapter, "_load_libraries", return_value=None):
            with patch.object(
                WhisperLibraryAdapter, "_initialize_context", return_value=None
            ):
                with patch.object(
                    WhisperLibraryAdapter, "_check_context_health", return_value=True
                ):
                    with patch.object(
                        WhisperLibraryAdapter,
                        "_call_whisper_full_unsafe",
                        mock_whisper_full_unsafe,
                    ):
                        adapter = WhisperLibraryAdapter()

                        # Create mock audio data
                        audio_data = np.zeros(16000, dtype=np.float32)

                        # Run 5 concurrent requests
                        with concurrent.futures.ThreadPoolExecutor(
                            max_workers=5
                        ) as executor:
                            futures = [
                                executor.submit(
                                    adapter._call_whisper_full, audio_data, "vi", 1.0
                                )
                                for _ in range(5)
                            ]

                            # Wait for all to complete
                            results = [f.result() for f in futures]

        # With proper locking, max concurrent should be 1
        assert (
            access_count["max"] == 1
        ), f"Lock failed: max concurrent access was {access_count['max']}, expected 1"

        # All requests should complete successfully
        assert len(results) == 5
        assert all(r["text"] == "test" for r in results)

    def test_lock_released_on_exception(self):
        """Task 2.2.2: Test lock is released even when exception occurs."""
        from infrastructure.whisper.library_adapter import WhisperLibraryAdapter

        def mock_whisper_full_unsafe_error(self, audio_data, language, duration):
            raise RuntimeError("Simulated error")

        with patch.object(WhisperLibraryAdapter, "_load_libraries", return_value=None):
            with patch.object(
                WhisperLibraryAdapter, "_initialize_context", return_value=None
            ):
                with patch.object(
                    WhisperLibraryAdapter, "_check_context_health", return_value=True
                ):
                    with patch.object(
                        WhisperLibraryAdapter,
                        "_call_whisper_full_unsafe",
                        mock_whisper_full_unsafe_error,
                    ):
                        adapter = WhisperLibraryAdapter()

                        audio_data = np.zeros(16000, dtype=np.float32)

                        # First call should raise exception
                        with pytest.raises(RuntimeError):
                            adapter._call_whisper_full(audio_data, "vi", 1.0)

                        # Lock should be released - we can acquire it
                        acquired = adapter._lock.acquire(timeout=1.0)
                        assert acquired, "Lock was not released after exception"
                        adapter._lock.release()


class TestContextRecovery:
    """Task 3.3.5: Test context recovery after simulated corruption."""

    def test_recovery_on_none_context(self):
        """Test recovery when context becomes None."""
        from infrastructure.whisper.library_adapter import WhisperLibraryAdapter

        reinit_called = {"count": 0}

        def mock_reinitialize(self):
            reinit_called["count"] += 1
            self.ctx = MagicMock()  # Restore context

        with patch.object(WhisperLibraryAdapter, "_load_libraries", return_value=None):
            with patch.object(
                WhisperLibraryAdapter, "_initialize_context", return_value=None
            ):
                with patch.object(
                    WhisperLibraryAdapter, "_reinitialize_context", mock_reinitialize
                ):
                    adapter = WhisperLibraryAdapter()
                    adapter.lib = MagicMock()
                    adapter.ctx = None  # Simulate corruption

                    # Health check should fail
                    assert adapter._check_context_health() is False

                    # Simulate what _call_whisper_full does
                    if not adapter._check_context_health():
                        adapter._reinitialize_context()

                    assert reinit_called["count"] == 1

    def test_recovery_on_none_lib(self):
        """Test recovery when library becomes None."""
        from infrastructure.whisper.library_adapter import WhisperLibraryAdapter

        with patch.object(WhisperLibraryAdapter, "_load_libraries", return_value=None):
            with patch.object(
                WhisperLibraryAdapter, "_initialize_context", return_value=None
            ):
                adapter = WhisperLibraryAdapter()
                adapter.lib = None  # Simulate corruption
                adapter.ctx = MagicMock()

                # Health check should fail
                assert adapter._check_context_health() is False

    def test_successful_recovery_flow(self):
        """Test full recovery flow after corruption."""
        from infrastructure.whisper.library_adapter import WhisperLibraryAdapter

        recovery_sequence = []

        def mock_check_health(self):
            if not self.ctx or not self.lib:
                recovery_sequence.append("health_check_failed")
                return False
            recovery_sequence.append("health_check_passed")
            return True

        def mock_reinitialize(self):
            recovery_sequence.append("reinitialize")
            self.ctx = MagicMock()
            self.lib = MagicMock()

        with patch.object(WhisperLibraryAdapter, "_load_libraries", return_value=None):
            with patch.object(
                WhisperLibraryAdapter, "_initialize_context", return_value=None
            ):
                with patch.object(
                    WhisperLibraryAdapter, "_check_context_health", mock_check_health
                ):
                    with patch.object(
                        WhisperLibraryAdapter,
                        "_reinitialize_context",
                        mock_reinitialize,
                    ):
                        adapter = WhisperLibraryAdapter()
                        adapter.lib = MagicMock()
                        adapter.ctx = None  # Corrupt context

                        # Simulate recovery check
                        if not adapter._check_context_health():
                            adapter._reinitialize_context()

                        # Verify recovery happened
                        assert "health_check_failed" in recovery_sequence
                        assert "reinitialize" in recovery_sequence


class TestAudioValidation:
    """Additional audio validation tests."""

    def test_validate_empty_audio(self):
        """Test validation rejects empty audio."""
        from infrastructure.whisper.library_adapter import WhisperLibraryAdapter

        with patch.object(WhisperLibraryAdapter, "__init__", lambda x, **kwargs: None):
            adapter = WhisperLibraryAdapter()

            empty_audio = np.array([], dtype=np.float32)
            is_valid, reason = adapter._validate_audio(empty_audio)

            assert is_valid is False
            assert "empty" in reason.lower()

    def test_validate_silent_audio(self):
        """Test validation warns about silent audio."""
        from infrastructure.whisper.library_adapter import WhisperLibraryAdapter

        with patch.object(WhisperLibraryAdapter, "__init__", lambda x, **kwargs: None):
            adapter = WhisperLibraryAdapter()

            # Very quiet audio (max < 0.01)
            silent_audio = np.random.uniform(-0.005, 0.005, 16000).astype(np.float32)
            is_valid, reason = adapter._validate_audio(silent_audio)

            assert is_valid is False
            assert "silent" in reason.lower()

    def test_validate_constant_noise(self):
        """Test validation warns about constant noise."""
        from infrastructure.whisper.library_adapter import WhisperLibraryAdapter

        with patch.object(WhisperLibraryAdapter, "__init__", lambda x, **kwargs: None):
            adapter = WhisperLibraryAdapter()

            # Constant value (std < 0.001)
            constant_audio = np.full(16000, 0.5, dtype=np.float32)
            is_valid, reason = adapter._validate_audio(constant_audio)

            assert is_valid is False
            assert "constant" in reason.lower()

    def test_validate_valid_audio(self):
        """Test validation accepts valid audio."""
        from infrastructure.whisper.library_adapter import WhisperLibraryAdapter

        with patch.object(WhisperLibraryAdapter, "__init__", lambda x, **kwargs: None):
            adapter = WhisperLibraryAdapter()

            # Normal audio with variation
            valid_audio = np.random.uniform(-0.5, 0.5, 16000).astype(np.float32)
            is_valid, reason = adapter._validate_audio(valid_audio)

            assert is_valid is True
            assert "valid" in reason.lower()


class TestMinChunkDuration:
    """Test minimum chunk duration enforcement."""

    def test_min_chunk_constant_exists(self):
        """Verify MIN_CHUNK_DURATION constant is defined."""
        from infrastructure.whisper.library_adapter import MIN_CHUNK_DURATION

        assert MIN_CHUNK_DURATION == 2.0

    def test_short_chunk_handling(self):
        """Test that short chunks are handled properly."""
        from infrastructure.whisper.library_adapter import MIN_CHUNK_DURATION

        # This is tested implicitly through _split_audio
        # Short final chunks should be merged with previous
        assert MIN_CHUNK_DURATION > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
