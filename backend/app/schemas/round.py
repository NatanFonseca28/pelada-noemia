from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.enums import PlayerType, Position
from app.models.round import AttendanceSource, RoundStatus, TeamRole


class RoundCreate(BaseModel):
    date: date
    notes: str | None = Field(default=None, max_length=500)


class RoundSummary(BaseModel):
    id: int
    date: date
    status: RoundStatus
    notes: str | None
    confirmed_count: int
    has_teams: bool
    tournament_id: int | None = None


class AttendanceOut(BaseModel):
    player_id: int
    name: str
    type: PlayerType
    primary_position: Position | None
    source: AttendanceSource
    updated_at: datetime


class TeamPlayerOut(BaseModel):
    player_id: int
    name: str
    photo_url: str | None
    position: str
    role: TeamRole
    filled_by: str
    moved_manually: bool


class TeamOut(BaseModel):
    id: int
    name: str
    color: str
    players: list[TeamPlayerOut]
    line_count: int
    has_fixed_gk: bool
    has_rotation_gk: bool
    uses_volunteer_gk: bool
    uses_shared_gk: bool = False  # sem goleiro próprio: usa os goleiros fixos da pelada


class DrawInfo(BaseModel):
    id: int
    seed: int
    mode: str
    num_teams: int
    warnings: list[str]
    infos: list[str]
    substitutions: list[dict]
    alternatives: list[dict]
    allow_short_team: bool = False
    created_at: datetime


class SimplePlayer(BaseModel):
    player_id: int
    name: str


class RoundDetail(RoundSummary):
    attendances: list[AttendanceOut]
    absences: list[AttendanceOut]  # avisaram que não vão (CANCELADO); sem registro = sem resposta
    my_player_id: int | None
    my_status: str | None  # CONFIRMADO / CANCELADO / None
    draw: DrawInfo | None
    teams: list[TeamOut]
    not_in_teams: list[SimplePlayer]  # confirmados fora dos times (reservas ou entraram depois do sorteio)
    shared_goalkeepers: list[SimplePlayer] = []  # goleiros fixos sem time: agarram para todos
    no_longer_confirmed: list[SimplePlayer]  # estão em time mas cancelaram


class AttendanceSet(BaseModel):
    confirmed: bool


class DrawRequest(BaseModel):
    num_teams: int | None = Field(default=None, ge=2, le=8)
    seed: int | None = Field(default=None, ge=1, le=2**31 - 1)
    # Permite um time com um a menos na linha, completado por alguém do time de fora
    allow_short_team: bool = False


class MoveRequest(BaseModel):
    player_id: int
    team_id: int | None = None  # None = tirar do time
    role: TeamRole | None = None
