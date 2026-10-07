"""Quem começa com a bola em cada partida (regra pura, sem banco).

- Fase de grupos e pelada normal: dividido o mais igual possível entre os times. Seguindo a ordem dos jogos, sai
  com a bola quem saiu menos vezes até ali; empate → o mandante (time da esquerda).
- Mata-mata (semifinal, final…): sempre o time de MELHOR CAMPANHA (ranking geral da fase de grupos).
"""
from dataclasses import dataclass

BALANCED_STAGES = {"GRUPO", "AMISTOSO"}


@dataclass(frozen=True)
class KickoffMatch:
    id: int
    seq: int
    stage: str
    home: int | None
    away: int | None


def assign_kickoffs(matches: list[KickoffMatch], campaign_rank: dict[int, int]) -> dict[int, int | None]:
    """{match_id: team_id que dá a saída} (None enquanto os times do jogo não estão definidos)."""
    out: dict[int, int | None] = {}
    count: dict[int, int] = {}
    for m in sorted(matches, key=lambda x: x.seq):
        if m.home is None or m.away is None:
            out[m.id] = None
        elif m.stage in BALANCED_STAGES:
            team = m.away if count.get(m.away, 0) < count.get(m.home, 0) else m.home
            count[team] = count.get(team, 0) + 1
            out[m.id] = team
        else:
            rh, ra = campaign_rank.get(m.home), campaign_rank.get(m.away)
            if rh is None and ra is None:
                out[m.id] = None
            else:
                out[m.id] = m.away if rh is None or (ra is not None and ra < rh) else m.home
    return out
