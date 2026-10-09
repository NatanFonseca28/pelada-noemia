"""Ponte com o WhatsApp do admin (Evolution API, não oficial). Os testes trocam por um gateway falso."""
import asyncio
import json
import urllib.error
import urllib.request
from typing import Protocol

from app.core.config import get_settings


class GatewayError(RuntimeError):
    pass


class WhatsAppGateway(Protocol):
    async def send_text(self, number: str, text: str, typing_ms: int = 1500) -> None: ...
    async def state(self) -> str: ...  # open | connecting | close | missing
    async def connect(self, webhook_url: str) -> str | None: ...  # QR Code (data URI) ou None se já conectado
    async def logout(self) -> None: ...


class EvolutionGateway:
    """Cliente da Evolution API v2 (https://doc.evolution-api.com)."""

    def __init__(self, url: str, api_key: str, instance: str):
        self.url = url.rstrip("/")
        self.key = api_key
        self.instance = instance

    async def _call(self, method: str, path: str, body: dict | None = None, ok404: bool = False,
                    timeout: float = 90) -> dict:
        # 90 s por padrão: no plano grátis do Render o serviço dorme e leva ~1 min para acordar
        def run() -> dict:
            req = urllib.request.Request(
                f"{self.url}{path}", method=method,
                data=json.dumps(body).encode() if body is not None else None,
                headers={"apikey": self.key, "Content-Type": "application/json"},
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 — URL da própria infraestrutura
                    raw = r.read()
                    return json.loads(raw) if raw else {}
            except urllib.error.HTTPError as exc:
                if ok404 and exc.code == 404:
                    return {"_missing": True}
                detail = exc.read().decode(errors="replace")[:200]
                raise GatewayError(f"Evolution API {exc.code}: {detail}") from exc
            except (urllib.error.URLError, TimeoutError) as exc:
                raise GatewayError(f"Evolution API indisponível: {exc}") from exc
        return await asyncio.to_thread(run)

    async def send_text(self, number: str, text: str, typing_ms: int = 1500) -> None:
        # `delay` mostra "digitando…" antes de enviar
        await self._call("POST", f"/message/sendText/{self.instance}",
                         {"number": number, "text": text, "delay": typing_ms})

    async def state(self) -> str:
        # consulta rápida (tela de status): se estiver dormindo, a chamada já serve para acordá-lo
        data = await self._call("GET", f"/instance/connectionState/{self.instance}", ok404=True, timeout=12)
        if data.get("_missing"):
            return "missing"
        return (data.get("instance") or {}).get("state") or data.get("state") or "close"

    async def connect(self, webhook_url: str) -> str | None:
        webhook = {"enabled": True, "url": webhook_url, "byEvents": False, "base64": True,
                   "events": ["MESSAGES_UPSERT", "CONNECTION_UPDATE"]}
        state = await self._call("GET", f"/instance/connectionState/{self.instance}", ok404=True)
        if state.get("_missing"):
            await self._call("POST", "/instance/create", {
                "instanceName": self.instance, "integration": "WHATSAPP-BAILEYS", "qrcode": True,
                "webhook": webhook,
            })
        else:
            await self._call("POST", f"/webhook/set/{self.instance}", {"webhook": webhook})
        if await self.state() == "open":
            return None
        data = await self._call("GET", f"/instance/connect/{self.instance}")
        return data.get("base64")

    async def logout(self) -> None:
        await self._call("DELETE", f"/instance/logout/{self.instance}", ok404=True)


_override: WhatsAppGateway | None = None


def set_gateway(gateway: WhatsAppGateway | None) -> None:
    """Para os testes: injeta um gateway falso."""
    global _override
    _override = gateway


def get_gateway() -> WhatsAppGateway | None:
    if _override is not None:
        return _override
    s = get_settings()
    if not (s.evolution_url and s.evolution_api_key):
        return None
    return EvolutionGateway(s.evolution_url, s.evolution_api_key, s.evolution_instance)
