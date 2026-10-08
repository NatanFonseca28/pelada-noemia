"""Chatbot de cobrança com um WhatsApp falso (sem Evolution API nem rede)."""
import base64
from datetime import UTC, datetime, timedelta
from io import BytesIO

import pytest
from PIL import Image

from app.core.config import get_settings
from app.domain.delinquency import reference_months
from app.services import chatbot_service
from app.services.chatbot_service import ChatbotService
from app.services.finance_service import today_local
from app.services.whatsapp_gateway import set_gateway

pytestmark = pytest.mark.asyncio(loop_scope="session")

SECRET = "segredo-teste"


class FakeWhatsApp:
    def __init__(self):
        self.sent: list[tuple[str, str]] = []
        self.connected = "open"

    async def send_text(self, number, text, typing_ms=1500):
        self.sent.append((number, text))

    async def state(self):
        return self.connected

    async def connect(self, webhook_url):
        self.webhook_url = webhook_url
        return "data:image/png;base64,QR"

    async def logout(self):
        self.connected = "close"


@pytest.fixture
def wa(monkeypatch):
    fake = FakeWhatsApp()
    set_gateway(fake)
    monkeypatch.setattr(get_settings(), "whatsapp_webhook_secret", SECRET)
    monkeypatch.setattr(get_settings(), "chatbot_webhook_base", "https://api.teste/api")
    monkeypatch.setattr(chatbot_service, "_next_charge_at", None)
    yield fake
    set_gateway(None)


def png_b64() -> str:
    out = BytesIO()
    Image.new("RGB", (40, 40), "green").save(out, format="PNG")
    return base64.b64encode(out.getvalue()).decode()


def inbound(phone_digits, text=None, image=False, msg_id="m1"):
    message = {"conversation": text} if text is not None else {}
    if image:
        message = {"imageMessage": {"caption": text or ""}, "base64": png_b64()}
    return {"event": "messages.upsert", "instance": "pelada",
            "data": {"key": {"remoteJid": f"{phone_digits}@s.whatsapp.net", "fromMe": False, "id": msg_id},
                     "message": message}}


async def drain(session_factory, clock=None):
    """Envia toda a fila, avançando o relógio para pular o intervalo entre cobranças."""
    t = clock or datetime.now(UTC)
    for _ in range(50):
        async with session_factory() as s:
            sent = await ChatbotService(s, clock=lambda: t).process_outbox(max_items=10)
        if not sent:
            t += timedelta(seconds=61)
            async with session_factory() as s:
                sent = await ChatbotService(s, clock=lambda: t).process_outbox(max_items=10)
            if not sent:
                return


