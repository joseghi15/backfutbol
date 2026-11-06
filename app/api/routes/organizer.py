from fastapi import APIRouter, Depends
from pymongo.database import Database

from app.db.mongo import get_db
from app.schemas.match import OrganizerMatchItem
from app.schemas.organizer import OrganizerSummary
from app.serializers import to_match

router = APIRouter(prefix="/organizer", tags=["organizer"])


@router.get("/summary", response_model=OrganizerSummary)
def get_summary(
    organizer_id: str,
    db: Database = Depends(get_db),
) -> OrganizerSummary:
    tournaments = list(db.tournaments.find({"organizer_id": organizer_id}))
    tournament_ids = [tournament["_id"] for tournament in tournaments]
    tournament_names = {
        tournament["_id"]: tournament["name"] for tournament in tournaments
    }

    if not tournament_ids:
        return OrganizerSummary(organizer_id=organizer_id)

    team_ids = {
        team_id
        for tournament in tournaments
        for team_id in tournament.get("team_ids", [])
    }
    teams = list(db.teams.find({"_id": {"$in": list(team_ids)}}))
    team_names = {team["_id"]: team["name"] for team in teams}
    player_ids = {
        member["player_id"]
        for team in teams
        for member in team.get("members", [])
        if member.get("player_id")
    }
    documents = list(db.matches.find({"tournament_id": {"$in": tournament_ids}}))
    upcoming = [
        OrganizerMatchItem(
            **to_match(document).model_dump(),
            tournament_name=tournament_names.get(document["tournament_id"], "Torneo"),
            home_team_name=team_names.get(document.get("home_team_id")),
            away_team_name=team_names.get(document.get("away_team_id")),
        )
        for document in documents
        if document.get("status") == "scheduled"
        and document.get("date")
        and document.get("time")
    ]
    upcoming.sort(key=lambda item: (item.date.isoformat(), item.time or "99:99"))

    return OrganizerSummary(
        organizer_id=organizer_id,
        tournaments=len(tournaments),
        teams=len(team_ids),
        players=len(player_ids),
        matches=len(documents),
        upcoming=upcoming[:5],
    )
