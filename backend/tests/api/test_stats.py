import uuid

import pytest

from tests.api.test_tournament import locked_round, result

pytestmark = pytest.mark.asyncio(loop_scope="session")


def ev(type_, team_id, player_id=None, assist=None, cid=None):
    return {"client_event_id": str(cid or uuid.uuid4()), "type": type_, "team_id": team_id,
            "player_id": player_id, "assist_player_id": assist}


async def setup_tournament(client, h, n_line=15, fmt="GRUPO_REPESCAGEM_FINAL"):
    rid = await locked_round(client, h, n_line)
    t = (await client.post(f"/api/rounds/{rid}/tournament", json={"format_code": fmt}, headers=h)).json()
    return rid, t


async def roster(client, h, match_id):
    sheet = (await client.get(f"/api/matches/{match_id}/events", headers=h)).json()
    return sheet, {int(k): v for k, v in sheet["rosters"].items()}


async def test_sumula_define_placar_e_e_idempotente(client, admin_headers, mesario_headers):
    _, t = await setup_tournament(client, admin_headers)
    m = t["matches"][0]
    home, away = m["home"]["id"], m["away"]["id"]
    sheet, rosters = await roster(client, admin_headers, m["id"])
    scorer, assist = rosters[home][0]["player_id"], rosters[home][1]["player_id"]
    rival = rosters[away][0]["player_id"]

    cid = uuid.uuid4()
    body = ev("GOL", home, scorer, assist, cid)
    s1 = (await client.post(f"/api/matches/{m['id']}/events", json=body, headers=mesario_headers)).json()
    s2 = (await client.post(f"/api/matches/{m['id']}/events", json=body, headers=mesario_headers)).json()
    assert len(s1["events"]) == len(s2["events"]) == 1  # reenvio não duplica
    assert (s2["home_score"], s2["away_score"]) == (1, 0)
    assert s2["events"][0]["player_name"] and s2["events"][0]["assist_name"]

    s = (await client.post(f"/api/matches/{m['id']}/events", json=ev("GOL_CONTRA", away, rival),
                           headers=mesario_headers)).json()
    assert (s["home_score"], s["away_score"]) == (2, 0)  # gol contra conta para o adversário
    s = (await client.post(f"/api/matches/{m['id']}/events", json=ev("AMARELO", away, rival),
                           headers=mesario_headers)).json()
    assert (s["home_score"], s["away_score"]) == (2, 0)

    # Jogador de outro time é recusado
    r = await client.post(f"/api/matches/{m['id']}/events", json=ev("GOL", home, rival), headers=admin_headers)
    assert r.status_code == 422

    # Excluir evento recalcula o placar
    own_goal = next(e for e in s["events"] if e["type"] == "GOL_CONTRA")
    s = (await client.delete(f"/api/events/{own_goal['id']}", headers=mesario_headers)).json()
    assert (s["home_score"], s["away_score"]) == (1, 0)


async def test_placar_rapido_concilia_com_sumula(client, admin_headers):
    _, t = await setup_tournament(client, admin_headers)
    m = t["matches"][0]
    home = m["home"]["id"]
    _, rosters = await roster(client, admin_headers, m["id"])
    await client.post(f"/api/matches/{m['id']}/events", json=ev("GOL", home, rosters[home][0]["player_id"]),
                      headers=admin_headers)
    # 3 × 1: completa com 2 gols sem autor para o mandante e 1 para o visitante
    t = (await result(client, admin_headers, m["id"], 3, 1)).json()
    assert (t["matches"][0]["home_score"], t["matches"][0]["away_score"]) == (3, 1)
    sheet, _ = await roster(client, admin_headers, m["id"])
    assert sum(1 for e in sheet["events"] if e["player_id"] is None) == 3
    # Não dá para baixar abaixo dos gols com autor
    r = await result(client, admin_headers, m["id"], 0, 1)
    assert r.status_code == 422
    # Corrigir para 1 × 0 remove os gols sem autor
    t = (await result(client, admin_headers, m["id"], 1, 0)).json()
    assert (t["matches"][0]["home_score"], t["matches"][0]["away_score"]) == (1, 0)


async def test_evento_em_partida_encerrada_atualiza_classificacao(client, admin_headers):
    _, t = await setup_tournament(client, admin_headers)
    m = t["matches"][0]
    t = (await result(client, admin_headers, m["id"], 0, 0)).json()
    assert {r["points"] for r in t["groups"][0]["standings"] if r["played"]} == {1}
    _, rosters = await roster(client, admin_headers, m["id"])
    home = m["home"]["id"]
    await client.post(f"/api/matches/{m['id']}/events", json=ev("GOL", home, rosters[home][0]["player_id"]),
                      headers=admin_headers)
    t = (await client.get(f"/api/tournaments/{t['id']}", headers=admin_headers)).json()
    leader = t["groups"][0]["standings"][0]
    assert leader["team"]["id"] == home and leader["points"] == 3


async def test_estatisticas_e_resumo(client, admin_headers, jogador_headers):
    rid, t = await setup_tournament(client, admin_headers)
    order = [x["id"] for x in t["teams"]]
    strength = {tid: i for i, tid in enumerate(order)}
    star = None
    for m in t["matches"][:3]:
        _, rosters = await roster(client, admin_headers, m["id"])
        winner = m["home"]["id"] if strength[m["home"]["id"]] < strength[m["away"]["id"]] else m["away"]["id"]
        scorer = rosters[winner][0]["player_id"]
        star = star or (scorer if winner == order[0] else None)
        await client.post(f"/api/matches/{m['id']}/events", json=ev("GOL", winner, scorer), headers=admin_headers)
        loser = m["away"]["id"] if winner == m["home"]["id"] else m["home"]["id"]
        await client.post(f"/api/matches/{m['id']}/events",
                          json=ev("AMARELO", loser, rosters[loser][0]["player_id"]), headers=admin_headers)
        t = (await result(client, admin_headers, m["id"], *((1, 0) if winner == m["home"]["id"] else (0, 1)))).json()
    rep, final = t["matches"][3], t["matches"][4]
    t = (await result(client, admin_headers, rep["id"], 2, 0)).json()
    t = (await result(client, admin_headers, final["id"], 1, 0)).json()
    assert t["champion"]["id"] == order[0]

    summary = (await client.get(f"/api/tournaments/{t['id']}/summary", headers=jogador_headers)).json()
    assert summary["total_yellows"] == 3
    assert summary["top_scorers"][0]["player_id"] == star  # 2 gols com autor (os do placar rápido não têm)
    assert summary["top_scorers"][0]["goals"] == 2

    stats = (await client.get("/api/stats/players", headers=jogador_headers)).json()
    s = next(x for x in stats if x["player_id"] == star)
    assert s["goals"] == 2 and s["titles"] == 1 and s["presences"] == 1
    assert s["matches"] == 3 and s["wins"] == 3 and s["win_rate"] == 100.0  # 2 do grupo + final
    assert len(stats) == 15  # todos os escalados aparecem (presença)

    profile = (await client.get(f"/api/stats/players/{star}", headers=jogador_headers)).json()
    assert profile["stats"]["goals"] == 2
    (h,) = profile["history"]
    assert h["round_id"] == rid and h["champion"] and h["goals"] == 2

    assert (await client.get("/api/stats/players", params={"year": 2020}, headers=jogador_headers)).json() == []
    # Jogador não registra eventos
    r = await client.post(f"/api/matches/{final['id']}/events", json=ev("GOL", order[0]), headers=jogador_headers)
    assert r.status_code == 403
