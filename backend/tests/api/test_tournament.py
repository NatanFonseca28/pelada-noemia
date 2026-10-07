import pytest

from tests.api.test_rounds import confirm_all, make_players, new_round

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def locked_round(client, h, n_line, date="2026-10-07"):
    ids = await make_players(client, h, n_line)
    rid = await new_round(client, h, date)
    await confirm_all(client, h, rid, ids)
    r = await client.post(f"/api/rounds/{rid}/draw", json={}, headers=h)
    assert r.status_code == 200, r.text
    await client.post(f"/api/rounds/{rid}/lock", headers=h)
    return rid


async def result(client, h, mid, hs, as_, hp=None, ap=None):
    body = {"home_score": hs, "away_score": as_}
    if hp is not None:
        body |= {"home_penalties": hp, "away_penalties": ap}
    return await client.post(f"/api/matches/{mid}/result", json=body, headers=h)


async def test_formatos_e_criacao_exige_times_travados(client, admin_headers):
    ids = await make_players(client, admin_headers, 15)
    rid = await new_round(client, admin_headers)
    await confirm_all(client, admin_headers, rid, ids)
    await client.post(f"/api/rounds/{rid}/draw", json={}, headers=admin_headers)

    f = (await client.get(f"/api/rounds/{rid}/tournament/formats", headers=admin_headers)).json()
    assert f["num_teams"] == 3
    assert {o["code"] for o in f["options"]} == {"GRUPO_REPESCAGEM_FINAL"}
    best = next(o for o in f["options"] if o["recommended"])
    assert best["legs"] == 2  # há tempo: ida e volta

    r = await client.post(f"/api/rounds/{rid}/tournament", json={"format_code": "GRUPO_REPESCAGEM_FINAL"},
                          headers=admin_headers)
    assert r.status_code == 422  # times não travados
    await client.post(f"/api/rounds/{rid}/lock", headers=admin_headers)
    r = await client.post(f"/api/rounds/{rid}/tournament",
                          json={"format_code": "GRUPO_REPESCAGEM_FINAL", "legs": 2, "final_weight": "1.5"},
                          headers=admin_headers)
    assert r.status_code == 201, r.text
    t = r.json()
    assert t["legs"] == 2 and len(t["matches"]) == 8
    assert [m["leg"] for m in t["matches"][:6]] == [1, 1, 1, 2, 2, 2]
    # 8 jogos, troca 2: tabela fixa de 8 min; o resto (76 − 48 = 28 min) vai para 2º×3º e final
    assert t["match_seconds"] == 480
    rep_, final = t["matches"][6], t["matches"][7]
    assert rep_["home_label"] == "2º do grupo A" and rep_["away_label"] == "3º do grupo A"
    assert final["home_label"] == "1º do grupo A" and final["away_label"] == "Vencedor 2º × 3º"
    # Fecha exatamente 90 minutos
    total = sum(m["planned_seconds"] for m in t["matches"]) + 2 * 60 * 7
    assert total == 90 * 60 and final["planned_seconds"] > rep_["planned_seconds"]
    # Não pode destravar com campeonato criado
    assert (await client.post(f"/api/rounds/{rid}/unlock", headers=admin_headers)).status_code == 422


