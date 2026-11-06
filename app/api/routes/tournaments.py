from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from app.core.ids import new_id
from app.db.mongo import get_db
from app.schemas.player import TournamentPlayerStat
from app.schemas.tournament import (
    Tournament,
    TournamentCreate,
    TournamentDetail,
    TournamentStatusUpdate,
    TournamentTeamAdd,
)
from app.serializers import to_tournament, to_tournament_detail

router = APIRouter(prefix="/tournaments", tags=["tournaments"])

ALLOWED_TRANSITIONS = {
    "draft": {"published", "in_progress"},
    "published": {"in_progress"},
    "in_progress": {"finished"},
    "finished": set(),
}

MIN_PLAYERS_BY_MODALITY = {
    "Fútbol 5": 5,
    "Fútbol 7": 7,
    "Fútbol 11": 11,
}


@router.post("", response_model=Tournament, status_code=201)
def create_tournament(
    payload: TournamentCreate,
    db: Database = Depends(get_db),
) -> Tournament:
    name = payload.name.strip()
    min_required = MIN_PLAYERS_BY_MODALITY[payload.modality]

    if payload.min_players < min_required:
        raise HTTPException(
            status_code=422,
            detail=f"El mínimo para {payload.modality} es {min_required}.",
        )

    if db.tournaments.find_one(
        {"organizer_id": payload.organizer_id, "name": name},
        {"_id": 1},
    ):
        raise HTTPException(
            status_code=409,
            detail="Ya tenés un torneo con ese nombre.",
        )

    now = datetime.now(UTC)
    document = {
        "_id": new_id("trn"),
        "name": name,
        "organizer_id": payload.organizer_id,
        "format": payload.format,
        "modality": payload.modality,
        "teams_count": payload.teams_count,
        "surface": payload.surface.strip(),
        "start_date": (payload.start_date.isoformat() if payload.start_date else None),
        "end_date": payload.end_date.isoformat() if payload.end_date else None,
        "min_players": payload.min_players,
        "main_venue": payload.main_venue.strip() if payload.main_venue else None,
        "status": payload.status,
        "registration_closed": False,
        "team_ids": [],
        "created_at": now,
        "updated_at": now,
    }

    try:
        db.tournaments.insert_one(document)
    except DuplicateKeyError as error:
        raise HTTPException(
            status_code=409,
            detail="Ya tenés un torneo con ese nombre.",
        ) from error

    return to_tournament(document)


@router.get("", response_model=list[Tournament])
def list_tournaments(
    organizer_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
    db: Database = Depends(get_db),
) -> list[Tournament]:
    query = {"organizer_id": organizer_id} if organizer_id else {}
    documents = db.tournaments.find(query).sort("created_at", -1).limit(limit)
    return [to_tournament(document) for document in documents]


@router.get("/{tournament_id}", response_model=TournamentDetail)
def get_tournament(
    tournament_id: str,
    db: Database = Depends(get_db),
) -> TournamentDetail:
    document = db.tournaments.find_one({"_id": tournament_id})

    if not document:
        raise HTTPException(status_code=404, detail="Torneo no encontrado.")

    return to_tournament_detail(document, db)


@router.patch("/{tournament_id}/status", response_model=Tournament)
def update_tournament_status(
    tournament_id: str,
    payload: TournamentStatusUpdate,
    db: Database = Depends(get_db),
) -> Tournament:
    document = db.tournaments.find_one({"_id": tournament_id})

    if not document:
        raise HTTPException(status_code=404, detail="Torneo no encontrado.")

    current = document["status"]

    if payload.status == current:
        return to_tournament(document)

    if payload.status not in ALLOWED_TRANSITIONS[current]:
        raise HTTPException(
            status_code=409,
            detail=f"No se puede pasar de {current} a {payload.status}.",
        )

    if payload.status == "in_progress":
        if len(document.get("team_ids", [])) < 2:
            raise HTTPException(
                status_code=409,
                detail="El torneo necesita al menos 2 equipos para iniciar.",
            )

        if not document.get("registration_closed"):
            raise HTTPException(
                status_code=409,
                detail="Cerrá la inscripción antes de iniciar el torneo.",
            )

        if db.matches.count_documents({"tournament_id": tournament_id}) == 0:
            raise HTTPException(
                status_code=409,
                detail="Generá el calendario antes de iniciar el torneo.",
            )

        scheduled = db.matches.count_documents(
            {
                "tournament_id": tournament_id,
                "date": {"$ne": None},
                "time": {"$ne": None},
            }
        )

        if scheduled == 0:
            raise HTTPException(
                status_code=409,
                detail="Asigná fecha y hora al menos a un partido.",
            )

    updates = {
        "status": payload.status,
        "updated_at": datetime.now(UTC),
    }

    if payload.status == "in_progress":
        updates["registration_closed"] = True

    db.tournaments.update_one(
        {"_id": tournament_id},
        {"$set": updates},
    )

    updated = db.tournaments.find_one({"_id": tournament_id})

    if not updated:
        raise HTTPException(status_code=404, detail="Torneo no encontrado.")

    return to_tournament(updated)


