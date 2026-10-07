import pytest

from app.domain.delinquency import reference_months
from app.services.finance_service import today_local
from tests.api.conftest import _login, _make_user

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_jogador_ve_so_as_proprias_mensalidades(client, admin_headers, session_factory, superadmin_headers):
    prev, cur = reference_months(today_local())
    pid = (await client.post("/api/players", json={"name": "Meu Jogador", "type": "MENSALISTA",
                                                   "primary_position": "ALA"}, headers=admin_headers)).json()["id"]
    other = (await client.post("/api/players", json={"name": "Outro", "type": "MENSALISTA",
                                                     "primary_position": "ALA"}, headers=admin_headers)).json()["id"]
    await client.put("/api/finance/fees", json={"player_id": pid, "month": prev.isoformat(), "amount": "50"},
                     headers=admin_headers)
    await client.put("/api/finance/fees", json={"player_id": other, "month": cur.isoformat(), "amount": "50"},
                     headers=admin_headers)
    await client.put("/api/finance/charge-message", json={"message": "Oi {nome}", "pix_key": "pix@pelada"},
                     headers=superadmin_headers)

    user = await _make_user(session_factory, "eu@test.com", "JOGADOR")
    async with session_factory() as s:
        u = await s.get(type(user), user.id)
        u.player_id = pid
        await s.commit()
    h = await _login(client, "eu@test.com")

    me = (await client.get("/api/finance/me", params={"year": cur.year}, headers=h)).json()
    assert me["has_player"] and me["player_name"] == "Meu Jogador" and me["type"] == "MENSALISTA"
    by_month = {m["month"]: m for m in me["months"]}
    assert len(me["months"]) == 12
    assert by_month[prev.isoformat()]["status"] == "paid"
    assert by_month[cur.isoformat()]["status"] == "open"
    assert me["months_due"] == [cur.isoformat()] and me["amount_due"] == "50.00"
    assert me["total_paid"] == ("50.00" if prev.year == cur.year else "0.00")
    assert me["pix_key"] == "pix@pelada"

    # sem jogador vinculado: nada
    await _make_user(session_factory, "solto@test.com", "JOGADOR")
    solto = (await client.get("/api/finance/me", headers=await _login(client, "solto@test.com"))).json()
    assert solto["has_player"] is False and solto["months"] == []
    # e o resto do financeiro continua só para admin
    assert (await client.get("/api/finance/overview", headers=h)).status_code == 403
