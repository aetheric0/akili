"""
Health Endpoint Module.

This module defines the `/health` enpoint used for application health checks.
It provides a simple way to verify that the FastAPI application is running
and responsive. The endpoint can be extended in the future to include
system metrics such as database connectivity, cache availability, or other
service dependencies.
"""

from fastapi import APIRouter

router = APIRouter(
    prefix="/health", 
    tags=['health']
)

@router.get("/", summary="Health Check", response_description="Health status of the API")
async def health_check() -> dict[str, str]:
    """
    Perform a basic health check.

    Returns a JSON response with:
    - `status`: Static string `"ok"` indicating the API is alive.
    - `timestamp`: Current UTC timestamp in ISO 8601 format.

    This endpoint can be used by monitoring tools (e.g., Kubernetes,
    Docker healthchecks, load balancers) to determine whether the
    application is operational.
    """
    return {
        "status": "ok",
        "timestamp": "{{}}"
    }
