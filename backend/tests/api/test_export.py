from io import BytesIO

import pytest
from openpyxl import load_workbook

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_exportacao_so_admin(client, mesario_headers, jogador_headers):
    for h in (mesario_headers, jogador_headers):
        assert (await client.get("/api/export/xlsx", headers=h)).status_code == 403
        assert (await client.get("/api/export/tables", headers=h)).status_code == 403


async def test_exporta_todas_as_tabelas_sem_segredos(client, admin_headers):
    await client.post("/api/players", json={"name": "Natan", "type": "MENSALISTA", "primary_position": "ALA"},
                      headers=admin_headers)
    tables = (await client.get("/api/export/tables", headers=admin_headers)).json()
    names = {t["name"] for t in tables}
    assert {"users", "players", "monthly_fees", "audit_logs"} <= names
    assert "refresh_tokens" not in names

    r = await client.get("/api/export/xlsx", headers=admin_headers)
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    wb = load_workbook(BytesIO(r.content))
    assert wb.sheetnames[0] == "Sobre"
    assert len(wb.sheetnames) == len(tables) + 1

    users = wb["Usuários"]
    header = [c.value for c in users[1]]
    assert "email" in header and "password_hash" not in header
    jogadores = wb["Jogadores"]
    assert [c.value for c in jogadores[2]][[c.value for c in jogadores[1]].index("name")] == "Natan"
    audit_header = [c.value for c in wb["Auditoria"][1]]
    assert audit_header[:3] == ["id", "user_id", "user_nome"]
    assert wb["Auditoria"].cell(2, 3).value == "Admin"


async def test_exporta_tabelas_escolhidas(client, admin_headers):
    r = await client.get("/api/export/xlsx", params=[("tables", "players"), ("tables", "cash_entries")],
                         headers=admin_headers)
    sheets = load_workbook(BytesIO(r.content)).sheetnames
    assert sheets[0] == "Sobre" and sorted(sheets[1:]) == ["Caixa", "Jogadores"]
    r = await client.get("/api/export/xlsx", params={"tables": "refresh_tokens"}, headers=admin_headers)
    assert r.status_code == 422
