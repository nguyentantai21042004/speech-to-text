"""
Unit tests for audio chunking configuration and validation.

Tests the chunking configuration settings and validation logic.
Note: Actual chunking implementation is not yet available in library_adapter.py,
so these tests focus on configuration validation.
"""

import pytest
from core.config import get_settings, Settings


class TestChunkingConfiguration:
    """Tests for chunking configuration settings"""

    def test_chunking_settings_exist(self):
        """Test that chunking configuration settings are defined"""
        settings = get_settings()

        assert hasattr(settings, "whisper_chunk_enabled")
        assert hasattr(settings, "whisper_chunk_duration")
        assert hasattr(settings, "whisper_chunk_overlap")

    def test_chunking_default_values(self):
        """Test default values for chunking configuration"""
        settings = get_settings()

        # Check default values match expected
        assert settings.whisper_chunk_duration == 30
        # Note: Default overlap may vary based on .env settings
        # Just verify it's a reasonable value (1-10 seconds)
        assert 1 <= settings.whisper_chunk_overlap <= 10
        assert isinstance(settings.whisper_chunk_enabled, bool)

    def test_chunk_overlap_validation_valid(self):
        """Test that valid overlap passes validation"""
        settings = get_settings()

        # Default overlap (3) should be valid for duration (30)
        # 3 < 30/2 = 15, so this should pass
        assert settings.validate_chunk_overlap() is True

    def test_chunk_overlap_validation_invalid(self):
        """Test that invalid overlap raises ValueError"""
        # Test the validation logic directly by creating a settings object
        # and manually setting invalid values
        settings = get_settings()

        # Save original values
        original_duration = settings.whisper_chunk_duration
        original_overlap = settings.whisper_chunk_overlap

        try:
            # Temporarily set invalid values
            settings.whisper_chunk_duration = 30
            settings.whisper_chunk_overlap = 20  # 20 >= 30/2 = 15, invalid

            with pytest.raises(ValueError, match="must be less than half"):
                settings.validate_chunk_overlap()
        finally:
            # Restore original values
            settings.whisper_chunk_duration = original_duration
            settings.whisper_chunk_overlap = original_overlap

    def test_chunk_overlap_boundary(self):
        """Test overlap at exactly half of duration (should fail)"""
        settings = get_settings()

        # Save original values
        original_duration = settings.whisper_chunk_duration
        original_overlap = settings.whisper_chunk_overlap

        try:
            settings.whisper_chunk_duration = 30
            settings.whisper_chunk_overlap = 15  # Exactly half, should fail

            with pytest.raises(ValueError, match="must be less than half"):
                settings.validate_chunk_overlap()
        finally:
            settings.whisper_chunk_duration = original_duration
            settings.whisper_chunk_overlap = original_overlap

    def test_chunk_overlap_just_under_boundary(self):
        """Test overlap just under half of duration (should pass)"""
        settings = get_settings()

        # Save original values
        original_duration = settings.whisper_chunk_duration
        original_overlap = settings.whisper_chunk_overlap

        try:
            settings.whisper_chunk_duration = 30
            settings.whisper_chunk_overlap = 14  # Just under half, should pass

            assert settings.validate_chunk_overlap() is True
        finally:
            settings.whisper_chunk_duration = original_duration
            settings.whisper_chunk_overlap = original_overlap


class TestChunkCalculations:
    """Tests for chunk boundary calculations (pure logic, no I/O)"""

    def test_calculate_chunk_count(self):
        """Test calculating number of chunks needed for audio"""

        def calculate_chunks(duration: float, chunk_duration: int, overlap: int) -> int:
            """Calculate number of chunks needed for given duration"""
            if duration <= chunk_duration:
                return 1

            effective_chunk = chunk_duration - overlap
            remaining = duration - chunk_duration
            additional_chunks = int(remaining / effective_chunk) + (
                1 if remaining % effective_chunk > 0 else 0
            )
            return 1 + additional_chunks

        # Test cases
        assert calculate_chunks(25.0, 30, 3) == 1  # Short audio, single chunk
        assert calculate_chunks(30.0, 30, 3) == 1  # Exactly one chunk
        assert calculate_chunks(50.0, 30, 3) == 2  # Needs 2 chunks
        assert calculate_chunks(90.0, 30, 3) == 4  # Needs 4 chunks

    def test_calculate_chunk_boundaries(self):
        """Test calculating start/end times for each chunk"""

        def calculate_boundaries(
            duration: float, chunk_duration: int, overlap: int
        ) -> list:
            """Calculate (start, end) boundaries for each chunk"""
            boundaries = []
            start = 0.0

            while start < duration:
                end = min(start + chunk_duration, duration)
                boundaries.append((start, end))

                if end >= duration:
                    break

                start = end - overlap

            return boundaries

        # Test with 90 seconds, 30s chunks, 3s overlap
        boundaries = calculate_boundaries(90.0, 30, 3)

        assert len(boundaries) == 4
        assert boundaries[0] == (0.0, 30.0)
        assert boundaries[1] == (27.0, 57.0)
        assert boundaries[2] == (54.0, 84.0)
        assert boundaries[3] == (81.0, 90.0)

    def test_short_audio_single_chunk(self):
        """Test that short audio produces single chunk"""

        def calculate_boundaries(
            duration: float, chunk_duration: int, overlap: int
        ) -> list:
            boundaries = []
            start = 0.0

            while start < duration:
                end = min(start + chunk_duration, duration)
                boundaries.append((start, end))

                if end >= duration:
                    break

                start = end - overlap

            return boundaries

        # 20 second audio with 30s chunks should be single chunk
        boundaries = calculate_boundaries(20.0, 30, 3)

        assert len(boundaries) == 1
        assert boundaries[0] == (0.0, 20.0)


class TestTextMerging:
    """Tests for merging transcribed text chunks"""

    def test_merge_basic_chunks(self):
        """Test basic text chunk merging"""

        def merge_chunks(chunks: list) -> str:
            """Merge text chunks, removing empty strings and extra whitespace"""
            return " ".join(chunk.strip() for chunk in chunks if chunk.strip())

        chunks = ["Hello world", "this is a", "test"]
        result = merge_chunks(chunks)

        assert result == "Hello world this is a test"

    def test_merge_with_empty_strings(self):
        """Test merging with empty strings"""

        def merge_chunks(chunks: list) -> str:
            return " ".join(chunk.strip() for chunk in chunks if chunk.strip())

        chunks = ["Hello", "", "world", "   ", "test"]
        result = merge_chunks(chunks)

        assert result == "Hello world test"

    def test_merge_with_whitespace(self):
        """Test merging with extra whitespace"""

        def merge_chunks(chunks: list) -> str:
            return " ".join(chunk.strip() for chunk in chunks if chunk.strip())

        chunks = ["  Hello  ", "  world  "]
        result = merge_chunks(chunks)

        assert result == "Hello world"

    def test_merge_empty_list(self):
        """Test merging empty list"""

        def merge_chunks(chunks: list) -> str:
            return " ".join(chunk.strip() for chunk in chunks if chunk.strip())

        result = merge_chunks([])
        assert result == ""

    def test_merge_all_empty(self):
        """Test merging list of empty strings"""

        def merge_chunks(chunks: list) -> str:
            return " ".join(chunk.strip() for chunk in chunks if chunk.strip())

        result = merge_chunks(["", "   ", ""])
        assert result == ""
