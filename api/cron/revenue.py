"""Cron: atualiza receita (Shopify) → fact_orders.
Chamado pela Vercel a cada 35 minutos.
"""
from http.server import BaseHTTPRequestHandler
import json
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _authorized(headers) -> bool:
    secret = os.environ.get('CRON_SECRET', '')
    if not secret:
        return True
    return headers.get('Authorization', '') == f'Bearer {secret}'


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if not _authorized(self.headers):
            self._json(401, {"error": "unauthorized"})
            return
        try:
            from dotenv import load_dotenv
            load_dotenv()
            from ingestion.main import run_smart_shopify_ingestion
            run_smart_shopify_ingestion()
            self._json(200, {"status": "ok", "job": "revenue"})
        except Exception as e:
            logger.error({"event": "cron_failed", "job": "revenue", "error": str(e)})
            from api.cron._alert import send_failure_alert
            send_failure_alert("revenue", str(e))
            self._json(500, {"error": str(e)})

    def _json(self, code: int, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        logger.debug(fmt, *args)
