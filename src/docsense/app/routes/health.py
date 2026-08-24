from fastapi import APIRouter, status


router = APIRouter()

@router.get("/health", status_code=status.HTTP_200_OK)
def api_status():
    return {"status": "ok"}