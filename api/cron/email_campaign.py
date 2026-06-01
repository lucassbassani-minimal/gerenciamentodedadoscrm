"""Cron: atualiza métricas de campanhas de e-mail → campaign_email_metrics.
Chamado pela Vercel todo dia às 3h30 UTC (00h30 BRT).
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
            from ingestion.campaign_metrics_daily import run_yesterday
            run_yesterday()
            self._json(200, {"status": "ok", "job": "email_campaign"})
        except Exception as e:
            logger.error({"event": "cron_failed", "job": "email_campaign", "error": str(e)})
            from ingestion.alert import send_failure_alert
            send_failure_alert("email_campaign", str(e))
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