async def test_campeonato_completo_com_semis_e_penaltis(client, admin_headers, mesario_headers):
    rid = await locked_round(client, admin_headers, 20)  # 4 times
    t = (await client.post(f"/api/rounds/{rid}/tournament", json={"format_code": "GRUPO_SEMI_FINAL"},
                           headers=admin_headers)).json()
    assert len(t["matches"]) == 9
    order = [team["id"] for team in t["teams"]]
    strength = {tid: i for i, tid in enumerate(order)}  # time de menor índice vence

    # Mesário lança os resultados da fase de grupos
    for m in t["matches"][:6]:
        hs, as_ = (2, 0) if strength[m["home"]["id"]] < strength[m["away"]["id"]] else (0, 2)
        r = await result(client, mesario_headers, m["id"], hs, as_)
        assert r.status_code == 200, r.text
    t = r.json()
    table = t["groups"][0]["standings"]
    assert [row["team"]["id"] for row in table] == order and t["groups"][0]["complete"]
    sf1, sf2, final = t["matches"][6:]
    assert (sf1["home"]["id"], sf1["away"]["id"]) == (order[0], order[2])  # 1º × 3º
    assert (sf2["home"]["id"], sf2["away"]["id"]) == (order[1], order[3])  # 2º × 4º
    assert final["home"] is None

    # Empate no mata-mata exige pênaltis
    r = await result(client, admin_headers, sf1["id"], 1, 1)
    assert r.status_code == 422 and "pênaltis" in r.json()["detail"]
    t = (await result(client, admin_headers, sf1["id"], 1, 1, 3, 4)).json()
    assert t["matches"][8]["home"]["id"] == order[2]  # vencedor dos pênaltis vai à final
    t = (await result(client, admin_headers, sf2["id"], 0, 1)).json()
    final = t["matches"][8]
    assert (final["home"]["id"], final["away"]["id"]) == (order[2], order[3])

    # Não dá para corrigir a semi depois da final
    t = (await result(client, admin_headers, final["id"], 2, 0)).json()
    assert t["status"] == "ENCERRADO" and t["champion"]["id"] == order[2] and t["runner_up"]["id"] == order[3]
    rnd = (await client.get(f"/api/rounds/{rid}", headers=admin_headers)).json()
    assert rnd["status"] == "ENCERRADA"
    r = await result(client, admin_headers, sf1["id"], 2, 0)
    assert r.status_code == 422 and "F" in r.json()["detail"]

    # Reabrir a final volta o campeonato para andamento
    t = (await client.post(f"/api/matches/{final['id']}/reopen", headers=admin_headers)).json()
    assert t["status"] == "EM_ANDAMENTO" and t["champion"] is None
    # Mesário também pode reabrir (escape para encerramento acidental); jogador não
    await result(client, admin_headers, final["id"], 2, 0)
    assert (await client.post(f"/api/matches/{final['id']}/reopen", headers=mesario_headers)).status_code == 200


async def test_dois_grupos_cruzados(client, admin_headers):
    rid = await locked_round(client, admin_headers, 25)  # 5 times
    t = (await client.post(f"/api/rounds/{rid}/tournament", json={"format_code": "DOIS_GRUPOS_SEMI_FINAL"},
                           headers=admin_headers)).json()
    assert sorted(len(g["standings"]) for g in t["groups"]) == [2, 3]
    group_matches = [m for m in t["matches"] if m["stage"] == "GRUPO"]
    for m in group_matches:
        t = (await result(client, admin_headers, m["id"], 1, 0)).json()
    tables = {g["name"]: [r["team"]["id"] for r in g["standings"]] for g in t["groups"]}
    sf1, sf2 = [m for m in t["matches"] if m["stage"] == "SEMIFINAL"]
    assert (sf1["home"]["id"], sf1["away"]["id"]) == (tables["A"][0], tables["B"][1])
    assert (sf2["home"]["id"], sf2["away"]["id"]) == (tables["B"][0], tables["A"][1])


async def test_3_times_repescagem_e_final(client, admin_headers):
    rid = await locked_round(client, admin_headers, 15)
    t = (await client.post(f"/api/rounds/{rid}/tournament", json={"format_code": "GRUPO_REPESCAGEM_FINAL"},
                           headers=admin_headers)).json()
    order = [team["id"] for team in t["teams"]]
    strength = {tid: i for i, tid in enumerate(order)}
    for m in t["matches"][:3]:
        hs, as_ = (1, 0) if strength[m["home"]["id"]] < strength[m["away"]["id"]] else (0, 1)
        t = (await result(client, admin_headers, m["id"], hs, as_)).json()
    rep_, final = t["matches"][3], t["matches"][4]
    assert (rep_["home"]["id"], rep_["away"]["id"]) == (order[1], order[2])
    assert final["home"]["id"] == order[0] and final["away"] is None
    t = (await result(client, admin_headers, rep_["id"], 0, 2)).json()
    assert t["matches"][4]["away"]["id"] == order[2]  # vencedor do 2º×3º enfrenta o 1º
    t = (await result(client, admin_headers, final["id"], 0, 1)).json()
    assert t["champion"]["id"] == order[2] and t["runner_up"]["id"] == order[0]


