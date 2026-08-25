from fastapi import FastAPI

from .routes.health import router as health_router
from .routes.documents import router as file_router

# NOTE: The single app instance — every router, middleware, and handler attaches to this.
app = FastAPI()

# NOTE: Health check endpoints (GET /health -> 200).
app.include_router(health_router)

# NOTE: Document upload endpoints, mounted under "/files" (POST /files/ -> 201).
app.include_router(file_router, prefix="/files")

# TODO: Add a global exception handler so any raised service exception we
# forget to catch in a route (e.g. a new one added later) returns a clean
# error response instead of a generic, unhandled 500.

# TODO: Add CORS middleware once the frontend's origin is known.