"""Empréstimo de jogadores para completar times desfalcados (regra pura, sem banco).

Depois da chamada, um time que ficou com menos de `per_team` na linha é completado, em cada partida,
por alguém de um time que está FORA daquela partida. Critérios, nesta ordem:
 1. Descanso: evita quem joga pelo próprio time na partida seguinte.
 2. Rodízio: evita repetir quem foi emprestado na partida anterior e prefere quem foi emprestado menos vezes.
 3. Posição: mesma posição de quem faltou; depois quem a tem como secundária; depois qualquer um.
 4. Equilíbrio: força (nível + velocidade) mais parecida com a de quem faltou.
Partidas encerradas mantêm os empréstimos gravados (`fixed`); as demais são recalculadas a cada mudança
da chamada, então um atrasado que chega cancela os empréstimos das partidas seguintes.
Com só 2 times não há time de fora: não há empréstimo (o admin ajusta manualmente).
"""
from dataclasses import dataclass, field

GOALKEEPER_ROLE = "GOLEIRO_FIXO"


@dataclass(frozen=True)
class LoanPlayer:
    id: int
    name: str
    team_id: int
    role: str  # LINHA | REVEZAMENTO | GOLEIRO_FIXO
    position: str  # posição em que foi escalado
    primary: str | None = None
    secondary: str | None = None
    strength: int = 6


@dataclass(frozen=True)
class LoanMatch:
    id: int
    seq: int
    home_team_id: int | None
    away_team_id: int | None
    finished: bool = False

    @property
    def teams(self) -> set[int]:
        return {t for t in (self.home_team_id, self.away_team_id) if t is not None}


@dataclass(frozen=True)
class Loan:
    match_id: int
    team_id: int  # time que recebe
    player_id: int  # emprestado
    from_team_id: int
    replaces_id: int  # quem faltou
    strength_delta: float  # força média do time com o emprestado − com quem faltou


@dataclass
class LoanPlan:
    loans: list[Loan] = field(default_factory=list)
    # partidas com time desfalcado que não puderam ser completadas (ex.: 2 times, sem time de fora)
    unfilled: dict[int, list[int]] = field(default_factory=dict)  # match_id → [player_id que faltou]


def _line(p: LoanPlayer) -> bool:
    return p.role != GOALKEEPER_ROLE


def missing_by_team(players: list[LoanPlayer], absent: set[int], per_team: int) -> dict[int, list[LoanPlayer]]:
    """Quem faltou e precisa ser reposto, por time (só quando a linha presente ficou abaixo de `per_team`).

    Um time de 6 (com revezamento) que perde 1 fica com 5 e não precisa de empréstimo.
    """
    out: dict[int, list[LoanPlayer]] = {}
    for team_id in {p.team_id for p in players}:
        line = [p for p in players if p.team_id == team_id and _line(p)]
        present = [p for p in line if p.id not in absent]
        need = per_team - len(present)
        if need > 0:
            gone = sorted((p for p in line if p.id in absent), key=lambda p: (p.role != "LINHA", p.id))
            out[team_id] = gone[:need]
    return out


def _avg(values: list[int]) -> float:
    return sum(values) / len(values) if values else 0.0


def plan_loans(
    players: list[LoanPlayer],
    absent: set[int],
    matches: list[LoanMatch],
    per_team: int = 5,
    fixed: list[Loan] | None = None,
) -> LoanPlan:
    plan = LoanPlan()
    fixed = fixed or []
    missing = missing_by_team(players, absent, per_team)
    team_line = {t: [p.strength for p in players if p.team_id == t and _line(p)] for t in {p.team_id for p in players}}
    ordered = sorted(matches, key=lambda m: m.seq)
    times_loaned: dict[int, int] = {}
    loaned_in: dict[int, set[int]] = {}  # match_id → emprestados naquela partida

    for loan in fixed:
        times_loaned[loan.player_id] = times_loaned.get(loan.player_id, 0) + 1
        loaned_in.setdefault(loan.match_id, set()).add(loan.player_id)

    for i, m in enumerate(ordered):
        if m.finished:
            plan.loans.extend(x for x in fixed if x.match_id == m.id)
            continue
        if len(m.teams) < 2:
            continue  # mata-mata com times ainda indefinidos
        nxt = next((x for x in ordered[i + 1:] if len(x.teams) == 2), None)
        prev = ordered[i - 1] if i > 0 else None
        used: set[int] = set()
        for team_id in sorted(m.teams):
            for gone in missing.get(team_id, []):
                pool = [p for p in players
                        if p.team_id not in m.teams and _line(p) and p.id not in absent and p.id not in used]
                if not pool:
                    plan.unfilled.setdefault(m.id, []).append(gone.id)
                    continue

                def key(p: LoanPlayer, gone: LoanPlayer = gone) -> tuple:
                    plays_next = nxt is not None and p.team_id in nxt.teams
                    consecutive = prev is not None and p.id in loaned_in.get(prev.id, set())
                    pos = 0 if p.position == gone.position or p.primary == gone.position else \
                        1 if p.secondary == gone.position else 2
                    return (plays_next, consecutive, pos, times_loaned.get(p.id, 0),
                            abs(p.strength - gone.strength), p.id)

                pick = min(pool, key=key)
                used.add(pick.id)
                times_loaned[pick.id] = times_loaned.get(pick.id, 0) + 1
                loaned_in.setdefault(m.id, set()).add(pick.id)
                original = team_line[team_id]
                present = [p.strength for p in players
                           if p.team_id == team_id and _line(p) and p.id not in absent]
                delta = _avg(present + [pick.strength]) - _avg(original) if original else 0.0
                plan.loans.append(Loan(m.id, team_id, pick.id, pick.team_id, gone.id, round(delta, 2)))
    return plan
