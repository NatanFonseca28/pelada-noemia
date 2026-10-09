"""WhatsApp oficial (WhatsApp Business Platform / Cloud API da Meta). Os testes trocam por um gateway falso.

Mensagem que inicia conversa = modelo aprovado pela Meta (a cobrança, com botões de resposta rápida).
Dentro de 24 h da última mensagem do jogador, o bot responde com texto livre.
"""
import asyncio
import hashlib
import hmac
import json
import urllib.error
import urllib.request
from typing import Protocol

from app.core.config import get_settings

GRAPH = "https://graph.facebook.com"


class GatewayError(RuntimeError):
    pass


class WhatsAppGateway(Protocol):
    async def send_text(self, number: str, text: str) -> str | None: ...
    async def send_template(self, number: str, name: str, params: list[str],
                            buttons: list[str] | None = None) -> str | None: ...
    async def state(self) -> str: ...  # open | offline
    async def info(self) -> dict: ...  # número exibido, nome verificado, status dos modelos
    async def download_media(self, media_id: str) -> tuple[bytes, str]: ...
    async def owner_number(self) -> str | None: ...  # dígitos do número da pelada


class MetaCloudGateway:
    def __init__(self, token: str, phone_number_id: str, waba_id: str | None, version: str, language: str,
                 templates: list[str]):
        self.token = token
        self.phone_id = phone_number_id
        self.waba_id = waba_id
        self.base = f"{GRAPH}/{version}"
        self.language = language
        self.templates = templates

    async def _call(self, method: str, url: str, body: dict | None = None, raw: bool = False):
        def run():
            req = urllib.request.Request(
                url if url.startswith("http") else f"{self.base}{url}", method=method,
                data=json.dumps(body).encode() if body is not None else None,
                headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
            )
            try:
                with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 — graph.facebook.com
                    data = r.read()
                    return (data, r.headers.get_content_type()) if raw else (json.loads(data) if data else {})
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode(errors="replace")
                try:
                    detail = json.loads(detail)["error"]["message"]
                except (ValueError, KeyError, TypeError):
                    detail = detail[:200]
                raise GatewayError(f"WhatsApp {exc.code}: {detail}") from exc
            except (urllib.error.URLError, TimeoutError) as exc:
                raise GatewayError(f"WhatsApp indisponível: {exc}") from exc
        return await asyncio.to_thread(run)

    async def _send(self, body: dict) -> str | None:
        data = await self._call("POST", f"/{self.phone_id}/messages", {"messaging_product": "whatsapp", **body})
        return ((data.get("messages") or [{}])[0]).get("id")

    async def send_text(self, number: str, text: str) -> str | None:
        return await self._send({"to": number, "type": "text", "text": {"body": text, "preview_url": False}})

    async def send_template(self, number: str, name: str, params: list[str],
                            buttons: list[str] | None = None) -> str | None:
        components: list[dict] = []
        if params:
            components.append({"type": "body", "parameters": [{"type": "text", "text": p} for p in params]})
        for i, payload in enumerate(buttons or []):
            components.append({"type": "button", "sub_type": "quick_reply", "index": str(i),
                               "parameters": [{"type": "payload", "payload": payload}]})
        return await self._send({"to": number, "type": "template",
                                 "template": {"name": name, "language": {"code": self.language},
                                              "components": components}})

    async def state(self) -> str:
        try:
            await self._call("GET", f"/{self.phone_id}?fields=id")
            return "open"
        except GatewayError:
            return "offline"

    async def info(self) -> dict:
        number = await self._call("GET", f"/{self.phone_id}?fields=display_phone_number,verified_name,quality_rating")
        templates: dict[str, str] = {}
        if self.waba_id:
            data = await self._call("GET", f"/{self.waba_id}/message_templates?fields=name,status,language&limit=100")
            for t in data.get("data", []):
                if t.get("name") in self.templates and t.get("language") == self.language:
                    templates[t["name"]] = t.get("status", "?")
        return {"number": number.get("display_phone_number"), "name": number.get("verified_name"),
                "quality": number.get("quality_rating"),
                "templates": {n: templates.get(n, "NÃO CRIADO") for n in self.templates}}

    async def download_media(self, media_id: str) -> tuple[bytes, str]:
        meta = await self._call("GET", f"/{media_id}")
        if not meta.get("url"):
            raise GatewayError("Mídia sem URL")
        return await self._call("GET", meta["url"], raw=True)

    async def owner_number(self) -> str | None:
        number = await self._call("GET", f"/{self.phone_id}?fields=display_phone_number")
        digits = "".join(c for c in number.get("display_phone_number") or "" if c.isdigit())
        return digits or None


def valid_signature(body: bytes, header: str | None, app_secret: str) -> bool:
    """Webhook da Meta: X-Hub-Signature-256 = "sha256=" + HMAC-SHA256(corpo, App Secret)."""
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(header[7:], expected)


_override: WhatsAppGateway | None = None


def set_gateway(gateway: WhatsAppGateway | None) -> None:
    """Para os testes: injeta um gateway falso."""
    global _override
    _override = gateway


def get_gateway() -> WhatsAppGateway | None:
    if _override is not None:
        return _override
    s = get_settings()
    if not (s.meta_wa_token and s.meta_wa_phone_number_id):
        return None
    return MetaCloudGateway(s.meta_wa_token, s.meta_wa_phone_number_id, s.meta_waba_id, s.meta_graph_version,
                            s.meta_template_language, [s.meta_template_charge, s.meta_template_paid])
