"""Classificação da fase de grupos e resolução do mata-mata (puro)."""
import random
from dataclasses import asdict, dataclass

DEFAULT_TIEBREAKERS = ["PONTOS", "SALDO_GOLS", "GOLS_PRO", "CONFRONTO_DIRETO", "SORTEIO"]


@dataclass(frozen=True)
class Result:
    home: int
    away: int
    home_goals: int
    away_goals: int


@dataclass(frozen=True)
class PointsConfig:
    win: int = 3
    draw: int = 1
    loss: int = 0


@dataclass
class Row:
    team: int
    played: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    goals_for: int = 0
    goals_against: int = 0
    points: int = 0
    position: int = 0
    tiebreak_note: str | None = None

    @property
    def goal_diff(self) -> int:
        return self.goals_for - self.goals_against

    def to_dict(self) -> dict:
        return {**asdict(self), "goal_diff": self.goal_diff}


def _table(teams: list[int], results: list[Result], pts: PointsConfig) -> dict[int, Row]:
    rows = {t: Row(t) for t in teams}
    for r in results:
        if r.home not in rows or r.away not in rows:
            continue
        h, a = rows[r.home], rows[r.away]
        h.played += 1
        a.played += 1
        h.goals_for += r.home_goals
        h.goals_against += r.away_goals
        a.goals_for += r.away_goals
        a.goals_against += r.home_goals
        if r.home_goals > r.away_goals:
            h.wins, a.losses = h.wins + 1, a.losses + 1
            h.points, a.points = h.points + pts.win, a.points + pts.loss
        elif r.home_goals < r.away_goals:
            a.wins, h.losses = a.wins + 1, h.losses + 1
            a.points, h.points = a.points + pts.win, h.points + pts.loss
        else:
            h.draws, a.draws = h.draws + 1, a.draws + 1
            h.points, a.points = h.points + pts.draw, a.points + pts.draw
    return rows


LABELS = {
    "PONTOS": "pontos",
    "SALDO_GOLS": "saldo de gols",
    "GOLS_PRO": "gols pró",
    "CONFRONTO_DIRETO": "confronto direto",
    "SORTEIO": "sorteio",
}


def compute_standings(
    teams: list[int],
    results: list[Result],
    points: PointsConfig = PointsConfig(),
    tiebreakers: list[str] = DEFAULT_TIEBREAKERS,
    seed: int = 0,
) -> list[Row]:
    rows = _table(teams, results, points)
    lottery = random.Random(seed)
    lottery_key = {t: lottery.random() for t in sorted(teams)}

    def value(criterion: str, team: int, tied: list[int]) -> tuple:
        row = rows[team]
        if criterion == "PONTOS":
            return (row.points,)
        if criterion == "SALDO_GOLS":
            return (row.goal_diff,)
        if criterion == "GOLS_PRO":
            return (row.goals_for,)
        if criterion == "CONFRONTO_DIRETO":
            # Mini-tabela só com os jogos entre os empatados: pontos, depois saldo
            mini = _table(tied, [r for r in results if r.home in tied and r.away in tied], points)
            return (mini[team].points, mini[team].goal_diff)
        if criterion == "SORTEIO":
            return (lottery_key[team],)
        raise ValueError(f"Critério desconhecido: {criterion}")

    def rank(group: list[int], criteria: list[str]) -> list[int]:
        if len(group) <= 1 or not criteria:
            return sorted(group)
        criterion, rest = criteria[0], criteria[1:]
        keyed = {t: value(criterion, t, group) for t in group}
        ordered: list[int] = []
        for v in sorted(set(keyed.values()), reverse=True):
            bucket = [t for t in group if keyed[t] == v]
            if len(bucket) > 1:
                ordered += rank(bucket, rest)
            else:
                ordered += bucket
                if len(group) > 1 and criterion != "PONTOS":
                    rows[bucket[0]].tiebreak_note = rows[bucket[0]].tiebreak_note or LABELS[criterion]
        return ordered

    criteria = list(tiebreakers)
    if "PONTOS" not in criteria:
        criteria.insert(0, "PONTOS")
    ordered = rank(list(teams), criteria)
    out = []
    for pos, t in enumerate(ordered, start=1):
        rows[t].position = pos
        out.append(rows[t])
    return out


# ---------------------------------------------------------------- mata-mata


@dataclass
class KnockoutResult:
    home: int
    away: int
    home_goals: int
    away_goals: int
    home_penalties: int | None = None
    away_penalties: int | None = None


class TieRuleError(ValueError):
    pass


def knockout_winner(r: KnockoutResult, rule: str, campaign_rank: dict[int, int] | None = None) -> int:
    """Vencedor de um jogo eliminatório conforme a regra de empate configurada."""
    if r.home_goals != r.away_goals:
        return r.home if r.home_goals > r.away_goals else r.away
    if rule == "PENALTIS":
        if r.home_penalties is None or r.away_penalties is None:
            raise TieRuleError("Empate no mata-mata: informe o placar dos pênaltis")
        if r.home_penalties == r.away_penalties:
            raise TieRuleError("Os pênaltis não podem terminar empatados")
        return r.home if r.home_penalties > r.away_penalties else r.away
    if rule == "MELHOR_CAMPANHA":
        ranks = campaign_rank or {}
        return min((r.home, r.away), key=lambda t: ranks.get(t, 99))
    if rule == "GOL_DE_OURO":
        raise TieRuleError("Regra gol de ouro: o jogo não termina empatado; registre o gol da vitória")
    raise TieRuleError(f"Regra de empate desconhecida: {rule}")


def resolve_source(
    source: str,
    group_tables: dict[str, list[Row]],
    group_complete: dict[str, bool],
    winners: dict[str, int],
    losers: dict[str, int],
) -> int | None:
    """"A:1" → 1º do grupo A (se o grupo terminou); "V:SF1" → vencedor da SF1; "P:SF1" → perdedor."""
    kind, ref = source.split(":", 1)
    if kind == "V":
        return winners.get(ref)
    if kind == "P":
        return losers.get(ref)
    if not group_complete.get(kind):
        return None
    table = group_tables.get(kind, [])
    pos = int(ref)
    return table[pos - 1].team if 0 < pos <= len(table) else None


def campaign_ranking(group_tables: dict[str, list[Row]]) -> dict[int, int]:
    """Ranking geral por campanha (posição no grupo, pontos, saldo, gols) — usado em MELHOR_CAMPANHA."""
    rows = [row for table in group_tables.values() for row in table]
    rows.sort(key=lambda r: (r.position, -r.points, -r.goal_diff, -r.goals_for))
    return {r.team: i for i, r in enumerate(rows, start=1)}

