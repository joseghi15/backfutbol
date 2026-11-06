import os

os.environ["BACKFUTBOL_ENVIRONMENT"] = "test"
os.environ["BACKFUTBOL_MONGODB_URI"] = "mongodb://localhost:27017"

import mongomock
import pytest
from fastapi.testclient import TestClient

from app.db.mongo import ensure_indexes, get_db
from app.main import app


@pytest.fixture
def db():
    client = mongomock.MongoClient()
    database = client["backfutbol_test"]
    ensure_indexes(database)
    return database


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
