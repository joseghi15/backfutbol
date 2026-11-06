from datetime import datetime

from pydantic import BaseModel, Field


class LineupPlayer(BaseModel):
    player_id: str
    position: str = Field(min_length=1, max_length=40)
    jersey_number: int | None = Field(default=None, ge=1, le=99)


class LineupSide(BaseModel):
    formation: str = Field(min_length=1, max_length=20)
    starters: list[LineupPlayer]
    bench: list[LineupPlayer] = []


class MatchLineupUpsert(BaseModel):
    tournament_id: str
    home_team_id: str
    away_team_id: str
    home: LineupSide
    away: LineupSide
    confirmed: bool = False


class MatchLineup(MatchLineupUpsert):
    id: str
    match_id: str
    created_at: datetime
    updated_at: datetime
