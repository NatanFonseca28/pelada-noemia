from datetime import time
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.models.enums import KnockoutTieRule, RedCardRule, Tiebreaker, TopScorerTiebreak
from app.schemas.common import ORMModel


class SettingsBase(BaseModel):
    weekday: int = Field(ge=0, le=6)
    start_time: time
    total_minutes: int = Field(ge=20, le=300)
    line_players_per_team: int = Field(ge=3, le=10)
    balance_by_skill: bool
    extra_team_threshold: int = Field(ge=1, le=10)
    changeover_minutes: int = Field(ge=0, le=15)
    group_match_minutes: int = Field(ge=1, le=60)
    final_weight: Decimal = Field(ge=Decimal("1.0"), le=Decimal("3.0"))
    points_win: int = Field(ge=0, le=10)
    points_draw: int = Field(ge=0, le=10)
    points_loss: int = Field(ge=0, le=10)
    tiebreakers: list[Tiebreaker]
    knockout_tie_rule: KnockoutTieRule
    top_scorer_tiebreak: TopScorerTiebreak
    casual_goal_limit: int = Field(ge=1, le=10)
    casual_match_minutes: int = Field(ge=1, le=60)
    red_card_rule: RedCardRule
    two_yellows_red: bool

    @field_validator("tiebreakers")
    @classmethod
    def unique_tiebreakers(cls, v: list[Tiebreaker]) -> list[Tiebreaker]:
        if len(set(v)) != len(v):
            raise ValueError("Critérios de desempate repetidos")
        if not v:
            raise ValueError("Informe ao menos um critério de desempate")
        return v


class SettingsOut(ORMModel, SettingsBase):
    pass


class SettingsUpdate(SettingsBase):
    pass
