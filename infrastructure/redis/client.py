"""
Redis client for async job state management.

Manages STT job states with Redis as temporary storage.
Key format: stt:job:{request_id}
TTL: Configurable via settings (default 1 hour)
"""

import json
from typing import Any, Optional

from redis import Redis
from redis.exceptions import RedisError

from core.config import get_settings
from core.logger import logger


class RedisClient:
    """
    Redis client wrapper for STT job state management.

    Handles connection management and provides methods for:
    - Setting job state with TTL
    - Getting job state
    - Checking job existence
    """

    def __init__(self):
        """Initialize Redis client with settings from config."""
        self._client: Optional[Redis] = None

    def _get_client(self) -> Redis:
        """Get or create Redis client connection."""
        if self._client is None:
            settings = get_settings()
            self._client = Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                password=settings.redis_password if settings.redis_password else None,
                db=settings.redis_db,
                decode_responses=True,  # Auto-decode bytes to str
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            logger.info(
                f"Redis client created: {settings.redis_host}:{settings.redis_port}"
            )
        return self._client

    def _get_key(self, request_id: str) -> str:
        """
        Generate Redis key for job.

        Args:
            request_id: Unique job identifier

        Returns:
            Redis key in format: stt:job:{request_id}
        """
        return f"stt:job:{request_id}"

    async def set_job_state(
        self, request_id: str, state: dict[str, Any], ttl: Optional[int] = None
    ) -> bool:
        """
        Set job state in Redis with TTL.

        Args:
            request_id: Unique job identifier
            state: Job state dictionary (will be JSON-serialized)
            ttl: Time-to-live in seconds (uses config default if not provided)

        Returns:
            True if successful, False otherwise
        """
        try:
            client = self._get_client()
            key = self._get_key(request_id)
            value = json.dumps(state)

            if ttl is None:
                settings = get_settings()
                ttl = settings.redis_job_ttl

            client.setex(key, ttl, value)
            logger.debug(f"Set job state: {key} (TTL: {ttl}s)")
            return True
        except RedisError as e:
            logger.error(f"Failed to set job state for {request_id}: {e}")
            return False

    async def get_job_state(self, request_id: str) -> Optional[dict[str, Any]]:
        """
        Get job state from Redis.

        Args:
            request_id: Unique job identifier

        Returns:
            Job state dict if exists, None otherwise
        """
        try:
            client = self._get_client()
            key = self._get_key(request_id)
            value = client.get(key)

            if value is None:
                logger.debug(f"Job state not found: {key}")
                return None

            state = json.loads(value)
            logger.debug(f"Got job state: {key}")
            return state
        except (RedisError, json.JSONDecodeError) as e:
            logger.error(f"Failed to get job state for {request_id}: {e}")
            return None

    async def job_exists(self, request_id: str) -> bool:
        """
        Check if job exists in Redis.

        Args:
            request_id: Unique job identifier

        Returns:
            True if job exists, False otherwise
        """
        try:
            client = self._get_client()
            key = self._get_key(request_id)
            exists = client.exists(key)
            return bool(exists)
        except RedisError as e:
            logger.error(f"Failed to check job existence for {request_id}: {e}")
            return False

    async def delete_job(self, request_id: str) -> bool:
        """
        Delete job from Redis.

        Args:
            request_id: Unique job identifier

        Returns:
            True if deleted, False otherwise
        """
        try:
            client = self._get_client()
            key = self._get_key(request_id)
            client.delete(key)
            logger.debug(f"Deleted job: {key}")
            return True
        except RedisError as e:
            logger.error(f"Failed to delete job {request_id}: {e}")
            return False

    def ping(self) -> bool:
        """
        Check Redis connection health.

        Returns:
            True if Redis is reachable, False otherwise
        """
        try:
            client = self._get_client()
            return client.ping()
        except RedisError as e:
            logger.error(f"Redis ping failed: {e}")
            return False

    def close(self):
        """Close Redis connection."""
        if self._client:
            self._client.close()
            self._client = None
            logger.info("Redis connection closed")


# Global singleton
_redis_client: Optional[RedisClient] = None


def get_redis_client() -> RedisClient:
    """Get or create RedisClient singleton."""
    global _redis_client
    if _redis_client is None:
        logger.info("Creating RedisClient instance...")
        _redis_client = RedisClient()
    return _redis_client
