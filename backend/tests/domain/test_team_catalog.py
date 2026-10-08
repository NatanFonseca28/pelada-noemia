import pytest

from app.domain.draw import DrawConfig, DrawError, TeamIdentity, run_draw
from app.domain.team_catalog import club_color, club_name, club_tla
from tests.domain.test_draw import make_players

POOL = [TeamIdentity(n, "#e0443a", n[:3].upper(), None) for n in
        ("Flamengo", "Palmeiras", "Corinthians", "Santos", "Grêmio", "Bahia")]


def test_cores_dos_clubes():
    assert club_color("Red / Black") == "#e0443a"
    assert club_color("White / Black") == "#1f2937"  # pula o branco
    assert club_color("White") == "#e5e7eb"
    assert club_color(None) == "#5d6b5f"


def test_nomes_e_siglas():
    assert club_name("BSA", {"shortName": "Mineiro", "tla": "CAM"}) == "Atlético-MG"
    assert club_name("WC", {"shortName": "Germany", "tla": "GER"}) == "Alemanha"
    assert club_name("PL", {"shortName": "Arsenal", "tla": "ARS"}) == "Arsenal"
    assert club_tla("Coritiba", "COR") == "CFC" and club_tla("Corinthians", "cor") == "COR"


def test_sorteio_com_clubes_reprodutivel_e_sem_mudar_os_jogadores():
    players = make_players(zag=6, ala=6, ata=3)
    with_clubs = run_draw(players, DrawConfig(), seed=7, team_pool=POOL)
    colors = run_draw(players, DrawConfig(), seed=7)
    again = run_draw(players, DrawConfig(), seed=7, team_pool=list(reversed(POOL)))
    names = [t.name for t in with_clubs.teams]
    assert len(set(names)) == 3 and set(names) <= {c.name for c in POOL}
    assert names == [t.name for t in again.teams]  # mesma seed, mesmos clubes (independe da ordem)
    assert [t.abbr for t in with_clubs.teams] == [n[:3].upper() for n in names]
    # escolher clubes não altera quem cai em cada time
    assert [[p.player_id for p in t.players] for t in with_clubs.teams] == \
           [[p.player_id for p in t.players] for t in colors.teams]
    assert [t.name for t in colors.teams] == ["Verde", "Azul", "Vermelho"]


def test_campeonato_com_poucos_clubes():
    with pytest.raises(DrawError, match="só 2 clubes"):
        run_draw(make_players(zag=6, ala=6, ata=3), DrawConfig(), seed=1, team_pool=POOL[:2])
