"""NEOVAM HMS -> NEOVAM SMS Gateway client.

The HMS never talks to the upstream SMS provider directly.  The Oracle-hosted
NEOVAM gateway owns the provider credentials and fixed whitelisted egress IP.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request


@dataclass
class GatewayResult:
    configured: bool
    status: str
    request_id: str | None = None
    provider_message_id: str | None = None
    response_text: str | None = None


def _config() -> tuple[str, str, str, float]:
    url = os.getenv("HMS_SMS_GATEWAY_URL", "").strip().rstrip("/")
    client_id = os.getenv("HMS_SMS_GATEWAY_CLIENT_ID", "").strip()
    secret = os.getenv("HMS_SMS_GATEWAY_SECRET", "").strip()
    try:
        timeout = float(os.getenv("HMS_SMS_GATEWAY_TIMEOUT_SECONDS", "8"))
    except ValueError:
        timeout = 8.0
    return url, client_id, secret, max(1.0, min(timeout, 60.0))


def gateway_status() -> dict:
    url, client_id, secret, timeout = _config()
    parsed = urllib.parse.urlparse(url) if url else None
    return {
        "configured": bool(url and client_id and secret),
        "gateway_origin": f"{parsed.scheme}://{parsed.netloc}" if parsed and parsed.scheme and parsed.netloc else None,
        "client_id": client_id or None,
        "timeout_seconds": timeout,
    }


def _signature(secret: str, timestamp: str, body: bytes) -> str:
    material = timestamp.encode("utf-8") + b"." + body
    return hmac.new(secret.encode("utf-8"), material, hashlib.sha256).hexdigest()


def send_sms_via_gateway(
    *,
    phone: str,
    message: str,
    event_type: str,
    hospital_id: int | str | None,
    visit_id: int | str | None,
    idempotency_key: str,
) -> GatewayResult:
    url, client_id, secret, timeout = _config()
    if not (url and client_id and secret):
        return GatewayResult(configured=False, status="QUEUED", response_text="NEOVAM SMS gateway is not configured")

    endpoint = url if url.endswith("/v1/messages") else f"{url}/v1/messages"
    payload = {
        "to": phone,
        "message": message,
        "event_type": event_type or "GENERAL",
        "hospital_id": hospital_id,
        "visit_id": visit_id,
    }
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    timestamp = str(int(time.time()))
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Client-ID": client_id,
        "X-Timestamp": timestamp,
        "X-Signature": _signature(secret, timestamp, body),
        "Idempotency-Key": idempotency_key,
        "User-Agent": "NEOVAM-HMS/1.0",
    }
    req = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read(8000).decode("utf-8", "replace")
            try:
                data = json.loads(raw) if raw else {}
            except Exception:
                data = {}
            status = str(data.get("status") or "SENT").upper()
            if status not in {"QUEUED", "SENDING", "SENT", "FAILED"}:
                status = "SENT" if 200 <= getattr(response, "status", 200) < 300 else "FAILED"
            return GatewayResult(
                configured=True,
                status=status,
                request_id=str(data.get("request_id")) if data.get("request_id") else None,
                provider_message_id=str(data.get("provider_message_id")) if data.get("provider_message_id") else None,
                response_text=raw[:8000],
            )
    except urllib.error.HTTPError as exc:
        raw = exc.read(8000).decode("utf-8", "replace")
        return GatewayResult(configured=True, status="FAILED", response_text=f"HTTP {exc.code}: {raw}"[:8000])
    except Exception as exc:
        return GatewayResult(configured=True, status="FAILED", response_text=str(exc)[:8000])
