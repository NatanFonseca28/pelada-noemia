import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.match_event import EventType


class EventIn(BaseModel):
    client_event_id: uuid.UUID
    type: EventType
    team_id: int
    player_id: int | None = None
    assist_player_id: int | None = None
    minute: int | None = Field(default=None, ge=0, le=200)
    second: int | None = Field(default=None, ge=0, le=59)

    @model_validator(mode="after")
    def check(self):
        if self.type != EventType.GOL and self.player_id is None:
            raise ValueError("Informe o jogador")
        if self.assist_player_id is not None and self.type != EventType.GOL:
            raise ValueError("Assistência só em gol")
        if self.assist_player_id is not None and self.assist_player_id == self.player_id:
            raise ValueError("O autor do gol não pode ser o da assistência")
        return self


class EventOut(BaseModel):
    id: int
    client_event_id: uuid.UUID
    type: EventType
    team_id: int
    player_id: int | None
    player_name: str | None
    assist_player_id: int | None
    assist_name: str | None
    minute: int | None
    second: int | None
    created_at: datetime


class RosterPlayer(BaseModel):
    player_id: int
    name: str
    role: str


class MatchSheet(BaseModel):
    """Súmula: eventos da partida + elencos dos dois times."""

    match_id: int
    status: str
    home_team_id: int | None
    away_team_id: int | None
    home_score: int
    away_score: int
    events: list[EventOut]
    rosters: dict[int, list[RosterPlayer]]
