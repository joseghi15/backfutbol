from pymongo.database import Database

from app.schemas.lineup import MatchLineup
from app.schemas.match import Match
from app.schemas.player import Player
from app.schemas.team import Team, TeamDetail, TeamMember
from app.schemas.tournament import Tournament, TournamentDetail


def to_player(document: dict) -> Player:
    return Player(
        id=document["_id"],
        tag=document["tag"],
        first_name=document["first_name"],
        last_name=document["last_name"],
        name=document["name"],
        position=document["position"],
        role=document["role"],
        is_ghost=document["is_ghost"],
        cedula=document.get("cedula"),
        phone=document.get("phone"),
        elo=document.get("elo", 1000),
        stats=document.get("stats", {}),
        created_at=document["created_at"],
    )


def to_team(document: dict) -> Team:
    return Team(
        id=document["_id"],
        code=document["code"],
        name=document["name"],
        captain_name=document["captain_name"],
        initials=document["initials"],
        members=[TeamMember(**member) for member in document.get("members", [])],
        created_at=document["created_at"],
    )


def to_team_detail(document: dict, db: Database) -> TeamDetail:
    team = to_team(document)
    member_ids = [member.player_id for member in team.members]
    player_documents = {
        player["_id"]: player
        for player in db.players.find({"_id": {"$in": member_ids}})
    }
    players = [
        to_player(player_documents[member_id])
        for member_id in member_ids
        if member_id in player_documents
    ]

    return TeamDetail(**team.model_dump(), players=players)


def to_tournament(document: dict) -> Tournament:
    return Tournament(
        id=document["_id"],
        name=document["name"],
        organizer_id=document["organizer_id"],
        format=document["format"],
        modality=document["modality"],
        teams_count=document["teams_count"],
        surface=document["surface"],
        start_date=document.get("start_date"),
        end_date=document.get("end_date"),
        min_players=document["min_players"],
        main_venue=document.get("main_venue"),
        status=document["status"],
        registration_closed=document.get("registration_closed", False),
        team_ids=document.get("team_ids", []),
        created_at=document["created_at"],
        updated_at=document["updated_at"],
    )


def to_tournament_detail(document: dict, db: Database) -> TournamentDetail:
    tournament = to_tournament(document)
    team_documents = list(db.teams.find({"_id": {"$in": tournament.team_ids}}))
    teams = [to_team(team) for team in team_documents]

    return TournamentDetail(**tournament.model_dump(), teams=teams)


def to_match(document: dict) -> Match:
    return Match(
        id=document["_id"],
        tournament_id=document["tournament_id"],
        stage=document["stage"],
        round_label=document.get("round_label"),
        home_team_id=document.get("home_team_id"),
        away_team_id=document.get("away_team_id"),
        home_label=document.get("home_label"),
        away_label=document.get("away_label"),
        date=document.get("date"),
        time=document.get("time"),
        venue=document.get("venue"),
        status=document["status"],
        created_at=document["created_at"],
        updated_at=document["updated_at"],
    )


def to_lineup(document: dict) -> MatchLineup:
    return MatchLineup(
        id=document["_id"],
        match_id=document["match_id"],
        tournament_id=document["tournament_id"],
        home_team_id=document["home_team_id"],
        away_team_id=document["away_team_id"],
        home=document["home"],
        away=document["away"],
        confirmed=document["confirmed"],
        created_at=document["created_at"],
        updated_at=document["updated_at"],
    )
