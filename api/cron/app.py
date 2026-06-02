"""App Flask unificado para todos os cron jobs — novo runtime Vercel."""
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


@app.route('/api/cron/revenue', methods=['GET'])
def revenue():
    if not _authorized():
        return jsonify({'error': 'unauthorized'}), 401
    try:
        from ingestion.main import run_smart_shopify_ingestion
        run_smart_shopify_ingestion()
        from ingestion.alert import log_cron
        log_cron('revenue', 'ok')
        return jsonify({'status': 'ok', 'job': 'revenue'})
    except Exception as e:
        logger.error({'event': 'cron_failed', 'job': 'revenue', 'error': str(e)})
        from ingestion.alert import send_failure_alert
        send_failure_alert('revenue', str(e))
        return jsonify({'error': str(e)}), 500


@app.route('/api/cron/sessions', methods=['GET'])
def sessions():
    if not _authorized():
        return jsonify({'error': 'unauthorized'}), 401
    try:
        from ingestion.main import run_sheets_ingestion
        run_sheets_ingestion()
        from ingestion.alert import log_cron
        log_cron('sessions', 'ok')
        return jsonify({'status': 'ok', 'job': 'sessions'})
    except Exception as e:
        logger.error({'event': 'cron_failed', 'job': 'sessions', 'error': str(e)})
        from ingestion.alert import send_failure_alert
        send_failure_alert('sessions', str(e))
        return jsonify({'error': str(e)}), 500


@app.route('/api/cron/email_flow', methods=['GET'])
def email_flow():
    if not _authorized():
        return jsonify({'error': 'unauthorized'}), 401
    try:
        from ingestion.flow_metrics_daily import run_yesterday
        run_yesterday()
        from ingestion.alert import log_cron
        log_cron('email_flow', 'ok')
        return jsonify({'status': 'ok', 'job': 'email_flow'})
    except Exception as e:
        logger.error({'event': 'cron_failed', 'job': 'email_flow', 'error': str(e)})
        from ingestion.alert import send_failure_alert
        send_failure_alert('email_flow', str(e))
        return jsonify({'error': str(e)}), 500


@app.route('/api/cron/email_campaign', methods=['GET'])
def email_campaign():
    if not _authorized():
        return jsonify({'error': 'unauthorized'}), 401
    try:
        from ingestion.campaign_metrics_daily import run_yesterday
        run_yesterday()
        from ingestion.alert import log_cron
        log_cron('email_campaign', 'ok')
        return jsonify({'status': 'ok', 'job': 'email_campaign'})
    except Exception as e:
        logger.error({'event': 'cron_failed', 'job': 'email_campaign', 'error': str(e)})
        from ingestion.alert import send_failure_alert
        send_failure_alert('email_campaign', str(e))
        return jsonify({'error': str(e)}), 500


@app.route('/api/cron/forms', methods=['GET'])
def forms():
    if not _authorized():
        return jsonify({'error': 'unauthorized'}), 401
    try:
        from ingestion.main import run_forms_ingestion
        run_forms_ingestion()
        from ingestion.alert import log_cron
        log_cron('forms', 'ok')
        return jsonify({'status': 'ok', 'job': 'forms'})
    except Exception as e:
        logger.error({'event': 'cron_failed', 'job': 'forms', 'error': str(e)})
        from ingestion.alert import send_failure_alert
        send_failure_alert('forms', str(e))
        return jsonify({'error': str(e)}), 500
