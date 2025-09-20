"""
SRE Agent Server - FastAPI server for the SRE agent with health checks and monitoring.
"""

import os
import uvicorn
import time
from datetime import datetime
from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from google.adk.cli.fast_api import get_fast_api_app

try:
    from .utils import get_logger
except ImportError:
    from utils import get_logger

# Configure logging using shared utility
logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Add request/response logging for troubleshooting"""

    async def dispatch(self, request, call_next):
        start_time = time.time()
        logger.info(f"Request: {request.method} {request.url}")

        try:
            response = await call_next(request)
            duration_ms = (time.time() - start_time) * 1000
            logger.info(f"Response: {response.status_code} in {duration_ms:.1f}ms")
            return response
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"Request failed after {duration_ms:.1f}ms: {e}")
            raise


def get_session_service_uri():
    """Get session service URI from environment"""
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "srebot")
    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD", "postgres")

    return f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"


def create_app() -> FastAPI:
    """Create and configure the FastAPI application"""
    session_uri = get_session_service_uri()
    port = os.getenv("PORT", "8000")
    env = os.getenv("NODE_ENV", "development")

    logger.info(f"SRE Agent API Service initializing - Port: {port}, Env: {env}")
    logger.debug(f"Session URI: {session_uri}")

    # Create FastAPI app using ADK (API-only, no web UI)
    app: FastAPI = get_fast_api_app(
        agents_dir=".",
        allow_origins=["*"],
        web=False,  # API-only mode
        session_service_uri=session_uri,
    )

    # Add request logging middleware
    app.add_middleware(RequestLoggingMiddleware)

    @app.get("/health")
    async def health_check():
        """Health check endpoint with system information"""
        return {
            "status": "healthy",
            "service": "sre-agent-api",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0",
            "mode": "api-only",
            "port": port,
            "environment": env,
        }

    @app.get("/health/readiness")
    async def readiness_check():
        """Readiness probe for Kubernetes"""
        return {"status": "ready", "service": "sre-agent-api"}

    @app.get("/health/liveness")
    async def liveness_check():
        """Liveness probe for Kubernetes"""
        return {"status": "alive", "service": "sre-agent-api"}

    @app.on_event("startup")
    async def startup_event():
        """Log startup information"""
        route_count = len(
            [r for r in app.routes if hasattr(r, "methods") and hasattr(r, "path")]
        )
        logger.info(
            f"SRE Agent API Service ready - {route_count} routes available on port {port}"
        )

    return app


# Create the app instance
app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port, reload=False)
