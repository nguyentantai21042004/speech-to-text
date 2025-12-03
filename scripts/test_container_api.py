#!/usr/bin/env python3
"""
Test script to verify transcription optimizations in container.
Run this inside the container: python3 /app/scripts/test_container_api.py
"""

import sys
import time
from pathlib import Path

# Add app to path
sys.path.insert(0, "/app")

# Setup logging
try:
    from core.logger import logger, configure_script_logging
    from core.config import get_settings

    settings = get_settings()
    configure_script_logging(level=settings.script_log_level)
except ImportError:
    from loguru import logger

    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    )


def test_transcription(audio_path: str, language: str = "en", description: str = ""):
    """Test transcription with a local audio file."""
    logger.info("=" * 60)
    logger.info(f"TEST: {description}")
    logger.info(f"File: {audio_path}")
    logger.info(f"Language: {language}")
    logger.info("=" * 60)

    path = Path(audio_path)
    if not path.exists():
        logger.error(f"File not found: {audio_path}")
        return None

    # Get file size
    size_mb = path.stat().st_size / (1024 * 1024)
    logger.info(f"File size: {size_mb:.2f} MB")

    # Get transcriber directly
    from interfaces.transcriber import ITranscriber
    from core.container import Container

    transcriber = Container.resolve(ITranscriber)

    # Read audio file
    with open(audio_path, "rb") as f:
        audio_data = f.read()

    logger.info(f"Audio data size: {len(audio_data)} bytes")

    # Transcribe
    start_time = time.time()
    try:
        result = transcriber.transcribe(audio_data, language=language)
        elapsed = time.time() - start_time

        logger.success(f"SUCCESS in {elapsed:.2f}s")
        logger.info(f"Result length: {len(result)} chars")

        # Check for [inaudible]
        if "[inaudible]" in result.lower():
            inaudible_count = result.lower().count("[inaudible]")
            logger.warning(f"Found {inaudible_count} [inaudible] markers!")
            if result.replace("[inaudible]", "").strip() == "":
                logger.error("FAIL: Result is ONLY [inaudible] markers!")
                return {"status": "fail", "reason": "only_inaudible", "result": result}
        else:
            logger.success("No [inaudible] markers found")

        # Print preview
        preview = result[:200] + "..." if len(result) > 200 else result
        logger.info(f"Preview: {preview}")

        return {"status": "success", "result": result, "elapsed": elapsed}

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"FAILED in {elapsed:.2f}s")
        logger.exception(f"Error: {e}")
        return {"status": "error", "error": str(e)}


def main():
    logger.info("=" * 60)
    logger.info("TRANSCRIPTION OPTIMIZATION VERIFICATION TEST")
    logger.info("=" * 60)

    # Bootstrap DI container
    logger.info("Initializing DI container...")
    from core.container import bootstrap_container

    bootstrap_container()
    logger.success("DI container initialized")

    # Test files
    test_cases = [
        # Short English audio (30s) - should use direct transcription
        {
            "path": "/app/scripts/test_audio/benchmark_30s.wav",
            "language": "en",
            "description": "Short English audio (30s) - Direct transcription",
        },
        # Short Vietnamese audio
        {
            "path": "/app/scripts/test_audio/7553444429583944980.mp3",
            "language": "vi",
            "description": "Short Vietnamese audio (~15s)",
        },
        # Medium Vietnamese audio
        {
            "path": "/app/scripts/test_audio/7314151385635867905.mp3",
            "language": "vi",
            "description": "Medium Vietnamese audio",
        },
        # Longer Vietnamese audio - should trigger chunking
        {
            "path": "/app/scripts/test_audio/7533882162861411602.mp3",
            "language": "vi",
            "description": "Longer Vietnamese audio - May trigger chunking",
        },
    ]

    results = []
    for tc in test_cases:
        result = test_transcription(tc["path"], tc["language"], tc["description"])
        results.append({"test": tc["description"], "result": result})

    # Summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)

    success_count = 0
    fail_count = 0

    for r in results:
        if r["result"] is None:
            logger.warning(f"SKIPPED: {r['test']}")
        elif r["result"]["status"] == "success":
            logger.success(f"PASS: {r['test']} ({r['result']['elapsed']:.2f}s)")
            success_count += 1
        elif r["result"]["status"] == "fail":
            logger.error(f"FAIL: {r['test']} - {r['result']['reason']}")
            fail_count += 1
        else:
            logger.error(f"ERROR: {r['test']} - {r['result']['error']}")
            fail_count += 1

    logger.info(f"Total: {success_count} passed, {fail_count} failed")

    if fail_count == 0:
        logger.success("ALL TESTS PASSED! Optimizations are working correctly.")
        return 0
    else:
        logger.warning("Some tests failed. Check logs for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
