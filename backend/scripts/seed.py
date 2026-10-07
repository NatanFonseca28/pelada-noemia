"""Popula o banco com configurações e usuários de teste.

Uso:
  python -m scripts.seed           # configurações + usuários de teste
  python -m scripts.seed --demo    # + 30 jogadores fictícios (para testar sorteio/campeonato)

O elenco real vem da planilha: python -m scripts.import_planilha "PELADA DE QUARTA CONTROLE.xlsx"
Idempotente: não duplica usuários/jogadores já existentes (chave: e-mail / nome).
"""
import asyncio
import random
import sys

from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.enums import PlayerType, Position, UserRole, UserStatus
from app.models.player import Player
from app.models.settings import PeladaSettings
from app.models.user import User

Z, A, AT, G = Position.ZAGUEIRO, Position.ALA, Position.ATACANTE, Position.GOLEIRO_FIXO

# nome, apelido, posição principal, secundária, nível
PLAYERS: list[tuple[str, str | None, Position, Position | None, int | None]] = [
    ("Carlos Henrique Souza", "Carlão", Z, A, 4),
    ("Rodrigo Alves", "Digão", Z, None, 3),
    ("Marcelo Pereira", "Marcelão", Z, AT, 3),
    ("Fábio Nogueira", None, Z, A, 2),
    ("Anderson Lima", "Dinho", Z, None, 4),
    ("Thiago Barbosa", "Thiaguinho", Z, A, 3),
    ("Leandro Costa", "Leleco", Z, None, 2),
    ("Gustavo Ribeiro", "Guga", Z, AT, 5),
    ("Felipe Martins", "Felipinho", A, AT, 4),
    ("Bruno Carvalho", "Brunão", A, Z, 3),
    ("Diego Fernandes", None, A, None, 3),
    ("Rafael Gomes", "Rafa", A, AT, 5),
    ("Lucas Rocha", "Luquinha", A, Z, 2),
    ("Vinícius Teixeira", "Vini", A, None, 4),
    ("Eduardo Moreira", "Dudu", A, AT, 3),
    ("Matheus Araújo", "Matheuzinho", A, Z, 2),
    ("Pedro Henrique Dias", "PH", AT, A, 5),
    ("João Victor Cardoso", "JV", AT, None, 4),
    ("Renato Freitas", "Renatinho", AT, A, 3),
    ("Alexandre Pinto", "Xande", AT, Z, 3),
    ("Gabriel Mendes", "Gabigol", AT, A, 4),
    ("Paulo Sérgio Ramos", "Paulinho", AT, None, 2),
    ("Ricardo Azevedo", "Ricardinho", Z, A, 3),
    ("André Luiz Castro", "Andrezinho", A, Z, 3),
    ("Wellington Silva", "Tom", Z, None, 1),
    ("Caio Batista", None, A, AT, 3),
    ("Sérgio Lopes", "Serginho", AT, A, 2),
    ("Roberto Farias", "Beto Paredão", G, None, 4),
    ("Jorge Antunes", "Jorjão", G, None, 3),
    ("Murilo Cunha", "Murilão", G, None, 2),
]


async def seed(demo: bool, admin_only: bool = False) -> None:
    settings = get_settings()
    rng = random.Random(42)
    async with SessionLocal() as session:
        if await session.get(PeladaSettings, 1) is None:
            session.add(PeladaSettings(id=1))

        players_by_name: dict[str, Player] = {
            p.name: p for p in await session.scalars(select(Player))
        }
        for i, (name, nick, primary, secondary, level) in enumerate(PLAYERS if demo else []):
            if name in players_by_name:
                continue
            player = Player(
                name=name,
                nickname=nick,
                type=PlayerType.ISENTO if primary == G else PlayerType.MENSALISTA if i % 3 else PlayerType.DIARISTA,
                primary_position=primary,
                secondary_position=secondary,
                skill_level=level,
                active=rng.random() > 0.03,
            )
            session.add(player)
            players_by_name[name] = player
        await session.flush()

        users = [
            (settings.admin_email, "Administrador", settings.admin_password, UserRole.ADMIN, None, UserStatus.ATIVO),
            ("mesario@pelada.app", "Mesário da Pelada", "mesario123", UserRole.MESARIO, None, UserStatus.ATIVO),
            ("carlao@pelada.app", "Carlos Henrique Souza", "jogador123", UserRole.JOGADOR,
             "Carlos Henrique Souza", UserStatus.ATIVO),
            ("rafa@pelada.app", "Rafael Gomes", "jogador123", UserRole.JOGADOR, "Rafael Gomes", UserStatus.ATIVO),
            ("novato@pelada.app", "Novato Pendente", "jogador123", UserRole.JOGADOR, None, UserStatus.PENDENTE),
        ]
        if admin_only:  # produção com banco vazio: nada de contas de teste
            users = users[:1]
        for email, name, password, role, player_name, status in users:
            if await session.scalar(select(User).where(User.email == email)):
                continue
            session.add(
                User(
                    email=email,
                    name=name,
                    password_hash=hash_password(password),
                    role=role,
                    status=status,
                    player_id=players_by_name[player_name].id if player_name in players_by_name else None,
                )
            )
        await session.commit()
    print(f"Seed concluído: {len(PLAYERS) if demo else 0} jogadores fictícios, {len(users)} usuários.")
    print(f"Admin: {settings.admin_email} / {settings.admin_password}")
    print("Mesário: mesario@pelada.app / mesario123 · Jogador: carlao@pelada.app / jogador123")


if __name__ == "__main__":
    asyncio.run(seed(demo="--demo" in sys.argv, admin_only="--admin-only" in sys.argv))
