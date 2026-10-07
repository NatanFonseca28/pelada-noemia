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


async def test_para_cobrar_inclui_quem_deve_um_dos_dois_meses(client, admin_headers):
    from app.domain.delinquency import reference_months
    from app.services.finance_service import today_local

    prev, cur = reference_months(today_local())

    async def player(name):
        return (await client.post("/api/players", json={"name": name, "type": "MENSALISTA", "primary_position": "ALA",
                                                        "phone": "21987654321"}, headers=admin_headers)).json()["id"]

    async def pay(pid, month, amount="50"):
        r = await client.put("/api/finance/fees", json={"player_id": pid, "month": month.isoformat(), "amount": amount},
                             headers=admin_headers)
        assert r.status_code == 200

    dois = await player("Deve dois")
    so_atual = await player("Deve atual")
    so_anterior = await player("Deve anterior")
    em_dia = await player("Em dia")
    await pay(so_atual, prev)
    await pay(so_anterior, cur)
    await pay(em_dia, prev)
    await pay(em_dia, cur)

    lst = {d["name"]: d for d in (await client.get("/api/finance/to-charge", headers=admin_headers)).json()}
    assert set(lst) == {"Deve dois", "Deve atual", "Deve anterior"}
    assert lst["Deve dois"]["delinquent"] and lst["Deve dois"]["months_due"] == [prev.isoformat(), cur.isoformat()]
    assert lst["Deve dois"]["amount_due"] == "100.00"
    assert not lst["Deve atual"]["delinquent"] and lst["Deve atual"]["months_due"] == [cur.isoformat()]
    assert lst["Deve atual"]["amount_due"] == "50.00"
    assert lst["Deve anterior"]["months_due"] == [prev.isoformat()]

    # inadimplentes (2 meses) continuam separados; contagens no resumo
    assert [d["name"] for d in (await client.get("/api/finance/delinquents", headers=admin_headers)).json()] == ["Deve dois"]
    ov = (await client.get("/api/finance/overview", params={"year": cur.year}, headers=admin_headers)).json()
    assert ov["delinquent_count"] == 1 and ov["to_charge_count"] == 3

    # dá para cobrar quem deve só 1 mês; quem está em dia, não
    r = await client.post("/api/finance/charges", json={"player_id": so_atual}, headers=admin_headers)
    assert r.status_code == 201
    assert (await client.post("/api/finance/charges", json={"player_id": em_dia}, headers=admin_headers)).status_code == 422


async def test_diarista_nunca_e_inadimplente_nem_cobrado(client, admin_headers):
    from app.domain.delinquency import reference_months
    from app.services.finance_service import today_local

    prev, cur = reference_months(today_local())
    body = {"name": "Diarista Zé", "type": "DIARISTA", "primary_position": "ALA", "phone": "21987654321"}
    dia = (await client.post("/api/players", json=body, headers=admin_headers)).json()["id"]
    men = (await client.post("/api/players", json={**body, "name": "Mensalista Zé", "type": "MENSALISTA"},
                             headers=admin_headers)).json()["id"]
    # diarista com pagamento parcial nos dois meses: mesmo assim não vira inadimplente
    for m in (prev, cur):
        await client.put("/api/finance/fees", json={"player_id": dia, "month": m.isoformat(), "amount": "10"},
                         headers=admin_headers)

    ov = (await client.get("/api/finance/overview", params={"year": cur.year}, headers=admin_headers)).json()
    rows = {r["name"]: r for r in ov["rows"]}
    assert rows["Mensalista Zé"]["delinquent"] and not rows["Diarista Zé"]["delinquent"]
    assert ov["delinquent_count"] == 1 and ov["to_charge_count"] == 1
    # grade: mensalistas primeiro, depois diaristas
    types = [r["type"] for r in ov["rows"]]
    assert types == sorted(types, key=lambda t: t != "MENSALISTA")
    assert [d["player_id"] for d in (await client.get("/api/finance/to-charge", headers=admin_headers)).json()] == [men]
    r = await client.post("/api/finance/charges", json={"player_id": dia}, headers=admin_headers)
    assert r.status_code == 422
