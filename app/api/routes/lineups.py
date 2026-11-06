from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pymongo.database import Database

from app.core.ids import new_id
from app.db.mongo import get_db
from app.schemas.lineup import LineupSide, MatchLineup, MatchLineupUpsert
from app.serializers import to_lineup

router = APIRouter(prefix="/matches", tags=["lineups"])

EXPECTED_STARTERS = {
    "Fútbol 5": 5,
    "Fútbol 7": 7,
    "Fútbol 11": 11,
}


def validate_side(
    side: LineupSide,
    team: dict,
    expected_starters: int,
) -> None:
    if len(side.starters) != expected_starters:
        raise HTTPException(
            status_code=422,
            detail=(
                f"La alineación necesita {expected_starters} titulares "
                f"y recibió {len(side.starters)}."
            ),
        )

    player_ids = [player.player_id for player in side.starters]
    player_ids.extend(player.player_id for player in side.bench)

    if len(player_ids) != len(set(player_ids)):
        raise HTTPException(
            status_code=422,
            detail="Un jugador no puede repetirse en la alineación.",
        )

    member_ids = {member["player_id"] for member in team.get("members", [])}
    missing = [player_id for player_id in player_ids if player_id not in member_ids]

    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Hay jugadores que no pertenecen al equipo: {', '.join(missing)}.",
        )


@router.get("/{match_id}/lineup", response_model=MatchLineup)
def get_match_lineup(
    match_id: str,
    db: Database = Depends(get_db),
) -> MatchLineup:
    document = db.match_lineups.find_one({"match_id": match_id})

    if not document:
        raise HTTPException(status_code=404, detail="Alineación no encontrada.")

    return to_lineup(document)


@router.put("/{match_id}/lineup", response_model=MatchLineup)
def upsert_match_lineup(
    match_id: str,
    payload: MatchLineupUpsert,
    db: Database = Depends(get_db),
) -> MatchLineup:
    if payload.home_team_id == payload.away_team_id:
        raise HTTPException(
            status_code=422,
            detail="El equipo local y el visitante deben ser distintos.",
        )

    tournament = db.tournaments.find_one({"_id": payload.tournament_id})

    if not tournament:
        raise HTTPException(status_code=404, detail="Torneo no encontrado.")

    team_ids = set(tournament.get("team_ids", []))

    if payload.home_team_id not in team_ids or payload.away_team_id not in team_ids:
        raise HTTPException(
            status_code=422,
            detail="Los dos equipos deben estar inscriptos en el torneo.",
        )

    home_team = db.teams.find_one({"_id": payload.home_team_id})
    away_team = db.teams.find_one({"_id": payload.away_team_id})

    if not home_team or not away_team:
        raise HTTPException(status_code=404, detail="Equipo no encontrado.")

    expected = EXPECTED_STARTERS[tournament["modality"]]
    validate_side(payload.home, home_team, expected)
    validate_side(payload.away, away_team, expected)

    existing = db.match_lineups.find_one({"match_id": match_id})
    now = datetime.now(UTC)
    document = {
        "_id": existing["_id"] if existing else new_id("lin"),
        "match_id": match_id,
        "tournament_id": payload.tournament_id,
        "home_team_id": payload.home_team_id,
        "away_team_id": payload.away_team_id,
        "home": payload.home.model_dump(),
        "away": payload.away.model_dump(),
        "confirmed": payload.confirmed,
        "created_at": existing["created_at"] if existing else now,
        "updated_at": now,
    }

    db.match_lineups.replace_one({"match_id": match_id}, document, upsert=True)
    return to_lineup(document)
