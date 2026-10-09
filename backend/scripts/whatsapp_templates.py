"""Envia os modelos do chatbot para aprovação da Meta e mostra o status.

Uso: docker compose exec api python -m scripts.whatsapp_templates   (META_WA_TOKEN e META_WABA_ID no ambiente)
"""
import json
import urllib.error
import urllib.request

from app.core.config import get_settings
from app.domain.chatbot import TEMPLATES, template_definition


def call(method: str, url: str, token: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as exc:
        return {"error": json.loads(exc.read() or b"{}").get("error", {})}


def main() -> None:
    s = get_settings()
    base = f"https://graph.facebook.com/{s.meta_graph_version}/{s.meta_waba_id}/message_templates"
    existing = {(t["name"], t.get("language")): t.get("status")
                for t in call("GET", base + "?fields=name,status,language&limit=100", s.meta_wa_token).get("data", [])}
    for t in TEMPLATES:
        key = (t["name"], s.meta_template_language)
        if key in existing:
            print(f"{t['name']}: já existe ({existing[key]})")
            continue
        r = call("POST", base, s.meta_wa_token, template_definition(t, s.meta_template_language))
        print(f"{t['name']}: {r.get('status') or r}")


if __name__ == "__main__":
    main()
