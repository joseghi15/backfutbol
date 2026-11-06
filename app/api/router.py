from fastapi import APIRouter

from app.api.routes import (
    catalog,
    fixtures,
    health,
    lineups,
    live,
    organizer,
    players,
    teams,
    tournaments,
)

api_router = APIRouter()
api_router.include_router(catalog.router)
api_router.include_router(health.router)
api_router.include_router(players.router)
api_router.include_router(teams.router)
api_router.include_router(tournaments.router)
api_router.include_router(fixtures.router)
api_router.include_router(live.router)
api_router.include_router(lineups.router)
api_router.include_router(organizer.router)
