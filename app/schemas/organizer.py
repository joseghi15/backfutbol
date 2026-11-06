from pydantic import BaseModel

from app.schemas.match import OrganizerMatchItem


class OrganizerSummary(BaseModel):
    organizer_id: str
    tournaments: int = 0
    teams: int = 0
    players: int = 0
    matches: int = 0
    upcoming: list[OrganizerMatchItem] = []
