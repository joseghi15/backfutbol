from datetime import date as Date
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

MatchStage = Literal[
    "league",
    "round_of_16",
    "quarter",
    "semi",
    "final",
]
MatchStatus = Literal["scheduled", "in_progress", "finished"]


def validate_time(value: str | None) -> str | None:
    if value is None:
        return value

    parts = value.split(":")

    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        raise ValueError("La hora debe tener formato HH:MM.")

    hours, minutes = (int(part) for part in parts)

    if hours > 23 or minutes > 59:
        raise ValueError("La hora debe estar entre 00:00 y 23:59.")

    return f"{hours:02d}:{minutes:02d}"


class MatchCreate(BaseModel):
    home_team_id: str
    away_team_id: str
    date: Date | None = None
    time: str | None = None
    venue: str | None = Field(default=None, max_length=120)
    round_label: str | None = Field(default=None, max_length=80)
    stage: MatchStage = "league"

    @field_validator("time")
    @classmethod
    def validate_match_time(cls, value: str | None) -> str | None:
        return validate_time(value)


class MatchUpdate(BaseModel):
    date: Date | None = None
    time: str | None = None
    venue: str | None = Field(default=None, max_length=120)

    @field_validator("time")
    @classmethod
    def validate_match_time(cls, value: str | None) -> str | None:
        return validate_time(value)


class Match(BaseModel):
    id: str
    tournament_id: str
    stage: MatchStage
    round_label: str | None = None
    home_team_id: str | None = None
    away_team_id: str | None = None
    home_label: str | None = None
    away_label: str | None = None
    date: Date | None = None
    time: str | None = None
    venue: str | None = None
    status: MatchStatus
    created_at: datetime
    updated_at: datetime


class OrganizerMatchItem(Match):
    tournament_name: str
    home_team_name: str | None = None
    away_team_name: str | None = None