async def test_chatbot_cobra_responde_e_admin_confirma(client, admin_headers, superadmin_headers, session_factory, wa):
    prev, cur = reference_months(today_local())

    async def player(name, phone, opt_in=True):
        return (await client.post("/api/players", json={
            "name": name, "type": "MENSALISTA", "primary_position": "ALA", "phone": phone,
            "whatsapp_opt_in": opt_in}, headers=admin_headers)).json()["id"]

    deve = await player("Deve Tudo", "21987650001")
    sem_ok = await player("Sem Aceite", "21987650002", opt_in=False)
    em_dia = await player("Em Dia", "21987650003")
    for m in (prev, cur):
        await client.put("/api/finance/fees", json={"player_id": em_dia, "month": m.isoformat(), "amount": "50"},
                         headers=admin_headers)
    await client.put("/api/finance/charge-message", json={"message": "Oi {nome}, {meses}: {valor}. {gestor}",
                                                           "pix_key": "pix@pelada"}, headers=superadmin_headers)

    # desligado: não cobra
    r = await client.post("/api/chatbot/charge-all", headers=admin_headers)
    assert r.status_code == 422 and "desligado" in r.json()["detail"]
    # superadmin conecta (vira dono do número) e liga
    c = (await client.post("/api/chatbot/connect", headers=superadmin_headers)).json()
    assert c["qr"].startswith("data:image") and wa.webhook_url.endswith(f"/chatbot/webhook/{SECRET}")
    owner = c["owner_user_id"]
    assert (await client.put("/api/chatbot/settings", json={"enabled": True, "daily_limit": 40,
                                                           "owner_user_id": owner},
                             headers=superadmin_headers)).status_code == 200
    assert (await client.put("/api/chatbot/settings", json={"enabled": True, "daily_limit": 40},
                             headers=admin_headers)).status_code == 403

    res = (await client.post("/api/chatbot/charge-all", headers=admin_headers)).json()
    assert "Deve Tudo" in res["queued"] and "Em Dia" not in res["queued"]
    assert {"name": "Sem Aceite", "reason": "não aceitou WhatsApp"} in res["skipped"]
    await drain(session_factory)
    texts = [t for n, t in wa.sent if n == "5521987650001"]
    assert texts[0].startswith("Oi Deve Tudo") and "R$ 100,00" in texts[0]
    assert texts[1].startswith("Responda com o número:")
    assert all(n != "5521987650002" for n, _ in wa.sent)
    # cobrar de novo dentro de 3 dias: pula (individual dá 409, a não ser com force)
    r = await client.post(f"/api/chatbot/charge/{deve}", json={}, headers=admin_headers)
    assert r.status_code == 409
    assert (await client.post(f"/api/chatbot/charge/{deve}", json={"force": True},
                              headers=admin_headers)).status_code == 200
    await drain(session_factory)
    # a auditoria "charge" continua alimentando "Última cobrança"
    lst = {d["name"]: d for d in (await client.get("/api/finance/to-charge", headers=admin_headers)).json()}
    assert lst["Deve Tudo"]["last_charged_at"] is not None

    # webhook: sem segredo certo = 404; número desconhecido é ignorado
    assert (await client.post("/api/chatbot/webhook/errado", json=inbound("5521987650001", "1"))).status_code == 404
    r = await client.post(f"/api/chatbot/webhook/{SECRET}", json=inbound("5521900000000", "1"))
    assert r.json()["result"] == "ignorado"

    wa.sent.clear()
    # 1 = Pix copia e cola (WhatsApp antigo sem o 9 também é reconhecido)
    r = await client.post(f"/api/chatbot/webhook/{SECRET}", json=inbound("552187650001", "1", msg_id="a"))
    assert r.json()["result"] == "PIX"
    await drain(session_factory)
    assert any("Chave: pix@pelada" in t for _, t in wa.sent)
    assert any(t.startswith("000201") and "br.gov.bcb.pix" in t for _, t in wa.sent)

    # 2 + comprovante = pedido de baixa com imagem; admin confirma e o mês vira pago
    await client.post(f"/api/chatbot/webhook/{SECRET}", json=inbound("5521987650001", "2", msg_id="b"))
    await client.post(f"/api/chatbot/webhook/{SECRET}", json=inbound("5521987650001", image=True, msg_id="c"))
    replies = (await client.get("/api/chatbot/replies", headers=admin_headers)).json()
    pago = next(x for x in replies if x["kind"] == "PAGO")
    assert pago["media_url"].startswith("/api/media/comprovantes/") and pago["amount"] == "100.00"
    assert (await client.post(f"/api/chatbot/replies/{pago['id']}/confirm", headers=admin_headers)).status_code == 204
    lst = {d["name"] for d in (await client.get("/api/finance/to-charge", headers=admin_headers)).json()}
    assert "Deve Tudo" not in lst
    await drain(session_factory)
    assert any(t.startswith("Pagamento confirmado") for _, t in wa.sent)

    # 3 = pedido de "F" (mês atual); 4 = falar com o gestor
    await client.post(f"/api/chatbot/webhook/{SECRET}", json=inbound("5521987650001", "3", msg_id="d"))
    await client.post(f"/api/chatbot/webhook/{SECRET}", json=inbound("5521987650001", "4", msg_id="e"))
    kinds = {x["kind"]: x for x in (await client.get("/api/chatbot/replies", headers=admin_headers)).json()}
    assert set(kinds) == {"FORA", "FALAR"}
    # já pago no mês atual: aprovar "F" não apaga o pagamento
    await client.post(f"/api/chatbot/replies/{kinds['FORA']['id']}/confirm", headers=admin_headers)
    ov = (await client.get("/api/finance/overview", params={"year": cur.year}, headers=admin_headers)).json()
    row = next(r for r in ov["rows"] if r["player_id"] == deve)
    assert row["cells"][cur.strftime("%Y-%m")]["amount"] == "50.00"
    assert (await client.post(f"/api/chatbot/replies/{kinds['FALAR']['id']}/reject",
                              headers=admin_headers)).status_code == 204
    assert (await client.get("/api/chatbot/replies", headers=admin_headers)).json() == []

    # repetição da mesma mensagem (reenvio do webhook) não duplica
    r = await client.post(f"/api/chatbot/webhook/{SECRET}", json=inbound("5521987650001", "4", msg_id="e"))
    assert r.json()["result"] == "repetido"

    await drain(session_factory)
    status = (await client.get("/api/chatbot/status", headers=admin_headers)).json()
    assert status["enabled"] and status["state"] == "open" and status["pending"] == 0


async def test_intervalo_entre_cobrancas(client, admin_headers, superadmin_headers, session_factory, wa):
    """Duas cobranças seguidas: a 2ª só sai depois do intervalo aleatório (25–60 s)."""
    for i in range(2):
        await client.post("/api/players", json={"name": f"Gap {i}", "type": "MENSALISTA", "primary_position": "ALA",
                                                "phone": f"2198765100{i}", "whatsapp_opt_in": True},
                          headers=admin_headers)
    await client.post("/api/chatbot/connect", headers=superadmin_headers)
    await client.put("/api/chatbot/settings", json={"enabled": True, "daily_limit": 40}, headers=superadmin_headers)
    await client.post("/api/chatbot/charge-all", headers=admin_headers)
    t0 = datetime.now(UTC)
    async with session_factory() as s:
        sent = await ChatbotService(s, clock=lambda: t0).process_outbox(max_items=10)
    assert sent == 2  # 1ª cobrança + o menu; a próxima cobrança espera
    async with session_factory() as s:
        assert await ChatbotService(s, clock=lambda: t0 + timedelta(seconds=10)).process_outbox(10) == 0
    async with session_factory() as s:
        assert await ChatbotService(s, clock=lambda: t0 + timedelta(seconds=61)).process_outbox(10) >= 1
