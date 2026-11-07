from fastapi import APIRouter

from app.database import connection

router = APIRouter()


@router.get("/health")
async def health():
    await connection.ping()
    return {"status": "ok"}
