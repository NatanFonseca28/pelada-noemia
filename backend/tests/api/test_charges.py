import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_mensagem_so_superadmin_edita(client, admin_headers, superadmin_headers, jogador_headers):
    msg = (await client.get("/api/finance/charge-message", headers=admin_headers)).json()
    assert msg["is_default"] and "{nome}" in msg["message"] and msg["pix_key"] is None
    assert {v["name"] for v in msg["variables"]} == {"nome", "meses", "valor", "mensalidade", "pix", "gestor"}
    assert (await client.get("/api/finance/charge-message", headers=jogador_headers)).status_code == 403

    body = {"message": "Oi {nome}, são {valor}. Pix {pix}", "pix_key": "pelada@pix.com"}
    assert (await client.put("/api/finance/charge-message", json=body, headers=admin_headers)).status_code == 403
    r = await client.put("/api/finance/charge-message", json=body, headers=superadmin_headers)
    assert r.status_code == 200 and r.json()["message"] == body["message"] and not r.json()["is_default"]
    assert (await client.get("/api/finance/charge-message", headers=admin_headers)).json()["pix_key"] == "pelada@pix.com"

    bad = await client.put("/api/finance/charge-message", json={"message": "Oi {nmoe}"}, headers=superadmin_headers)
    assert bad.status_code == 422 and "{nmoe}" in bad.json()["detail"]
    # voltar ao padrão
    r = await client.put("/api/finance/charge-message", json={"message": msg["default_message"], "pix_key": ""},
                         headers=superadmin_headers)
    assert r.json()["is_default"] and r.json()["pix_key"] is None


async def test_registra_quem_cobrou(client, admin_headers, superadmin_headers, jogador_headers):
    pid = (await client.post("/api/players", json={"name": "Devedor", "type": "MENSALISTA", "primary_position": "ALA",
                                                   "phone": "21987654321"}, headers=admin_headers)).json()["id"]
    before = (await client.get("/api/finance/delinquents", headers=admin_headers)).json()
    assert before[0]["last_charged_at"] is None

    assert (await client.post("/api/finance/charges", json={"player_id": pid}, headers=jogador_headers)).status_code == 403
    r = await client.post("/api/finance/charges", json={"player_id": pid}, headers=admin_headers)
    assert r.status_code == 201 and r.json()["charged_by"] == "Admin"
    after = (await client.get("/api/finance/delinquents", headers=superadmin_headers)).json()
    assert after[0]["last_charged_by"] == "Admin" and after[0]["last_charged_at"]

    # quem está em dia não é cobrado
    ok = (await client.post("/api/players", json={"name": "Em dia", "type": "DIARISTA", "primary_position": "ALA"},
                            headers=admin_headers)).json()["id"]
    assert (await client.post("/api/finance/charges", json={"player_id": ok}, headers=admin_headers)).status_code == 422
    logs = (await client.get("/api/audit", params={"entity": "charge"}, headers=superadmin_headers)).json()
    assert logs[0]["action"] == "CHARGE" and logs[0]["after"]["amount"] == "100.00"
