from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.team import Team

TournamentFormat = Literal["liga", "copa"]
GameModality = Literal["Fútbol 5", "Fútbol 7", "Fútbol 11"]
TournamentStatus = Literal["draft", "published", "in_progress", "finished"]


class TournamentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    organizer_id: str = Field(min_length=1)
    format: TournamentFormat
    modality: GameModality
    teams_count: int = Field(ge=2, le=64)
    surface: str = Field(default="Sintético", max_length=40)
    start_date: date | None = None
    end_date: date | None = None
    min_players: int = Field(default=5, ge=1, le=30)
    main_venue: str | None = Field(default=None, max_length=120)
    status: Literal["draft"] = "draft"

    @model_validator(mode="after")
    def validate_dates(self) -> "TournamentCreate":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("La fecha de fin no puede ser anterior al inicio.")
        return self


class Tournament(BaseModel):
    id: str
    name: str
    organizer_id: str
    format: TournamentFormat
    modality: GameModality
    teams_count: int
    surface: str
    start_date: date | None = None
    end_date: date | None = None
    min_players: int
    main_venue: str | None = None
    status: TournamentStatus
    registration_closed: bool = False
    team_ids: list[str] = []
    created_at: datetime
    updated_at: datetime


class TournamentDetail(Tournament):
    teams: list[Team] = []


class TournamentStatusUpdate(BaseModel):
    status: TournamentStatus


class TournamentTeamAdd(BaseModel):
    team_id: str
