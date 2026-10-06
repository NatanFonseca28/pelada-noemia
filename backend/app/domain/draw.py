"""Sorteio de times — serviço puro (sem banco), determinístico pela seed.

Regras (ver plano, seção 0 e "Regras do sorteio"):
 1. Goleiros fixos são separados dos jogadores de linha.
 2. N = floor(linha / 5) (ou o nº escolhido pelo admin). Mínimo 2 times; com 2 times,
    cada time precisa de goleiro fixo ou excedente (mínimo 12 jogadores) → "pelada normal".
    Com 3+ times é campeonato; time sem goleiro usa voluntário do time de fora.
 3. Grupos por posição principal, embaralhados (ou ordenados por nível, se equilibrar).
 4. Distribuição circular por posição até a cota 2 ZAG / 2 ALA / 1 ATA.
 5. Vagas sem jogador da posição: 1º quem tem a posição como secundária, depois jogadores
    sem posição definida, depois qualquer restante. Tudo registrado em `substitutions`.
 6. Excedentes (linha mod 5) vão um por time, priorizando times sem goleiro fixo,
    marcados como revezamento no gol.
 7. Goleiros fixos sorteados entre os times, no máximo um por time; sobras geram aviso.
 8. "Equilibrar por nível": ordem serpentina pelo nível dentro de cada posição.
 9. A seed e o resultado são devolvidos para persistência/auditoria.
10. Sobra grande → `alternatives` para o admin decidir.
"""
import random
from dataclasses import asdict, dataclass, field
from enum import StrEnum

ALGORITHM_VERSION = "1.0"
DEFAULT_LEVEL = 3

LINE_POSITIONS = ("ZAGUEIRO", "ALA", "ATACANTE")
GOALKEEPER = "GOLEIRO_FIXO"
TEAM_NAMES = [
    ("Verde", "#1f9d55"),
    ("Azul", "#2f6fdb"),
    ("Vermelho", "#e0443a"),
    ("Amarelo", "#f4c20d"),
    ("Preto", "#1f2937"),
    ("Branco", "#e5e7eb"),
    ("Laranja", "#ea580c"),
    ("Roxo", "#7c3aed"),
]


class DrawError(ValueError):
    """Erro de regra do sorteio (mensagem pronta para exibir ao admin)."""


class Role(StrEnum):
    LINHA = "LINHA"
    GOLEIRO_FIXO = "GOLEIRO_FIXO"
    REVEZAMENTO = "REVEZAMENTO"  # excedente que reveza no gol


class FilledBy(StrEnum):
    PRIMARIA = "PRIMARIA"
    SECUNDARIA = "SECUNDARIA"
    SEM_POSICAO = "SEM_POSICAO"
    QUALQUER = "QUALQUER"


class Mode(StrEnum):
    PELADA_NORMAL = "PELADA_NORMAL"
    CAMPEONATO = "CAMPEONATO"


@dataclass(frozen=True)
class DrawPlayer:
    id: int
    name: str
    primary: str | None  # None = posição a definir
    secondary: str | None = None
    level: int | None = None

    @property
    def lvl(self) -> int:
        return self.level or DEFAULT_LEVEL


@dataclass(frozen=True)
class DrawConfig:
    line_per_team: int = 5
    balance_by_skill: bool = False
    extra_team_threshold: int = 3

    @property
    def composition(self) -> dict[str, int]:
        """2/2/1 para 5 na linha; proporcional para outros tamanhos (mín. 1 atacante)."""
        n = self.line_per_team
        if n == 5:
            return {"ZAGUEIRO": 2, "ALA": 2, "ATACANTE": 1}
        zag = max(1, round(n * 0.4))
        ala = max(1, round(n * 0.4))
        ata = max(1, n - zag - ala)
        while zag + ala + ata > n:
            ala -= 1
        return {"ZAGUEIRO": zag, "ALA": ala, "ATACANTE": ata}


@dataclass
class TeamSlot:
    player_id: int
    name: str
    position: str  # posição em que foi escalado (ou GOLEIRO_FIXO)
    role: Role
    filled_by: FilledBy
    level: int


