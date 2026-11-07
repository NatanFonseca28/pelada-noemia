"""Papel por presença (linha | goleiro), diária antecipada do diarista e regra de nunca passar de 6 por time."""
import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")

POS = ["ZAGUEIRO", "ZAGUEIRO", "ALA", "ALA", "ATACANTE"]


async def player(client, headers, name, type_="DIARISTA", pos="ALA"):
    r = await client.post("/api/players", json={"name": name, "type": type_, "primary_position": pos}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def new_round(client, headers, date):
    r = await client.post("/api/rounds", json={"date": date}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def att(client, headers, rid, pid, **body):
    r = await client.put(f"/api/rounds/{rid}/attendances/{pid}", json={"confirmed": True, **body}, headers=headers)
    assert r.status_code == 200, r.text
    return {a["player_id"]: a for a in r.json()["attendances"]}


async def test_diarista_de_linha_paga_e_goleiro_nao(client, admin_headers):
    await client.put("/api/finance/config", json={"monthly_fee": "50", "daily_fee": "25",
                                                  "finance_opening_balance": "0", "finance_opening_month": None},
                     headers=admin_headers)
    linha = await player(client, admin_headers, "Diarista Linha")
    gk = await player(client, admin_headers, "Diarista Goleiro")
    mens = await player(client, admin_headers, "Mensalista", "MENSALISTA")
    rid = await new_round(client, admin_headers, "2026-11-04")

    a = await att(client, admin_headers, rid, linha)
    assert a[linha]["role"] == "LINHA" and a[linha]["fee_amount"] == "25.00" and a[linha]["paid"] is False
    a = await att(client, admin_headers, rid, gk, role="GOLEIRO")
    assert a[gk]["role"] == "GOLEIRO" and a[gk]["fee_amount"] is None  # só agarra: não paga
    a = await att(client, admin_headers, rid, mens, role="GOLEIRO")
    assert a[mens]["role"] == "GOLEIRO" and a[mens]["fee_amount"] is None
    # trocar de papel recalcula enquanto não pago
    a = await att(client, admin_headers, rid, gk, role="LINHA")
    assert a[gk]["fee_amount"] == "25.00"
    a = await att(client, admin_headers, rid, gk, role="GOLEIRO")
    assert a[gk]["fee_amount"] is None

    # quem não paga diária não tem o que marcar como pago
    r = await client.put(f"/api/rounds/{rid}/attendances/{gk}/paid", json={"paid": True}, headers=admin_headers)
    assert r.status_code == 422

    r = await client.put(f"/api/rounds/{rid}/attendances/{linha}/paid", json={"paid": True}, headers=admin_headers)
    assert r.status_code == 200
    assert {x["player_id"]: x for x in r.json()["attendances"]}[linha]["paid"] is True

    d = (await client.get("/api/finance/daily", params={"month": "2026-11-01"}, headers=admin_headers)).json()
    assert d["expected"] == "25.00" and d["received"] == "25.00" and d["pending"] == "0.00"
    assert d["rounds"][0]["free_goalkeepers"] == ["Diarista Goleiro"]
    o = (await client.get("/api/finance/overview", params={"year": 2026}, headers=admin_headers)).json()
    assert o["summary"][10]["income"] == "25.00" and o["balance"] == "25.00"


async def test_so_o_proprio_jogador_e_admin_veem_a_diaria(client, admin_headers, jogador_headers):
    pid = await player(client, admin_headers, "Fulano")
    rid = await new_round(client, admin_headers, "2026-11-11")
    await att(client, admin_headers, rid, pid)
    cur = (await client.get(f"/api/rounds/{rid}", headers=jogador_headers)).json()
    assert cur["attendances"][0]["fee_amount"] is None and cur["attendances"][0]["paid"] is None
    r = await client.put(f"/api/rounds/{rid}/attendances/{pid}/paid", json={"paid": True}, headers=jogador_headers)
    assert r.status_code == 403


async def test_agarrar_vira_goleiro_no_sorteio(client, admin_headers):
    ids = [await player(client, admin_headers, f"L{i:02}", "MENSALISTA", POS[i % 5]) for i in range(15)]
    rid = await new_round(client, admin_headers, "2026-11-18")
    extra = await player(client, admin_headers, "Quer agarrar")  # cadastrado como ALA
    for pid in ids:
        await att(client, admin_headers, rid, pid)
    await att(client, admin_headers, rid, extra, role="GOLEIRO")
    d = (await client.post(f"/api/rounds/{rid}/draw", json={}, headers=admin_headers)).json()
    assert len(d["teams"]) == 3 and all(t["line_count"] == 5 for t in d["teams"])
    assert [g["player_id"] for g in d["shared_goalkeepers"]] == [extra]  # agarra para todos, fora dos times
    assert d["not_in_teams"] == []


async def test_time_nunca_passa_de_6(client, admin_headers):
    ids = [await player(client, admin_headers, f"M{i:02}", "MENSALISTA", POS[i % 5]) for i in range(15)]
    rid = await new_round(client, admin_headers, "2026-11-25")
    for pid in ids:
        await att(client, admin_headers, rid, pid)
    d = (await client.post(f"/api/rounds/{rid}/draw", json={}, headers=admin_headers)).json()
    team_a, team_b, team_c = d["teams"]
    # time B recebe 1 (6 no total, ok); o 7º é recusado
    first = team_a["players"][0]["player_id"]
    r = await client.post(f"/api/rounds/{rid}/move", json={"player_id": first, "team_id": team_b["id"]},
                          headers=admin_headers)
    assert r.status_code == 200
    second = team_c["players"][0]["player_id"]
    r = await client.post(f"/api/rounds/{rid}/move", json={"player_id": second, "team_id": team_b["id"]},
                          headers=admin_headers)
    assert r.status_code == 422 and "não existe reserva" in r.json()["detail"].lower()


# ---------- fechamento do ano ----------

async def test_ano_fechado_e_somente_leitura_para_admin(client, admin_headers, superadmin_headers, monkeypatch):
    from datetime import date

    from app.core import year_lock

    pid = await player(client, admin_headers, "Fechamento", "MENSALISTA")
    fee = {"player_id": pid, "month": "2026-06-01", "amount": "50", "marker": None, "settled": False}
    assert (await client.put("/api/finance/fees", json=fee, headers=admin_headers)).status_code == 200

    # 31/12/2026 ainda é 2026: aberto
    monkeypatch.setattr(year_lock, "today", lambda: date(2026, 12, 31))
    assert (await client.put("/api/finance/fees", json={**fee, "amount": "55"}, headers=admin_headers)).status_code == 200

    # 01/01/2027: 2026 fechado para admin, liberado para superadmin
    monkeypatch.setattr(year_lock, "today", lambda: date(2027, 1, 1))
    r = await client.put("/api/finance/fees", json={**fee, "amount": "60"}, headers=admin_headers)
    assert r.status_code == 422 and "fechado" in r.json()["detail"]
    assert (await client.put("/api/finance/fees", json={**fee, "amount": "60"}, headers=superadmin_headers)).status_code == 200
    r = await client.post("/api/rounds", json={"date": "2026-06-23"}, headers=admin_headers)
    assert r.status_code == 422
    # carência: dezembro de 2026 segue editável até 31/01/2027 (pagamento tardio)
    dec = {**fee, "month": "2026-12-01", "amount": "50"}
    assert (await client.put("/api/finance/fees", json=dec, headers=admin_headers)).status_code == 200
    monkeypatch.setattr(year_lock, "today", lambda: date(2027, 2, 1))
    assert (await client.put("/api/finance/fees", json={**dec, "amount": "60"}, headers=admin_headers)).status_code == 422


async def test_resumo_do_ano_e_saldo_que_segue(client, admin_headers):
    await client.put("/api/finance/config", json={"monthly_fee": "50", "daily_fee": "20",
                                                  "finance_opening_balance": "100", "finance_opening_month": "2026-01-01"},
                     headers=admin_headers)
    pid = await player(client, admin_headers, "Resumo", "MENSALISTA")
    await client.put("/api/finance/fees", json={"player_id": pid, "month": "2026-03-01", "amount": "50",
                                                "marker": None, "settled": False}, headers=admin_headers)
    await client.post("/api/finance/entries", json={"month": "2026-04-01", "kind": "SAIDA", "category": "CAMPO",
                                                    "description": "Campo", "amount": "30"}, headers=admin_headers)
    d = (await client.get("/api/dashboard/year-summary", params={"year": 2026}, headers=admin_headers)).json()
    assert d["fees_total"] == "50.00" and d["expenses"] == "30.00" and d["net"] == "20.00"
    assert d["opening_balance"] == "0.00" and d["closing_balance"] == "120.00"  # 100 + 50 - 30
    nxt = (await client.get("/api/dashboard/year-summary", params={"year": 2027}, headers=admin_headers)).json()
    assert nxt["opening_balance"] == d["closing_balance"]
    assert (await client.get("/api/dashboard/year-summary", params={"year": 2025}, headers=admin_headers)).status_code == 422
