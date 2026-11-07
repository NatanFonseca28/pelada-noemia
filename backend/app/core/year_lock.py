"""Fechamento do ano: depois de 31/12 o ano que passou vira somente leitura (só o superadmin corrige).

A virada é pela data no fuso da pelada. Carência: dezembro do ano que fechou continua editável até 31/01, para registrar o
pagamento tardio da mensalidade/diária de dezembro.
"""
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationError
from app.models.user import User

FIRST_YEAR = 2026  # a pelada começou em 2026: não há dados antes
TZ = ZoneInfo("America/Sao_Paulo")


def today() -> date:
    return datetime.now(TZ).date()


def is_closed(d: date) -> bool:
    now = today()
    if d.year >= now.year:
        return False
    return not (d.year == now.year - 1 and d.month == 12 and now.month == 1)  # carência de dezembro


def ensure_open(d: date, actor: User | None) -> None:
    """Recusa a edição de um registro de ano fechado, exceto para o superadmin."""
    if is_closed(d) and not (actor is not None and actor.is_superadmin):
        raise ValidationError(f"{d.year} está fechado (somente leitura). Peça ao superadmin para corrigir.")


async def ensure_round_open(session: AsyncSession, round_id: int, actor: User | None) -> None:
    from app.models.round import Round

    rnd = await session.get(Round, round_id)
    if rnd is None:
        raise NotFoundError("Rodada não encontrada")
    ensure_open(rnd.date, actor)


async def ensure_match_open(session: AsyncSession, match_id: int, actor: User | None) -> None:
    from app.models.round import Round
    from app.models.tournament import Match, Tournament

    d = await session.scalar(
        select(Round.date).join(Tournament, Tournament.round_id == Round.id)
        .join(Match, Match.tournament_id == Tournament.id).where(Match.id == match_id)
    )
    if d is not None:
        ensure_open(d, actor)
