from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import case, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationError
from app.domain.charge_message import CHARGE_VARIABLES, DEFAULT_CHARGE_MESSAGE
from app.domain.delinquency import amount_due, is_delinquent, months_owed, reference_months
from app.models.audit import AuditLog
from app.models.enums import PlayerType
from app.models.finance import CashEntry, CashKind, CollectionItem, FinanceCollection, MonthlyFee
from app.models.player import Player
from app.models.user import User
from app.repositories.settings_repo import SettingsRepository
from app.schemas.finance import (
    CashEntryIn,
    ChargeMessageIn,
    ChargeMessageOut,
    ChargeOut,
    ChargeVariable,
    DelinquentOut,
    CollectionIn,
    CollectionItemIn,
    CollectionItemUpdate,
    FeeCellIn,
    FeeCellOut,
    FeeRow,
    FinanceConfig,
    FinanceOverview,
    MonthSummary,
)
from app.services import audit_service

ZERO = Decimal("0.00")
TZ = ZoneInfo("America/Sao_Paulo")


def today_local() -> date:
    """Data de hoje no fuso da pelada (a regra de inadimplência olha o mês atual e o anterior)."""
    return datetime.now(TZ).date()


def month_key(m: date) -> str:
    return m.strftime("%Y-%m")


class FinanceService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = SettingsRepository(session)

    # ---------- Configuração ----------
    async def get_config(self) -> FinanceConfig:
        return FinanceConfig.model_validate(await self.settings.get_current())

    async def update_config(self, data: FinanceConfig, actor: User) -> FinanceConfig:
        current = await self.settings.get_current()
        before = FinanceConfig.model_validate(current).model_dump(mode="json")
        for key, value in data.model_dump().items():
            setattr(current, key, value)
        await audit_service.record(
            self.session, user_id=actor.id, action="UPDATE", entity="finance_config", entity_id=1,
            before=before, after=data.model_dump(mode="json"),
        )
        await self.session.commit()
        return data

    # ---------- Visão geral ----------
    async def overview(self, year: int) -> FinanceOverview:
        config = await self.get_config()
        months = [date(year, m, 1) for m in range(1, 13)]

        fees = list(
            await self.session.scalars(select(MonthlyFee).where(extract("year", MonthlyFee.month) == year))
        )
        entries = list(
            await self.session.scalars(select(CashEntry).where(extract("year", CashEntry.month) == year))
        )
        player_ids = {f.player_id for f in fees}
        players = list(
            await self.session.scalars(
                select(Player).where(
                    (Player.id.in_(player_ids))
                    | ((Player.type == PlayerType.MENSALISTA) & Player.active.is_(True))
                )
            )
        )

        cells: dict[int, dict[str, FeeCellOut]] = defaultdict(dict)
        for f in fees:
            cells[f.player_id][month_key(f.month)] = FeeCellOut(amount=f.amount, marker=f.marker)

        # Ordem: quem tem pagamento no ano primeiro (pela 1ª mensalidade), depois os demais por nome
        first_paid = {pid: min(c) for pid, c in cells.items()}
        players.sort(key=lambda p: (p.id not in first_paid, p.display_name.casefold()))
        overdue = await self.delinquency()
        ref_months = list(reference_months(today_local()))
        rows = [
            FeeRow(
                player_id=p.id,
                name=p.display_name,
                type=p.type.value,
                active=p.active,
                cells=cells.get(p.id, {}),
                total=sum((c.amount or ZERO for c in cells.get(p.id, {}).values()), ZERO),
                delinquent=p.id in overdue,
                months_due=ref_months if p.id in overdue else [],
            )
            for p in players
        ]

        summary = []
        for m in months:
            fee_total = sum((f.amount or ZERO for f in fees if f.month == m), ZERO)
            income = sum((e.amount for e in entries if e.month == m and e.kind == CashKind.ENTRADA), ZERO)
            expenses = sum((e.amount for e in entries if e.month == m and e.kind == CashKind.SAIDA), ZERO)
            summary.append(
                MonthSummary(
                    month=m,
                    fees=fee_total,
                    income=income,
                    expenses=expenses,
                    net=fee_total + income - expenses,
                    paid_count=sum(1 for f in fees if f.month == m and f.amount),
                )
            )

        return FinanceOverview(
            year=year,
            months=months,
            rows=rows,
            summary=summary,
            config=config,
            balance=await self.balance(config),
            year_total=sum((s.fees + s.income for s in summary), ZERO),
            reference_months=ref_months,
            delinquent_count=len(overdue),
            to_charge_count=len(await self.owing()),
        )

    # ---------- Inadimplência ----------
    async def delinquency(self) -> dict[int, list[Decimal | None]]:
        """Mensalistas ativos sem pagar o mês atual nem o anterior → {player_id: valores pagos nos 2 meses}."""
        fee = (await self.get_config()).monthly_fee
        return {pid: a for pid, a in (await self._reference_payments()).items() if is_delinquent(a, fee)}

    async def owing(self) -> dict[int, list[Decimal | None]]:
        """Mensalistas ativos com pelo menos um dos dois meses de referência em aberto (para cobrar)."""
        fee = (await self.get_config()).monthly_fee
        months = list(reference_months(today_local()))
        return {pid: a for pid, a in (await self._reference_payments()).items() if months_owed(months, a, fee)}

    async def _reference_payments(self) -> dict[int, list[Decimal | None]]:
        """{player_id: valores pagos no (mês anterior, mês atual)} de cada mensalista ativo."""
        months = reference_months(today_local())
        players = list(await self.session.scalars(
            select(Player.id).where(Player.type == PlayerType.MENSALISTA, Player.active.is_(True))
        ))
        if not players:
            return {}
        paid = {
            (f.player_id, f.month): f.amount
            for f in await self.session.scalars(
                select(MonthlyFee).where(MonthlyFee.player_id.in_(players), MonthlyFee.month.in_(months))
            )
        }
        return {pid: [paid.get((pid, m)) for m in months] for pid in players}

    async def delinquents(self, include_partial: bool = False) -> list[DelinquentOut]:
        """Inadimplentes (devem os 2 meses). Com `include_partial`, também quem deve só 1 dos 2 (lista "Para cobrar")."""
        fee = (await self.get_config()).monthly_fee
        overdue = await (self.owing() if include_partial else self.delinquency())
        months = list(reference_months(today_local()))
        players = list(await self.session.scalars(select(Player).where(Player.id.in_(overdue)))) if overdue else []
        charged = await self._last_charges([p.id for p in players])
        out = [
            DelinquentOut(player_id=p.id, name=p.display_name, phone=p.phone, whatsapp_opt_in=p.whatsapp_opt_in,
                          months_due=months_owed(months, overdue[p.id], fee), amount_due=amount_due(overdue[p.id], fee),
                          delinquent=is_delinquent(overdue[p.id], fee),
                          last_charged_at=charged.get(p.id, (None, None))[0],
                          last_charged_by=charged.get(p.id, (None, None))[1])
            for p in players
        ]
        return sorted(out, key=lambda d: d.name.casefold())

    async def _last_charges(self, player_ids: list[int]) -> dict[int, tuple[datetime, str | None]]:
        """Última cobrança registrada de cada jogador (auditoria, entity="charge") e quem cobrou."""
        if not player_ids:
            return {}
        rows = (await self.session.execute(
            select(AuditLog.entity_id, AuditLog.created_at, User.name)
            .outerjoin(User, User.id == AuditLog.user_id)
            .where(AuditLog.entity == "charge", AuditLog.entity_id.in_([str(i) for i in player_ids]))
            .order_by(AuditLog.created_at.desc())
        )).all()
        last: dict[int, tuple[datetime, str | None]] = {}
        for entity_id, at, name in rows:
            last.setdefault(int(entity_id), (at, name.split()[0] if name else None))
        return last

    async def charge(self, player_id: int, actor: User) -> ChargeOut:
        """Registra que `actor` abriu a cobrança no WhatsApp (o envio sai do aparelho dele)."""
        overdue = await self.owing()
        if player_id not in overdue:
            raise ValidationError("Este jogador está com as mensalidades em dia")
        fee = (await self.get_config()).monthly_fee
        months = [m.isoformat() for m in months_owed(list(reference_months(today_local())), overdue[player_id], fee)]
        await audit_service.record(
            self.session, user_id=actor.id, action="CHARGE", entity="charge", entity_id=player_id,
            after={"months": months, "amount": str(amount_due(overdue[player_id], fee))},
        )
        await self.session.commit()
        return ChargeOut(player_id=player_id, charged_at=datetime.now(TZ), charged_by=actor.name.split()[0])

    async def charge_message(self) -> ChargeMessageOut:
        current = await SettingsRepository(self.session).get_current()
        return ChargeMessageOut(
            message=current.charge_message or DEFAULT_CHARGE_MESSAGE,
            pix_key=current.pix_key,
            is_default=not current.charge_message,
            default_message=DEFAULT_CHARGE_MESSAGE,
            variables=[ChargeVariable(name=k, description=v) for k, v in CHARGE_VARIABLES.items()],
        )

    async def set_charge_message(self, data: ChargeMessageIn, actor: User) -> ChargeMessageOut:
        current = await SettingsRepository(self.session).get_current()
        before = {"charge_message": current.charge_message, "pix_key": current.pix_key}
        current.charge_message = None if data.message == DEFAULT_CHARGE_MESSAGE else data.message
        current.pix_key = (data.pix_key or "").strip() or None
        await audit_service.record(self.session, user_id=actor.id, action="UPDATE", entity="charge_message",
                                   entity_id="1", before=before,
                                   after={"charge_message": current.charge_message, "pix_key": current.pix_key})
        await self.session.commit()
        return await self.charge_message()

    async def balance(self, config: FinanceConfig | None = None) -> Decimal:
        """Saldo = saldo inicial + (mensalidades + entradas − saídas) a partir do mês de abertura."""
        config = config or await self.get_config()
        start = config.finance_opening_month or date(1900, 1, 1)
        fees = await self.session.scalar(
            select(func.coalesce(func.sum(MonthlyFee.amount), 0)).where(MonthlyFee.month >= start)
        )
        signed = func.sum(case((CashEntry.kind == CashKind.ENTRADA, CashEntry.amount), else_=-CashEntry.amount))
        entries = await self.session.scalar(select(func.coalesce(signed, 0)).where(CashEntry.month >= start))
        return (config.finance_opening_balance + Decimal(fees) + Decimal(entries)).quantize(Decimal("0.01"))

    # ---------- Mensalidades ----------
    async def set_fee(self, data: FeeCellIn, actor: User) -> FeeCellOut | None:
        if await self.session.get(Player, data.player_id) is None:
            raise NotFoundError("Jogador não encontrado")
        fee = await self.session.scalar(
            select(MonthlyFee).where(MonthlyFee.player_id == data.player_id, MonthlyFee.month == data.month)
        )
        before = {"amount": str(fee.amount) if fee and fee.amount is not None else None,
                  "marker": fee.marker if fee else None}
        marker = (data.marker or "").strip() or None
        if data.amount is None and marker is None:
            if fee:
                await self.session.delete(fee)
            result = None
        else:
            if fee is None:
                fee = MonthlyFee(player_id=data.player_id, month=data.month)
                self.session.add(fee)
            fee.amount, fee.marker = data.amount, marker
            result = FeeCellOut(amount=data.amount, marker=marker)
        await audit_service.record(
            self.session, user_id=actor.id, action="UPDATE", entity="monthly_fee",
            entity_id=f"{data.player_id}:{month_key(data.month)}",
            before=before, after={"amount": str(data.amount) if data.amount is not None else None, "marker": marker},
        )
        await self.session.commit()
        return result

    # ---------- Caixa ----------
    async def list_entries(self, year: int) -> list[CashEntry]:
        return list(
            await self.session.scalars(
                select(CashEntry)
                .where(extract("year", CashEntry.month) == year)
                .order_by(CashEntry.month.desc(), CashEntry.id.desc())
            )
        )

    async def create_entry(self, data: CashEntryIn, actor: User) -> CashEntry:
        entry = CashEntry(**data.model_dump())
        self.session.add(entry)
        await self.session.flush()
        await audit_service.record(
            self.session, user_id=actor.id, action="CREATE", entity="cash_entry", entity_id=entry.id,
            after=audit_service.snapshot(entry),
        )
        await self.session.commit()
        return entry

    async def update_entry(self, entry_id: int, data: CashEntryIn, actor: User) -> CashEntry:
        entry = await self._entry(entry_id)
        before = audit_service.snapshot(entry)
        for k, v in data.model_dump().items():
            setattr(entry, k, v)
        await audit_service.record(
            self.session, user_id=actor.id, action="UPDATE", entity="cash_entry", entity_id=entry.id,
            before=before, after=audit_service.snapshot(entry),
        )
        await self.session.commit()
        await self.session.refresh(entry)
        return entry

    async def delete_entry(self, entry_id: int, actor: User) -> None:
        entry = await self._entry(entry_id)
        await audit_service.record(
            self.session, user_id=actor.id, action="DELETE", entity="cash_entry", entity_id=entry.id,
            before=audit_service.snapshot(entry),
        )
        await self.session.delete(entry)
        await self.session.commit()

    async def _entry(self, entry_id: int) -> CashEntry:
        entry = await self.session.get(CashEntry, entry_id)
        if entry is None:
            raise NotFoundError("Lançamento não encontrado")
        return entry

    # ---------- Cobranças avulsas ----------
    async def list_collections(self) -> list[FinanceCollection]:
        return list(await self.session.scalars(select(FinanceCollection).order_by(FinanceCollection.id.desc())))

    async def create_collection(self, data: CollectionIn, actor: User) -> FinanceCollection:
        col = FinanceCollection(**data.model_dump())
        self.session.add(col)
        await self.session.flush()
        await audit_service.record(
            self.session, user_id=actor.id, action="CREATE", entity="collection", entity_id=col.id,
            after=data.model_dump(mode="json"),
        )
        await self.session.commit()
        return await self._collection(col.id)

    async def delete_collection(self, collection_id: int, actor: User) -> None:
        col = await self._collection(collection_id)
        await audit_service.record(
            self.session, user_id=actor.id, action="DELETE", entity="collection", entity_id=col.id,
            before={"title": col.title, "items": [i.name for i in col.items]},
        )
        await self.session.delete(col)
        await self.session.commit()

    async def add_item(self, collection_id: int, data: CollectionItemIn, actor: User) -> FinanceCollection:
        col = await self._collection(collection_id)
        if data.player_id is not None and await self.session.get(Player, data.player_id) is None:
            raise NotFoundError("Jogador não encontrado")
        item = CollectionItem(
            collection_id=col.id, name=data.name.strip(), player_id=data.player_id,
            amount=data.amount if data.amount is not None else col.amount_per_person, paid=data.paid,
        )
        self.session.add(item)
        await self.session.flush()
        await audit_service.record(
            self.session, user_id=actor.id, action="CREATE", entity="collection_item", entity_id=item.id,
            after=audit_service.snapshot(item),
        )
        await self.session.commit()
        return await self._collection(col.id)

    async def update_item(self, item_id: int, data: CollectionItemUpdate, actor: User) -> FinanceCollection:
        item = await self.session.get(CollectionItem, item_id)
        if item is None:
            raise NotFoundError("Item não encontrado")
        before = audit_service.snapshot(item)
        changes = data.model_dump(exclude_unset=True)
        if "player_id" in changes and changes["player_id"] is not None:
            if await self.session.get(Player, changes["player_id"]) is None:
                raise NotFoundError("Jogador não encontrado")
        for k, v in changes.items():
            if k in ("paid", "amount", "name") and v is None:
                raise ValidationError(f"Campo '{k}' não pode ser nulo")
            setattr(item, k, v)
        await audit_service.record(
            self.session, user_id=actor.id, action="UPDATE", entity="collection_item", entity_id=item.id,
            before=before, after=audit_service.snapshot(item),
        )
        await self.session.commit()
        return await self._collection(item.collection_id)

    async def delete_item(self, item_id: int, actor: User) -> FinanceCollection:
        item = await self.session.get(CollectionItem, item_id)
        if item is None:
            raise NotFoundError("Item não encontrado")
        collection_id = item.collection_id
        await audit_service.record(
            self.session, user_id=actor.id, action="DELETE", entity="collection_item", entity_id=item.id,
            before=audit_service.snapshot(item),
        )
        await self.session.delete(item)
        await self.session.commit()
        return await self._collection(collection_id)

    async def _collection(self, collection_id: int) -> FinanceCollection:
        # populate_existing recarrega os itens (selectin) após inserções/remoções
        col = await self.session.get(FinanceCollection, collection_id, populate_existing=True)
        if col is None:
            raise NotFoundError("Cobrança não encontrada")
        return col
