# backfutbol

API del proyecto con **FastAPI**, **Python 3.13** y **MongoDB Atlas**.

## Requisitos

- [uv](https://docs.astral.sh/uv/)
- Cluster de MongoDB Atlas con acceso desde tu IP

## Configuración

```bash
cp .env.example .env
```

Completar en `.env`:

```bash
BACKFUTBOL_MONGODB_URI=mongodb+srv://USUARIO:PASSWORD@CLUSTER.mongodb.net/backfutbol
BACKFUTBOL_MONGODB_DB=backfutbol
```

`.env` está ignorado por git y contiene credenciales.

## Ejecutar

```bash
uv sync
uv run fastapi dev app/main.py --host 0.0.0.0 --port 8000
```

- API local: `http://localhost:8000/api/v1`
- Documentación: `http://localhost:8000/docs`
- Health: `http://localhost:8000/api/v1/health`
- Health de MongoDB: `http://localhost:8000/api/v1/health/db`

Para Expo Go en un teléfono, la API debe escuchar en `0.0.0.0` y el front debe
usar la IP LAN de la máquina.

## Endpoints de la Fase 0

### Catálogo

- `GET /catalog`

### Jugadores

- `POST /players`
- `GET /players/search?q=...`
- `GET /players/{player_id}`

### Equipos

- `POST /teams`
- `GET /teams/search?q=...`
- `GET /teams/{team_id}`
- `POST /teams/{team_id}/players`

### Torneos

- `POST /tournaments`
- `GET /tournaments?organizer_id=...`
- `GET /tournaments/{tournament_id}`
- `PATCH /tournaments/{tournament_id}/status`
- `POST /tournaments/{tournament_id}/teams`
- `POST /tournaments/{tournament_id}/close-registration`
- `POST /tournaments/{tournament_id}/fixture/generate`
- `GET /tournaments/{tournament_id}/matches`
- `POST /tournaments/{tournament_id}/matches`
- `PATCH /matches/{match_id}`
- `GET /tournaments/{tournament_id}/player-stats`

### Organizador

- `GET /organizer/matches?organizer_id=...`
- `GET /organizer/summary?organizer_id=...`

### Alineaciones

- `GET /matches/{match_id}/lineup`
- `PUT /matches/{match_id}/lineup`
- `POST /matches/{match_id}/start`

### Partido en vivo

- `GET /matches/{match_id}/live`
- `PUT /matches/{match_id}/live`
- `POST /matches/{match_id}/live/goals`
- `POST /matches/{match_id}/live/cards`
- `POST /matches/{match_id}/live/substitutions`
- `PUT /matches/{match_id}/live/planilla/{player_id}`
- `POST /matches/{match_id}/live/offline-sync`
- `POST /matches/{match_id}/live/social-verification`
- `POST /matches/{match_id}/live/close`
- `POST /matches/{match_id}/live/reopen`

## Comandos

```bash
uv run pytest
uv run ruff check .
uv run ruff format .
```

## Estructura

```
app/
├── main.py
├── core/
│   ├── config.py
│   └── ids.py
├── db/
│   └── mongo.py
├── schemas/
│   ├── player.py
│   ├── team.py
│   ├── tournament.py
│   ├── match.py
│   ├── lineup.py
│   ├── live.py
│   └── organizer.py
├── serializers.py
└── api/
    ├── router.py
    └── routes/
        ├── catalog.py
        ├── health.py
        ├── players.py
        ├── teams.py
        ├── tournaments.py
        ├── fixtures.py
        ├── lineups.py
        ├── live.py
        └── organizer.py
tests/
```
