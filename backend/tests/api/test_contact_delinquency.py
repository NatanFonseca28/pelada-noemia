import pytest
from sqlalchemy import select

from app.domain.delinquency import reference_months
from app.models.player import Player
from app.services.finance_service import today_local

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def create(client, h, name, ptype="MENSALISTA", **extra):
    body = {"name": name, "type": ptype, "primary_position": "ALA", **extra}
    r = await client.post("/api/players", json=body, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


async def test_telefone_normalizado_e_so_admin_ve(client, admin_headers, mesario_headers, jogador_headers):
    p = await create(client, admin_headers, "Contato", phone="(21) 98765-4321", whatsapp_opt_in=True)
    assert p["phone"] == "+5521987654321" and p["whatsapp_opt_in"] is True

    for h in (jogador_headers, mesario_headers):
        one = (await client.get(f"/api/players/{p['id']}", headers=h)).json()
        assert one["phone"] is None and one["whatsapp_opt_in"] is False
        listed = (await client.get("/api/players", headers=h)).json()
        assert all(x["phone"] is None for x in listed)
    assert (await client.get(f"/api/players/{p['id']}", headers=admin_headers)).json()["phone"] == "+5521987654321"

    # editar, limpar e validar
    r = await client.patch(f"/api/players/{p['id']}", json={"phone": "11 3456-7890"}, headers=admin_headers)
    assert r.json()["phone"] == "+551134567890"
    r = await client.patch(f"/api/players/{p['id']}", json={"phone": "(20) 98765-4321"}, headers=admin_headers)
    assert r.status_code == 422 and "DDD" in r.json()["detail"]
    r = await client.patch(f"/api/players/{p['id']}", json={"phone": ""}, headers=admin_headers)
    assert r.json()["phone"] is None


async def test_inadimplentes_dos_dois_ultimos_meses(client, admin_headers, jogador_headers, session_factory):
    prev, cur = reference_months(today_local())
    devedor = await create(client, admin_headers, "Devedor", phone="21987654321")
    so_atual = await create(client, admin_headers, "Pagou atual")
    so_anterior = await create(client, admin_headers, "Pagou anterior")
    parcial = await create(client, admin_headers, "Parcial")
    diarista = await create(client, admin_headers, "Diarista", ptype="DIARISTA")
    inativo = await create(client, admin_headers, "Inativo", active=False)

    async def pay(pid, month, amount):
        r = await client.put("/api/finance/fees", json={"player_id": pid, "month": month.isoformat(), "amount": amount},
                             headers=admin_headers)
        assert r.status_code == 200, r.text

    await pay(so_atual["id"], cur, "50")
    await pay(so_anterior["id"], prev, "50")
    await pay(parcial["id"], prev, "20")
    await pay(parcial["id"], cur, "30")

    ov = (await client.get("/api/finance/overview", params={"year": cur.year}, headers=admin_headers)).json()
    flagged = {r["name"] for r in ov["rows"] if r["delinquent"]}
    assert flagged == {"Devedor", "Parcial"}
    assert ov["delinquent_count"] == 2
    assert ov["reference_months"] == [prev.isoformat(), cur.isoformat()]
    row = next(r for r in ov["rows"] if r["name"] == "Devedor")
    assert row["months_due"] == [prev.isoformat(), cur.isoformat()]
    assert diarista["id"] and inativo["id"]  # existem, mas nunca entram na regra

    lst = (await client.get("/api/finance/delinquents", headers=admin_headers)).json()
    by_name = {d["name"]: d for d in lst}
    assert set(by_name) == {"Devedor", "Parcial"}
    assert by_name["Devedor"]["phone"] == "+5521987654321" and by_name["Devedor"]["amount_due"] == "100.00"
    assert by_name["Parcial"]["amount_due"] == "50.00" and by_name["Parcial"]["phone"] is None

    assert (await client.get("/api/finance/delinquents", headers=jogador_headers)).status_code == 403
    async with session_factory() as s:  # nada é gravado: é só cálculo
        assert (await s.scalar(select(Player).where(Player.name == "Devedor"))).phone == "+5521987654321"
