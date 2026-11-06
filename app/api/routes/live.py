from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from pymongo.database import Database

from app.core.ids import new_id
from app.db.mongo import get_db
from app.schemas.live import (
    LiveClosePayload,
    OfflineSyncPayload,
    RegisterCardPayload,
    RegisterGoalPayload,
    RegisterSubstitutionPayload,
    SocialVerificationPayload,
    UpdatePlayerStatsPayload,
)

router = APIRouter(tags=["live"])


def format_clock(seconds: int) -> str:
    minutes, remainder = divmod(max(0, int(seconds)), 60)
    return f"{minutes:02d}:{remainder:02d}"


def get_snapshot(db: Database, match_id: str) -> dict[str, Any]:
    document = db.live_matches.find_one({"_id": match_id})

    if not document:
        raise HTTPException(status_code=404, detail="Partido en vivo no encontrado.")

    return document["data"]


def save_snapshot(
    db: Database,
    match_id: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    now = datetime.now(UTC)
    db.live_matches.update_one(
        {"_id": match_id},
        {
            "$set": {
                "match_id": match_id,
                "data": data,
                "updated_at": now,
            }
        },
        upsert=True,
    )

    phase = data.get("phase")
    match_status = "finished" if phase == "finished" else "in_progress"

    db.matches.update_one(
        {"_id": match_id},
        {
            "$set": {
                "status": match_status,
                "home_score": data.get("homeScore", 0),
                "away_score": data.get("awayScore", 0),
                "updated_at": now,
            }
        },
    )
    return data


def sync_scores(data: dict[str, Any]) -> None:
    lines = data.get("playerStats", [])

    if not lines:
        return

    data["homeScore"] = sum(
        int(line.get("goals", 0)) for line in lines if line.get("teamId") == "white"
    )
    data["awayScore"] = sum(
        int(line.get("goals", 0)) for line in lines if line.get("teamId") == "green"
    )


def prepend_event(data: dict[str, Any], event: dict[str, Any]) -> None:
    data["events"] = [event, *data.get("events", [])]


def find_line(data: dict[str, Any], player_id: str) -> dict[str, Any] | None:
    return next(
        (
            line
            for line in data.get("playerStats", [])
            if line.get("playerId") == player_id
        ),
        None,
    )


def rebuild_player_events(data: dict[str, Any], player_id: str) -> None:
    line = find_line(data, player_id)

    if not line:
        return

    others = [
        event
        for event in data.get("events", [])
        if event.get("playerId") != player_id or event.get("tone") == "swap"
    ]
    generated: list[dict[str, Any]] = []
    name = line.get("playerName", "Jugador")

    for _ in range(int(line.get("goals", 0))):
        generated.append(
            {
                "id": new_id("ev"),
                "minute": "PT",
                "title": f"Gol de {name}",
                "subtitle": "Ajuste de planilla",
                "tone": "goal",
                "playerId": player_id,
            }
        )

    for _ in range(int(line.get("yellowCards", 0))):
        generated.append(
            {
                "id": new_id("ev"),
                "minute": "PT",
                "title": f"Amarilla para {name}",
                "subtitle": "Ajuste de planilla",
                "tone": "card",
                "playerId": player_id,
            }
        )

    for _ in range(int(line.get("redCards", 0))):
        generated.append(
            {
                "id": new_id("ev"),
                "minute": "PT",
                "title": f"Roja para {name}",
                "subtitle": "Ajuste de planilla",
                "tone": "card",
                "playerId": player_id,
            }
        )

    data["events"] = [*generated, *others]


def apply_player_stats(
    db: Database,
    data: dict[str, Any],
    stored: dict[str, Any],
) -> None:
    applied = stored.get("appliedStats") or {}
    next_applied: dict[str, dict[str, int]] = dict(applied)
    keys = (
        "goals",
        "assists",
        "yellow_cards",
        "red_cards",
        "mvp",
        "matches_played",
    )

    for line in data.get("playerStats", []):
        player_id = line.get("playerId")

        if not player_id:
            continue

        if (
            int(line.get("minutesPlayed", 0)) <= 0
            and int(line.get("enteredAtMinute", 0)) < 0
        ):
            continue

        current = {
            "goals": int(line.get("goals", 0)),
            "assists": int(line.get("assists", 0)),
            "yellow_cards": int(line.get("yellowCards", 0)),
            "red_cards": int(line.get("redCards", 0)),
            "mvp": 1 if line.get("mvp") else 0,
            "matches_played": 1,
        }
        previous = applied.get(player_id, {})
        increments = {}

        for key in keys:
            delta = current[key] - int(previous.get(key, 0))

            if delta:
                increments[f"stats.{key}"] = delta

        if increments:
            db.players.update_one(
                {"_id": player_id},
                {"$inc": increments},
            )

        next_applied[player_id] = current

    data["appliedStats"] = next_applied


def apply_elo(db: Database, data: dict[str, Any]) -> None:
    home_score = int(data.get("homeScore", 0))
    away_score = int(data.get("awayScore", 0))

    for line in data.get("playerStats", []):
        player_id = line.get("playerId")

        if not player_id:
            continue

        if (
            int(line.get("minutesPlayed", 0)) <= 0
            and int(line.get("enteredAtMinute", 0)) < 0
        ):
            continue

        team = line.get("teamId")
        goals = int(line.get("goals", 0))
        assists = int(line.get("assists", 0))
        performance = goals * 6 + assists * 4 + (15 if line.get("mvp") else 0)

        if home_score == away_score:
            delta = min(30, 5 + performance // 2)
        else:
            winner = "white" if home_score > away_score else "green"
            if team == winner:
                delta = min(45, 20 + performance)
            else:
                delta = -min(20, 3 + performance // 2)

        player = db.players.find_one({"_id": player_id}, {"elo": 1})

        if not player:
            continue

        current = int(player.get("elo", 1000))
        db.players.update_one(
            {"_id": player_id},
            {"$set": {"elo": max(100, current + delta)}},
        )


@router.get("/matches/{match_id}/live")
def read_live_match(
    match_id: str,
    db: Database = Depends(get_db),
) -> dict[str, Any]:
    return get_snapshot(db, match_id)


@router.put("/matches/{match_id}/live")
def update_live_match(
    match_id: str,
    payload: dict[str, Any] = Body(...),
    db: Database = Depends(get_db),
) -> dict[str, Any]:
    if not db.matches.find_one({"_id": match_id}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Partido no encontrado.")

    return save_snapshot(db, match_id, payload)


@router.post("/matches/{match_id}/live/goals")
def register_goal(
    match_id: str,
    payload: RegisterGoalPayload,
    db: Database = Depends(get_db),
) -> dict[str, Any]:
    data = get_snapshot(db, match_id)
    scorer = next(
        (
            player
            for player in data.get("onPitch", [])
            if player.get("id") == payload.scorerId
        ),
        None,
    )
    scorer_stats = find_line(data, payload.scorerId)

    if not scorer:
        return data

    if scorer_stats and int(scorer_stats.get("redCards", 0)) > 0:
        return data

    if payload.team == "white":
        data["homeScore"] = int(data.get("homeScore", 0)) + 1
    else:
        data["awayScore"] = int(data.get("awayScore", 0)) + 1

    scorer["goals"] = int(scorer.get("goals", 0)) + 1

    if scorer_stats:
        scorer_stats["goals"] = int(scorer_stats.get("goals", 0)) + 1

    assist_player = None

    if payload.assistPlayerId:
        assist_player = next(
            (
                player
                for player in data.get("onPitch", [])
                if player.get("id") == payload.assistPlayerId
            ),
            None,
        )
        assist_stats = find_line(data, payload.assistPlayerId)

        if assist_stats:
            assist_stats["assists"] = int(assist_stats.get("assists", 0)) + 1

    score_text = f"{data.get('homeScore', 0)} – {data.get('awayScore', 0)}"
    subtitle = (
        f"Asistencia de {assist_player.get('name', 'Jugador')} · {score_text}"
        if assist_player
        else f"{payload.goalType or 'Jugada colectiva'} · {score_text}"
    )
    title = f"Gol de {scorer.get('name', 'Jugador')}"
    minute = payload.minute or f"{int(data.get('elapsedSeconds', 0)) // 60}'"

    prepend_event(
        data,
        {
            "id": new_id("ev"),
            "minute": minute,
            "title": title,
            "subtitle": subtitle,
            "tone": "goal",
            "playerId": scorer.get("id"),
        },
    )

    if data.get("syncState") == "offline":
        now = datetime.now()
        timestamp = now.strftime("%H:%M:%S")
        data["offlineQueue"] = [
            {
                "id": new_id("q"),
                "timestamp": timestamp,
                "description": f"{title} ({score_text})",
                "payload": payload.model_dump(),
            },
            *data.get("offlineQueue", []),
        ]
        data["lastSyncedAt"] = (
            f"Sin señal · {len(data['offlineQueue'])} evento(s) en cola local"
        )
    else:
        data["syncState"] = "synced"
        data["lastSyncedAt"] = "Sincronizado al instante"

    return save_snapshot(db, match_id, data)


@router.post("/matches/{match_id}/live/cards")
def register_card(
    match_id: str,
    payload: RegisterCardPayload,
    db: Database = Depends(get_db),
) -> dict[str, Any]:
    data = get_snapshot(db, match_id)
    player = next(
        (
            item
            for item in data.get("onPitch", [])
            if item.get("id") == payload.playerId
        ),
        None,
    )
    stats = find_line(data, payload.playerId)

    if not player or not stats or int(stats.get("redCards", 0)) > 0:
        return data

    team_name = (
        data.get("homeTeamName", "Local")
        if player.get("team") == "white"
        else data.get("awayTeamName", "Visitante")
    )
    title = f"Amarilla para {player.get('name', 'Jugador')}"
    subtitle = team_name

    if payload.cardType == "yellow":
        stats["yellowCards"] = int(stats.get("yellowCards", 0)) + 1

        if int(stats["yellowCards"]) >= 2:
            stats["redCards"] = 1
            title = f"Doble amarilla · {player.get('name', 'Jugador')}"
            subtitle = f"{team_name} · Expulsado"
    else:
        stats["redCards"] = int(stats.get("redCards", 0)) + 1
        title = f"Roja para {player.get('name', 'Jugador')}"
        subtitle = f"{team_name} · Expulsado"

    prepend_event(
        data,
        {
            "id": new_id("ev"),
            "minute": payload.minute or "0'",
            "title": title,
            "subtitle": subtitle,
            "tone": "card",
            "playerId": player.get("id"),
        },
    )

    return save_snapshot(db, match_id, data)


@router.post("/matches/{match_id}/live/substitutions")
def register_substitution(
    match_id: str,
    payload: RegisterSubstitutionPayload,
    db: Database = Depends(get_db),
) -> dict[str, Any]:
    data = get_snapshot(db, match_id)
    out_player = next(
        (
            player
            for player in data.get("onPitch", [])
            if player.get("id") == payload.outPlayerId
        ),
        None,
    )
    in_player = next(
        (
            player
            for player in data.get("bench", [])
            if player.get("id") == payload.inPlayerId
        ),
        None,
    )

    if (
        not out_player
        or not in_player
        or out_player.get("team") != in_player.get("team")
    ):
        return data

    out_stats = find_line(data, payload.outPlayerId)
    in_stats = find_line(data, payload.inPlayerId)

    if (
        not out_stats
        or not in_stats
        or int(out_stats.get("enteredAtMinute", -1)) < 0
        or int(out_stats.get("redCards", 0)) > 0
    ):
        return data

    minute = max(0, int(payload.minuteNumber))
    out_stats["minutesPlayed"] = int(out_stats.get("minutesPlayed", 0)) + max(
        0,
        minute - int(out_stats.get("enteredAtMinute", 0)),
    )
    out_stats["enteredAtMinute"] = -1
    in_stats["minutesPlayed"] = 0
    in_stats["enteredAtMinute"] = minute

    data["onPitch"] = [
        {
            "id": in_player.get("id"),
            "initials": in_player.get("initials"),
            "name": in_player.get("name"),
            "position": in_player.get("position"),
            "team": in_player.get("team"),
            "goals": 0,
        }
        if player.get("id") == out_player.get("id")
        else player
        for player in data.get("onPitch", [])
    ]
    data["bench"] = [
        player
        for player in data.get("bench", [])
        if player.get("id") != in_player.get("id")
    ]

    team_name = (
        data.get("homeTeamName", "Local")
        if out_player.get("team") == "white"
        else data.get("awayTeamName", "Visitante")
    )

    prepend_event(
        data,
        {
            "id": new_id("ev"),
            "minute": payload.minute or "0'",
            "title": f"Cambio en {team_name}",
            "subtitle": (
                f"{out_player.get('name', 'Jugador')} → "
                f"{in_player.get('name', 'Jugador')}"
            ),
            "tone": "swap",
        },
    )

    return save_snapshot(db, match_id, data)


@router.put("/matches/{match_id}/live/planilla/{player_id}")
def update_player_stats(
    match_id: str,
    player_id: str,
    payload: UpdatePlayerStatsPayload,
    db: Database = Depends(get_db),
) -> dict[str, Any]:
    data = get_snapshot(db, match_id)
    line = find_line(data, player_id)

    if not line or data.get("sheetClosed"):
        return data

    previous = {
        "goals": int(line.get("goals", 0)),
        "yellowCards": int(line.get("yellowCards", 0)),
        "redCards": int(line.get("redCards", 0)),
    }
    line["goals"] = max(0, int(payload.goals))
    line["assists"] = max(0, int(payload.assists))
    line["yellowCards"] = max(0, int(payload.yellowCards))
    line["redCards"] = max(0, int(payload.redCards))

    on_pitch_player = next(
        (player for player in data.get("onPitch", []) if player.get("id") == player_id),
        None,
    )

    if on_pitch_player:
        on_pitch_player["goals"] = line["goals"]

    sync_scores(data)

    if (
        previous["goals"] != line["goals"]
        or previous["yellowCards"] != line["yellowCards"]
        or previous["redCards"] != line["redCards"]
    ):
        rebuild_player_events(data, player_id)

    return save_snapshot(db, match_id, data)


@router.post("/matches/{match_id}/live/offline-sync")
def update_offline_sync(
    match_id: str,
    payload: OfflineSyncPayload,
    db: Database = Depends(get_db),
) -> dict[str, Any]:
    data = get_snapshot(db, match_id)

    if payload.action == "toggle_offline":
        if data.get("syncState") == "offline":
            queue = data.get("offlineQueue", [])
            data["syncState"] = "pending" if queue else "synced"
            data["lastSyncedAt"] = (
                f"Conexión recuperada · {len(queue)} pendiente(s) por enviar"
                if queue
                else "Conexión recuperada · Sincronizado"
            )
        else:
            data["syncState"] = "offline"
            data["lastSyncedAt"] = "Modo cancha sin señal · Guardando en cola local"
    else:
        count = len(data.get("offlineQueue", []))
        data["offlineQueue"] = []
        data["syncState"] = "synced"
        data["lastSyncedAt"] = (
            f"✓ {count} evento(s) sincronizados sin duplicados"
            if count > 0
            else "✓ Planilla sincronizada al día"
        )

    return save_snapshot(db, match_id, data)


@router.post("/matches/{match_id}/live/social-verification")
def verify_player_stat_line(
    match_id: str,
    payload: SocialVerificationPayload,
    db: Database = Depends(get_db),
) -> dict[str, Any]:
    data = get_snapshot(db, match_id)
    verification = data.setdefault(
        "socialVerification",
        {
            "quorumPercent": 0,
            "requiredQuorumPercent": 70,
            "verified": False,
            "confirmedVoters": 0,
            "totalVoters": 0,
            "organizerReviewOpen": False,
            "lines": [],
        },
    )
    line = next(
        (
            item
            for item in verification.get("lines", [])
            if item.get("playerId") == payload.playerId
        ),
        None,
    )

    if line:
        line["status"] = payload.decision

        if payload.decision == "disputed":
            line["disputeNote"] = (
                payload.disputeNote or ""
            ).strip() or "Disputa enviada a revisión del organizador"

    confirmed = len(
        [
            item
            for item in verification.get("lines", [])
            if item.get("status") == "confirmed"
        ]
    )
    disputed = len(
        [
            item
            for item in verification.get("lines", [])
            if item.get("status") == "disputed"
        ]
    )
    total_voters = max(1, int(verification.get("totalVoters", 1)))
    verification["confirmedVoters"] = min(total_voters, 8 + confirmed)
    verification["quorumPercent"] = round(
        verification["confirmedVoters"] / total_voters * 100
    )
    verification["organizerReviewOpen"] = disputed > 0
    verification["verified"] = (
        verification["quorumPercent"]
        >= int(verification.get("requiredQuorumPercent", 70))
        and disputed == 0
    )

    return save_snapshot(db, match_id, data)


def advance_cup_winner(
    db: Database,
    match_id: str,
    data: dict[str, Any],
) -> None:
    match = db.matches.find_one({"_id": match_id})

    if not match:
        return

    tournament = db.tournaments.find_one(
        {"_id": match["tournament_id"]},
        {"format": 1},
    )

    if not tournament or tournament.get("format") != "copa":
        return

    round_label = match.get("round_label") or ""
    home_score = int(data.get("homeScore", 0))
    away_score = int(data.get("awayScore", 0))

    if not round_label or home_score == away_score:
        return

    winner_id = (
        match.get("home_team_id")
        if home_score > away_score
        else match.get("away_team_id")
    )

    if not winner_id:
        return

    winner_label = f"Ganador {round_label}"
    next_matches = db.matches.find(
        {
            "tournament_id": match["tournament_id"],
            "_id": {"$ne": match_id},
            "$or": [
                {"home_label": winner_label},
                {"away_label": winner_label},
            ],
        }
    )
    now = datetime.now(UTC)

    for next_match in next_matches:
        updates: dict[str, Any] = {"updated_at": now}

        if next_match.get("home_label") == winner_label:
            updates["home_team_id"] = winner_id

        if next_match.get("away_label") == winner_label:
            updates["away_team_id"] = winner_id

        db.matches.update_one({"_id": next_match["_id"]}, {"$set": updates})


@router.post("/matches/{match_id}/live/close")
def close_live_match(
    match_id: str,
    payload: LiveClosePayload,
    db: Database = Depends(get_db),
) -> dict[str, Any]:
    document = db.live_matches.find_one({"_id": match_id})

    if not document:
        raise HTTPException(status_code=404, detail="Partido en vivo no encontrado.")

    stored = document["data"]
    data = payload.snapshot or stored
    was_closed = bool(stored.get("sheetClosed"))
    elo_applied = bool(stored.get("eloApplied")) or bool(data.get("eloApplied"))

    sync_scores(data)

    for line in data.get("playerStats", []):
        line["mvp"] = line.get("playerId") == payload.mvp_player_id

    mvp_name = next(
        (
            line.get("playerName", "Jugador")
            for line in data.get("playerStats", [])
            if line.get("mvp")
        ),
        "Jugador",
    )

    data["sheetClosed"] = True
    data["phase"] = "finished"
    data["periodLabel"] = "Finalizado"
    data["clock"] = format_clock(int(data.get("elapsedSeconds", 0)))
    data["finalized"] = True

    apply_player_stats(db, data, stored)

    if not elo_applied:
        apply_elo(db, data)
        data["eloApplied"] = True

    if not was_closed:
        prepend_event(
            data,
            {
                "id": new_id("ev"),
                "minute": f"{int(data.get('elapsedSeconds', 0)) // 60}'",
                "title": "Planilla cerrada",
                "subtitle": f"MVP: {mvp_name}",
                "tone": "swap",
            },
        )

    save_snapshot(db, match_id, data)
    advance_cup_winner(db, match_id, data)
    return data


@router.post("/matches/{match_id}/live/reopen")
def reopen_live_match(
    match_id: str,
    db: Database = Depends(get_db),
) -> dict[str, Any]:
    data = get_snapshot(db, match_id)
    was_closed = bool(data.get("sheetClosed"))
    data["sheetClosed"] = False
    data["phase"] = "finished"
    data["periodLabel"] = "Finalizado · Reabierto"

    if was_closed:
        prepend_event(
            data,
            {
                "id": new_id("ev"),
                "minute": "PT",
                "title": "Planilla reabierta",
                "subtitle": "Edición habilitada",
                "tone": "swap",
            },
        )

    save_snapshot(db, match_id, data)
    return data
