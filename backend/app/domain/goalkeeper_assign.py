"""Goleiro fixo da pelada em cada partida (regra pura, sem banco).

Goleiro fixo sem time agarra para os times de 5 na linha (sem goleiro próprio nem excedente revezando).
Em cada partida, o goleiro vai para o lado que teve menos jogos com goleiro até ali; empate → o mandante.
Com 2+ goleiros da pelada, os dois lados têm goleiro. Se só um lado precisa, o goleiro vai para ele.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class GkMatch:
    id: int
    seq: int
    home: int | None
    away: int | None


def assign_match_goalkeepers(
    matches: list[GkMatch], needy_teams: set[int], shared_gks: list[int]
) -> dict[int, dict[int, int]]:
    """{match_id: {team_id: goleiro_id}} só para os jogos em que algum time precisa de goleiro."""
    out: dict[int, dict[int, int]] = {}
    if not shared_gks or not needy_teams:
        return out
    count: dict[int, int] = {}
    for m in sorted(matches, key=lambda x: x.seq):
        if m.home is None or m.away is None:
            continue
        sides = [t for t in (m.home, m.away) if t in needy_teams]
        sides.sort(key=lambda t: count.get(t, 0))  # estável: empate segue home, away
        chosen = sides[: len(shared_gks)]
        if not chosen:
            continue
        out[m.id] = {t: gk for t, gk in zip(chosen, shared_gks, strict=False)}
        for t in chosen:
            count[t] = count.get(t, 0) + 1
    return out
