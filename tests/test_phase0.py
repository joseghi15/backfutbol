from fastapi.testclient import TestClient


def create_player(
    client: TestClient,
    first_name: str,
    last_name: str,
    cedula: str | None = None,
    phone: str | None = None,
    is_ghost: bool = False,
) -> dict:
    response = client.post(
        "/api/v1/players",
        json={
            "first_name": first_name,
            "last_name": last_name,
            "position": "Mediocampista",
            "cedula": cedula,
            "phone": phone,
            "is_ghost": is_ghost,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_team(client: TestClient, name: str, code: str | None = None) -> dict:
    response = client.post(
        "/api/v1/teams",
        json={
            "name": name,
            "captain_name": "Capitán de prueba",
            "code": code,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def add_player_to_team(
    client: TestClient,
    team_id: str,
    player_id: str,
    jersey_number: int,
) -> dict:
    response = client.post(
        f"/api/v1/teams/{team_id}/players",
        json={"player_id": player_id, "jersey_number": jersey_number},
    )
    assert response.status_code == 200, response.text
    return response.json()


def create_tournament(
    client: TestClient,
    organizer_id: str,
    name: str,
    modality: str = "Fútbol 5",
    teams_count: int = 8,
    format: str = "liga",
    min_players: int = 5,
) -> dict:
    response = client.post(
        "/api/v1/tournaments",
        json={
            "name": name,
            "organizer_id": organizer_id,
            "format": format,
            "modality": modality,
            "teams_count": teams_count,
            "surface": "Sintético",
            "min_players": min_players,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def add_team_to_tournament(
    client: TestClient,
    tournament_id: str,
    team_id: str,
) -> dict:
    response = client.post(
        f"/api/v1/tournaments/{tournament_id}/teams",
        json={"team_id": team_id},
    )
    assert response.status_code == 200, response.text
    return response.json()


def build_team_with_players(
    client: TestClient,
    name: str,
    count: int,
    offset: int,
) -> tuple[dict, list[dict]]:
    team = create_team(client, name)
    players = []

    for index in range(count):
        player = create_player(
            client,
            f"Jugador {offset + index}",
            name,
        )
        add_player_to_team(client, team["id"], player["id"], index + 1)
        players.append(player)

    return team, players


def test_ghost_requires_cedula_or_phone(client: TestClient) -> None:
    response = client.post(
        "/api/v1/players",
        json={
            "first_name": "Fantasma",
            "last_name": "Sin datos",
            "position": "Defensor",
            "is_ghost": True,
        },
    )

    assert response.status_code == 422


def test_player_search_by_tag_and_name(client: TestClient) -> None:
    player = create_player(
        client,
        "Martín",
        "Díaz",
        cedula="27450118",
        is_ghost=True,
    )

    by_tag = client.get(
        "/api/v1/players/search",
        params={"q": player["tag"]},
    )
    by_name = client.get(
        "/api/v1/players/search",
        params={"q": "Martín"},
    )

    assert by_tag.status_code == 200
    assert by_tag.json()[0]["id"] == player["id"]
    assert by_name.status_code == 200
    assert any(item["id"] == player["id"] for item in by_name.json())


def test_duplicate_player_identity_is_rejected(client: TestClient) -> None:
    create_player(client, "Ana", "Pérez", cedula="12345678", is_ghost=True)

    response = client.post(
        "/api/v1/players",
        json={
            "first_name": "Otra",
            "last_name": "Persona",
            "position": "Arquero",
            "cedula": "12345678",
            "is_ghost": True,
        },
    )

    assert response.status_code == 409


def test_team_code_and_search(client: TestClient) -> None:
    team = create_team(client, "La Rabona FC")

    assert team["code"].startswith("EQ-")

    response = client.get(
        "/api/v1/teams/search",
        params={"q": team["code"]},
    )

    assert response.status_code == 200
    assert response.json()[0]["id"] == team["id"]


def test_team_roster_and_duplicate_player(client: TestClient) -> None:
    team, players = build_team_with_players(client, "Los Cuervos", 2, 0)

    detail = client.get(f"/api/v1/teams/{team['id']}")

    assert detail.status_code == 200
    assert len(detail.json()["players"]) == 2

    duplicate = client.post(
        f"/api/v1/teams/{team['id']}/players",
        json={"player_id": players[0]["id"], "jersey_number": 10},
    )

    assert duplicate.status_code == 409


def test_team_rejects_duplicate_jersey(client: TestClient) -> None:
    team = create_team(client, "Equipo Dorsales")
    player_one = create_player(client, "Uno", "Dorsal")
    player_two = create_player(client, "Dos", "Dorsal")

    add_player_to_team(client, team["id"], player_one["id"], 10)

    duplicate = client.post(
        f"/api/v1/teams/{team['id']}/players",
        json={"player_id": player_two["id"], "jersey_number": 10},
    )

    assert duplicate.status_code == 409


def test_tournament_flow_and_start_validation(client: TestClient) -> None:
    organizer_id = "org-1"
    tournament = create_tournament(
        client,
        organizer_id,
        "Liga de Prueba",
    )
    team_one, _ = build_team_with_players(client, "Equipo Uno", 5, 400)

    add_team_to_tournament(client, tournament["id"], team_one["id"])

    early_start = client.patch(
        f"/api/v1/tournaments/{tournament['id']}/status",
        json={"status": "in_progress"},
    )

    assert early_start.status_code == 409

    team_two, _ = build_team_with_players(client, "Equipo Dos", 5, 410)
    add_team_to_tournament(client, tournament["id"], team_two["id"])

    published = client.patch(
        f"/api/v1/tournaments/{tournament['id']}/status",
        json={"status": "published"},
    )
    start_without_close = client.patch(
        f"/api/v1/tournaments/{tournament['id']}/status",
        json={"status": "in_progress"},
    )
    closed = client.post(f"/api/v1/tournaments/{tournament['id']}/close-registration")
    start_without_calendar = client.patch(
        f"/api/v1/tournaments/{tournament['id']}/status",
        json={"status": "in_progress"},
    )
    generated = client.post(f"/api/v1/tournaments/{tournament['id']}/fixture/generate")
    start_without_dates = client.patch(
        f"/api/v1/tournaments/{tournament['id']}/status",
        json={"status": "in_progress"},
    )

    first_match = generated.json()[0]
    scheduled = client.patch(
        f"/api/v1/matches/{first_match['id']}",
        json={
            "date": "2026-11-12",
            "time": "18:00",
            "venue": "Cancha Central",
        },
    )
    started = client.patch(
        f"/api/v1/tournaments/{tournament['id']}/status",
        json={"status": "in_progress"},
    )

    assert published.status_code == 200
    assert start_without_close.status_code == 409
    assert closed.status_code == 200
    assert start_without_calendar.status_code == 409
    assert generated.status_code == 200
    assert start_without_dates.status_code == 409
    assert scheduled.status_code == 200
    assert started.status_code == 200
    assert started.json()["status"] == "in_progress"
    assert started.json()["registration_closed"] is True

    listed = client.get(
        "/api/v1/tournaments",
        params={"organizer_id": organizer_id},
    )

    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_tournament_min_players_matches_modality(client: TestClient) -> None:
    response = client.post(
        "/api/v1/tournaments",
        json={
            "name": "Liga F11 inválida",
            "organizer_id": "org-4",
            "format": "liga",
            "modality": "Fútbol 11",
            "teams_count": 8,
            "min_players": 5,
        },
    )

    assert response.status_code == 422

    valid = client.post(
        "/api/v1/tournaments",
        json={
            "name": "Liga F11 válida",
            "organizer_id": "org-4",
            "format": "liga",
            "modality": "Fútbol 11",
            "teams_count": 8,
            "min_players": 11,
        },
    )

    assert valid.status_code == 201


def test_tournament_name_is_unique_per_organizer(client: TestClient) -> None:
    create_tournament(client, "org-2", "Copa Única")

    response = client.post(
        "/api/v1/tournaments",
        json={
            "name": "Copa Única",
            "organizer_id": "org-2",
            "format": "copa",
            "modality": "Fútbol 7",
            "teams_count": 8,
            "surface": "Sintético",
            "min_players": 7,
        },
    )

    assert response.status_code == 409


def test_tournament_team_quota_and_duplicate(client: TestClient) -> None:
    tournament = create_tournament(
        client,
        "org-5",
        "Copa de Equipos",
        teams_count=2,
    )
    team_one = create_team(client, "Equipo A")
    team_two = create_team(client, "Equipo B")
    team_three = create_team(client, "Equipo C")

    add_team_to_tournament(client, tournament["id"], team_one["id"])

    duplicate = client.post(
        f"/api/v1/tournaments/{tournament['id']}/teams",
        json={"team_id": team_one["id"]},
    )

    assert duplicate.status_code == 409

    add_team_to_tournament(client, tournament["id"], team_two["id"])

    over_quota = client.post(
        f"/api/v1/tournaments/{tournament['id']}/teams",
        json={"team_id": team_three["id"]},
    )

    assert over_quota.status_code == 409


def test_close_registration_requires_min_players(client: TestClient) -> None:
    tournament = create_tournament(
        client,
        "org-6",
        "Torneo Incompleto",
        min_players=5,
    )
    team_one, _ = build_team_with_players(client, "Corto A", 2, 100)
    team_two, _ = build_team_with_players(client, "Corto B", 2, 110)

    add_team_to_tournament(client, tournament["id"], team_one["id"])
    add_team_to_tournament(client, tournament["id"], team_two["id"])

    response = client.post(f"/api/v1/tournaments/{tournament['id']}/close-registration")

    assert response.status_code == 422


def test_generate_league_fixture_and_schedule_collision(
    client: TestClient,
) -> None:
    tournament = create_tournament(client, "org-7", "Liga ORG-05")
    teams = [
        build_team_with_players(client, f"Equipo Liga {index}", 5, 200 + index * 10)
        for index in range(3)
    ]

    for team, _ in teams:
        add_team_to_tournament(client, tournament["id"], team["id"])

    closed = client.post(f"/api/v1/tournaments/{tournament['id']}/close-registration")
    generated = client.post(f"/api/v1/tournaments/{tournament['id']}/fixture/generate")

    assert closed.status_code == 200
    assert closed.json()["registration_closed"] is True
    assert generated.status_code == 200
    assert len(generated.json()) == 3

    first, second = generated.json()[0], generated.json()[1]
    scheduled = client.patch(
        f"/api/v1/matches/{first['id']}",
        json={
            "date": "2026-11-10",
            "time": "18:00",
            "venue": "Cancha Central",
        },
    )

    assert scheduled.status_code == 200

    collision = client.patch(
        f"/api/v1/matches/{second['id']}",
        json={
            "date": "2026-11-10",
            "time": "18:00",
            "venue": "Cancha Central",
        },
    )

    assert collision.status_code == 409

    rescheduled = client.patch(
        f"/api/v1/matches/{second['id']}",
        json={
            "date": "2026-11-10",
            "time": "20:00",
            "venue": "Cancha Norte",
        },
    )

    assert rescheduled.status_code == 200


def test_generate_cup_bracket(client: TestClient) -> None:
    tournament = create_tournament(
        client,
        "org-8",
        "Copa ORG-05",
        format="copa",
    )
    teams = [
        build_team_with_players(client, f"Equipo Copa {index}", 5, 300 + index * 10)
        for index in range(4)
    ]

    for team, _ in teams:
        add_team_to_tournament(client, tournament["id"], team["id"])

    client.post(f"/api/v1/tournaments/{tournament['id']}/close-registration")
    generated = client.post(f"/api/v1/tournaments/{tournament['id']}/fixture/generate")

    assert generated.status_code == 200
    matches = generated.json()
    assert len(matches) == 3
    assert len([match for match in matches if match["stage"] == "semi"]) == 2

    final = next(match for match in matches if match["stage"] == "final")
    assert final["home_team_id"] is None
    assert final["home_label"] is not None


def test_start_match_requires_confirmed_lineup(client: TestClient) -> None:
    tournament = create_tournament(client, "org-9", "Liga ORG-07")
    home, home_players = build_team_with_players(client, "Local ORG07", 5, 500)
    away, away_players = build_team_with_players(client, "Visitante ORG07", 5, 510)

    add_team_to_tournament(client, tournament["id"], home["id"])
    add_team_to_tournament(client, tournament["id"], away["id"])
    client.post(f"/api/v1/tournaments/{tournament['id']}/close-registration")
    generated = client.post(f"/api/v1/tournaments/{tournament['id']}/fixture/generate")
    match = generated.json()[0]
    client.patch(
        f"/api/v1/matches/{match['id']}",
        json={
            "date": "2026-11-25",
            "time": "18:00",
            "venue": "Cancha Central",
        },
    )
    client.patch(
        f"/api/v1/tournaments/{tournament['id']}/status",
        json={"status": "in_progress"},
    )

    without_lineup = client.post(f"/api/v1/matches/{match['id']}/start")

    assert without_lineup.status_code == 409

    lineup = client.put(
        f"/api/v1/matches/{match['id']}/lineup",
        json={
            "tournament_id": tournament["id"],
            "home_team_id": home["id"],
            "away_team_id": away["id"],
            "home": {
                "formation": "2-2",
                "starters": [
                    {"player_id": player["id"], "position": "Mediocampista"}
                    for player in home_players
                ],
            },
            "away": {
                "formation": "2-2",
                "starters": [
                    {"player_id": player["id"], "position": "Mediocampista"}
                    for player in away_players
                ],
            },
            "confirmed": True,
        },
    )
    started = client.post(f"/api/v1/matches/{match['id']}/start")

    assert lineup.status_code == 200
    assert started.status_code == 200
    assert started.json()["status"] == "in_progress"


def test_tournament_player_stats(client: TestClient) -> None:
    tournament = create_tournament(client, "org-10", "Liga ORG-08")
    team, _ = build_team_with_players(client, "Equipo Stats", 2, 600)

    add_team_to_tournament(client, tournament["id"], team["id"])

    response = client.get(f"/api/v1/tournaments/{tournament['id']}/player-stats")

    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 2
    assert rows[0]["team_name"] == "Equipo Stats"
    assert rows[0]["goals"] == 0
    assert rows[0]["elo"] == 1000


def test_live_snapshot_persistence(client: TestClient, db) -> None:
    db.matches.insert_one(
        {
            "_id": "match-live-test",
            "tournament_id": "tournament-live-test",
            "stage": "league",
            "round_label": "Fecha 1",
            "home_team_id": "team-live-home",
            "away_team_id": "team-live-away",
            "status": "scheduled",
            "created_at": "2026-11-05T00:00:00Z",
            "updated_at": "2026-11-05T00:00:00Z",
        }
    )
    db.players.insert_one(
        {
            "_id": "p-live-test",
            "stats": {
                "goals": 0,
                "assists": 0,
                "yellow_cards": 0,
                "red_cards": 0,
                "mvp": 0,
                "matches_played": 0,
            },
        }
    )
    snapshot = {
        "matchId": "match-live-test",
        "headerSubtitle": "Liga · Fecha 1",
        "clock": "12:00",
        "periodLabel": "1er tiempo",
        "phase": "live",
        "period": 1,
        "elapsedSeconds": 720,
        "halfDurationSeconds": 1500,
        "sheetClosed": False,
        "homeTeamName": "Local",
        "awayTeamName": "Visitante",
        "homeScore": 2,
        "awayScore": 1,
        "onPitch": [],
        "bench": [],
        "playerStats": [
            {
                "playerId": "p-live-test",
                "goals": 1,
                "assists": 0,
                "yellowCards": 0,
                "redCards": 0,
                "mvp": False,
            }
        ],
        "stats": [],
        "events": [],
        "syncState": "synced",
        "lastSyncedAt": "Ahora",
        "offlineQueue": [],
        "socialVerification": {
            "quorumPercent": 0,
            "requiredQuorumPercent": 70,
            "verified": False,
            "confirmedVoters": 0,
            "totalVoters": 1,
            "organizerReviewOpen": False,
            "lines": [],
        },
    }

    saved = client.put(
        "/api/v1/matches/match-live-test/live",
        json=snapshot,
    )
    loaded = client.get("/api/v1/matches/match-live-test/live")
    closed = client.post(
        "/api/v1/matches/match-live-test/live/close",
        json={"mvp_player_id": "p-live-test", "snapshot": snapshot},
    )
    repeated = client.post(
        "/api/v1/matches/match-live-test/live/close",
        json={"mvp_player_id": "p-live-test", "snapshot": snapshot},
    )

    assert saved.status_code == 200
    assert loaded.status_code == 200
    assert loaded.json()["clock"] == "12:00"
    assert closed.status_code == 200
    assert closed.json()["sheetClosed"] is True
    assert repeated.status_code == 200

    player = db.players.find_one({"_id": "p-live-test"})
    match = db.matches.find_one({"_id": "match-live-test"})

    assert player["stats"]["goals"] == 1
    assert player["stats"]["matches_played"] == 1
    assert player["stats"]["mvp"] == 1
    assert match["status"] == "finished"


def test_organizer_matches_endpoint(client: TestClient, db) -> None:
    db.tournaments.insert_one(
        {
            "_id": "t-org-list",
            "name": "Liga Organizador",
            "organizer_id": "org-list",
        }
    )
    db.teams.insert_many(
        [
            {"_id": "team-org-a", "name": "Local Org", "code": "T-ORG-A"},
            {"_id": "team-org-b", "name": "Visitante Org", "code": "T-ORG-B"},
        ]
    )
    db.matches.insert_one(
        {
            "_id": "match-org-list",
            "tournament_id": "t-org-list",
            "stage": "league",
            "round_label": "Fecha 1",
            "home_team_id": "team-org-a",
            "away_team_id": "team-org-b",
            "status": "scheduled",
            "created_at": "2026-11-05T00:00:00Z",
            "updated_at": "2026-11-05T00:00:00Z",
        }
    )

    response = client.get(
        "/api/v1/organizer/matches",
        params={"organizer_id": "org-list"},
    )

    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["tournament_name"] == "Liga Organizador"
    assert rows[0]["home_team_name"] == "Local Org"
    assert rows[0]["away_team_name"] == "Visitante Org"


def test_lineup_validates_modality_and_team_membership(
    client: TestClient,
) -> None:
    tournament = create_tournament(
        client,
        "org-3",
        "Liga F5",
        modality="Fútbol 5",
    )
    home, home_players = build_team_with_players(client, "Local", 5, 10)
    away, away_players = build_team_with_players(client, "Visitante", 5, 20)

    add_team_to_tournament(client, tournament["id"], home["id"])
    add_team_to_tournament(client, tournament["id"], away["id"])

    invalid = client.put(
        "/api/v1/matches/match-1/lineup",
        json={
            "tournament_id": tournament["id"],
            "home_team_id": home["id"],
            "away_team_id": away["id"],
            "home": {
                "formation": "2-2",
                "starters": [
                    {"player_id": home_players[0]["id"], "position": "Arquero"}
                ],
            },
            "away": {
                "formation": "2-2",
                "starters": [
                    {"player_id": player["id"], "position": "Mediocampista"}
                    for player in away_players
                ],
            },
            "confirmed": True,
        },
    )

    assert invalid.status_code == 422

    valid = client.put(
        "/api/v1/matches/match-1/lineup",
        json={
            "tournament_id": tournament["id"],
            "home_team_id": home["id"],
            "away_team_id": away["id"],
            "home": {
                "formation": "2-2",
                "starters": [
                    {"player_id": player["id"], "position": "Mediocampista"}
                    for player in home_players
                ],
            },
            "away": {
                "formation": "2-2",
                "starters": [
                    {"player_id": player["id"], "position": "Mediocampista"}
                    for player in away_players
                ],
            },
            "confirmed": True,
        },
    )

    assert valid.status_code == 200, valid.text
    assert valid.json()["confirmed"] is True

    fetched = client.get("/api/v1/matches/match-1/lineup")

    assert fetched.status_code == 200
    assert len(fetched.json()["home"]["starters"]) == 5


def test_catalog_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/catalog")

    assert response.status_code == 200
    catalog = response.json()
    assert catalog["gameModalities"] == ["Fútbol 5", "Fútbol 7", "Fútbol 11"]
    assert "Penal" in catalog["goalTypes"]
    assert catalog["playerPositions"]


def test_organizer_summary_endpoint(client: TestClient, db) -> None:
    db.tournaments.insert_one(
        {
            "_id": "t-summary",
            "name": "Liga Resumen",
            "organizer_id": "org-summary",
            "teams_count": 8,
            "team_ids": ["team-summary-a", "team-summary-b"],
        }
    )
    db.teams.insert_many(
        [
            {
                "_id": "team-summary-a",
                "name": "Local Resumen",
                "code": "EQ-SUMA",
                "captain_name": "Cap A",
                "initials": "LA",
                "members": [{"player_id": "p-summary-a"}],
            },
            {
                "_id": "team-summary-b",
                "name": "Visitante Resumen",
                "code": "EQ-SUMB",
                "captain_name": "Cap B",
                "initials": "VB",
                "members": [{"player_id": "p-summary-b"}],
            },
        ]
    )
    db.matches.insert_one(
        {
            "_id": "match-summary",
            "tournament_id": "t-summary",
            "stage": "league",
            "round_label": "Fecha 1",
            "home_team_id": "team-summary-a",
            "away_team_id": "team-summary-b",
            "date": "2026-11-10",
            "time": "18:00",
            "status": "scheduled",
            "created_at": "2026-11-05T00:00:00Z",
            "updated_at": "2026-11-05T00:00:00Z",
        }
    )

    response = client.get(
        "/api/v1/organizer/summary",
        params={"organizer_id": "org-summary"},
    )

    assert response.status_code == 200
    summary = response.json()
    assert summary["tournaments"] == 1
    assert summary["teams"] == 2
    assert summary["players"] == 2
    assert summary["matches"] == 1
    assert summary["upcoming"][0]["home_team_name"] == "Local Resumen"


def test_live_event_endpoints(client: TestClient, db) -> None:
    db.matches.insert_one(
        {
            "_id": "match-events",
            "tournament_id": "t-events",
            "stage": "league",
            "round_label": "Fecha 1",
            "home_team_id": "team-events-a",
            "away_team_id": "team-events-b",
            "status": "in_progress",
            "created_at": "2026-11-05T00:00:00Z",
            "updated_at": "2026-11-05T00:00:00Z",
        }
    )
    db.players.insert_many(
        [
            {
                "_id": "p-ev-1",
                "tag": "#EV-0001",
                "name": "Goleador",
                "elo": 1000,
                "stats": {
                    "goals": 0,
                    "assists": 0,
                    "yellow_cards": 0,
                    "red_cards": 0,
                    "mvp": 0,
                    "matches_played": 0,
                },
            },
            {
                "_id": "p-ev-2",
                "tag": "#EV-0002",
                "name": "Asistidor",
                "elo": 1000,
                "stats": {
                    "goals": 0,
                    "assists": 0,
                    "yellow_cards": 0,
                    "red_cards": 0,
                    "mvp": 0,
                    "matches_played": 0,
                },
            },
            {
                "_id": "p-ev-3",
                "tag": "#EV-0003",
                "name": "Rival",
                "elo": 1000,
                "stats": {
                    "goals": 0,
                    "assists": 0,
                    "yellow_cards": 0,
                    "red_cards": 0,
                    "mvp": 0,
                    "matches_played": 0,
                },
            },
            {
                "_id": "p-ev-bench",
                "tag": "#EV-0004",
                "name": "Suplente",
                "elo": 1000,
                "stats": {
                    "goals": 0,
                    "assists": 0,
                    "yellow_cards": 0,
                    "red_cards": 0,
                    "mvp": 0,
                    "matches_played": 0,
                },
            },
        ]
    )
    snapshot = {
        "matchId": "match-events",
        "headerSubtitle": "Liga · Fecha 1",
        "clock": "00:00",
        "periodLabel": "1er tiempo",
        "phase": "live",
        "period": 1,
        "elapsedSeconds": 600,
        "halfDurationSeconds": 1500,
        "sheetClosed": False,
        "homeTeamName": "Local",
        "awayTeamName": "Visitante",
        "homeScore": 0,
        "awayScore": 0,
        "onPitch": [
            {
                "id": "p-ev-1",
                "initials": "GO",
                "name": "Goleador",
                "position": "Delantero",
                "team": "white",
                "goals": 0,
            },
            {
                "id": "p-ev-2",
                "initials": "AS",
                "name": "Asistidor",
                "position": "Mediocampista",
                "team": "white",
                "goals": 0,
            },
            {
                "id": "p-ev-3",
                "initials": "RI",
                "name": "Rival",
                "position": "Defensor",
                "team": "green",
                "goals": 0,
            },
        ],
        "bench": [
            {
                "id": "p-ev-bench",
                "initials": "SU",
                "name": "Suplente",
                "position": "Defensor",
                "team": "white",
            }
        ],
        "playerStats": [
            {
                "matchId": "match-events",
                "playerId": "p-ev-1",
                "playerName": "Goleador",
                "initials": "GO",
                "teamId": "white",
                "teamName": "Local",
                "goals": 0,
                "assists": 0,
                "yellowCards": 0,
                "redCards": 0,
                "minutesPlayed": 0,
                "enteredAtMinute": 0,
                "mvp": False,
            },
            {
                "matchId": "match-events",
                "playerId": "p-ev-2",
                "playerName": "Asistidor",
                "initials": "AS",
                "teamId": "white",
                "teamName": "Local",
                "goals": 0,
                "assists": 0,
                "yellowCards": 0,
                "redCards": 0,
                "minutesPlayed": 0,
                "enteredAtMinute": 0,
                "mvp": False,
            },
            {
                "matchId": "match-events",
                "playerId": "p-ev-3",
                "playerName": "Rival",
                "initials": "RI",
                "teamId": "green",
                "teamName": "Visitante",
                "goals": 0,
                "assists": 0,
                "yellowCards": 0,
                "redCards": 0,
                "minutesPlayed": 0,
                "enteredAtMinute": 0,
                "mvp": False,
            },
            {
                "matchId": "match-events",
                "playerId": "p-ev-bench",
                "playerName": "Suplente",
                "initials": "SU",
                "teamId": "white",
                "teamName": "Local",
                "goals": 0,
                "assists": 0,
                "yellowCards": 0,
                "redCards": 0,
                "minutesPlayed": 0,
                "enteredAtMinute": -1,
                "mvp": False,
            },
        ],
        "stats": [],
        "events": [],
        "syncState": "synced",
        "lastSyncedAt": "Ahora",
        "offlineQueue": [],
        "socialVerification": {
            "quorumPercent": 0,
            "requiredQuorumPercent": 70,
            "verified": False,
            "confirmedVoters": 0,
            "totalVoters": 4,
            "organizerReviewOpen": False,
            "lines": [],
        },
    }
    client.put("/api/v1/matches/match-events/live", json=snapshot)

    goal = client.post(
        "/api/v1/matches/match-events/live/goals",
        json={
            "team": "white",
            "scorerId": "p-ev-1",
            "assistPlayerId": "p-ev-2",
            "goalType": "Penal",
            "minute": "10'",
        },
    )
    card = client.post(
        "/api/v1/matches/match-events/live/cards",
        json={
            "team": "white",
            "playerId": "p-ev-1",
            "cardType": "yellow",
            "minute": "12'",
        },
    )
    substitution = client.post(
        "/api/v1/matches/match-events/live/substitutions",
        json={
            "outPlayerId": "p-ev-2",
            "inPlayerId": "p-ev-bench",
            "minuteNumber": 20,
            "minute": "20'",
        },
    )
    planilla = client.put(
        "/api/v1/matches/match-events/live/planilla/p-ev-1",
        json={"goals": 2, "assists": 0, "yellowCards": 1, "redCards": 0},
    )
    closed = client.post(
        "/api/v1/matches/match-events/live/close",
        json={"mvp_player_id": "p-ev-1"},
    )

    assert goal.status_code == 200
    assert goal.json()["homeScore"] == 1
    assert goal.json()["playerStats"][0]["goals"] == 1
    assert goal.json()["playerStats"][1]["assists"] == 1
    assert card.status_code == 200
    assert card.json()["playerStats"][0]["yellowCards"] == 1
    assert substitution.status_code == 200
    assert substitution.json()["bench"] == []
    bench_line = next(
        line
        for line in substitution.json()["playerStats"]
        if line["playerId"] == "p-ev-bench"
    )
    assert bench_line["enteredAtMinute"] == 20
    assert planilla.status_code == 200
    assert planilla.json()["homeScore"] == 2
    assert closed.status_code == 200
    assert closed.json()["sheetClosed"] is True

    player = db.players.find_one({"_id": "p-ev-1"})
    assert player["stats"]["goals"] == 2
    assert player["stats"]["mvp"] == 1
    assert player["stats"]["matches_played"] == 1


def test_cup_winner_advances_to_next_round(client: TestClient, db) -> None:
    db.tournaments.insert_one(
        {
            "_id": "t-cup-advance",
            "name": "Copa Avance",
            "organizer_id": "org-cup",
            "format": "copa",
            "modality": "Fútbol 5",
            "teams_count": 4,
            "min_players": 5,
            "team_ids": ["team-cup-a", "team-cup-b"],
        }
    )
    db.matches.insert_many(
        [
            {
                "_id": "cup-semi-1",
                "tournament_id": "t-cup-advance",
                "stage": "semi",
                "round_label": "Semifinal 1",
                "home_team_id": "team-cup-a",
                "away_team_id": "team-cup-b",
                "home_label": None,
                "away_label": None,
                "date": None,
                "time": None,
                "venue": None,
                "status": "scheduled",
                "created_at": "2026-11-05T00:00:00Z",
                "updated_at": "2026-11-05T00:00:00Z",
            },
            {
                "_id": "cup-final",
                "tournament_id": "t-cup-advance",
                "stage": "final",
                "round_label": "Final 1",
                "home_team_id": None,
                "away_team_id": None,
                "home_label": "Ganador Semifinal 1",
                "away_label": "Ganador Semifinal 2",
                "date": None,
                "time": None,
                "venue": None,
                "status": "scheduled",
                "created_at": "2026-11-05T00:00:00Z",
                "updated_at": "2026-11-05T00:00:00Z",
            },
        ]
    )
    snapshot = {
        "matchId": "cup-semi-1",
        "headerSubtitle": "Copa · Semifinal 1",
        "clock": "50:00",
        "periodLabel": "Finalizado",
        "phase": "live",
        "period": 2,
        "elapsedSeconds": 3000,
        "halfDurationSeconds": 1500,
        "sheetClosed": False,
        "homeTeamName": "Local",
        "awayTeamName": "Visitante",
        "homeScore": 2,
        "awayScore": 1,
        "onPitch": [],
        "bench": [],
        "playerStats": [],
        "stats": [],
        "events": [],
        "syncState": "synced",
        "lastSyncedAt": "Ahora",
        "offlineQueue": [],
        "socialVerification": {
            "quorumPercent": 0,
            "requiredQuorumPercent": 70,
            "verified": False,
            "confirmedVoters": 0,
            "totalVoters": 0,
            "organizerReviewOpen": False,
            "lines": [],
        },
    }
    client.put("/api/v1/matches/cup-semi-1/live", json=snapshot)
    closed = client.post(
        "/api/v1/matches/cup-semi-1/live/close",
        json={"mvp_player_id": "p-cup-none"},
    )

    assert closed.status_code == 200
    final = db.matches.find_one({"_id": "cup-final"})
    assert final["home_team_id"] == "team-cup-a"
    assert final["away_team_id"] is None
