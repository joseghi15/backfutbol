from typing import Literal

from pydantic import BaseModel


class LiveClosePayload(BaseModel):
    mvp_player_id: str
    snapshot: dict | None = None


class RegisterGoalPayload(BaseModel):
    team: Literal["white", "green"] = "white"
    scorerId: str
    goalType: str | None = None
    assistPlayerId: str | None = None
    minute: str | None = None


class RegisterCardPayload(BaseModel):
    team: Literal["white", "green"] = "white"
    playerId: str
    cardType: Literal["yellow", "red"]
    minute: str | None = None


class RegisterSubstitutionPayload(BaseModel):
    outPlayerId: str
    inPlayerId: str
    minute: str | None = None
    minuteNumber: int = 0


class UpdatePlayerStatsPayload(BaseModel):
    goals: int = 0
    assists: int = 0
    yellowCards: int = 0
    redCards: int = 0


class OfflineSyncPayload(BaseModel):
    action: Literal["toggle_offline", "sync_now"]


class SocialVerificationPayload(BaseModel):
    playerId: str
    decision: Literal["confirmed", "disputed"]
    disputeNote: str | None = None
