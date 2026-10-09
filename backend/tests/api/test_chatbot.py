"""Chatbot de cobrança na API oficial da Meta, com um WhatsApp falso (sem rede)."""
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from io import BytesIO

import pytest
from PIL import Image

from app.core.config import get_settings
from app.domain.delinquency import reference_months
from app.services.chatbot_service import ChatbotService
from app.services.finance_service import today_local
from app.services.whatsapp_gateway import set_gateway

pytestmark = pytest.mark.asyncio(loop_scope="session")

APP_SECRET = "segredo-do-app"
OWN = "5521999990000"  # número da pelada


def png() -> bytes:
    out = BytesIO()
    Image.new("RGB", (40, 40), "green").save(out, format="PNG")
    return out.getvalue()


class FakeWhatsApp:
    def __init__(self):
        self.sent: list[dict] = []
        self.n = 0

    async def _id(self):
        self.n += 1
        return f"wamid.{self.n}"

    async def send_text(self, number, text):
        self.sent.append({"to": number, "text": text})
        return await self._id()

    async def send_template(self, number, name, params, buttons=None):
        self.sent.append({"to": number, "template": name, "params": params, "buttons": buttons})
        return await self._id()

    async def state(self):
        return "open"

    async def info(self):
        return {"number": "+55 21 99999-0000", "name": "Pelada", "quality": "GREEN",
                "templates": {"cobranca_mensalidade": "APPROVED", "pagamento_confirmado": "APPROVED"}}

    async def download_media(self, media_id):
        return png(), "image/png"

    async def owner_number(self):
        return OWN


@pytest.fixture
def wa(monkeypatch):
    fake = FakeWhatsApp()
    set_gateway(fake)
    monkeypatch.setattr(get_settings(), "meta_app_secret", APP_SECRET)
    monkeypatch.setattr(get_settings(), "meta_verify_token", "verifica")
    yield fake
    set_gateway(None)


def event(frm, msg_id, ts=None, **message):
    msg = {"from": frm, "id": msg_id, "timestamp": str(ts or int(datetime.now(UTC).timestamp())), **message}
    return {"object": "whatsapp_business_account",
            "entry": [{"id": "WABA", "changes": [{"field": "messages", "value": {"messages": [msg]}}]}]}


