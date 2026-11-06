from functools import lru_cache

from pymongo import MongoClient
from pymongo.database import Database

from app.core.config import get_settings


@lru_cache
def get_client() -> MongoClient:
    settings = get_settings()
    return MongoClient(
        settings.mongodb_uri,
        serverSelectionTimeoutMS=settings.mongodb_timeout_ms,
    )


def get_db() -> Database:
    settings = get_settings()
    return get_client()[settings.mongodb_db]


def ensure_indexes(db: Database) -> None:
    db.players.create_index("tag", unique=True)
    db.players.create_index("cedula", unique=True, sparse=True)
    db.players.create_index("phone", unique=True, sparse=True)
    db.teams.create_index("code", unique=True)
    db.tournaments.create_index(
        [("organizer_id", 1), ("name", 1)],
        unique=True,
    )
    db.match_lineups.create_index("match_id", unique=True)
    db.matches.create_index([("tournament_id", 1), ("date", 1), ("time", 1)])
    db.matches.create_index(
        [("tournament_id", 1), ("home_team_id", 1), ("away_team_id", 1)]
    )
    db.live_matches.create_index("match_id", unique=True)
