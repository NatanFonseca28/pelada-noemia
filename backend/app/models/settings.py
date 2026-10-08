from datetime import date, time
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, SmallInteger, String, Text, Time
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.models.enums import KnockoutTieRule, RedCardRule, TopScorerTiebreak, pg_enum

DEFAULT_TIEBREAKERS = ["PONTOS", "SALDO_GOLS", "GOLS_PRO", "CONFRONTO_DIRETO", "SORTEIO"]


class PeladaSettings(TimestampMixin, Base):
    """Configuração vigente (linha única, id=1). Rodadas/sorteios/campeonatos guardam snapshot."""

    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    # Agenda
    weekday: Mapped[int] = mapped_column(SmallInteger, default=2)  # 0=segunda ... 2=quarta
    start_time: Mapped[time] = mapped_column(Time, default=time(20, 0))
    total_minutes: Mapped[int] = mapped_column(SmallInteger, default=90)
    # Times / sorteio
    line_players_per_team: Mapped[int] = mapped_column(SmallInteger, default=5)
    balance_by_skill: Mapped[bool] = mapped_column(Boolean, default=False)
    extra_team_threshold: Mapped[int] = mapped_column(SmallInteger, default=3)
    # Campeonato
    changeover_minutes: Mapped[int] = mapped_column(SmallInteger, default=2)
    group_match_minutes: Mapped[int] = mapped_column(SmallInteger, default=8)
    final_weight: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=Decimal("1.00"))
    points_win: Mapped[int] = mapped_column(SmallInteger, default=3)
    points_draw: Mapped[int] = mapped_column(SmallInteger, default=1)
    points_loss: Mapped[int] = mapped_column(SmallInteger, default=0)
    tiebreakers: Mapped[list[str]] = mapped_column(JSONB, default=lambda: list(DEFAULT_TIEBREAKERS))
    knockout_tie_rule: Mapped[KnockoutTieRule] = mapped_column(
        pg_enum(KnockoutTieRule, "knockout_tie_rule"), default=KnockoutTieRule.PENALTIS
    )
    top_scorer_tiebreak: Mapped[TopScorerTiebreak] = mapped_column(
        pg_enum(TopScorerTiebreak, "top_scorer_tiebreak"), default=TopScorerTiebreak.DIVIDIDA
    )
    # Pelada normal (2 times)
    casual_goal_limit: Mapped[int] = mapped_column(SmallInteger, default=2)
    casual_match_minutes: Mapped[int] = mapped_column(SmallInteger, default=10)
    # Cartões
    red_card_rule: Mapped[RedCardRule] = mapped_column(
        pg_enum(RedCardRule, "red_card_rule"), default=RedCardRule.RESTO_CAMPEONATO
    )
    two_yellows_red: Mapped[bool] = mapped_column(Boolean, default=True)
    # Financeiro
    monthly_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("50.00"))
    finance_opening_balance: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    finance_opening_month: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Páginas ocultas por categoria (definidas pelo superadmin): {"JOGADOR": ["/estatisticas"], ...}
    # Cobrança por WhatsApp (editável só pelo superadmin)
    charge_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    pix_key: Mapped[str | None] = mapped_column(String(140), nullable=True)
    # Chatbot de cobrança (WhatsApp de um admin, via Evolution API): só o superadmin altera
    chatbot_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    chatbot_daily_limit: Mapped[int] = mapped_column(SmallInteger, default=40, server_default="40")
    chatbot_owner_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    hidden_pages: Mapped[dict[str, list[str]]] = mapped_column(JSONB, default=dict, server_default="{}")