async def post_event(client, payload, secret=APP_SECRET):
    body = json.dumps(payload).encode()
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return await client.post("/api/chatbot/webhook", content=body,
                             headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"})


async def drain(session_factory, clock=None):
    async with session_factory() as s:
        await ChatbotService(s, clock=clock or (lambda: datetime.now(UTC))).process_outbox(max_items=50)


async def test_chatbot_oficial_fluxo_completo(client, admin_headers, superadmin_headers, session_factory, wa):
    prev, cur = reference_months(today_local())

    async def player(name, phone, opt_in=True):
        return (await client.post("/api/players", json={
            "name": name, "type": "MENSALISTA", "primary_position": "ALA", "phone": phone,
            "whatsapp_opt_in": opt_in}, headers=admin_headers)).json()["id"]

    deve = await player("Deve Tudo", "21987650001")
    await player("Sem Aceite", "21987650002", opt_in=False)
    pelada = await player("Numero Da Pelada", "21999990000")
    em_dia = await player("Em Dia", "21987650003")
    for m in (prev, cur):
        await client.put("/api/finance/fees", json={"player_id": em_dia, "month": m.isoformat(), "amount": "50"},
                         headers=admin_headers)
    await client.put("/api/finance/charge-message", json={"message": "Oi {nome}", "pix_key": "pix@pelada"},
                     headers=superadmin_headers)

    # verificação do webhook (painel da Meta)
    r = await client.get("/api/chatbot/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "verifica",
                                                         "hub.challenge": "123"})
    assert r.status_code == 200 and r.text == "123"
    r = await client.get("/api/chatbot/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "x",
                                                         "hub.challenge": "123"})
    assert r.status_code == 403

    r = await client.post("/api/chatbot/charge-all", headers=admin_headers)
    assert r.status_code == 422 and "desligado" in r.json()["detail"]
    assert (await client.put("/api/chatbot/settings", json={"enabled": True, "daily_limit": 40},
                             headers=admin_headers)).status_code == 403
    st = (await client.put("/api/chatbot/settings", json={"enabled": True, "daily_limit": 40},
                           headers=superadmin_headers)).json()
    assert st["enabled"] and st["owner_name"]  # quem liga vira o {gestor}
    det = (await client.get("/api/chatbot/status", params={"details": True}, headers=admin_headers)).json()
    assert det["info"]["templates"]["cobranca_mensalidade"] == "APPROVED"

    res = (await client.post("/api/chatbot/charge-all", headers=admin_headers)).json()
    assert "Deve Tudo" in res["queued"] and "Em Dia" not in res["queued"]
    assert {"name": "Sem Aceite", "reason": "não aceitou WhatsApp"} in res["skipped"]
    assert {"name": "Numero Da Pelada", "reason": "é o número do WhatsApp da pelada"} in res["skipped"]
    r = await client.post(f"/api/chatbot/charge/{pelada}", json={"force": True}, headers=admin_headers)
    assert r.status_code == 422 and "mesmo número" in r.json()["detail"]
    await drain(session_factory)
    tpl = next(m for m in wa.sent if m["to"] == "5521987650001")
    assert tpl["template"] == "cobranca_mensalidade" and tpl["buttons"] == ["PIX", "PAGO", "FORA", "FALAR"]
    assert tpl["params"][0] == "Deve Tudo" and tpl["params"][3] == "R$ 100,00" and tpl["params"][4] == "pix@pelada"
    assert (await client.post(f"/api/chatbot/charge/{deve}", json={}, headers=admin_headers)).status_code == 409

    # assinatura errada = 403; número desconhecido = ignorado
    r = await post_event(client, event("5521987650001", "x", type="text", text={"body": "1"}), secret="errado")
    assert r.status_code == 403
    r = await post_event(client, event("5521900000000", "y", type="text", text={"body": "1"}))
    assert r.json()["results"] == ["ignorado"]

    wa.sent.clear()
    # botão "Pix copia e cola" (WhatsApp antigo sem o 9 também é reconhecido)
    r = await post_event(client, event("552187650001", "a", type="button",
                                       button={"payload": "PIX", "text": "Pix copia e cola"}))
    assert r.json()["results"] == ["PIX"]
    await drain(session_factory)
    assert any("Chave: pix@pelada" in m.get("text", "") for m in wa.sent)
    assert any(m.get("text", "").startswith("000201") for m in wa.sent)

    # "Já paguei" + foto = pedido com comprovante baixado da Meta; admin confirma
    await post_event(client, event("5521987650001", "b", type="button", button={"payload": "PAGO"}))
    await post_event(client, event("5521987650001", "c", type="image", image={"id": "MEDIA1"}))
    replies = (await client.get("/api/chatbot/replies", headers=admin_headers)).json()
    pago = next(x for x in replies if x["kind"] == "PAGO")
    assert pago["media_url"].startswith("/api/media/comprovantes/")
    assert (await client.post(f"/api/chatbot/replies/{pago['id']}/confirm", headers=admin_headers)).status_code == 204
    assert "Deve Tudo" not in {d["name"] for d in (await client.get("/api/finance/to-charge",
                                                                     headers=admin_headers)).json()}
    wa.sent.clear()
    await drain(session_factory)
    assert wa.sent[-1]["text"].startswith("Pagamento confirmado")  # dentro de 24 h: texto livre

    # digitado "3" e botão "Falar"
    await post_event(client, event("5521987650001", "d", type="text", text={"body": "3"}))
    await post_event(client, event("5521987650001", "e", type="interactive",
                                   interactive={"type": "button_reply", "button_reply": {"id": "FALAR"}}))
    kinds = {x["kind"] for x in (await client.get("/api/chatbot/replies", headers=admin_headers)).json()}
    assert kinds == {"FORA", "FALAR"}

    # repetição e reentrega antiga não duplicam
    r = await post_event(client, event("5521987650001", "e", type="text", text={"body": "4"}))
    assert r.json()["results"] == ["repetido"]
    old = int(datetime.now(UTC).timestamp()) - 3600
    r = await post_event(client, event("5521987650001", "z", ts=old, type="text", text={"body": "4"}))
    assert r.json()["results"] == ["repetido"]

    # "parar": deixa de receber cobranças pelo WhatsApp
    r = await post_event(client, event("5521987650001", "p1", type="text", text={"body": "parar"}))
    assert r.json()["results"] == ["STOP"]
    players = {p["id"]: p for p in (await client.get("/api/players", headers=admin_headers)).json()}
    assert players[deve]["whatsapp_opt_in"] is False

    # falha de entrega informada pela Meta aparece na fila
    async with session_factory() as s:
        from sqlalchemy import select

        from app.models.chatbot import WhatsAppOutbox
        first = await s.scalar(select(WhatsAppOutbox).where(WhatsAppOutbox.kind == "COBRANCA"))
    status_evt = {"entry": [{"changes": [{"value": {"statuses": [{
        "id": first.message_id, "status": "failed", "errors": [{"code": 131026, "title": "Message undeliverable"}]}]}}]}]}
    await post_event(client, status_evt)
    queue = (await client.get("/api/chatbot/queue", headers=admin_headers)).json()
    assert any(q["status"] == "ERRO" and "131026" in (q["error"] or "") for q in queue)


async def test_confirmacao_fora_da_janela_usa_modelo(client, admin_headers, superadmin_headers, session_factory, wa):
    pid = (await client.post("/api/players", json={"name": "Janela", "type": "MENSALISTA", "primary_position": "ALA",
                                                   "phone": "21987651111", "whatsapp_opt_in": True},
                             headers=admin_headers)).json()["id"]
    await client.put("/api/chatbot/settings", json={"enabled": True, "daily_limit": 40}, headers=superadmin_headers)
    await client.post(f"/api/chatbot/charge/{pid}", json={}, headers=admin_headers)
    await drain(session_factory)
    old = int((datetime.now(UTC) - timedelta(hours=30)).timestamp())
    await post_event(client, event("5521987651111", "j1", ts=old, type="button", button={"payload": "PAGO"}))
    reply = next(x for x in (await client.get("/api/chatbot/replies", headers=admin_headers)).json()
                 if x["player_id"] == pid)
    await client.post(f"/api/chatbot/replies/{reply['id']}/confirm", headers=admin_headers)
    wa.sent.clear()
    await drain(session_factory)
    confirm = next(m for m in wa.sent if m["to"] == "5521987651111" and "template" in m)
    assert confirm["template"] == "pagamento_confirmado"
