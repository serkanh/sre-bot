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
from .utils import setup_logger

# Configure logging using shared utility with custom format for server
logger = setup_logger(
    "SRE_AGENT", format_string="%(asctime)s - SRE_AGENT - %(levelname)s - %(message)s"
)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Add request/response logging for troubleshooting"""

    async def dispatch(self, request, call_next):
        request_id = (
            f"sre_{int(time.time() * 1000)}_{hash(str(request.url)) % 10000:04d}"
        )
        start_time = time.time()

        logger.info(f"🚀 [{request_id}] {request.method} {request.url}")

        try:
            response = await call_next(request)
            duration_ms = (time.time() - start_time) * 1000
            logger.info(
                f"✅ [{request_id}] {response.status_code} in {duration_ms:.2f}ms"
            )
            return response
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"💥 [{request_id}] FAILED after {duration_ms:.2f}ms: {e}")
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

    # Determine if web UI should be enabled
    ui_enabled = os.getenv("ADK_UI_ENABLED", "False").lower() in ("true", "1", "t")

    # Get session service URI
    session_uri = get_session_service_uri()

    # Log startup configuration
    logger.info("🎛️ SRE Agent Service initializing...")
    logger.info(f"🔧 UI enabled: {ui_enabled}")
    logger.info(f"🌐 Environment: {os.getenv('NODE_ENV', 'development')}")
    logger.info(f"🚪 Port: {os.getenv('PORT', '8000')}")
    logger.info(f"📁 Agents dir: .")
    logger.info(f"💾 Session URI: {session_uri}")

    # Create FastAPI app using ADK
    app: FastAPI = get_fast_api_app(
        agents_dir=".",
        allow_origins=["*"],
        web=ui_enabled,
        session_service_uri=session_uri,
    )

    # Add request logging middleware
    app.add_middleware(RequestLoggingMiddleware)
    logger.info("📡 Request logging middleware added")

    @app.get("/health")
    async def health_check():
        """Health check endpoint with system information"""
        health_id = f"health_{int(time.time() * 1000)}"

        health_info = {
            "status": "healthy",
            "service": "sre-agent",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0",
            "ui_enabled": ui_enabled,
            "port": os.getenv("PORT", "8000"),
            "environment": os.getenv("NODE_ENV", "development"),
            "agents_dir": ".",
            "process_id": os.getpid(),
            "health_check_id": health_id,
        }

        logger.info(f"🏥 [{health_id}] Health check requested")
        return health_info

    @app.get("/health/readiness")
    async def readiness_check():
        """Readiness probe for Kubernetes"""
        return {"status": "ready", "service": "sre-agent"}

    @app.get("/health/liveness")
    async def liveness_check():
        """Liveness probe for Kubernetes"""
        return {"status": "alive", "service": "sre-agent"}

    @app.on_event("startup")
    async def startup_event():
        """Log startup information"""
        startup_id = f"startup_{int(time.time() * 1000)}"
        logger.info(f"🚀 [{startup_id}] SRE Agent Service startup complete")

        # Log available routes
        route_count = 0
        for route in app.routes:
            if hasattr(route, "methods") and hasattr(route, "path"):
                route_count += 1
                logger.info(
                    f"🛣️ [{startup_id}] Route: {list(route.methods)} {route.path}"
                )

        logger.info(f"✅ [{startup_id}] Service ready! Found {route_count} routes")
        logger.info(f"🎯 [{startup_id}] Listening on port {os.getenv('PORT', '8000')}")

    return app


# Create the app instance
app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port, reload=False)
