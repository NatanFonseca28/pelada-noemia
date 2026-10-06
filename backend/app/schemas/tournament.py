from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.models.tournament import MatchStatus, TournamentStatus


class FormatOptionOut(BaseModel):
    code: str
    legs: int
    name: str
    description: str
    total_matches: int
    match_seconds: int
    final_seconds: int | None
    feasible: bool
    knockout_seconds: int | None
    recommended: bool
    note: str | None
    groups: dict[str, list[int]]


class FormatsOut(BaseModel):
    num_teams: int
    total_minutes: int
    changeover_minutes: int
    group_match_minutes: int
    final_weight: Decimal
    options: list[FormatOptionOut]


class TournamentCreate(BaseModel):
    format_code: str
    legs: int = Field(default=1, ge=1, le=2)
    final_weight: Decimal | None = Field(default=None, ge=Decimal("1"), le=Decimal("3"))


class TeamRef(BaseModel):
    id: int
    name: str
    color: str


class StandingRow(BaseModel):
    position: int
    team: TeamRef
    played: int
    wins: int
    draws: int
    losses: int
    goals_for: int
    goals_against: int
    goal_diff: int
    points: int
    tiebreak_note: str | None


class GroupOut(BaseModel):
    name: str
    complete: bool
    standings: list[StandingRow]


class MatchOut(BaseModel):
    id: int
    seq: int
    code: str
    stage: str
    leg: int
    group: str | None
    home: TeamRef | None
    away: TeamRef | None
    home_source: str | None
    away_source: str | None
    home_label: str
    away_label: str
    planned_seconds: int
    goal_limit: int | None
    status: MatchStatus
    home_score: int
    away_score: int
    home_penalties: int | None
    away_penalties: int | None
    winner_team_id: int | None
    started_at: datetime | None
    elapsed_before_pause: int
    ended_at: datetime | None
    version: int


class TournamentOut(BaseModel):
    id: int
    round_id: int
    round_date: str
    format_code: str
    format_name: str
    legs: int
    status: TournamentStatus
    match_seconds: int
    knockout_seconds: int | None
    final_seconds: int | None
    config: dict
    teams: list[TeamRef]
    groups: list[GroupOut]
    matches: list[MatchOut]
    next_match_id: int | None
    champion: TeamRef | None
    runner_up: TeamRef | None
    finished_at: datetime | None


class MatchResultIn(BaseModel):
    home_score: int = Field(ge=0, le=99)
    away_score: int = Field(ge=0, le=99)
    home_penalties: int | None = Field(default=None, ge=0, le=99)
    away_penalties: int | None = Field(default=None, ge=0, le=99)
    # Opcional — tempo medido pelo cronômetro do mesário ("Finalizar súmula")
    started_at: datetime | None = None  # 1º "iniciar"
    ended_at: datetime | None = None  # "finalizar"
    played_seconds: int | None = Field(default=None, ge=0, le=6 * 3600)  # tempo de bola rolando (sem pausas)

    @model_validator(mode="after")
    def penalties_together(self):
        if (self.home_penalties is None) != (self.away_penalties is None):
            raise ValueError("Informe os pênaltis dos dois times")
        if self.started_at and self.ended_at and self.ended_at < self.started_at:
            raise ValueError("O fim da partida não pode ser antes do início")
        return self
