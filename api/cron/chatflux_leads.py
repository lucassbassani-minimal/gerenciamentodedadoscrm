"""Cron: ingere totais diários de leads por vendedor do Chatflux (/api/leads) a cada 30 min."""
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from flask import Flask, jsonify, request
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)


def _authorized() -> bool:
    secret = os.environ.get('CRON_SECRET', '')
    if not secret:
        return True
    return request.headers.get('Authorization', '') == f'Bearer {secret}'


@app.route('/api/cron/chatflux_leads', methods=['GET'])
def chatflux_leads():
    if not _authorized():
        return jsonify({'error': 'unauthorized'}), 401
    try:
        from ingestion.sources.chatflux_leads import run_chatflux_leads_ingestion
        total = run_chatflux_leads_ingestion()
        from ingestion.alert import log_cron
        log_cron('chatflux_leads', 'ok')
        return jsonify({'status': 'ok', 'job': 'chatflux_leads', 'rows': total})
    except Exception as e:
        logger.error({'event': 'cron_failed', 'job': 'chatflux_leads', 'error': str(e)})
        from ingestion.alert import send_failure_alert
        send_failure_alert('chatflux_leads', str(e))
        return jsonify({'error': str(e)}), 500
