from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

Role = Literal["player", "organizer", "admin"]


class PlayerStats(BaseModel):
    goals: int = 0
    assists: int = 0
    yellow_cards: int = 0
    red_cards: int = 0
    mvp: int = 0
    matches_played: int = 0


class PlayerCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=60)
    last_name: str = Field(min_length=1, max_length=60)
    position: str = Field(min_length=1, max_length=40)
    tag: str | None = Field(default=None, max_length=20)
    cedula: str | None = Field(default=None, max_length=20)
    phone: str | None = Field(default=None, max_length=30)
    role: Role = "player"
    is_ghost: bool = False

    @model_validator(mode="after")
    def validate_ghost_identity(self) -> "PlayerCreate":
        if self.is_ghost and not (self.cedula or self.phone):
            raise ValueError("El perfil fantasma necesita cédula o teléfono.")
        return self


class TournamentPlayerStat(BaseModel):
    player_id: str
    tag: str
    name: str
    team_id: str
    team_name: str
    position: str
    jersey_number: int | None = None
    goals: int = 0
    assists: int = 0
    yellow_cards: int = 0
    red_cards: int = 0
    mvp: int = 0
    matches_played: int = 0
    elo: int = 1000


class Player(BaseModel):
    id: str
    tag: str
    first_name: str
    last_name: str
    name: str
    position: str
    role: Role
    is_ghost: bool
    cedula: str | None = None
    phone: str | None = None
    elo: int = 1000
    stats: PlayerStats = Field(default_factory=PlayerStats)
    created_at: datetime
