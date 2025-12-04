"""
Health Check API Routes.
"""

from fastapi import APIRouter
from typing import Dict

from internal.api.schemas import HealthResponse
from internal.api.schemas.common_schemas import StandardResponse
from internal.api.utils import success_response
from core import get_settings


router = APIRouter(tags=["Health"])


def create_health_routes(app) -> APIRouter:
    """
    Factory function to create health routes.

    Args:
        app: FastAPI application instance

    Returns:
        APIRouter: Configured router with health endpoints
    """

    @router.get(
        "/",
        response_model=StandardResponse,
        summary="Root Endpoint",
        description="Get basic API information",
        operation_id="get_root",
        responses={
            200: {
                "description": "API information",
                "content": {
                    "application/json": {
                        "example": {
                            "error_code": 0,
                            "message": "API service is running",
                            "data": {
                                "service": "Speech-to-Text API",
                                "version": "1.0.0",
                                "status": "running",
                            },
                        }
                    }
                },
            }
        },
    )
    async def root():
        """
        Root endpoint.

        Returns basic information about the API service including
        service name, version, and current status.

        **Returns:**
        Service metadata and status information.
        """
        settings = get_settings()
        return success_response(
            message="API service is running",
            data={
                "service": settings.app_name,
                "version": settings.app_version,
                "status": "running",
            },
        )

    @router.get(
        "/health",
        response_model=StandardResponse,
        summary="Health Check",
        description="Check service health including model initialization status",
        operation_id="health_check",
        responses={
            200: {
                "description": "Health status",
                "content": {
                    "application/json": {
                        "examples": {
                            "healthy": {
                                "summary": "Service operational with model loaded",
                                "value": {
                                    "error_code": 0,
                                    "message": "Service is healthy",
                                    "data": {
                                        "status": "healthy",
                                        "service": "SMAP Service",
                                        "version": "1.0.0",
                                        "model": {
                                            "initialized": True,
                                            "size": "base",
                                            "ram_mb": 1000,
                                        },
                                    },
                                },
                            },
                        }
                    }
                },
            }
        },
    )
    async def health_check():
        """
        Health check endpoint.

        **Returns:**
        Health status object indicating:
        - Overall health status (healthy/unhealthy)
        - Service name and version
        - Model initialization status, size, and configuration
        """
        import time

        settings = get_settings()

        # Get model status from app state
        model_initialized = getattr(app.state, "model_initialized", False)
        model_size = getattr(app.state, "model_size", None)
        model_config = getattr(app.state, "model_config", {})
        model_init_timestamp = getattr(app.state, "model_init_timestamp", None)
        model_init_error = getattr(app.state, "model_init_error", None)

        # Check Redis health
        redis_healthy = False
        redis_error = None
        try:
            from infrastructure.redis import get_redis_client

            redis_client = get_redis_client()
            redis_healthy = redis_client.ping()
        except Exception as e:
            redis_error = str(e)

        # Build model info
        model_info = {
            "initialized": model_initialized,
            "size": model_size,
            "ram_mb": model_config.get("ram_mb") if model_config else None,
        }

        # Add uptime if model is initialized
        if model_initialized and model_init_timestamp:
            model_info["uptime_seconds"] = round(time.time() - model_init_timestamp, 2)

        # Add error if model failed to initialize
        if not model_initialized and model_init_error:
            model_info["error"] = model_init_error

        # Build Redis info
        redis_info = {"healthy": redis_healthy}
        if redis_error:
            redis_info["error"] = redis_error

        # Determine overall health status
        # Service is healthy if model is initialized (Redis is optional for backward compatibility)
        status = "healthy" if model_initialized else "unhealthy"
        message = (
            "Service is healthy"
            if model_initialized
            else "Service unhealthy: model not initialized"
        )

        health_data = HealthResponse(
            status=status,
            service=settings.app_name,
            version=settings.app_version,
        )

        # Convert Pydantic model to dict and add model info and redis info
        health_dict = health_data.model_dump()
        health_dict["model"] = model_info
        health_dict["redis"] = redis_info

        return success_response(message=message, data=health_dict)

    return router
