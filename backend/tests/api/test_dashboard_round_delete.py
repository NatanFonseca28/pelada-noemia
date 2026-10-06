import pytest
from sqlalchemy import func, select

from app.models.audit import AuditLog
from app.models.finance import MonthlyFee
from app.models.match_event import MatchEvent
from app.models.round import Round, Team
from app.models.tournament import Match, Tournament
from tests.api.test_stats import ev, roster, setup_tournament

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def count(s, model, *where):
    return await s.scalar(select(func.count()).select_from(model).where(*where))


async def test_excluir_rodada_ja_realizada_exige_force(client, admin_headers, mesario_headers, session_factory):
    rid, t = await setup_tournament(client, admin_headers)
    m = t["matches"][0]
    _, rosters = await roster(client, admin_headers, m["id"])
    home = m["home"]["id"]
    await client.post(f"/api/matches/{m['id']}/events", json=ev("GOL", home, rosters[home][0]["player_id"]),
                      headers=mesario_headers)
    pid = rosters[home][0]["player_id"]
    r = await client.put("/api/finance/fees", json={"player_id": pid, "month": "2026-10-01", "amount": "50"},
                         headers=admin_headers)
    assert r.status_code == 200

    r = await client.delete(f"/api/rounds/{rid}", headers=admin_headers)
    assert r.status_code == 422 and "definitiva" in r.json()["detail"]
    assert (await client.delete(f"/api/rounds/{rid}?force=true", headers=mesario_headers)).status_code == 403

    assert (await client.delete(f"/api/rounds/{rid}?force=true", headers=admin_headers)).status_code == 204
    async with session_factory() as s:
        assert await count(s, Round, Round.id == rid) == 0
        assert await count(s, Tournament, Tournament.id == t["id"]) == 0
        assert await count(s, Match, Match.tournament_id == t["id"]) == 0
        assert await count(s, MatchEvent, MatchEvent.match_id == m["id"]) == 0
        assert await count(s, Team, Team.round_id == rid) == 0
        assert await count(s, MonthlyFee, MonthlyFee.player_id == pid) == 1  # financeiro intacto
        log = await s.scalar(select(AuditLog).where(AuditLog.entity == "round", AuditLog.entity_id == str(rid),
                                                    AuditLog.action == "DELETE"))
        assert log.before["events"] == 1 and log.before["matches"] == len(t["matches"])


async def test_dashboard_so_admin_e_numeros(client, admin_headers, mesario_headers, jogador_headers):
    for name, ptype, active in [("M1", "MENSALISTA", True), ("M2", "MENSALISTA", True),
                                ("D1", "DIARISTA", True), ("Xis", "MENSALISTA", False)]:
        body = {"name": name, "type": ptype, "primary_position": "ALA", "active": active}
        assert (await client.post("/api/players", json=body, headers=admin_headers)).status_code == 201

    for h in (mesario_headers, jogador_headers):
        assert (await client.get("/api/dashboard", headers=h)).status_code == 403
    d = (await client.get("/api/dashboard", headers=admin_headers)).json()
    assert d["squad"] == {"monthly_active": 2, "daily_active": 1, "inactive": 1}
    fin = d["finance"]
    assert fin["delinquent_count"] == 2 and fin["delinquent_amount"] == "200.00"
    assert fin["monthly_total"] == 2 and fin["monthly_paid"] == 0
    assert d["pending"]["monthly_without_whatsapp"] == 2
    assert d["current_round"] is None and d["season"]["rounds_played"] == 0
