import re
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from app.core.ids import build_initials, build_team_code, new_id
from app.db.mongo import get_db
from app.schemas.team import Team, TeamCreate, TeamDetail, TeamPlayerAdd
from app.serializers import to_team, to_team_detail

router = APIRouter(prefix="/teams", tags=["teams"])


def normalize_code(value: str) -> str:
    return value.strip().upper()


@router.post("", response_model=Team, status_code=201)
def create_team(payload: TeamCreate, db: Database = Depends(get_db)) -> Team:
    name = payload.name.strip()
    initials = (payload.initials or build_initials(name)).upper()

    if payload.code:
        code = normalize_code(payload.code)
        if db.teams.find_one({"code": code}, {"_id": 1}):
            raise HTTPException(status_code=409, detail="El código ya está en uso.")
    else:
        code = ""

    attempts = 1 if payload.code else 10

    for _ in range(attempts):
        candidate = code or build_team_code()
        document = {
            "_id": new_id("team"),
            "code": candidate,
            "name": name,
            "captain_name": payload.captain_name.strip(),
            "initials": initials,
            "members": [],
            "created_at": datetime.now(UTC),
        }

        try:
            db.teams.insert_one(document)
            return to_team(document)
        except DuplicateKeyError as error:
            if payload.code:
                raise HTTPException(
                    status_code=409,
                    detail="El código ya está en uso.",
                ) from error

    raise HTTPException(status_code=409, detail="No se pudo generar un código único.")


@router.get("/search", response_model=list[Team])
def search_teams(
    q: str = Query(min_length=1, max_length=80),
    limit: int = Query(default=20, ge=1, le=50),
    db: Database = Depends(get_db),
) -> list[Team]:
    pattern = re.escape(q.strip())
    query = {
        "$or": [
            {"code": {"$regex": pattern, "$options": "i"}},
            {"name": {"$regex": pattern, "$options": "i"}},
            {"captain_name": {"$regex": pattern, "$options": "i"}},
        ]
    }

    documents = db.teams.find(query).limit(limit)
    return [to_team(document) for document in documents]


@router.get("/{team_id}", response_model=TeamDetail)
def get_team(team_id: str, db: Database = Depends(get_db)) -> TeamDetail:
    document = db.teams.find_one({"_id": team_id})

    if not document:
        raise HTTPException(status_code=404, detail="Equipo no encontrado.")

    return to_team_detail(document, db)


@router.post("/{team_id}/players", response_model=TeamDetail)
def add_team_player(
    team_id: str,
    payload: TeamPlayerAdd,
    db: Database = Depends(get_db),
) -> TeamDetail:
    team = db.teams.find_one({"_id": team_id})

    if not team:
        raise HTTPException(status_code=404, detail="Equipo no encontrado.")

    player = db.players.find_one({"_id": payload.player_id})

    if not player:
        raise HTTPException(status_code=404, detail="Jugador no encontrado.")

    if any(
        member["player_id"] == payload.player_id for member in team.get("members", [])
    ):
        raise HTTPException(
            status_code=409,
            detail="El jugador ya pertenece a este equipo.",
        )

    if payload.jersey_number is not None and any(
        member.get("jersey_number") == payload.jersey_number
        for member in team.get("members", [])
    ):
        raise HTTPException(
            status_code=409,
            detail="El dorsal ya está en uso en este equipo.",
        )

    member = {
        "player_id": payload.player_id,
        "jersey_number": payload.jersey_number,
        "position": payload.position or player["position"],
    }

    db.teams.update_one(
        {"_id": team_id},
        {"$push": {"members": member}},
    )

    updated = db.teams.find_one({"_id": team_id})

    if not updated:
        raise HTTPException(status_code=404, detail="Equipo no encontrado.")

    return to_team_detail(updated, db)
