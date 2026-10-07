from enum import StrEnum

from sqlalchemy import Enum as SAEnum


class UserRole(StrEnum):
    ADMIN = "ADMIN"
    MESARIO = "MESARIO"
    JOGADOR = "JOGADOR"


class UserStatus(StrEnum):
    PENDENTE = "PENDENTE"
    ATIVO = "ATIVO"
    BLOQUEADO = "BLOQUEADO"


class PlayerType(StrEnum):
    MENSALISTA = "MENSALISTA"
    DIARISTA = "DIARISTA"
    ISENTO = "ISENTO"  # goleiro fixo: não paga mensalidade nem diária


class Position(StrEnum):
    ZAGUEIRO = "ZAGUEIRO"
    ALA = "ALA"
    ATACANTE = "ATACANTE"
    GOLEIRO_FIXO = "GOLEIRO_FIXO"


class KnockoutTieRule(StrEnum):
    PENALTIS = "PENALTIS"
    MELHOR_CAMPANHA = "MELHOR_CAMPANHA"
    GOL_DE_OURO = "GOL_DE_OURO"


class RedCardRule(StrEnum):
    NENHUMA = "NENHUMA"
    PROXIMA_PARTIDA = "PROXIMA_PARTIDA"
    RESTO_CAMPEONATO = "RESTO_CAMPEONATO"


class TopScorerTiebreak(StrEnum):
    DIVIDIDA = "DIVIDIDA"
    MAIS_ASSISTENCIAS = "MAIS_ASSISTENCIAS"
    MENOS_JOGOS = "MENOS_JOGOS"
    SORTEIO = "SORTEIO"


class Tiebreaker(StrEnum):
    PONTOS = "PONTOS"
    SALDO_GOLS = "SALDO_GOLS"
    GOLS_PRO = "GOLS_PRO"
    CONFRONTO_DIRETO = "CONFRONTO_DIRETO"
    SORTEIO = "SORTEIO"


def pg_enum(enum_cls: type[StrEnum], name: str) -> SAEnum:
    """Enum nativo do Postgres usando os valores (não os nomes) do StrEnum."""
    return SAEnum(enum_cls, name=name, values_callable=lambda e: [m.value for m in e])
