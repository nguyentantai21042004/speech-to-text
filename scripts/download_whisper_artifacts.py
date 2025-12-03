#!/usr/bin/env python3
"""
Download Whisper artifacts from MinIO based on model size.
Usage: python scripts/download_whisper_artifacts.py [base|small|medium]
"""
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Setup logging first (before other imports that might log)
try:
    from core.logger import logger, configure_script_logging
    from core.config import get_settings

    settings = get_settings()
    configure_script_logging(level=settings.script_log_level)

    MINIO_ENDPOINT = settings.minio_endpoint
    MINIO_ACCESS_KEY = settings.minio_access_key
    MINIO_SECRET_KEY = settings.minio_secret_key
except ImportError:
    # Fallback if core modules not available
    from loguru import logger

    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    )

    MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
    MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")

try:
    import boto3
    from botocore.exceptions import ClientError
    from botocore.client import Config
except ImportError:
    logger.error("boto3 not installed. Install with: pip install boto3")
    sys.exit(1)

BUCKET_NAME = "whisper-artifacts"


def download_artifacts(model_size="small"):
    """Download Whisper artifacts for specified model size"""

    # Create models directory and output subdirectory
    # Default: models/whisper_{size}_xeon/ (matches WHISPER_ARTIFACTS_DIR=models)
    models_dir = Path("models")
    models_dir.mkdir(exist_ok=True)

    output_dir = models_dir / f"whisper_{model_size}_xeon"
    output_dir.mkdir(exist_ok=True)

    logger.info(f"Downloading Whisper {model_size.upper()} artifacts...")
    logger.info(f"From: {MINIO_ENDPOINT}/{BUCKET_NAME}")
    logger.info(f"To: {output_dir}/")

    # Create S3 client
    s3_client = boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )

    # List of files to download
    prefix = f"whisper_{model_size}_xeon/"

    try:
        # List objects in bucket
        response = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)

        if "Contents" not in response:
            logger.error(f"No artifacts found for {model_size} model")
            return False

        total_files = len(
            [obj for obj in response["Contents"] if obj["Key"].split("/")[-1]]
        )
        logger.info(f"Found {total_files} files to download")

        # Download each file
        downloaded = 0
        for obj in response["Contents"]:
            key = obj["Key"]
            filename = key.split("/")[-1]

            if not filename:  # Skip directory entries
                continue

            local_path = output_dir / filename
            file_size_mb = obj["Size"] / (1024 * 1024)

            logger.info(f"Downloading {filename} ({file_size_mb:.1f} MB)...")

            try:
                s3_client.download_file(BUCKET_NAME, key, str(local_path))
                downloaded += 1
            except ClientError as e:
                logger.error(f"Failed to download {filename}: {e}")
                return False

        logger.success(f"Downloaded {downloaded} files to: {output_dir}/")

        # Verify critical files exist
        required_files = [
            "libwhisper.so",
            "libggml.so.0",
            "libggml-base.so.0",
            "libggml-cpu.so.0",
            f"ggml-{model_size}-q5_1.bin",
        ]

        missing_files = []
        for file in required_files:
            if not (output_dir / file).exists():
                missing_files.append(file)
                logger.error(f"Missing required file: {file}")

        if missing_files:
            logger.error(f"Missing {len(missing_files)} required files")
            return False

        logger.success("All required files verified")
        return True

    except ClientError as e:
        logger.error(f"Error accessing MinIO: {e}")
        return False


if __name__ == "__main__":
    if len(sys.argv) > 1:
        model_size = sys.argv[1].lower()
    else:
        model_size = os.getenv("WHISPER_MODEL_SIZE", "base")

    if model_size not in ["base", "small", "medium"]:
        logger.error("Invalid model size")
        logger.info("Usage: python download_whisper_artifacts.py [base|small|medium]")
        logger.info("Or set WHISPER_MODEL_SIZE environment variable")
        sys.exit(1)

    success = download_artifacts(model_size)
    sys.exit(0 if success else 1)
