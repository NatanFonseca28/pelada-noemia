from io import BytesIO

import pytest
from openpyxl import Workbook

from tests.domain.test_finance_sheet import ROWS

pytestmark = pytest.mark.asyncio(loop_scope="session")


def xlsx_bytes(rows) -> bytes:
    wb = Workbook()
    ws = wb.active
    for r in rows:
        ws.append(list(r))
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


async def _import(client, headers):
    files = {"file": ("planilha.xlsx", xlsx_bytes(ROWS), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    return await client.post("/api/finance/import", files=files, headers=headers)


async def test_financeiro_so_admin(client, mesario_headers, jogador_headers):
    for h in (mesario_headers, jogador_headers):
        assert (await client.get("/api/finance/overview", headers=h)).status_code == 403
        assert (await _import(client, h)).status_code == 403
    assert (await client.get("/api/finance/overview")).status_code == 401


async def test_importa_planilha_e_calcula_saldo(client, admin_headers):
    r = await _import(client, admin_headers)
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["players_created"] == ["Daniel", "DG", "Wagner", "Rodrigo Gomes", "Leonardo", "Guma", "Michel"]
    assert res["opening_balance"] == "2266.00" and res["opening_month"] == "2026-03-01"

    players = (await client.get("/api/players", headers=admin_headers)).json()
    rodrigo = next(p for p in players if p["name"] == "Rodrigo Gomes")
    assert rodrigo["primary_position"] == "ZAGUEIRO"
    assert next(p for p in players if p["name"] == "Daniel")["primary_position"] is None

    ov = (await client.get("/api/finance/overview", params={"year": 2026}, headers=admin_headers)).json()
    mar = ov["summary"][2]
    assert mar["fees"] == "100.00"  # Daniel 50 + Guma 35+15
    assert mar["income"] == "300.00"
    assert mar["expenses"] == "800.00"  # valor do campo
    # saldo = 2266 + março (100 + 300 − 800)
    assert ov["balance"] == "1866.00"
    wagner = next(r for r in ov["rows"] if r["name"] == "Wagner")
    assert wagner["cells"]["2026-02"] == {"amount": None, "marker": "F", "settled": False}

    cols = (await client.get("/api/finance/collections", headers=admin_headers)).json()
    assert [(i["name"], i["amount"], i["paid"], i["player_id"] is not None) for i in cols[0]["items"]] == [
        ("Peter", "20.00", False, False),
        ("Daniel", "20.00", True, True),
        ("Penetra", "20.00", False, False),
    ]


async def test_reimportar_nao_duplica(client, admin_headers):
    await _import(client, admin_headers)
    r = await _import(client, admin_headers)
    assert r.json()["players_created"] == []
    assert len(r.json()["players_matched"]) == 7
    entries = (await client.get("/api/finance/entries", params={"year": 2026}, headers=admin_headers)).json()
    assert len(entries) == 3
    assert len((await client.get("/api/finance/collections", headers=admin_headers)).json()) == 1


async def test_importar_arquivo_invalido(client, admin_headers):
    files = {"file": ("x.xlsx", b"nao e planilha", "application/octet-stream")}
    r = await client.post("/api/finance/import", files=files, headers=admin_headers)
    assert r.status_code == 422


async def test_editar_mensalidade_lancamento_e_cobranca(client, admin_headers, superadmin_headers):
    pid = (await client.post("/api/players", json={"name": "Natan", "type": "MENSALISTA",
                                                    "primary_position": "ALA"}, headers=admin_headers)).json()["id"]
    cfg = {"monthly_fee": "50", "finance_opening_balance": "1000", "finance_opening_month": "2026-10-15"}
    r = await client.put("/api/finance/config", json=cfg, headers=admin_headers)
    assert r.json()["finance_opening_month"] == "2026-10-01"

    r = await client.put("/api/finance/fees", json={"player_id": pid, "month": "2026-10-01", "amount": "50"},
                         headers=admin_headers)
    assert r.status_code == 200 and r.json()["amount"] == "50.00"
    # Mês anterior à abertura não afeta o saldo
    await client.put("/api/finance/fees", json={"player_id": pid, "month": "2026-09-01", "amount": "50"},
                     headers=admin_headers)
    entry = {"month": "2026-10-01", "kind": "SAIDA", "category": "CAMPO", "description": "Aluguel", "amount": "300"}
    eid = (await client.post("/api/finance/entries", json=entry, headers=admin_headers)).json()["id"]

    ov = (await client.get("/api/finance/overview", params={"year": 2026}, headers=admin_headers)).json()
    assert ov["balance"] == "750.00"  # 1000 + 50 − 300
    natan = next(r for r in ov["rows"] if r["player_id"] == pid)
    assert natan["total"] == "100.00"

    # Apagar a célula
    r = await client.put("/api/finance/fees", json={"player_id": pid, "month": "2026-10-01"}, headers=admin_headers)
    assert r.json() is None
    assert (await client.delete(f"/api/finance/entries/{eid}", headers=admin_headers)).status_code == 204
    ov = (await client.get("/api/finance/overview", params={"year": 2026}, headers=admin_headers)).json()
    assert ov["balance"] == "1000.00"

    col = (await client.post("/api/finance/collections", json={"title": "Bola nova", "amount_per_person": "15"},
                             headers=admin_headers)).json()
    col = (await client.post(f"/api/finance/collections/{col['id']}/items", json={"name": "Natan", "player_id": pid},
                             headers=admin_headers)).json()
    item = col["items"][0]
    assert item["amount"] == "15.00" and item["paid"] is False
    col = (await client.patch(f"/api/finance/collection-items/{item['id']}", json={"paid": True},
                              headers=admin_headers)).json()
    assert col["items"][0]["paid"] is True

    logs = (await client.get("/api/audit", params={"entity": "monthly_fee"}, headers=superadmin_headers)).json()
    assert len(logs) == 3


async def test_quitado_e_fora_na_cobranca_e_no_portal(client, admin_headers, jogador_headers):
    from app.domain.delinquency import reference_months
    from app.services.finance_service import today_local

    prev, cur = reference_months(today_local())

    async def player(name):
        return (await client.post("/api/players", json={"name": name, "type": "MENSALISTA", "primary_position": "ALA",
                                                        "phone": "21987654321"}, headers=admin_headers)).json()["id"]

    async def cell(pid, month, **data):
        return await client.put("/api/finance/fees", json={"player_id": pid, "month": month.isoformat(), **data},
                                headers=admin_headers)

    quitou = await player("Quitou com desconto")
    fora = await player("Ficou fora")
    fora_e_vazio = await player("Fora e vazio")
    vazio = await player("Nada pago")
    assert (await cell(quitou, prev, amount="30", settled=True)).json() == {
        "amount": "30.00", "marker": None, "settled": True}
    await cell(quitou, cur, amount="50")
    assert (await cell(fora, prev, marker="f")).json()["marker"] == "F"  # normaliza
    await cell(fora, cur, marker="F")
    await cell(fora_e_vazio, prev, marker="F")
    await cell(vazio, prev, amount="10")  # parcial: continua devendo
    # regras de validação
    assert (await cell(vazio, cur, settled=True)).status_code == 422  # quitado sem valor
    assert (await cell(vazio, cur, amount="50", marker="F")).status_code == 422  # F não leva valor

    lst = {d["name"]: d for d in (await client.get("/api/finance/to-charge", headers=admin_headers)).json()}
    assert "Quitou com desconto" not in lst and "Ficou fora" not in lst
    assert not lst["Fora e vazio"]["delinquent"] and lst["Fora e vazio"]["months_due"] == [cur.isoformat()]
    assert lst["Nada pago"]["delinquent"] and lst["Nada pago"]["amount_due"] == "90.00"

    # portal: qualquer logado vê, sem valores nem telefones; deslogado não
    assert (await client.get("/api/finance/transparency")).status_code == 401
    r = await client.get("/api/finance/transparency", params={"year": cur.year}, headers=jogador_headers)
    assert r.status_code == 200, r.text
    t = r.json()
    assert set(t) == {"year", "months", "balance", "year_income", "year_expenses", "summary", "expenses", "players"}

    async def state(name, month):  # em janeiro o mês anterior está no portal do ano passado
        data = (await client.get("/api/finance/transparency", params={"year": month.year},
                                 headers=jogador_headers)).json()
        return next(p["months"] for p in data["players"] if p["name"] == name)[month.strftime("%Y-%m")]

    assert await state("Quitou com desconto", prev) == "paid" and await state("Quitou com desconto", cur) == "paid"
    assert await state("Ficou fora", prev) == "out"
    assert await state("Fora e vazio", cur) == "open"
    assert await state("Nada pago", prev) == "partial"
    assert "21987654321" not in r.text and "phone" not in r.text
