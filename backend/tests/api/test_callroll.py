"""Chamada no local + empréstimo de jogadores (roteiro do teste em produção)."""
import uuid

import pytest

from tests.api.test_tournament import locked_round, result

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_chamada_falta_emprestimo_e_atrasado(client, admin_headers, mesario_headers, jogador_headers):
    rid = await locked_round(client, admin_headers, 15, date="2026-12-30")  # 3 times de 5
    r = await client.post(f"/api/rounds/{rid}/tournament", json={"format_code": "GRUPO_REPESCAGEM_FINAL"},
                          headers=admin_headers)
    assert r.status_code == 201, r.text
    d = (await client.get(f"/api/rounds/{rid}", headers=admin_headers)).json()
    assert d["loans"] == [] and all(a["checkin"] is None for a in d["attendances"])

    # jogador comum não faz chamada; mesário faz
    some = d["teams"][0]["players"][0]["player_id"]
    assert (await client.put(f"/api/rounds/{rid}/checkin/{some}", json={"status": "FALTOU"},
                             headers=jogador_headers)).status_code == 403
    d = (await client.post(f"/api/rounds/{rid}/checkin/all-present", headers=mesario_headers)).json()
    assert all(a["checkin"] == "PRESENTE" for a in d["attendances"])

    # falta de um jogador do 1º time
    team = d["teams"][0]
    gone = next(p for p in team["players"] if p["role"] == "LINHA")
    d = (await client.put(f"/api/rounds/{rid}/checkin/{gone['player_id']}", json={"status": "FALTOU"},
                          headers=mesario_headers)).json()
    loans = d["loans"]
    assert loans and all(x["team_id"] == team["id"] and x["replaces_name"] == gone["name"] for x in loans)
    assert all(x["from_team_name"] != team["name"] for x in loans)
    assert all(x["strength_delta"] is None for x in loans)  # mesário não vê força
    admin_view = (await client.get(f"/api/rounds/{rid}", headers=admin_headers)).json()
    assert all(x["strength_delta"] is not None for x in admin_view["loans"])

    # campeonato mostra o empréstimo na partida e a súmula aceita gol do emprestado
    t = (await client.get(f"/api/rounds/{rid}/tournament", headers=admin_headers)).json()
    first = next(m for m in t["matches"] if m["loans"])
    loan = first["loans"][0]
    sheet = (await client.get(f"/api/matches/{first["id"]}/events", headers=mesario_headers)).json()
    roster = sheet["rosters"][str(loan["team_id"])]
    assert any(p["player_id"] == loan["player_id"] and p["role"] == "EMPRESTADO" for p in roster)
    assert all(p["player_id"] != gone["player_id"] for p in roster)
    ev = {"client_event_id": str(uuid.uuid4()), "type": "GOL", "team_id": loan["team_id"],
          "player_id": loan["player_id"]}
    assert (await client.post(f"/api/matches/{first['id']}/events", json=ev, headers=mesario_headers)).status_code in (200, 201)

    # encerra a partida: o empréstimo fica gravado
    home_is_team = first["home"]["id"] == loan["team_id"]
    assert (await result(client, mesario_headers, first["id"], 1 if home_is_team else 0,
                         0 if home_is_team else 1)).status_code == 200

    # o atrasado chega: só o jogo encerrado mantém empréstimo
    d = (await client.put(f"/api/rounds/{rid}/checkin/{gone['player_id']}", json={"status": "PRESENTE"},
                          headers=mesario_headers)).json()
    assert [x["match_id"] for x in d["loans"]] == [first["id"]] and d["loans"][0]["finished"]
    sheet = (await client.get(f"/api/matches/{first["id"]}/events", headers=mesario_headers)).json()
    assert any(p["role"] == "EMPRESTADO" for p in sheet["rosters"][str(loan["team_id"])])
