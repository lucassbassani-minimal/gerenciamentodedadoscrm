"""Cron: ingere eventos de disparo/resposta do Chatflux (WhatsApp) a cada 30 min."""
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


@app.route('/api/cron/chatflux', methods=['GET'])
def chatflux():
    if not _authorized():
        return jsonify({'error': 'unauthorized'}), 401
    try:
        from ingestion.sources.chatflux import run_chatflux_ingestion
        total = run_chatflux_ingestion()
        from ingestion.alert import log_cron
        log_cron('chatflux', 'ok')
        return jsonify({'status': 'ok', 'job': 'chatflux', 'rows': total})
    except Exception as e:
        logger.error({'event': 'cron_failed', 'job': 'chatflux', 'error': str(e)})
        from ingestion.alert import send_failure_alert
        send_failure_alert('chatflux', str(e))
        return jsonify({'error': str(e)}), 500
