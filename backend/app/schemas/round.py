from datetime import date, datetime
from typing import Literal

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
    checkin: str | None = None  # chamada no local: PRESENTE | FALTOU | None (não chamado)


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
    # Médias por jogador de linha (só ADMIN; None para os demais). Força = nível + velocidade.
    level_avg: float | None = None
    speed_avg: float | None = None
    strength_avg: float | None = None


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


class LoanOut(BaseModel):
    """Empréstimo de um jogador de um time que está de fora para completar um time desfalcado."""

    match_id: int
    match_seq: int
    match_label: str
    finished: bool
    team_id: int
    team_name: str
    player_id: int
    player_name: str
    from_team_name: str
    replaces_name: str
    strength_delta: float | None = None  # só ADMIN (força = nível + velocidade, que são internos)


class UnfilledOut(BaseModel):
    """Partida com time desfalcado sem ninguém para emprestar (ex.: só 2 times)."""

    match_id: int
    match_seq: int
    match_label: str
    missing_names: list[str]


class CheckinSet(BaseModel):
    status: Literal["PRESENTE", "FALTOU"] | None


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
    loans: list[LoanOut] = []  # escala de empréstimos depois da chamada (com campeonato montado)
    unfilled: list[UnfilledOut] = []


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
