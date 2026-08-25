from fastapi import FastAPI
from .routes.health import router as health_router
from .routes.documents import router as file_router

app = FastAPI()

#API Health Status(200)
app.include_router(health_router)

#Upload file/document(201)
app.include_router(file_router, prefix="/files")