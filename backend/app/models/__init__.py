"""Importa todos os models para que o metadata (Alembic/testes) os enxergue."""

from app.models.audit import AuditLog
from app.models.match_event import EventType, MatchEvent
from app.models.media import MediaFile
from app.models.finance import CashEntry, CollectionItem, FinanceCollection, MonthlyFee
from app.models.player import Player
from app.models.round import Attendance, Draw, Round, Team, TeamPlayer
from app.models.settings import PeladaSettings
from app.models.tournament import Match, Tournament, TournamentGroup, TournamentGroupTeam
from app.models.user import RefreshToken, User

__all__ = [
    "Attendance",
    "AuditLog",
    "CashEntry",
    "CollectionItem",
    "Draw",
    "FinanceCollection",
    "Match",
    "MatchEvent",
    "MediaFile",
    "EventType",
    "MonthlyFee",
    "PeladaSettings",
    "Player",
    "RefreshToken",
    "Round",
    "Team",
    "TeamPlayer",
    "Tournament",
    "TournamentGroup",
    "TournamentGroupTeam",
    "User",
]
