import re
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from app.core.ids import build_tag, new_id
from app.db.mongo import get_db
from app.schemas.player import Player, PlayerCreate
from app.serializers import to_player

router = APIRouter(prefix="/players", tags=["players"])


def normalize_tag(value: str) -> str:
    normalized = value.strip().upper()
    return normalized if normalized.startswith("#") else f"#{normalized}"


def build_player_document(payload: PlayerCreate, tag: str) -> dict:
    document = {
        "_id": new_id("ply"),
        "tag": tag,
        "first_name": payload.first_name.strip(),
        "last_name": payload.last_name.strip(),
        "name": f"{payload.first_name.strip()} {payload.last_name.strip()}",
        "position": payload.position.strip(),
        "role": payload.role,
        "is_ghost": payload.is_ghost,
        "elo": 1000,
        "stats": {
            "goals": 0,
            "assists": 0,
            "yellow_cards": 0,
            "red_cards": 0,
            "mvp": 0,
            "matches_played": 0,
        },
        "created_at": datetime.now(UTC),
    }

    if payload.cedula:
        document["cedula"] = payload.cedula.strip()
    if payload.phone:
        document["phone"] = payload.phone.strip()

    return document


@router.post("", response_model=Player, status_code=201)
def create_player(
    payload: PlayerCreate,
    db: Database = Depends(get_db),
) -> Player:
    if payload.tag:
        tag = normalize_tag(payload.tag)
        if db.players.find_one({"tag": tag}, {"_id": 1}):
            raise HTTPException(status_code=409, detail="El tag ya está en uso.")
    else:
        tag = ""

    if payload.cedula and db.players.find_one(
        {"cedula": payload.cedula.strip()}, {"_id": 1}
    ):
        raise HTTPException(status_code=409, detail="La cédula ya está registrada.")

    if payload.phone and db.players.find_one(
        {"phone": payload.phone.strip()}, {"_id": 1}
    ):
        raise HTTPException(status_code=409, detail="El teléfono ya está registrado.")

    attempts = 1 if payload.tag else 10

    for _ in range(attempts):
        candidate = tag or build_tag(payload.first_name, payload.last_name)
        document = build_player_document(payload, candidate)

        try:
            db.players.insert_one(document)
            return to_player(document)
        except DuplicateKeyError as error:
            if payload.tag:
                raise HTTPException(
                    status_code=409,
                    detail="El tag, cédula o teléfono ya está en uso.",
                ) from error

    raise HTTPException(status_code=409, detail="No se pudo generar un tag único.")


@router.get("/search", response_model=list[Player])
def search_players(
    q: str = Query(min_length=1, max_length=80),
    limit: int = Query(default=20, ge=1, le=50),
    db: Database = Depends(get_db),
) -> list[Player]:
    pattern = re.escape(q.strip())
    query = {
        "$or": [
            {"tag": {"$regex": pattern, "$options": "i"}},
            {"first_name": {"$regex": pattern, "$options": "i"}},
            {"last_name": {"$regex": pattern, "$options": "i"}},
            {"name": {"$regex": pattern, "$options": "i"}},
        ]
    }

    documents = db.players.find(query).limit(limit)
    return [to_player(document) for document in documents]


@router.get("/{player_id}", response_model=Player)
def get_player(player_id: str, db: Database = Depends(get_db)) -> Player:
    document = db.players.find_one({"_id": player_id})

    if not document:
        raise HTTPException(status_code=404, detail="Jugador no encontrado.")

    return to_player(document)
