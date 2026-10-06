"""Formatos de campeonato, tabela de jogos e cálculo do tempo por partida (puro).

Há um único campo: as partidas são sequenciais. Regras da pelada:
- Todo jogo da fase de grupos dura `group_match_minutes` (8 min por padrão), independente do formato.
- A pelada sempre fecha a duração total: o tempo restante (descontadas as trocas) vai inteiro para o
  mata-mata, na proporção 1 para cada jogo eliminatório e `peso_final` para a final (que absorve
  também o arredondamento).
- Todo jogo de mata-mata precisa ser mais longo que o jogo de tabela; senão o formato é inviável.
- Se houver tempo, a fase de grupos é em ida e volta (cada jogo vale normalmente, sem agregado).
- Mata-mata: 3 times → 2º×3º e final contra o 1º; 4+ times em grupo único → 1º×3º e 2º×4º;
  dois grupos → 1ºA×2ºB e 1ºB×2ºA (ou final direta entre os 1º).
"""
from dataclasses import asdict, dataclass
from decimal import ROUND_FLOOR, Decimal
from enum import StrEnum
from itertools import combinations


class FormatCode(StrEnum):
    # PONTOS_CORRIDOS e GRUPO_FINAL não são mais oferecidos (não fecham os 90 min sem passar de 10 min
    # por jogo), mas continuam aqui para campeonatos antigos.
    PONTOS_CORRIDOS = "PONTOS_CORRIDOS"
    GRUPO_FINAL = "GRUPO_FINAL"
    GRUPO_REPESCAGEM_FINAL = "GRUPO_REPESCAGEM_FINAL"
    GRUPO_SEMI_FINAL = "GRUPO_SEMI_FINAL"
    DOIS_GRUPOS_FINAL = "DOIS_GRUPOS_FINAL"
    DOIS_GRUPOS_SEMI_FINAL = "DOIS_GRUPOS_SEMI_FINAL"
    PELADA_NORMAL = "PELADA_NORMAL"


class Stage(StrEnum):
    GRUPO = "GRUPO"
    SEMIFINAL = "SEMIFINAL"
    FINAL = "FINAL"
    AMISTOSO = "AMISTOSO"  # pelada normal


FORMAT_INFO: dict[FormatCode, tuple[str, str]] = {
    FormatCode.PONTOS_CORRIDOS: ("Pontos corridos", "Todos contra todos; campeão é o 1º colocado."),
    FormatCode.GRUPO_FINAL: ("Grupo único + final", "Todos contra todos; final entre 1º e 2º."),
    FormatCode.GRUPO_REPESCAGEM_FINAL: (
        "Grupo único + 2º×3º + final", "Todos contra todos; 2º×3º e o vencedor enfrenta o 1º na final."
    ),
    FormatCode.GRUPO_SEMI_FINAL: ("Grupo único + semifinais + final", "Todos contra todos; semis 1º×3º e 2º×4º."),
    FormatCode.DOIS_GRUPOS_FINAL: ("Dois grupos + final", "Final entre os 1º colocados de cada grupo."),
    FormatCode.DOIS_GRUPOS_SEMI_FINAL: (
        "Dois grupos + semifinais cruzadas + final", "Semis 1ºA×2ºB e 1ºB×2ºA."
    ),
    FormatCode.PELADA_NORMAL: ("Pelada normal", "2 times: partidas curtas em sequência (gols ou tempo), sem campeão."),
}


@dataclass
class MatchPlan:
    """Partida planejada. Times da fase de grupos vêm como índice (0..N-1);
    no mata-mata, como origem: "A:1" (1º do grupo A), "V:SF1" (vencedor da SF1)."""

    seq: int
    stage: Stage
    code: str
    leg: int = 1  # 1 = ida, 2 = volta
    group: str | None = None
    home: int | None = None
    away: int | None = None
    home_source: str | None = None
    away_source: str | None = None


@dataclass
class FormatOption:
    code: FormatCode
    legs: int
    name: str
    description: str
    groups: dict[str, list[int]]
    matches: list[MatchPlan]
    total_matches: int
    match_seconds: int  # jogos de tabela
    knockout_seconds: int | None  # jogos eliminatórios antes da final
    final_seconds: int | None
    feasible: bool
    note: str | None = None
    recommended: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class TimeConfig:
    total_minutes: int = 90
    changeover_minutes: int = 2
    final_weight: Decimal = Decimal("1")
    group_match_minutes: int = 8
    casual_match_minutes: int = 10


