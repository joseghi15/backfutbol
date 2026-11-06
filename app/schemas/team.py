from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.player import Player


class TeamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    captain_name: str = Field(min_length=1, max_length=80)
    initials: str | None = Field(default=None, max_length=3)
    code: str | None = Field(default=None, max_length=20)


class TeamMember(BaseModel):
    player_id: str
    jersey_number: int | None = Field(default=None, ge=1, le=99)
    position: str | None = None


class TeamPlayerAdd(BaseModel):
    player_id: str
    jersey_number: int | None = Field(default=None, ge=1, le=99)
    position: str | None = None


class Team(BaseModel):
    id: str
    code: str
    name: str
    captain_name: str
    initials: str
    members: list[TeamMember] = []
    created_at: datetime


class TeamDetail(Team):
    players: list[Player] = []
