# main.py

"""
Application entry point for the Akili API.

This module initializes the FastAPI application, registers all routers,
and provides a root endpoint. It can be run directly with Uvicorn for
local development or deployed via ASGI servers in production.
"""

# Config imports
from config import settings

# FASTAPI imports
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# APP Router imports
from app.routers.health import router as health_router
from app.routers.parser import router as parser_router
from app.routers.upload import router as upload_router
from app.routers.payment import router as payment_router
from app.routers.demo import router as demo_router
from app.routers.chat import router as chat_router

app = FastAPI(
    title="Akili",
    description=(
        "AI-powered study companion that generates summaries, quizzes,"
        " custom prompts, study guides, and personalized recommendations"
        " to support exam preparation."
    ),
    version="1.0"
)

# CORS Middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.UI_HOST],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Router Registration
app.include_router(health_router)
app.include_router(parser_router)
app.include_router(upload_router)
app.include_router(payment_router)
app.include_router(chat_router)


@app.get("/")
def home() -> dict[str, str]:
    """
    Root Endpoint for the API.

    Returns:
        dict[str, str]: A simple JSON message confirming the server
        is running and accessible.
    """
    return {
        "message": (
            "Hello, World! "
            "Akili The AI Study Pack server is live with FastAPI."
        )
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