# ---------------------------------------------------------------- jogos


def round_robin(teams: list[int]) -> list[tuple[int, int]]:
    """Todos contra todos pelo método do círculo, ordenado para alternar quem descansa."""
    ts = list(teams)
    if len(ts) < 2:
        return []
    if len(ts) % 2:
        ts.append(-1)  # folga
    n = len(ts)
    rounds = []
    for r in range(n - 1):
        pairs = []
        for i in range(n // 2):
            a, b = ts[i], ts[n - 1 - i]
            if a != -1 and b != -1:
                pairs.append((a, b) if r % 2 == 0 else (b, a))
        rounds.append(pairs)
        ts = [ts[0], ts[-1], *ts[1:-1]]
    games = [g for rnd in rounds for g in rnd]
    assert len(games) == len(list(combinations(teams, 2)))
    return games


def split_groups(n: int) -> dict[str, list[int]]:
    """Divide os times em 2 grupos alternando (0→A, 1→B, 2→A...); a ordem dos times já é sorteada."""
    return {"A": list(range(0, n, 2)), "B": list(range(1, n, 2))}


def _interleave(a: list, b: list) -> list:
    out = []
    for i in range(max(len(a), len(b))):
        if i < len(a):
            out.append(a[i])
        if i < len(b):
            out.append(b[i])
    return out


def _with_return_leg(games: list[tuple[int, int]], legs: int) -> list[tuple[int, int, int]]:
    """Ida e volta: todos os jogos de ida e depois a volta com mando invertido."""
    out = [(h, a, 1) for h, a in games]
    if legs == 2:
        out += [(a, h, 2) for h, a in games]
    return out


def build_matches(code: FormatCode, n: int, legs: int = 1) -> tuple[dict[str, list[int]], list[MatchPlan]]:
    plans: list[MatchPlan] = []

    def add(stage: Stage, code_: str, **kw) -> None:
        plans.append(MatchPlan(seq=len(plans) + 1, stage=stage, code=code_, **kw))

    if code == FormatCode.PELADA_NORMAL:
        add(Stage.AMISTOSO, "J1", home=0, away=1)
        return {}, plans

    if code in (FormatCode.DOIS_GRUPOS_FINAL, FormatCode.DOIS_GRUPOS_SEMI_FINAL):
        groups = split_groups(n)
        ga = [("A", g) for g in _with_return_leg(round_robin(groups["A"]), legs)]
        gb = [("B", g) for g in _with_return_leg(round_robin(groups["B"]), legs)]
        for i, (grp, (h, a, leg)) in enumerate(_interleave(ga, gb), start=1):
            add(Stage.GRUPO, f"G{i}", leg=leg, group=grp, home=h, away=a)
        if code == FormatCode.DOIS_GRUPOS_SEMI_FINAL:
            add(Stage.SEMIFINAL, "SF1", home_source="A:1", away_source="B:2")
            add(Stage.SEMIFINAL, "SF2", home_source="B:1", away_source="A:2")
            add(Stage.FINAL, "F", home_source="V:SF1", away_source="V:SF2")
        else:
            add(Stage.FINAL, "F", home_source="A:1", away_source="B:1")
        return groups, plans

    groups = {"A": list(range(n))}
    for i, (h, a, leg) in enumerate(_with_return_leg(round_robin(groups["A"]), legs), start=1):
        add(Stage.GRUPO, f"G{i}", leg=leg, group="A", home=h, away=a)
    if code == FormatCode.GRUPO_FINAL:
        add(Stage.FINAL, "F", home_source="A:1", away_source="A:2")
    elif code == FormatCode.GRUPO_REPESCAGEM_FINAL:
        add(Stage.SEMIFINAL, "R", home_source="A:2", away_source="A:3")
        add(Stage.FINAL, "F", home_source="A:1", away_source="V:R")
    elif code == FormatCode.GRUPO_SEMI_FINAL:
        add(Stage.SEMIFINAL, "SF1", home_source="A:1", away_source="A:3")
        add(Stage.SEMIFINAL, "SF2", home_source="A:2", away_source="A:4")
        add(Stage.FINAL, "F", home_source="V:SF1", away_source="V:SF2")
    return groups, plans


# ---------------------------------------------------------------- tempo


@dataclass(frozen=True)
class Timing:
    group_seconds: int
    knockout_seconds: int | None
    final_seconds: int | None
    feasible: bool
    total_seconds: int  # jogos + trocas (sempre a duração total)


def match_times(group_matches: int, knockout_matches: int, has_final: bool, cfg: TimeConfig) -> Timing:
    """Tempo de cada jogo. `knockout_matches` = eliminatórios antes da final."""
    total = group_matches + knockout_matches + (1 if has_final else 0)
    group = cfg.group_match_minutes * 60
    if total <= 0 or not has_final:
        return Timing(group, None, None, False, 0)
    changeovers = cfg.changeover_minutes * 60 * (total - 1)
    available = cfg.total_minutes * 60 - changeovers
    rest = available - group * group_matches
    if rest <= 0:  # só a fase de grupos já estoura a duração total
        return Timing(group, None, None, False, cfg.total_minutes * 60)
    weight = Decimal(cfg.final_weight)
    unit = int((Decimal(max(rest, 0)) / (Decimal(knockout_matches) + weight)).to_integral_value(rounding=ROUND_FLOOR))
    knockout = unit if knockout_matches else None
    final = rest - unit * knockout_matches  # a final absorve o arredondamento
    feasible = final > group and (knockout is None or knockout > group)
    return Timing(group, knockout, final, feasible, cfg.total_minutes * 60)


def available_codes(n: int) -> list[FormatCode]:
    if n == 2:
        return [FormatCode.PELADA_NORMAL]
    if n == 3:
        return [FormatCode.GRUPO_REPESCAGEM_FINAL]
    if n == 4:
        return [FormatCode.GRUPO_SEMI_FINAL]
    return [FormatCode.DOIS_GRUPOS_SEMI_FINAL, FormatCode.GRUPO_SEMI_FINAL, FormatCode.DOIS_GRUPOS_FINAL]


def suggest_formats(n: int, cfg: TimeConfig) -> list[FormatOption]:
    """Formatos possíveis para N times, em turno único e em ida e volta.

    Ordenação: viáveis primeiro; entre eles, ida e volta antes (regra da pelada), mantendo a ordem de
    preferência de `available_codes`. O primeiro viável é marcado como recomendado.
    """
    if n < 2:
        return []
    options = []
    for pref, code in enumerate(available_codes(n)):
        name, description = FORMAT_INFO[code]
        if code == FormatCode.PELADA_NORMAL:
            groups, matches = build_matches(code, n)
            secs = cfg.casual_match_minutes * 60
            estimate = (cfg.total_minutes + cfg.changeover_minutes) // (cfg.casual_match_minutes + cfg.changeover_minutes)
            options.append(FormatOption(code, 1, name, description, groups, matches, estimate, secs, None, None, True,
                                        note=f"Cerca de {estimate} partidas de até {cfg.casual_match_minutes} min"))
            continue
        for legs in (2, 1):
            groups, matches = build_matches(code, n, legs)
            g = sum(m.stage == Stage.GRUPO for m in matches)
            k = sum(m.stage == Stage.SEMIFINAL for m in matches)
            has_final = any(m.stage == Stage.FINAL for m in matches)
            t = match_times(g, k, has_final, cfg)
            label = f"{name} — ida e volta" if legs == 2 else name
            if t.feasible:
                note = None
            elif t.final_seconds is None:
                note = f"Só a fase de grupos ({g} × {cfg.group_match_minutes} min + trocas) passa de {cfg.total_minutes} min"
            else:
                shortest = min(x for x in (t.knockout_seconds, t.final_seconds) if x is not None)
                note = f"Mata-mata ficaria com {shortest // 60}:{shortest % 60:02d} (precisa passar de {cfg.group_match_minutes} min)"
            options.append(FormatOption(code, legs, label, description, groups, matches, len(matches),
                                        t.group_seconds, t.knockout_seconds, t.final_seconds, t.feasible, note))
    order = {id(o): i for i, o in enumerate(options)}
    options.sort(key=lambda o: (not o.feasible, -o.legs, order[id(o)]))
    for o in options:
        if o.feasible:
            o.recommended = True
            break
    return options
