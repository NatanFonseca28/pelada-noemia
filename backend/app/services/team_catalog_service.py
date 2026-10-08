"""Catálogo de clubes por campeonato, sincronizado do football-data.org.

Os escudos são baixados uma vez e guardados em `media_files` (o CSP do site só aceita imagens do próprio
domínio). PNG vira WEBP sanitizado; SVG é guardado como está e servido com `Content-Security-Policy: sandbox`.
"""
import asyncio
import json
import logging
import re
import urllib.request
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import ValidationError
from app.domain.draw import TeamIdentity
from app.domain.team_catalog import COMPETITIONS, club_color, club_name, club_tla
from app.models.catalog import CatalogClub, CatalogCompetition
from app.models.media import MediaFile
from app.services.storage import sanitize_image

log = logging.getLogger(__name__)

API = "https://api.football-data.org/v4"
CREST_HOST = "https://crests.football-data.org/"
MAX_CREST_BYTES = 512 * 1024
REQUEST_PAUSE = 6.5  # plano gratuito: 10 requisições por minuto
# SVG com script, eventos ou conteúdo externo é recusado (fica o escudo gerado pelo app)
UNSAFE_SVG = re.compile(rb"<script|<foreignObject|\bon[a-z]+\s*=|javascript:|<iframe|xlink:href\s*=\s*[\"']https?:", re.I)

Fetch = Callable[[str, dict[str, str]], Awaitable[bytes]]


async def http_get(url: str, headers: dict[str, str]) -> bytes:
    def run() -> bytes:
        req = urllib.request.Request(url, headers={"User-Agent": "pelada-noemia", **headers})
        with urllib.request.urlopen(req, timeout=20) as r:  # noqa: S310 — URLs fixas do football-data.org
            return r.read(MAX_CREST_BYTES * 8)
    return await asyncio.to_thread(run)


def crest_file(content: bytes, url: str) -> tuple[bytes, str] | None:
    """(conteúdo, content-type) pronto para guardar, ou None se o escudo não for seguro/válido."""
    if len(content) > MAX_CREST_BYTES:
        return None
    if url.lower().endswith(".svg"):
        head = content.lstrip()[:200].lower()
        if not (head.startswith(b"<svg") or head.startswith(b"<?xml")) or UNSAFE_SVG.search(content):
            return None
        return content, "image/svg+xml"
    try:
        return sanitize_image(content, max_side=256), "image/webp"
    except ValidationError:
        return None


class TeamCatalogService:
    def __init__(self, session: AsyncSession, fetch: Fetch = http_get, pause: float = REQUEST_PAUSE):
        self.session = session
        self.fetch = fetch
        self.pause = pause

    # ---------------------------------------------------------- leitura
    async def competitions(self) -> list[dict]:
        counts = dict((await self.session.execute(
            select(CatalogClub.competition_code, func.count()).group_by(CatalogClub.competition_code))).all())
        rows = await self.session.scalars(select(CatalogCompetition).order_by(CatalogCompetition.sort_order))
        return [{"code": c.code, "name": c.name, "season": c.season, "clubs": counts.get(c.code, 0),
                 "updated_at": c.updated_at} for c in rows]

    async def pool(self, code: str) -> list[TeamIdentity]:
        clubs = list(await self.session.scalars(select(CatalogClub).where(CatalogClub.competition_code == code)))
        if not clubs:
            raise ValidationError("Campeonato sem clubes no catálogo. Peça ao superadmin para atualizar os campeonatos.")
        return [TeamIdentity(c.name, c.color, c.tla, c.crest_path) for c in clubs]

    # ---------------------------------------------------------- sincronização
    async def sync(self, codes: list[str] | None = None) -> dict[str, int]:
        token = get_settings().football_data_token
        if not token:
            raise ValidationError("Configure FOOTBALL_DATA_TOKEN no servidor para atualizar os campeonatos.")
        done: dict[str, int] = {}
        for i, (code, name) in enumerate(c for c in COMPETITIONS if not codes or c[0] in codes):
            if i:
                await asyncio.sleep(self.pause)
            data = json.loads(await self.fetch(f"{API}/competitions/{code}/teams", {"X-Auth-Token": token}))
            done[code] = await self._save(code, name, data)
            await self.session.commit()
        return done

    async def _save(self, code: str, name: str, data: dict) -> int:
        comp = await self.session.get(CatalogCompetition, code)
        if comp is None:
            comp = CatalogCompetition(code=code, name=name)
            self.session.add(comp)
        start = (data.get("season") or {}).get("startDate") or ""
        comp.name = name
        comp.season = int(start[:4]) if start[:4].isdigit() else None
        comp.sort_order = next(i for i, c in enumerate(COMPETITIONS) if c[0] == code)
        comp.updated_at = datetime.now(UTC)
        await self.session.flush()

        existing = {c.api_id: c for c in await self.session.scalars(
            select(CatalogClub).where(CatalogClub.competition_code == code))}
        seen = set()
        for t in data.get("teams", []):
            api_id = t.get("id")
            if not api_id or not t.get("tla"):
                continue
            seen.add(api_id)
            club = existing.get(api_id)
            if club is None:
                club = CatalogClub(competition_code=code, api_id=api_id)
                self.session.add(club)
            club.name = club_name(code, t)[:40]
            club.tla = club_tla(club.name, t["tla"])
            club.color = club_color(t.get("clubColors"))
            await self._crest(club, t.get("crest"))
        for api_id, club in existing.items():
            if api_id not in seen:  # saiu do campeonato (ex.: rebaixado)
                await self._drop_crest(club.crest_path)
                await self.session.delete(club)
        return len(seen)

    async def _crest(self, club: CatalogClub, url: str | None) -> None:
        if not url or not url.startswith(CREST_HOST):
            return
        if club.crest_url == url and club.crest_path:
            return  # já baixado
        # mesmo escudo em 2 campeonatos (ex.: Premier League e Champions) = um só arquivo
        ext = "svg" if url.lower().endswith(".svg") else "webp"
        path = f"crests/{url.rsplit('/', 1)[-1].rsplit('.', 1)[0]}.{ext}"
        if await self.session.get(MediaFile, path) is None:
            try:
                file = crest_file(await self.fetch(url, {}), url)
            except Exception:  # escudo é opcional: sem ele, o app desenha o escudo gerado
                log.warning("Falha ao baixar escudo %s", url, exc_info=True)
                return
            if file is None:
                return
            self.session.add(MediaFile(path=path, content_type=file[1], content=file[0]))
        if club.crest_path and club.crest_path != path:
            await self._drop_crest(club.crest_path)
        club.crest_url, club.crest_path = url, path

    async def _drop_crest(self, path: str | None) -> None:
        # o mesmo escudo pode estar em times de rodadas antigas: só remove se nenhum outro clube usa
        if path and not await self.session.scalar(select(func.count()).select_from(CatalogClub)
                                                  .where(CatalogClub.crest_path == path)) > 1:
            from app.models.round import Team
            if not await self.session.scalar(select(func.count()).select_from(Team).where(Team.crest_path == path)):
                await self.session.execute(delete(MediaFile).where(MediaFile.path == path))
