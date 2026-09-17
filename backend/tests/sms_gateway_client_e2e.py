"""Contract test for HMS -> NEOVAM SMS Gateway."""
import hashlib
import hmac
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

captured = {}
SECRET = "shared-test-secret"
CLIENT = "hms-test"

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        captured["path"] = self.path
        captured["body"] = body
        captured["client"] = self.headers.get("X-Client-ID")
        captured["timestamp"] = self.headers.get("X-Timestamp")
        captured["signature"] = self.headers.get("X-Signature")
        captured["idempotency"] = self.headers.get("Idempotency-Key")
        expected = hmac.new(SECRET.encode(), captured["timestamp"].encode()+b"."+body, hashlib.sha256).hexdigest()
        if captured["client"] != CLIENT or captured["signature"] != expected:
            self.send_response(401); self.end_headers(); return
        response = json.dumps({"request_id":"sms_abc","status":"SENT","provider_message_id":"provider-123"}).encode()
        self.send_response(200)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(response)))
        self.end_headers(); self.wfile.write(response)
    def log_message(self, *args):
        pass

server = HTTPServer(("127.0.0.1", 0), Handler)
thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
port = server.server_address[1]
os.environ["HMS_SMS_GATEWAY_URL"] = f"http://127.0.0.1:{port}"
os.environ["HMS_SMS_GATEWAY_CLIENT_ID"] = CLIENT
os.environ["HMS_SMS_GATEWAY_SECRET"] = SECRET
os.environ["HMS_SMS_GATEWAY_TIMEOUT_SECONDS"] = "3"

from app.sms_gateway import gateway_status, send_sms_via_gateway

st = gateway_status()
assert st["configured"] is True and st["client_id"] == CLIENT
assert "secret" not in st

res = send_sms_via_gateway(
    phone="0712345678",
    message="Your laboratory results are ready. Please visit the doctor.",
    event_type="LAB_RESULTS_READY",
    hospital_id=1,
    visit_id=77,
    idempotency_key="LAB_RESULTS_READY:77",
)
assert res.status == "SENT"
assert res.request_id == "sms_abc"
assert res.provider_message_id == "provider-123"
assert captured["path"] == "/v1/messages"
payload = json.loads(captured["body"].decode())
assert payload["to"] == "0712345678"
assert payload["event_type"] == "LAB_RESULTS_READY"
assert payload["visit_id"] == 77
assert captured["idempotency"] == "LAB_RESULTS_READY:77"

server.shutdown(); server.server_close()

# Missing configuration must queue safely rather than crash clinical workflow.
os.environ.pop("HMS_SMS_GATEWAY_URL", None)
res2 = send_sms_via_gateway(phone="0712", message="x", event_type="TEST", hospital_id=1, visit_id=1, idempotency_key="x")
assert res2.configured is False and res2.status == "QUEUED"
print("sms gateway client e2e: PASS")
