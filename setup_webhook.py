#!/usr/bin/env python3
"""
🔗 Webhook Setup Script
========================
Vercel-এ deploy করার পর এই script একবার run করো।
এটা Telegram-কে বলবে যে updates কোথায় পাঠাতে হবে।

Usage:
    python setup_webhook.py

Requires:
    BOT_TOKEN  — BotFather থেকে পাওয়া token
    VERCEL_URL — তোমার Vercel app URL  (e.g. https://my-bot.vercel.app)
"""

import os, sys, urllib.request, urllib.parse, json

BOT_TOKEN  = os.environ.get("BOT_TOKEN",  "").strip()
VERCEL_URL = os.environ.get("VERCEL_URL", "").strip().rstrip("/")

# ── Fallback: ask interactively ──────────────────────────────────
if not BOT_TOKEN:
    BOT_TOKEN = input("🤖 BOT_TOKEN: ").strip()
if not VERCEL_URL:
    VERCEL_URL = input("🌐 VERCEL_URL (e.g. https://my-bot.vercel.app): ").strip().rstrip("/")

if not BOT_TOKEN or not VERCEL_URL:
    print("❌ BOT_TOKEN and VERCEL_URL are required!")
    sys.exit(1)

WEBHOOK_URL = f"{VERCEL_URL}/api/webhook"
API_BASE    = f"https://api.telegram.org/bot{BOT_TOKEN}"


def tg_request(method: str, payload: dict = None) -> dict:
    url  = f"{API_BASE}/{method}"
    data = json.dumps(payload or {}).encode()
    req  = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def main():
    print("\n" + "═" * 50)
    print("  🌺  ULTRA VPS BOT — Webhook Setup  🌺")
    print("═" * 50)

    # 1. Delete old webhook
    print("\n🗑  Removing old webhook...")
    r = tg_request("deleteWebhook", {"drop_pending_updates": True})
    print(f"   {'✅' if r.get('ok') else '❌'}  {r.get('description', r)}")

    # 2. Set new webhook
    print(f"\n🔗  Setting webhook → {WEBHOOK_URL}")
    r = tg_request("setWebhook", {
        "url": WEBHOOK_URL,
        "allowed_updates": ["message", "callback_query", "inline_query"],
        "drop_pending_updates": True,
        "max_connections": 40,
    })
    if not r.get("ok"):
        print(f"❌  Failed: {r}")
        sys.exit(1)
    print(f"   ✅  {r.get('description', 'Webhook set!')}")

    # 3. Confirm
    print("\n📋  Verifying webhook info...")
    info = tg_request("getWebhookInfo")
    if info.get("ok"):
        w = info["result"]
        print(f"   🌐  URL         : {w.get('url')}")
        print(f"   ✅  Pending      : {w.get('pending_update_count', 0)}")
        print(f"   🔒  Has cert     : {w.get('has_custom_certificate', False)}")
        last_err = w.get("last_error_message")
        if last_err:
            print(f"   ⚠️   Last error  : {last_err}")

    print("\n" + "═" * 50)
    print("  ✅  Done! Your bot is live on Vercel.")
    print("═" * 50 + "\n")


if __name__ == "__main__":
    main()