async def test_pelada_normal(client, admin_headers, jogador_headers):
    rid = await locked_round(client, admin_headers, 12)
    f = (await client.get(f"/api/rounds/{rid}/tournament/formats", headers=admin_headers)).json()
    assert [o["code"] for o in f["options"]] == ["PELADA_NORMAL"]
    t = (await client.post(f"/api/rounds/{rid}/tournament", json={"format_code": "PELADA_NORMAL"},
                           headers=admin_headers)).json()
    m1 = t["matches"][0]
    assert m1["goal_limit"] == 2 and m1["planned_seconds"] == 600
    r = await client.post(f"/api/tournaments/{t['id']}/matches", headers=admin_headers)
    assert r.status_code == 422  # partida atual não terminou
    await result(client, admin_headers, m1["id"], 2, 1)
    t = (await client.post(f"/api/tournaments/{t['id']}/matches", headers=admin_headers)).json()
    assert len(t["matches"]) == 2
    assert t["groups"][0]["standings"][0]["wins"] == 1
    # Jogador vê, mas não lança resultado
    assert (await client.get(f"/api/rounds/{rid}/tournament", headers=jogador_headers)).status_code == 200
    assert (await result(client, jogador_headers, t["matches"][1]["id"], 0, 0)).status_code == 403
    t = (await client.post(f"/api/tournaments/{t['id']}/finish", headers=admin_headers)).json()
    assert t["status"] == "ENCERRADO" and len(t["matches"]) == 1


async def test_excluir_campeonato_volta_rodada(client, admin_headers):
    rid = await locked_round(client, admin_headers, 15)
    t = (await client.post(f"/api/rounds/{rid}/tournament", json={"format_code": "GRUPO_REPESCAGEM_FINAL"},
                           headers=admin_headers)).json()
    assert (await client.delete(f"/api/tournaments/{t['id']}", headers=admin_headers)).status_code == 204
    assert (await client.get(f"/api/rounds/{rid}/tournament", headers=admin_headers)).status_code == 404
    assert (await client.post(f"/api/rounds/{rid}/unlock", headers=admin_headers)).status_code == 200


async def test_finalizar_sumula_grava_tempo_com_e_sem_pausas(client, admin_headers, mesario_headers, jogador_headers):
    rid = await locked_round(client, admin_headers, 15)
    t = (await client.post(f"/api/rounds/{rid}/tournament", json={"format_code": "GRUPO_REPESCAGEM_FINAL"},
                           headers=admin_headers)).json()
    m = t["matches"][0]
    body = {"home_score": 0, "away_score": 0, "started_at": "2026-10-21T20:00:00Z",
            "ended_at": "2026-10-21T20:11:40Z", "played_seconds": 552}
    t = (await client.post(f"/api/matches/{m['id']}/result", json=body, headers=mesario_headers)).json()
    done = t["matches"][0]
    assert done["elapsed_before_pause"] == 552  # 9:12 jogados
    assert done["started_at"].startswith("2026-10-21T20:00") and done["ended_at"].startswith("2026-10-21T20:11:40")

    # fim antes do início é recusado
    bad = {**body, "ended_at": "2026-10-21T19:00:00Z"}
    assert (await client.post(f"/api/matches/{m['id']}/result", json=bad, headers=admin_headers)).status_code == 422
    # jogador não reabre
    assert (await client.post(f"/api/matches/{m['id']}/reopen", headers=jogador_headers)).status_code == 403


async def test_quem_comeca_com_a_bola(client, admin_headers):
    from collections import Counter

    rid = await locked_round(client, admin_headers, 15)
    t = (await client.post(f"/api/rounds/{rid}/tournament", json={"format_code": "GRUPO_REPESCAGEM_FINAL"},
                           headers=admin_headers)).json()
    groups = [m for m in t["matches"] if m["stage"] == "GRUPO"]
    # fase de grupos: cada time dá a saída o mesmo número de vezes
    assert all(m["kickoff_team_id"] in (m["home"]["id"], m["away"]["id"]) for m in groups)
    assert len(set(Counter(m["kickoff_team_id"] for m in groups).values())) == 1
    # mata-mata ainda sem times definidos: sem saída
    assert all(m["kickoff_team_id"] is None for m in t["matches"] if m["stage"] != "GRUPO")

    for m, (h, a) in zip(groups, [(1, 0), (2, 0), (1, 0)], strict=True):
        await result(client, admin_headers, m["id"], h, a)
    t = (await client.get(f"/api/tournaments/{t['id']}", headers=admin_headers)).json()
    ranking = [row["team"]["id"] for row in t["groups"][0]["standings"]]  # 1º, 2º, 3º
    repescagem = t["matches"][3]  # 2º × 3º
    assert repescagem["kickoff_team_id"] == ranking[1]  # 2º colocado (melhor campanha que o 3º)
    await result(client, admin_headers, repescagem["id"], 0, 1)  # o 3º vence a repescagem
    t = (await client.get(f"/api/tournaments/{t['id']}", headers=admin_headers)).json()
    final = next(m for m in t["matches"] if m["stage"] == "FINAL")
    assert final["kickoff_team_id"] == ranking[0]  # 1º colocado sempre sai na final