@router.get(
    "/{tournament_id}/player-stats",
    response_model=list[TournamentPlayerStat],
)
def list_player_stats(
    tournament_id: str,
    db: Database = Depends(get_db),
) -> list[TournamentPlayerStat]:
    tournament = db.tournaments.find_one({"_id": tournament_id})

    if not tournament:
        raise HTTPException(status_code=404, detail="Torneo no encontrado.")

    team_ids = tournament.get("team_ids", [])
    teams = list(db.teams.find({"_id": {"$in": team_ids}}))
    player_ids = [
        member["player_id"] for team in teams for member in team.get("members", [])
    ]
    players = {
        player["_id"]: player
        for player in db.players.find({"_id": {"$in": player_ids}})
    }
    rows: list[TournamentPlayerStat] = []

    for team in teams:
        for member in team.get("members", []):
            player = players.get(member["player_id"])

            if not player:
                continue

            stats = player.get("stats", {})

            rows.append(
                TournamentPlayerStat(
                    player_id=player["_id"],
                    tag=player["tag"],
                    name=player["name"],
                    team_id=team["_id"],
                    team_name=team["name"],
                    position=member.get("position") or player["position"],
                    jersey_number=member.get("jersey_number"),
                    goals=stats.get("goals", 0),
                    assists=stats.get("assists", 0),
                    yellow_cards=stats.get("yellow_cards", 0),
                    red_cards=stats.get("red_cards", 0),
                    mvp=stats.get("mvp", 0),
                    matches_played=stats.get("matches_played", 0),
                    elo=player.get("elo", 1000),
                )
            )

    rows.sort(
        key=lambda row: (
            -row.goals,
            -row.assists,
            row.name,
        )
    )
    return rows


@router.post("/{tournament_id}/close-registration", response_model=Tournament)
def close_registration(
    tournament_id: str,
    db: Database = Depends(get_db),
) -> Tournament:
    document = db.tournaments.find_one({"_id": tournament_id})

    if not document:
        raise HTTPException(status_code=404, detail="Torneo no encontrado.")

    if document.get("registration_closed"):
        return to_tournament(document)

    if document["status"] not in {"draft", "published"}:
        raise HTTPException(
            status_code=409,
            detail="El torneo ya no admite cierre de inscripción.",
        )

    team_ids = document.get("team_ids", [])

    if len(team_ids) < 2:
        raise HTTPException(
            status_code=409,
            detail="El torneo necesita al menos 2 equipos.",
        )

    teams = list(db.teams.find({"_id": {"$in": team_ids}}))
    min_players = document["min_players"]
    incomplete = [
        team["name"] for team in teams if len(team.get("members", [])) < min_players
    ]

    if incomplete:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Estos equipos no llegan al mínimo de {min_players} jugadores: "
                f"{', '.join(incomplete)}."
            ),
        )

    db.tournaments.update_one(
        {"_id": tournament_id},
        {
            "$set": {
                "registration_closed": True,
                "updated_at": datetime.now(UTC),
            }
        },
    )

    updated = db.tournaments.find_one({"_id": tournament_id})

    if not updated:
        raise HTTPException(status_code=404, detail="Torneo no encontrado.")

    return to_tournament(updated)


@router.post("/{tournament_id}/teams", response_model=Tournament)
def add_tournament_team(
    tournament_id: str,
    payload: TournamentTeamAdd,
    db: Database = Depends(get_db),
) -> Tournament:
    document = db.tournaments.find_one({"_id": tournament_id})

    if not document:
        raise HTTPException(status_code=404, detail="Torneo no encontrado.")

    if document["status"] not in {"draft", "published"}:
        raise HTTPException(
            status_code=409,
            detail="La inscripción está cerrada para este torneo.",
        )

    if not db.teams.find_one({"_id": payload.team_id}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Equipo no encontrado.")

    team_ids = document.get("team_ids", [])

    if payload.team_id in team_ids:
        raise HTTPException(
            status_code=409,
            detail="El equipo ya está inscripto en el torneo.",
        )

    if len(team_ids) >= document["teams_count"]:
        raise HTTPException(
            status_code=409,
            detail="El torneo ya alcanzó el cupo de equipos.",
        )

    db.tournaments.update_one(
        {"_id": tournament_id},
        {
            "$push": {"team_ids": payload.team_id},
            "$set": {"updated_at": datetime.now(UTC)},
        },
    )

    updated = db.tournaments.find_one({"_id": tournament_id})

    if not updated:
        raise HTTPException(status_code=404, detail="Torneo no encontrado.")

    return to_tournament(updated)
