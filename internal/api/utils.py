"""
API utility functions for unified response formatting.

All responses follow the format:
{
    "error_code": int,      # 0 = success, 1+ = error
    "message": str,         # Human-readable message
    "data": Any,            # Response data (omit if empty)
    "errors": Any           # Validation/error details (omit if none)
}
"""

from typing import Any, Dict, Optional

from fastapi import HTTPException
from fastapi.responses import JSONResponse


def success_response(
    message: str = "Success",
    data: Any = None,
) -> Dict[str, Any]:
    """
    Create a success response dictionary.

    Args:
        message: Success message
        data: Response data (will be placed in 'data' field)

    Returns:
        Standard response dict with error_code=0

    Example:
        >>> success_response("Job submitted", {"request_id": "123", "status": "PROCESSING"})
        {"error_code": 0, "message": "Job submitted", "data": {"request_id": "123", "status": "PROCESSING"}}
    """
    response = {"error_code": 0, "message": message}
    if data is not None:
        response["data"] = data
    return response


def error_response(
    message: str,
    error_code: int = 1,
    errors: Any = None,
) -> Dict[str, Any]:
    """
    Create an error response dictionary.

    Args:
        message: Error message
        error_code: Error code (default: 1)
        errors: Detailed error info (validation errors, etc.)

    Returns:
        Standard response dict with error_code >= 1

    Example:
        >>> error_response("Validation error", errors={"media_url": "Invalid URL"})
        {"error_code": 1, "message": "Validation error", "errors": {"media_url": "Invalid URL"}}
    """
    response = {"error_code": error_code, "message": message}
    if errors is not None:
        response["errors"] = errors
    return response


def validation_error_response(
    errors: Dict[str, str],
    message: str = "Validation error",
) -> Dict[str, Any]:
    """
    Create a validation error response.

    Args:
        errors: Dict of field -> error message
        message: Overall error message

    Returns:
        Standard error response with errors field

    Example:
        >>> validation_error_response({"media_url": "URL is required", "request_id": "Cannot be empty"})
        {"error_code": 1, "message": "Validation error", "errors": {"media_url": "URL is required", ...}}
    """
    return error_response(message=message, error_code=1, errors=errors)


def json_success_response(
    message: str = "Success",
    data: Any = None,
    status_code: int = 200,
) -> JSONResponse:
    """
    Create a JSONResponse with success format.

    Args:
        message: Success message
        data: Response data
        status_code: HTTP status code (default: 200)

    Returns:
        JSONResponse with unified format
    """
    return JSONResponse(
        status_code=status_code,
        content=success_response(message=message, data=data),
    )


def json_error_response(
    message: str,
    status_code: int = 500,
    error_code: int = 1,
    errors: Any = None,
) -> JSONResponse:
    """
    Create a JSONResponse with error format.

    Args:
        message: Error message
        status_code: HTTP status code
        error_code: Application error code
        errors: Detailed error info

    Returns:
        JSONResponse with unified error format
    """
    return JSONResponse(
        status_code=status_code,
        content=error_response(message=message, error_code=error_code, errors=errors),
    )


async def handle_api_error(exception: Exception) -> Dict[str, Any]:
    """
    Convert exception to standard error response.

    Args:
        exception: Exception object

    Returns:
        Standard error response dict
    """
    if isinstance(exception, HTTPException):
        return error_response(
            message=exception.detail,
            error_code=1,
            errors={"detail": exception.detail},
        )
    return error_response(
        message=str(exception),
        error_code=1,
        errors={"detail": str(exception)},
    )
