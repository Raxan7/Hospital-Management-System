# NEOVAM HMS → Oracle SMS Gateway

NEOVAM HMS does not send directly to the upstream SMS provider.  It sends a signed HTTPS request to the NEOVAM SMS Gateway hosted on the Oracle VM whose public outbound IP is whitelisted by the provider.

## HMS environment

```env
HMS_SMS_GATEWAY_URL=https://sms-gateway.example.com
HMS_SMS_GATEWAY_CLIENT_ID=neovam-hms-prod
HMS_SMS_GATEWAY_SECRET=<same shared secret configured on gateway>
HMS_SMS_GATEWAY_TIMEOUT_SECONDS=8
```

The gateway URL may be either the gateway origin (`https://sms-gateway.example.com`) or the full messages endpoint (`https://sms-gateway.example.com/v1/messages`).

## Signed request

The HMS sends:

- `X-Client-ID`
- `X-Timestamp`
- `X-Signature`: HMAC-SHA256 of `timestamp + "." + raw JSON body`
- `Idempotency-Key`

The idempotency key is stable for an HMS SMS-outbox row. A retry therefore cannot create a second send if the gateway already accepted the original request.

## Clinical behavior

If the gateway is not configured, the message stays `QUEUED`. If the gateway/provider call fails, the message becomes `FAILED` and can be retried from the existing SMS outbox. A successful gateway response changes it to `SENT` and stores the gateway/provider IDs in `provider_response` for audit.

Admin users can inspect configuration safely at:

`GET /api/journey/sms-gateway/status`

The response never exposes `HMS_SMS_GATEWAY_SECRET`.
