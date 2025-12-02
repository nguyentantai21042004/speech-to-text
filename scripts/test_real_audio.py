#!/usr/bin/env python3
"""
Test with real audio files to verify Phase 1-4 features work in practice.
Run with: uv run python scripts/test_real_audio.py
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.logger import logger


def test_audio_duration():
    """Test getting audio duration from real files"""
    print("Testing audio duration detection...")

    from infrastructure.whisper.library_adapter import WhisperLibraryAdapter
    from unittest.mock import patch, MagicMock

    test_audio_dir = Path(__file__).parent / "test_audio"

    if not test_audio_dir.exists():
        print(f"  ⚠️ Test audio directory not found: {test_audio_dir}")
        return

    # Find a test audio file
    audio_files = list(test_audio_dir.glob("*.mp3")) + list(
        test_audio_dir.glob("*.wav")
    )

    if not audio_files:
        print(f"  ⚠️ No audio files found in {test_audio_dir}")
        return

    # Use mock adapter to test duration detection
    with patch.object(
        WhisperLibraryAdapter, "__init__", lambda x, model_size=None: None
    ):
        adapter = WhisperLibraryAdapter()

        for audio_file in audio_files[:3]:  # Test first 3 files
            try:
                duration = adapter.get_audio_duration(str(audio_file))
                print(f"  ✅ {audio_file.name}: {duration:.2f}s")
            except Exception as e:
                print(f"  ❌ {audio_file.name}: {e}")


def test_audio_loading_with_stats():
    """Test audio loading with statistics logging"""
    print("\nTesting audio loading with stats...")

    from infrastructure.whisper.library_adapter import WhisperLibraryAdapter
    from unittest.mock import patch

    test_audio_dir = Path(__file__).parent / "test_audio"

    if not test_audio_dir.exists():
        print(f"  ⚠️ Test audio directory not found: {test_audio_dir}")
        return

    # Find a short test audio file
    audio_files = list(test_audio_dir.glob("*.wav"))
    if not audio_files:
        audio_files = list(test_audio_dir.glob("*.mp3"))

    if not audio_files:
        print(f"  ⚠️ No audio files found")
        return

    # Use the benchmark file if available (it's shorter)
    benchmark_file = test_audio_dir / "benchmark_30s.wav"
    if benchmark_file.exists():
        test_file = benchmark_file
    else:
        test_file = audio_files[0]

    with patch.object(
        WhisperLibraryAdapter, "__init__", lambda x, model_size=None: None
    ):
        adapter = WhisperLibraryAdapter()

        try:
            print(f"  Loading: {test_file.name}")
            audio_data, duration = adapter._load_audio(str(test_file))
            print(f"  ✅ Loaded {len(audio_data)} samples, duration={duration:.2f}s")

            # Test validation
            is_valid, reason = adapter._validate_audio(audio_data)
            print(f"  ✅ Validation: is_valid={is_valid}, reason='{reason}'")

        except Exception as e:
            print(f"  ❌ Failed: {e}")


def test_chunk_splitting():
    """Test chunk splitting with real audio"""
    print("\nTesting chunk splitting...")

    from infrastructure.whisper.library_adapter import (
        WhisperLibraryAdapter,
        MIN_CHUNK_DURATION,
    )
    from unittest.mock import patch
    import tempfile
    import shutil

    test_audio_dir = Path(__file__).parent / "test_audio"

    # Find a longer audio file for chunking test
    audio_files = list(test_audio_dir.glob("*.mp3"))

    if not audio_files:
        print(f"  ⚠️ No MP3 files found for chunking test")
        return

    # Pick a file that's likely > 30s
    test_file = audio_files[0]

    with patch.object(
        WhisperLibraryAdapter, "__init__", lambda x, model_size=None: None
    ):
        adapter = WhisperLibraryAdapter()

        try:
            duration = adapter.get_audio_duration(str(test_file))
            print(f"  Audio: {test_file.name}, duration={duration:.2f}s")

            if duration < 35:
                print(f"  ⚠️ Audio too short for chunking test (need > 30s)")
                return

            # Create temp directory for chunks
            temp_dir = tempfile.mkdtemp()
            temp_audio = Path(temp_dir) / test_file.name
            shutil.copy(test_file, temp_audio)

            try:
                # Test splitting with 30s chunks, 3s overlap
                chunk_files = adapter._split_audio(
                    str(temp_audio), duration=duration, chunk_duration=30, overlap=3
                )

                print(f"  ✅ Created {len(chunk_files)} chunks")

                # Verify chunk files exist
                for i, chunk_file in enumerate(chunk_files):
                    if os.path.exists(chunk_file):
                        chunk_duration = adapter.get_audio_duration(chunk_file)
                        print(f"    Chunk {i+1}: {chunk_duration:.2f}s")
                        os.remove(chunk_file)  # Cleanup
                    else:
                        print(f"    ❌ Chunk {i+1} not found: {chunk_file}")

            finally:
                # Cleanup temp directory
                shutil.rmtree(temp_dir, ignore_errors=True)

        except Exception as e:
            print(f"  ❌ Failed: {e}")
            import traceback

            traceback.print_exc()


def main():
    print("=" * 60)
    print("Testing with Real Audio Files")
    print("=" * 60)
    print()

    test_audio_duration()
    test_audio_loading_with_stats()
    test_chunk_splitting()

    print()
    print("=" * 60)
    print("Real Audio Tests Complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
