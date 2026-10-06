from datetime import date

from pydantic import BaseModel

from app.models.enums import PlayerType, Position


class PlayerStats(BaseModel):
    player_id: int
    name: str
    photo_url: str | None
    type: PlayerType
    primary_position: Position | None
    presences: int
    matches: int
    wins: int
    draws: int
    losses: int
    win_rate: float  # aproveitamento em % (V=3, E=1)
    goals: int
    own_goals: int
    assists: int
    yellows: int
    reds: int
    titles: int
    runner_ups: int


class RoundHistory(BaseModel):
    round_id: int
    date: date
    tournament_id: int | None
    team_name: str | None
    team_color: str | None
    matches: int
    wins: int
    draws: int
    losses: int
    goals: int
    assists: int
    yellows: int
    reds: int
    champion: bool
    runner_up: bool


class PlayerProfile(BaseModel):
    stats: PlayerStats
    history: list[RoundHistory]


class ScorerOut(BaseModel):
    player_id: int
    name: str
    team_name: str | None
    team_color: str | None
    goals: int
    assists: int
    matches: int


class CardOut(BaseModel):
    player_id: int
    name: str
    yellows: int
    reds: int


class TournamentSummary(BaseModel):
    tournament_id: int
    top_scorers: list[ScorerOut]  # artilheiro(s) após o critério de desempate
    tiebreak: str
    scorers: list[ScorerOut]  # todos que marcaram
    cards: list[CardOut]
    total_goals: int
    total_yellows: int
    total_reds: int
