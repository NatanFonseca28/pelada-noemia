"""Catálogo de clubes (football-data.org simulado, sem rede) e sorteio com nomes de clubes."""
import json
from io import BytesIO

import pytest
from PIL import Image

from app.core.config import get_settings
from app.services.team_catalog_service import TeamCatalogService
from tests.api.test_rounds import confirm_all, make_players, new_round

pytestmark = pytest.mark.asyncio(loop_scope="session")


def png() -> bytes:
    out = BytesIO()
    Image.new("RGB", (300, 300), "red").save(out, format="PNG")
    return out.getvalue()


SAFE_SVG = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="10" height="10"/></svg>'
EVIL_SVG = b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"><script>alert(1)</script></svg>'


def payload(teams, start="2026-01-28"):
    return json.dumps({"season": {"startDate": start}, "teams": teams}).encode()


def team(api_id, short, tla, colors, crest):
    return {"id": api_id, "shortName": short, "tla": tla, "clubColors": colors, "crest": crest}


class FakeApi:
    def __init__(self, data):
        self.data = data
        self.crest_calls = 0

    async def __call__(self, url, headers):
        if url.startswith("https://crests.football-data.org/"):
            self.crest_calls += 1
            return SAFE_SVG if url.endswith("ok.svg") else EVIL_SVG if url.endswith(".svg") else png()
        code = url.split("/competitions/")[1].split("/")[0]
        return self.data[code]


async def test_sincroniza_clubes_escudos_e_sorteia(client, admin_headers, superadmin_headers, session_factory, monkeypatch):
    monkeypatch.setattr(get_settings(), "football_data_token", "teste")
    crest = "https://crests.football-data.org/"
    api = FakeApi({
        "BSA": payload([team(1, "Flamengo", "FLA", "Red / Black", crest + "1783.png"),
                        team(2, "Mineiro", "CAM", "Black / White", crest + "1766.png"),
                        team(3, "Coritiba", "COR", "Green / White", crest + "1.png"),
                        team(4, "Corinthians", "COR", "White / Black", crest + "2.png")]),
        "WC": payload([team(10, "Brazil", "BRA", "Yellow / Green", crest + "ok.svg"),
                       team(11, "Germany", "GER", "White / Black", crest + "evil.svg")], start="2026-06-11"),
    })
    async with session_factory() as s:
        done = await TeamCatalogService(s, fetch=api, pause=0).sync(["BSA", "WC"])
    assert done == {"BSA": 4, "WC": 2}
    assert api.crest_calls == 6

    comps = {c["code"]: c for c in (await client.get("/api/catalog/competitions", headers=admin_headers)).json()}
    assert comps["BSA"]["clubs"] == 4 and comps["BSA"]["season"] == 2026 and comps["WC"]["name"] == "Copa do Mundo"

    # 2ª sincronização: Coritiba saiu (rebaixado) e os escudos não são baixados de novo
    api.data["BSA"] = payload([team(1, "Flamengo", "FLA", "Red / Black", crest + "1783.png"),
                               team(2, "Mineiro", "CAM", "Black / White", crest + "1766.png"),
                               team(4, "Corinthians", "COR", "White / Black", crest + "2.png")])
    async with session_factory() as s:
        await TeamCatalogService(s, fetch=api, pause=0).sync(["BSA"])
    assert api.crest_calls == 6
    comps = {c["code"]: c for c in (await client.get("/api/catalog/competitions", headers=admin_headers)).json()}
    assert comps["BSA"]["clubs"] == 3

    # SVG seguro é servido com sandbox; o malicioso é recusado (fica o escudo gerado)
    from sqlalchemy import select

    from app.models.catalog import CatalogClub
    async with session_factory() as s:
        clubs = {c.name: c for c in await s.scalars(select(CatalogClub))}
    assert clubs["Brasil"].crest_path.endswith(".svg") and clubs["Alemanha"].crest_path is None
    assert clubs["Atlético-MG"].crest_path.endswith(".webp") and clubs["Corinthians"].tla == "COR"
    r = await client.get(f"/api/media/{clubs['Brasil'].crest_path}")
    assert r.status_code == 200 and "sandbox" in r.headers["content-security-policy"]

    # sorteio com o Brasileirão: nomes, siglas e escudos de clubes
    ids = await make_players(client, admin_headers, 15)
    rid = await new_round(client, admin_headers, "2026-11-25")
    await confirm_all(client, admin_headers, rid, ids)
    d = (await client.post(f"/api/rounds/{rid}/draw", json={"competition": "BSA"}, headers=admin_headers)).json()
    assert {t["name"] for t in d["teams"]} <= {"Flamengo", "Atlético-MG", "Corinthians"}
    assert all(t["abbr"] and t["crest_url"].startswith("/api/media/crests/") for t in d["teams"])
    assert d["draw"]["competition"] == "BSA"
    # sem campeonato: cores, como antes
    d = (await client.post(f"/api/rounds/{rid}/draw", json={}, headers=admin_headers)).json()
    assert [t["name"] for t in d["teams"]] == ["Verde", "Azul", "Vermelho"] and d["teams"][0]["crest_url"] is None
    # campeonato com menos clubes que times
    r = await client.post(f"/api/rounds/{rid}/draw", json={"competition": "WC"}, headers=admin_headers)
    assert r.status_code == 422 and "só 2 clubes" in r.json()["detail"]


async def test_sincronizar_so_superadmin_e_exige_token(client, admin_headers, superadmin_headers, monkeypatch):
    assert (await client.post("/api/catalog/sync", headers=admin_headers)).status_code == 403
    monkeypatch.setattr(get_settings(), "football_data_token", None)
    r = await client.post("/api/catalog/sync", headers=superadmin_headers)
    assert r.status_code == 422 and "FOOTBALL_DATA_TOKEN" in r.json()["detail"]
