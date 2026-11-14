"""
Web Push notifications — replaces the old Telegram bot for proactive alerts
(digest, scout results, follow-up nudges). n8n workflows call POST /push/notify
instead of the Telegram sendMessage API; this module fans that out to every
subscribed browser via the W3C Push API + VAPID.
"""

import base64
import json
import os

from pywebpush import webpush, WebPushException

from core import db


def _vapid_private_pem() -> str:
    """VAPID_PRIVATE_KEY in .env is base64-encoded PEM (kept single-line)."""
    return base64.b64decode(os.environ["VAPID_PRIVATE_KEY"]).decode()


def send_push(title: str, body: str, url: str = "/dashboard") -> dict:
    """
    Send one notification to every stored subscription. Prunes subscriptions
    that the push service reports as gone (410) or not found (404) — the
    browser unsubscribed or the device is gone for good.
    Never raises — a notification failure shouldn't break the caller (n8n).
    """
    subs = db.get_push_subscriptions()
    payload = json.dumps({"title": title, "body": body, "url": url})
    sent, pruned, failed = 0, 0, 0

    for sub in subs:
        subscription_info = {
            "endpoint": sub["endpoint"],
            "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]},
        }
        try:
            webpush(
                subscription_info=subscription_info,
                data=payload,
                vapid_private_key=_vapid_private_pem(),
                vapid_claims={"sub": os.environ.get("VAPID_CLAIM_EMAIL", "mailto:noreply@example.com")},
            )
            sent += 1
        except WebPushException as e:
            status = getattr(e.response, "status_code", None)
            if status in (404, 410):
                db.delete_push_subscription(sub["endpoint"])
                pruned += 1
            else:
                print(f"[push] send failed ({status}): {e}")
                failed += 1

    return {"sent": sent, "pruned": pruned, "failed": failed, "total_subscriptions": len(subs)}
