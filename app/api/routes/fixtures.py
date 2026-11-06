import random
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException
from pymongo.database import Database

from app.core.ids import new_id
from app.db.mongo import get_db
from app.schemas.match import (
    Match,
    MatchCreate,
    MatchUpdate,
    OrganizerMatchItem,
)
from app.serializers import to_match

router = APIRouter(tags=["fixtures"])

STAGE_ORDER = {
    "round_of_16": 0,
    "quarter": 1,
    "semi": 2,
    "final": 3,
    "league": 0,
}


def build_round_robin(team_ids: list[str]) -> list[list[tuple[str, str]]]:
    teams: list[str | None] = list(team_ids)

    if len(teams) % 2 == 1:
        teams.append(None)

    rounds: list[list[tuple[str, str]]] = []
    total = len(teams)

    for round_index in range(total - 1):
        pairs: list[tuple[str, str]] = []

        for index in range(total // 2):
            home = teams[index]
            away = teams[total - 1 - index]

            if home is None or away is None:
                continue

            if (round_index + index) % 2 == 0:
                pairs.append((home, away))
            else:
                pairs.append((away, home))

        rounds.append(pairs)
        teams = [teams[0], teams[-1], *teams[1:-1]]

    return rounds


def build_cup_documents(
    tournament: dict,
    team_ids: list[str],
) -> list[dict]:
    count = len(team_ids)

    if count not in {4, 8, 16}:
        raise HTTPException(
            status_code=422,
            detail="La copa requiere 4, 8 o 16 equipos.",
        )

    shuffled = random.sample(team_ids, count)

    if count == 16:
        rounds = [
            ("Octavos", "round_of_16", 8),
            ("Cuartos", "quarter", 4),
            ("Semifinal", "semi", 2),
            ("Final", "final", 1),
        ]
    elif count == 8:
        rounds = [
            ("Cuartos", "quarter", 4),
            ("Semifinal", "semi", 2),
            ("Final", "final", 1),
        ]
    else:
        rounds = [
            ("Semifinal", "semi", 2),
            ("Final", "final", 1),
        ]

    now = datetime.now(UTC)
    documents: list[dict] = []
    previous_labels: list[str] | None = None

    for label, stage, matches_count in rounds:
        if previous_labels is None:
            for index in range(matches_count):
                documents.append(
                    {
                        "_id": new_id("mat"),
                        "tournament_id": tournament["_id"],
                        "stage": stage,
                        "round_label": f"{label} {index + 1}",
                        "home_team_id": shuffled[index * 2],
                        "away_team_id": shuffled[index * 2 + 1],
                        "home_label": None,
                        "away_label": None,
                        "date": None,
                        "time": None,
                        "venue": tournament.get("main_venue"),
                        "status": "scheduled",
                        "created_at": now,
                        "updated_at": now,
                    }
                )
        else:
            for index in range(matches_count):
                home_label = (
                    previous_labels[index * 2]
                    if index * 2 < len(previous_labels)
                    else None
                )
                away_label = (
                    previous_labels[index * 2 + 1]
                    if index * 2 + 1 < len(previous_labels)
                    else None
                )

                documents.append(
                    {
                        "_id": new_id("mat"),
                        "tournament_id": tournament["_id"],
                        "stage": stage,
                        "round_label": f"{label} {index + 1}",
                        "home_team_id": None,
                        "away_team_id": None,
                        "home_label": home_label,
                        "away_label": away_label,
                        "date": None,
                        "time": None,
                        "venue": tournament.get("main_venue"),
                        "status": "scheduled",
                        "created_at": now,
                        "updated_at": now,
                    }
                )

        previous_labels = [
            f"Ganador {label} {index + 1}" for index in range(matches_count)
        ]

    return documents


def find_collision(
    db: Database,
    tournament_id: str,
    match_date: date,
    match_time: str,
    venue: str | None,
    home_team_id: str | None,
    away_team_id: str | None,
    exclude_id: str | None = None,
) -> str | None:
    query: dict = {
        "tournament_id": tournament_id,
        "date": match_date.isoformat(),
        "time": match_time,
    }

    if exclude_id:
        query["_id"] = {"$ne": exclude_id}

    team_ids = [
        team_id for team_id in (home_team_id, away_team_id) if team_id is not None
    ]

    if team_ids:
        team_conflict = db.matches.find_one(
            {
                **query,
                "$or": [
                    {"home_team_id": {"$in": team_ids}},
                    {"away_team_id": {"$in": team_ids}},
                ],
            }
        )

        if team_conflict:
            return "Uno de los equipos ya tiene un partido en ese horario."

    if venue:
        venue_conflict = db.matches.find_one({**query, "venue": venue})

        if venue_conflict:
            return "La cancha ya está ocupada en ese horario."

    return None


def sorted_matches(documents) -> list[Match]:
    matches = [to_match(document) for document in documents]
    matches.sort(
        key=lambda match: (
            match.date.isoformat() if match.date else "9999-12-31",
            match.time or "99:99",
            STAGE_ORDER.get(match.stage, 99),
            match.round_label or "",
        )
    )
    return matches


@router.get(
    "/organizer/matches",
    response_model=list[OrganizerMatchItem],
)
def list_organizer_matches(
    organizer_id: str,
    db: Database = Depends(get_db),
) -> list[OrganizerMatchItem]:
    tournaments = list(db.tournaments.find({"organizer_id": organizer_id}))
    tournament_names = {
        tournament["_id"]: tournament["name"] for tournament in tournaments
    }
    tournament_ids = list(tournament_names)

    if not tournament_ids:
        return []

    documents = list(db.matches.find({"tournament_id": {"$in": tournament_ids}}))
    team_ids = {
        team_id
        for document in documents
        for team_id in (
            document.get("home_team_id"),
            document.get("away_team_id"),
        )
        if team_id
    }
    team_names = {
        team["_id"]: team["name"]
        for team in db.teams.find({"_id": {"$in": list(team_ids)}})
    }
    items = [
        OrganizerMatchItem(
            **to_match(document).model_dump(),
            tournament_name=tournament_names.get(document["tournament_id"], "Torneo"),
            home_team_name=team_names.get(document.get("home_team_id")),
            away_team_name=team_names.get(document.get("away_team_id")),
        )
        for document in documents
    ]
    items.sort(
        key=lambda item: (
            item.date.isoformat() if item.date else "9999-12-31",
            item.time or "99:99",
        )
    )
    return items


@router.get("/tournaments/{tournament_id}/matches", response_model=list[Match])
def list_matches(
    tournament_id: str,
    db: Database = Depends(get_db),
) -> list[Match]:
    if not db.tournaments.find_one({"_id": tournament_id}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Torneo no encontrado.")

    return sorted_matches(db.matches.find({"tournament_id": tournament_id}))


@router.post(
    "/tournaments/{tournament_id}/fixture/generate",
    response_model=list[Match],
)
def generate_fixture(
    tournament_id: str,
    db: Database = Depends(get_db),
) -> list[Match]:
    tournament = db.tournaments.find_one({"_id": tournament_id})

    if not tournament:
        raise HTTPException(status_code=404, detail="Torneo no encontrado.")

    if not tournament.get("registration_closed"):
        raise HTTPException(
            status_code=409,
            detail="Cerrá la inscripción antes de generar el calendario.",
        )

    if db.matches.find_one({"tournament_id": tournament_id}, {"_id": 1}):
        raise HTTPException(
            status_code=409,
            detail="El torneo ya tiene partidos generados.",
        )

    team_ids = tournament.get("team_ids", [])

    if len(team_ids) < 2:
        raise HTTPException(
            status_code=409,
            detail="El torneo necesita al menos 2 equipos.",
        )

    if tournament["format"] == "copa":
        documents = build_cup_documents(tournament, team_ids)
    else:
        now = datetime.now(UTC)
        documents = []
        rounds = build_round_robin(team_ids)

        for round_index, pairs in enumerate(rounds, start=1):
            for home_team_id, away_team_id in pairs:
                documents.append(
                    {
                        "_id": new_id("mat"),
                        "tournament_id": tournament_id,
                        "stage": "league",
                        "round_label": f"Fecha {round_index}",
                        "home_team_id": home_team_id,
                        "away_team_id": away_team_id,
                        "home_label": None,
                        "away_label": None,
                        "date": None,
                        "time": None,
                        "venue": tournament.get("main_venue"),
                        "status": "scheduled",
                        "created_at": now,
                        "updated_at": now,
                    }
                )

    if documents:
        db.matches.insert_many(documents)

    return sorted_matches(db.matches.find({"tournament_id": tournament_id}))


@router.post(
    "/tournaments/{tournament_id}/matches",
    response_model=Match,
    status_code=201,
)
def create_match(
    tournament_id: str,
    payload: MatchCreate,
    db: Database = Depends(get_db),
) -> Match:
    tournament = db.tournaments.find_one({"_id": tournament_id})

    if not tournament:
        raise HTTPException(status_code=404, detail="Torneo no encontrado.")

    if not tournament.get("registration_closed"):
        raise HTTPException(
            status_code=409,
            detail="Cerrá la inscripción antes de cargar partidos.",
        )

    if payload.home_team_id == payload.away_team_id:
        raise HTTPException(
            status_code=422,
            detail="El equipo local y el visitante deben ser distintos.",
        )

    team_ids = set(tournament.get("team_ids", []))

    if payload.home_team_id not in team_ids or payload.away_team_id not in team_ids:
        raise HTTPException(
            status_code=422,
            detail="Los dos equipos deben estar inscriptos en el torneo.",
        )

    duplicate = db.matches.find_one(
        {
            "tournament_id": tournament_id,
            "home_team_id": payload.home_team_id,
            "away_team_id": payload.away_team_id,
            "stage": payload.stage,
        },
        {"_id": 1},
    )

    if duplicate:
        raise HTTPException(
            status_code=409,
            detail="Ese partido ya existe en el calendario.",
        )

    if payload.date and payload.time:
        collision = find_collision(
            db,
            tournament_id,
            payload.date,
            payload.time,
            payload.venue or tournament.get("main_venue"),
            payload.home_team_id,
            payload.away_team_id,
        )

        if collision:
            raise HTTPException(status_code=409, detail=collision)

    now = datetime.now(UTC)
    document = {
        "_id": new_id("mat"),
        "tournament_id": tournament_id,
        "stage": payload.stage,
        "round_label": payload.round_label or "Partido manual",
        "home_team_id": payload.home_team_id,
        "away_team_id": payload.away_team_id,
        "home_label": None,
        "away_label": None,
        "date": payload.date.isoformat() if payload.date else None,
        "time": payload.time,
        "venue": payload.venue or tournament.get("main_venue"),
        "status": "scheduled",
        "created_at": now,
        "updated_at": now,
    }

    db.matches.insert_one(document)
    return to_match(document)


@router.post("/matches/{match_id}/start", response_model=Match)
def start_match(
    match_id: str,
    db: Database = Depends(get_db),
) -> Match:
    document = db.matches.find_one({"_id": match_id})

    if not document:
        raise HTTPException(status_code=404, detail="Partido no encontrado.")

    tournament = db.tournaments.find_one({"_id": document["tournament_id"]})

    if not tournament or tournament.get("status") != "in_progress":
        raise HTTPException(
            status_code=409,
            detail="El torneo debe estar en curso para iniciar el partido.",
        )

    lineup = db.match_lineups.find_one({"match_id": match_id})

    if not lineup or not lineup.get("confirmed"):
        raise HTTPException(
            status_code=409,
            detail="Confirmá las alineaciones antes de iniciar el partido.",
        )

    db.matches.update_one(
        {"_id": match_id},
        {
            "$set": {
                "status": "in_progress",
                "updated_at": datetime.now(UTC),
            }
        },
    )

    updated = db.matches.find_one({"_id": match_id})

    if not updated:
        raise HTTPException(status_code=404, detail="Partido no encontrado.")

    return to_match(updated)


@router.patch("/matches/{match_id}", response_model=Match)
def update_match(
    match_id: str,
    payload: MatchUpdate,
    db: Database = Depends(get_db),
) -> Match:
    document = db.matches.find_one({"_id": match_id})

    if not document:
        raise HTTPException(status_code=404, detail="Partido no encontrado.")

    updates = payload.model_dump(exclude_none=True)

    if not updates:
        return to_match(document)

    next_date = updates.get("date", document.get("date"))
    next_time = updates.get("time", document.get("time"))
    next_venue = updates.get("venue", document.get("venue"))

    if next_date and next_time:
        if isinstance(next_date, date):
            next_date = next_date.isoformat()

        collision = find_collision(
            db,
            document["tournament_id"],
            date.fromisoformat(next_date),
            next_time,
            next_venue,
            document.get("home_team_id"),
            document.get("away_team_id"),
            exclude_id=match_id,
        )

        if collision:
            raise HTTPException(status_code=409, detail=collision)

    if isinstance(updates.get("date"), date):
        updates["date"] = updates["date"].isoformat()

    updates["updated_at"] = datetime.now(UTC)
    db.matches.update_one({"_id": match_id}, {"$set": updates})

    updated = db.matches.find_one({"_id": match_id})

    if not updated:
        raise HTTPException(status_code=404, detail="Partido no encontrado.")

    return to_match(updated)