@dataclass
class Team:
    index: int
    name: str
    color: str
    players: list[TeamSlot] = field(default_factory=list)

    @property
    def has_fixed_gk(self) -> bool:
        return any(p.role == Role.GOLEIRO_FIXO for p in self.players)

    @property
    def has_rotation_gk(self) -> bool:
        return any(p.role == Role.REVEZAMENTO for p in self.players)

    @property
    def line_count(self) -> int:
        return sum(1 for p in self.players if p.role != Role.GOLEIRO_FIXO)

    @property
    def level_sum(self) -> int:
        return sum(p.level for p in self.players if p.role != Role.GOLEIRO_FIXO)


@dataclass
class Substitution:
    player_id: int
    name: str
    team_index: int
    position: str
    filled_by: FilledBy


@dataclass
class Alternative:
    num_teams: int
    line_sizes: list[int]
    mode: Mode
    description: str


@dataclass
class DrawResult:
    seed: int
    algorithm_version: str
    mode: Mode
    num_teams: int
    teams: list[Team]
    substitutions: list[Substitution]
    warnings: list[str]
    infos: list[str]
    alternatives: list[Alternative]
    unassigned: list[int]  # goleiros fixos sem time

    def to_dict(self) -> dict:
        data = asdict(self)
        for team, raw in zip(self.teams, data["teams"], strict=True):
            raw.update(
                has_fixed_gk=team.has_fixed_gk,
                uses_volunteer_gk=self.mode == Mode.CAMPEONATO and not team.has_fixed_gk and not team.has_rotation_gk,
                line_count=team.line_count,
                level_sum=team.level_sum,
            )
        return data


# ---------------------------------------------------------------- helpers


def _order_candidates(players: list[DrawPlayer], rng: random.Random, balance: bool) -> list[DrawPlayer]:
    shuffled = list(players)
    rng.shuffle(shuffled)
    if balance:
        # estável: empates de nível mantêm a ordem aleatória acima
        shuffled.sort(key=lambda p: p.lvl, reverse=True)
    return shuffled


def _line_sizes(line_total: int, num_teams: int, per_team: int) -> list[int]:
    """Tamanho de linha alvo por time, SEM excedentes (no máximo `per_team`)."""
    if num_teams * per_team <= line_total:
        return [per_team] * num_teams
    base, rest = divmod(line_total, num_teams)
    return [base + 1 if i < rest else base for i in range(num_teams)]


def _quotas(sizes: list[int], config: DrawConfig) -> list[dict[str, int]]:
    """Cota por posição de cada time; times menores perdem vaga de ATA, depois ALA, depois ZAG."""
    quotas = []
    for size in sizes:
        q = dict(config.composition)
        deficit = config.line_per_team - size
        order = ["ATACANTE", "ALA", "ZAGUEIRO"]
        i = 0
        while deficit > 0 and any(q.values()):
            pos = order[i % 3]
            if q[pos] > 0:
                q[pos] -= 1
                deficit -= 1
            i += 1
        quotas.append(q)
    return quotas


def _team_order(n: int, round_no: int, balance: bool, offset: int) -> list[int]:
    base = [(offset + i) % n for i in range(n)]
    if balance and round_no % 2 == 1:
        return list(reversed(base))  # serpentina
    return base


def _describe(num_teams: int, sizes: list[int], per_team: int) -> str:
    mode = "pelada normal" if num_teams == 2 else "campeonato"
    sizes_txt = "/".join(str(s) for s in sizes)
    short = sum(1 for s in sizes if s < per_team)
    extra = f", {short} time(s) completado(s) por voluntário" if short else ""
    return f"{num_teams} times ({sizes_txt} na linha) — {mode}{extra}"


