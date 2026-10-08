"""Testes do empréstimo de jogadores após a chamada."""
from app.domain.loans import Loan, LoanMatch, LoanPlayer, missing_by_team, plan_loans

POS = ("ZAGUEIRO", "ZAGUEIRO", "ALA", "ALA", "ATACANTE")


def team(team_id, first_id, strengths=(6, 6, 6, 6, 6), extra=False):
    out = [LoanPlayer(first_id + i, f"T{team_id}P{i}", team_id, "LINHA", POS[i], POS[i], strength=s)
           for i, s in enumerate(strengths)]
    if extra:
        out.append(LoanPlayer(first_id + 9, f"T{team_id}R", team_id, "REVEZAMENTO", "ALA", "ALA"))
    return out


# 3 times (1, 2, 3): A×B, A×C, B×C, A×B, ...
def schedule(n=6):
    pairs = [(1, 2), (1, 3), (2, 3)]
    return [LoanMatch(10 + i, i + 1, *pairs[i % 3]) for i in range(n)]


def test_time_de_6_que_perde_um_nao_precisa_de_emprestimo():
    players = team(1, 100, extra=True) + team(2, 200) + team(3, 300)
    assert missing_by_team(players, {100}, 5) == {}
    assert plan_loans(players, {100}, schedule()).loans == []


def test_emprestimo_vem_do_time_de_fora_e_da_mesma_posicao():
    players = team(1, 100) + team(2, 200) + team(3, 300)
    plan = plan_loans(players, {100}, schedule(3))  # faltou um zagueiro do time 1
    by_match = {x.match_id: x for x in plan.loans}
    assert set(by_match) == {10, 11}  # o time 1 joga as partidas 1 e 2
    assert by_match[10].from_team_id == 3  # 1×2: o de fora é o 3
    assert by_match[11].from_team_id == 2  # 1×3: o de fora é o 2
    assert all(next(p for p in players if p.id == x.player_id).position == "ZAGUEIRO" for x in plan.loans)


def test_rodizio_nao_repete_o_mesmo_emprestado():
    players = team(1, 100) + team(2, 200) + team(3, 300)
    plan = plan_loans(players, {100}, schedule(6))
    from_3 = [x.player_id for x in plan.loans if x.from_team_id == 3]
    assert len(from_3) == 2 and len(set(from_3)) == 2  # os 2 zagueiros do time 3 se revezam


def test_evita_quem_joga_a_partida_seguinte():
    # 4 times: no jogo 1×2 estão de fora 3 e 4; o jogo seguinte é 3×1, então o emprestado vem do 4
    players = team(1, 100) + team(2, 200) + team(3, 300) + team(4, 400)
    matches = [LoanMatch(10, 1, 1, 2), LoanMatch(11, 2, 3, 1), LoanMatch(12, 3, 2, 4)]
    plan = plan_loans(players, {100}, matches)
    assert next(x for x in plan.loans if x.match_id == 10).from_team_id == 4


def test_forca_parecida_com_a_de_quem_faltou():
    players = team(1, 100, strengths=(9, 6, 6, 6, 6)) + team(2, 200) + team(3, 300, strengths=(3, 9, 6, 6, 6))
    plan = plan_loans(players, {100}, [LoanMatch(10, 1, 1, 2)])
    assert plan.loans[0].player_id == 301  # zagueiro de força 9, como quem faltou
    assert plan.loans[0].strength_delta == 0


def test_atrasado_que_chega_cancela_emprestimos_futuros():
    players = team(1, 100) + team(2, 200) + team(3, 300)
    matches = schedule(3)
    first = plan_loans(players, {100}, matches)
    done = [x for x in first.loans if x.match_id == 10]
    finished = [LoanMatch(10, 1, 1, 2, finished=True)] + matches[1:]
    after = plan_loans(players, set(), finished, fixed=done)  # chegou depois do 1º jogo
    assert after.loans == done  # o jogo encerrado mantém o empréstimo; os próximos não têm mais


def test_jogo_encerrado_conta_no_rodizio():
    players = team(1, 100) + team(2, 200) + team(3, 300)
    fixed = [Loan(10, 1, 300, 3, 100, 0.0)]
    plan = plan_loans(players, {100}, [LoanMatch(10, 1, 1, 2, finished=True), LoanMatch(11, 2, 1, 2)], fixed=fixed)
    assert next(x for x in plan.loans if x.match_id == 11).player_id == 301


def test_dois_times_sem_time_de_fora():
    players = team(1, 100) + team(2, 200)
    plan = plan_loans(players, {100}, [LoanMatch(10, 1, 1, 2)])
    assert plan.loans == [] and plan.unfilled == {10: [100]}


def test_goleiro_fixo_nunca_e_emprestado():
    players = team(1, 100) + team(2, 200) + [LoanPlayer(399, "G", 3, "GOLEIRO_FIXO", "GOLEIRO_FIXO")]
    plan = plan_loans(players, {100}, [LoanMatch(10, 1, 1, 2)])
    assert plan.loans == [] and plan.unfilled == {10: [100]}
