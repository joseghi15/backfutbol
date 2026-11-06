from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.core.config import get_settings
from app.db.mongo import get_db

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    environment: str


class DatabaseHealthResponse(BaseModel):
    status: str
    database: str


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(status="ok", environment=settings.environment)


@router.get("/health/db", response_model=DatabaseHealthResponse)
def health_db(db: Database = Depends(get_db)) -> DatabaseHealthResponse:
    try:
        db.list_collection_names()
    except PyMongoError as error:
        raise HTTPException(
            status_code=503,
            detail="MongoDB no está disponible.",
        ) from error

    return DatabaseHealthResponse(status="ok", database=db.name)
