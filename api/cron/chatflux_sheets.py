"""Cron: exporta fact_chatflux_events + fact_chatflux_leads_diario para a aba
"Base de Dados ChatFlux" no Google Sheets, a cada hora."""
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


@app.route('/api/cron/chatflux_sheets', methods=['GET'])
def chatflux_sheets():
    if not _authorized():
        return jsonify({'error': 'unauthorized'}), 401
    try:
        from ingestion.sources.chatflux_sheets_export import export_chatflux_to_sheets
        total = export_chatflux_to_sheets()
        from ingestion.alert import log_cron
        log_cron('chatflux_sheets', 'ok')
        return jsonify({'status': 'ok', 'job': 'chatflux_sheets', 'rows': total})
    except Exception as e:
        logger.error({'event': 'cron_failed', 'job': 'chatflux_sheets', 'error': str(e)})
        from ingestion.alert import send_failure_alert
        send_failure_alert('chatflux_sheets', str(e))
        return jsonify({'error': str(e)}), 500
