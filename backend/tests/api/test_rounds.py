import pytest
from sqlalchemy import select

from app.models.user import User

pytestmark = pytest.mark.asyncio(loop_scope="session")

POS = ["ZAGUEIRO", "ZAGUEIRO", "ALA", "ALA", "ATACANTE"]


async def make_players(client, headers, n_line=15, n_gk=0):
    ids = []
    for i in range(n_line):
        r = await client.post("/api/players", json={"name": f"Linha {i:02}", "type": "MENSALISTA",
                                                     "primary_position": POS[i % 5]}, headers=headers)
        ids.append(r.json()["id"])
    for i in range(n_gk):
        r = await client.post("/api/players", json={"name": f"Goleiro {i}", "type": "DIARISTA",
                                                     "primary_position": "GOLEIRO_FIXO"}, headers=headers)
        ids.append(r.json()["id"])
    return ids


async def new_round(client, headers, date="2026-10-07"):
    r = await client.post("/api/rounds", json={"date": date}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def confirm_all(client, headers, rid, ids):
    for pid in ids:
        r = await client.put(f"/api/rounds/{rid}/attendances/{pid}", json={"confirmed": True}, headers=headers)
        assert r.status_code == 200, r.text
    return r.json()


async def test_fluxo_completo_de_sorteio(client, admin_headers):
    ids = await make_players(client, admin_headers, 16, 1)
    rid = await new_round(client, admin_headers)
    detail = await confirm_all(client, admin_headers, rid, ids)
    assert detail["confirmed_count"] == 17 and detail["status"] == "ABERTA"

    r = await client.post(f"/api/rounds/{rid}/draw", json={}, headers=admin_headers)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "FECHADA"  # sortear fecha a lista
    assert d["draw"]["mode"] == "CAMPEONATO" and len(d["teams"]) == 3
    assert sum(len(t["players"]) for t in d["teams"]) == 17
    seed = d["draw"]["seed"]

    # Reproduzível pela seed
    first = [[p["player_id"] for p in t["players"]] for t in d["teams"]]
    await client.post(f"/api/rounds/{rid}/draw", json={}, headers=admin_headers)
    d2 = (await client.post(f"/api/rounds/{rid}/draw", json={"seed": seed}, headers=admin_headers)).json()
    assert [[p["player_id"] for p in t["players"]] for t in d2["teams"]] == first

    # Ajuste manual: mover para outro time
    team_a, team_b = d2["teams"][0], d2["teams"][1]
    pid = next(p["player_id"] for p in team_a["players"] if p["role"] == "LINHA")
    d3 = (await client.post(f"/api/rounds/{rid}/move", json={"player_id": pid, "team_id": team_b["id"]},
                            headers=admin_headers)).json()
    moved = next(p for t in d3["teams"] if t["id"] == team_b["id"] for p in t["players"] if p["player_id"] == pid)
    assert moved["moved_manually"] is True

    # Travar bloqueia novo sorteio e ajustes
    assert (await client.post(f"/api/rounds/{rid}/lock", headers=admin_headers)).json()["status"] == "TIMES_TRAVADOS"
    assert (await client.post(f"/api/rounds/{rid}/draw", json={}, headers=admin_headers)).status_code == 422
    r = await client.post(f"/api/rounds/{rid}/move", json={"player_id": pid, "team_id": team_a["id"]},
                          headers=admin_headers)
    assert r.status_code == 422
    assert (await client.post(f"/api/rounds/{rid}/unlock", headers=admin_headers)).json()["status"] == "FECHADA"


async def test_sorteio_com_poucos_jogadores_retorna_erro_claro(client, admin_headers):
    ids = await make_players(client, admin_headers, 10)
    rid = await new_round(client, admin_headers)
    await confirm_all(client, admin_headers, rid, ids)
    r = await client.post(f"/api/rounds/{rid}/draw", json={}, headers=admin_headers)
    assert r.status_code == 422
    assert "12" in r.json()["detail"]


async def test_presenca_do_jogador(client, admin_headers, jogador_headers, session_factory):
    ids = await make_players(client, admin_headers, 1)
    async with session_factory() as s:
        user = await s.scalar(select(User).where(User.email == "jogador@test.com"))
        user.player_id = ids[0]
        await s.commit()
    rid = await new_round(client, admin_headers)

    r = await client.put(f"/api/rounds/{rid}/attendance/me", json={"confirmed": True}, headers=jogador_headers)
    assert r.status_code == 200 and r.json()["my_status"] == "CONFIRMADO"
    cur = (await client.get("/api/rounds/current", headers=jogador_headers)).json()
    assert cur["id"] == rid and cur["confirmed_count"] == 1

    # Jogador não pode mexer na presença dos outros nem sortear
    assert (await client.put(f"/api/rounds/{rid}/attendances/{ids[0]}", json={"confirmed": False},
                             headers=jogador_headers)).status_code == 403
    assert (await client.post(f"/api/rounds/{rid}/draw", json={}, headers=jogador_headers)).status_code == 403

    await client.post(f"/api/rounds/{rid}/close", headers=admin_headers)
    r = await client.put(f"/api/rounds/{rid}/attendance/me", json={"confirmed": False}, headers=jogador_headers)
    assert r.status_code == 422  # lista fechada


async def test_lista_mudou_depois_do_sorteio(client, admin_headers):
    ids = await make_players(client, admin_headers, 16)
    rid = await new_round(client, admin_headers)
    await confirm_all(client, admin_headers, rid, ids[:15])
    d = (await client.post(f"/api/rounds/{rid}/draw", json={}, headers=admin_headers)).json()
    d = (await client.put(f"/api/rounds/{rid}/attendances/{ids[15]}", json={"confirmed": True},
                          headers=admin_headers)).json()
    assert [p["player_id"] for p in d["not_in_teams"]] == [ids[15]]
    d = (await client.put(f"/api/rounds/{rid}/attendances/{ids[0]}", json={"confirmed": False},
                          headers=admin_headers)).json()
    assert [p["player_id"] for p in d["no_longer_confirmed"]] == [ids[0]]
    # Encaixar o atrasado como revezamento
    team_id = d["teams"][0]["id"]
    d = (await client.post(f"/api/rounds/{rid}/move", json={"player_id": ids[15], "team_id": team_id,
                                                           "role": "REVEZAMENTO"}, headers=admin_headers)).json()
    assert d["not_in_teams"] == []
    d = (await client.post(f"/api/rounds/{rid}/move", json={"player_id": ids[0]}, headers=admin_headers)).json()
    assert d["no_longer_confirmed"] == []


async def test_formacao_alternativa_e_data_unica(client, admin_headers):
    ids = await make_players(client, admin_headers, 19)
    rid = await new_round(client, admin_headers)
    await confirm_all(client, admin_headers, rid, ids)
    d = (await client.post(f"/api/rounds/{rid}/draw", json={}, headers=admin_headers)).json()
    assert [a["num_teams"] for a in d["draw"]["alternatives"]] == [3, 4]
    d = (await client.post(f"/api/rounds/{rid}/draw", json={"num_teams": 4}, headers=admin_headers)).json()
    assert len(d["teams"]) == 4
    assert (await client.post("/api/rounds", json={"date": "2026-10-07"}, headers=admin_headers)).status_code == 409
