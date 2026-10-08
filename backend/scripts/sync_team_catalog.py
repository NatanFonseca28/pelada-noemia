"""Atualiza o catálogo de clubes (football-data.org). Uso: docker compose exec api python -m scripts.sync_team_catalog"""
import asyncio

from app.db.session import SessionLocal
from app.services.team_catalog_service import TeamCatalogService


async def main() -> None:
    async with SessionLocal() as session:
        done = await TeamCatalogService(session).sync()
    for code, count in done.items():
        print(f"{code}: {count} clubes")


if __name__ == "__main__":
    asyncio.run(main())