def max_teams(line_total: int, per_team: int) -> int:
    return -(-line_total // per_team)  # ceil


def suggest_alternatives(line_total: int, config: DrawConfig) -> list[Alternative]:
    """Formações possíveis quando a sobra é grande (regra 10)."""
    per = config.line_per_team
    n = line_total // per
    rest = line_total - n * per
    if n < 2 or rest < config.extra_team_threshold:
        return []
    options = []
    for teams in (n, n + 1):
        if teams > max_teams(line_total, per) or (teams >= 3 and line_total < 3 * per):
            continue  # campeonato exige ao menos 3 times completos de linha (15 jogadores)
        base = _line_sizes(line_total, teams, per)
        extra = line_total - sum(base)
        sizes = [s + (1 if i < extra % teams else 0) + extra // teams for i, s in enumerate(base)]
        mode = Mode.PELADA_NORMAL if teams == 2 else Mode.CAMPEONATO
        options.append(Alternative(teams, sizes, mode, _describe(teams, sizes, per)))
    return options


# ---------------------------------------------------------------- sorteio


def run_draw(
    players: list[DrawPlayer],
    config: DrawConfig,
    seed: int,
    num_teams: int | None = None,
) -> DrawResult:
    if len({p.id for p in players}) != len(players):
        raise DrawError("Jogador repetido na lista de confirmados")
    rng = random.Random(seed)
    per = config.line_per_team

    # Entrada ordenada por id: o resultado depende só da seed, não da ordem recebida
    players = sorted(players, key=lambda p: p.id)
    goalkeepers = [p for p in players if p.primary == GOALKEEPER]
    line = [p for p in players if p.primary != GOALKEEPER]
    total_line = len(line)

    # 2. Número de times
    auto_n = total_line // per
    if num_teams is None:
        n = auto_n
    else:
        n = num_teams
        if n > max_teams(total_line, per):
            raise DrawError(f"Jogadores de linha insuficientes para {n} times ({total_line} confirmados)")
    if n >= 3 and total_line < 3 * per:
        raise DrawError(f"Campeonato exige ao menos {3 * per} jogadores de linha (há {total_line}).")
    if n < 2:
        raise DrawError(
            f"São necessários ao menos {2 * per} jogadores de linha para 2 times "
            f"(há {total_line} de linha e {len(goalkeepers)} goleiro(s) fixo(s))."
        )

    sizes = _line_sizes(total_line, n, per)
    surplus = total_line - sum(sizes)  # excedentes
    if n == 2 and min(len(goalkeepers), 2) + surplus < 2:
        raise DrawError(
            "Para 2 times cada um precisa de um goleiro (fixo ou jogador a mais para revezar): "
            f"são necessários no mínimo {2 * per + 2} jogadores. Há {total_line} de linha e "
            f"{len(goalkeepers)} goleiro(s) fixo(s)."
        )

    teams = [Team(i, *TEAM_NAMES[i % len(TEAM_NAMES)]) for i in range(n)]
    quotas = _quotas(sizes, config)
    substitutions: list[Substitution] = []
    warnings: list[str] = []
    infos: list[str] = []

    # 3. Grupos por posição
    groups = {pos: _order_candidates([p for p in line if p.primary == pos], rng, config.balance_by_skill)
              for pos in LINE_POSITIONS}
    no_position = _order_candidates([p for p in line if p.primary is None], rng, config.balance_by_skill)
    if no_position:
        infos.append(
            f"{len(no_position)} jogador(es) sem posição definida foram usados como coringa: "
            + ", ".join(p.name for p in sorted(no_position, key=lambda p: p.name))
        )

    def place(team: Team, p: DrawPlayer, position: str, filled_by: FilledBy, role: Role = Role.LINHA) -> None:
        team.players.append(TeamSlot(p.id, p.name, position, role, filled_by, p.lvl))

    # Posições em falta: quem as tem como secundária vai para o fim da fila da própria
    # posição, para sobrar e cobrir a falta (regra 5)
    need = {pos: sum(q[pos] for q in quotas) for pos in LINE_POSITIONS}
    scarce = {pos for pos in LINE_POSITIONS if len(groups[pos]) < need[pos]}
    if scarce:
        for pos in LINE_POSITIONS:
            groups[pos].sort(key=lambda p: p.secondary in scarce)  # sort estável

    # 4. Distribuição circular por posição
    offset = rng.randrange(n)
    missing: dict[str, list[int]] = {pos: [] for pos in LINE_POSITIONS}
    for pos in LINE_POSITIONS:
        pool = groups[pos]
        rounds = max(q[pos] for q in quotas)
        for r in range(rounds):
            for t in _team_order(n, r, config.balance_by_skill, offset):
                if quotas[t][pos] > r:
                    if pool:
                        place(teams[t], pool.pop(0), pos, FilledBy.PRIMARIA)
                    else:
                        missing[pos].append(t)
        offset = (offset + 1) % n

    # 5. Vagas sem jogador da posição
    leftovers = [p for pos in LINE_POSITIONS for p in groups[pos]]
    leftovers = _order_candidates(leftovers, rng, config.balance_by_skill)
    for pos in sorted(LINE_POSITIONS, key=lambda p: -len(missing[p])):
        for t in missing[pos]:
            candidate, how = None, None
            for p in leftovers:
                if p.secondary == pos:
                    candidate, how = p, FilledBy.SECUNDARIA
                    break
            if candidate is None and no_position:
                candidate, how = no_position[0], FilledBy.SEM_POSICAO
            if candidate is None and leftovers:
                candidate, how = leftovers[0], FilledBy.QUALQUER
            if candidate is None:
                continue  # impossível: total de vagas ≤ jogadores de linha
            (no_position if how == FilledBy.SEM_POSICAO else leftovers).remove(candidate)
            place(teams[t], candidate, pos, how)
            substitutions.append(Substitution(candidate.id, candidate.name, t, pos, how))

    # 7. Goleiros fixos (antes dos excedentes, para priorizar times sem goleiro)
    gk_pool = list(goalkeepers)
    rng.shuffle(gk_pool)
    team_order = list(range(n))
    rng.shuffle(team_order)
    unassigned: list[int] = []
    for i, gk in enumerate(gk_pool):
        if i < n:
            place(teams[team_order[i]], gk, GOALKEEPER, FilledBy.PRIMARIA, Role.GOLEIRO_FIXO)
        else:
            unassigned.append(gk.id)
    if unassigned:
        names = ", ".join(g.name for g in gk_pool[n:])
        warnings.append(
            f"Há mais goleiros fixos ({len(gk_pool)}) do que times ({n}). Sem time: {names}. "
            "Mova-os manualmente para a linha ou deixe-os de fora."
        )

    # 6. Excedentes: um por time, priorizando quem não tem goleiro fixo
    extras = _order_candidates(leftovers + no_position, rng, config.balance_by_skill)
    without_gk = [t for t in team_order if not teams[t].has_fixed_gk]
    with_gk = [t for t in team_order if teams[t].has_fixed_gk]
    if config.balance_by_skill:
        without_gk.sort(key=lambda t: teams[t].level_sum)
        with_gk.sort(key=lambda t: teams[t].level_sum)
    priority = without_gk + with_gk
    for i, p in enumerate(extras):
        t = priority[i % n]
        position = p.primary or "ALA"
        how = FilledBy.PRIMARIA if p.primary else FilledBy.SEM_POSICAO
        place(teams[t], p, position, how, Role.REVEZAMENTO)

    # Times sem goleiro
    no_keeper = [t for t in teams if not t.has_fixed_gk and not t.has_rotation_gk]
    mode = Mode.PELADA_NORMAL if n == 2 else Mode.CAMPEONATO
    if no_keeper:
        infos.append(
            "Sem goleiro fixo nem excedente: "
            + ", ".join(f"Time {t.name}" for t in no_keeper)
            + ". O gol fica com um voluntário do time que está fora da partida."
        )
    if mode == Mode.PELADA_NORMAL:
        infos.append("Apenas 2 times: pelada normal (sem campeonato).")

    alternatives = suggest_alternatives(total_line, config) if num_teams is None else []
    if alternatives:
        warnings.append(
            f"Sobraram {total_line - auto_n * per} jogadores de linha. Veja as formações alternativas antes de travar."
        )

    for team in teams:
        order = {pos: i for i, pos in enumerate((GOALKEEPER, *LINE_POSITIONS))}
        team.players.sort(key=lambda s: (s.role == Role.REVEZAMENTO, order[s.position], s.name))

    return DrawResult(
        seed=seed,
        algorithm_version=ALGORITHM_VERSION,
        mode=mode,
        num_teams=n,
        teams=teams,
        substitutions=substitutions,
        warnings=warnings,
        infos=infos,
        alternatives=alternatives,
        unassigned=unassigned,
    )


def new_seed() -> int:
    return random.SystemRandom().randrange(1, 2**31)
