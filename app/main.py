"""Meeting Audio Analysis API — FastAPI application entry point."""

from pathlib import Path

from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.meetings import register_error_handlers, router as meetings_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    # Ensure required directories exist
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    Path(settings.TEMP_DIR).mkdir(parents=True, exist_ok=True)

    app = FastAPI(
        title="Meeting Audio Analysis",
        description="API for meeting audio transcription, speaker diarization, gender prediction, and sentiment analysis.",
        version="0.1.0",
    )

    # Register routers
    app.include_router(health_router)
    app.include_router(meetings_router)
    register_error_handlers(app)

    return app


app = create_app()
