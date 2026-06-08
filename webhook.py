"""
Vercel Serverless Function — Telegram Webhook Handler
POST /api/webhook  ←  Telegram sends updates here
GET  /api/webhook  ←  Health check
"""

import json, os, asyncio, logging
from http.server import BaseHTTPRequestHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class handler(BaseHTTPRequestHandler):

    def log_message(self, *args):
        pass  # silence default HTTP logs

    # ── Health check ──────────────────────────────────────────────
    def do_GET(self):
        body = json.dumps({"status": "ok", "bot": "Ultra VPS Bot", "version": "2.0"}).encode()
        self._send(200, "application/json", body)

    # ── Telegram update ───────────────────────────────────────────
    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length)
            update_dict = json.loads(raw)
        except Exception as e:
            logger.error(f"Bad request body: {e}")
            self._send(400, "text/plain", b"Bad Request")
            return

        try:
            asyncio.run(self._process(update_dict))
        except RuntimeError:
            # Already-running loop (shouldn't happen in serverless but just in case)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._process(update_dict))
            loop.close()

        self._send(200, "text/plain", b"OK")

    # ── Core async processor ──────────────────────────────────────
    async def _process(self, update_dict: dict):
        from telegram import Update
        from telegram.ext import Application
        import bot_core as core

        BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
        if not BOT_TOKEN:
            logger.error("BOT_TOKEN not set!")
            return

        app = (
            Application.builder()
            .token(BOT_TOKEN)
            .connect_timeout(30)
            .read_timeout(30)
            .write_timeout(30)
            .build()
        )

        # Register all handlers
        core.register_handlers(app)

        await app.initialize()
        update = Update.de_json(update_dict, app.bot)
        await app.process_update(update)
        await app.shutdown()

    # ── Helper ────────────────────────────────────────────────────
    def _send(self, code: int, ctype: str, body: bytes):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
