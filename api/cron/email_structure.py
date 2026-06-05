"""Cron: sincroniza estrutura de fluxos -> dim_assets/dim_asset_items. Roda às 3h BRT (6h UTC)."""
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


@app.route('/api/cron/email_structure', methods=['GET'])
def email_structure():
    if not _authorized():
        return jsonify({'error': 'unauthorized'}), 401
    try:
        from ingestion.flow_structure_daily import run_structure_sync
        run_structure_sync()
        from ingestion.alert import log_cron
        log_cron('email_structure', 'ok')
        return jsonify({'status': 'ok', 'job': 'email_structure'})
    except Exception as e:
        logger.error({'event': 'cron_failed', 'job': 'email_structure', 'error': str(e)})
        from ingestion.alert import send_failure_alert
        send_failure_alert('email_structure', str(e))
        return jsonify({'error': str(e)}), 500
