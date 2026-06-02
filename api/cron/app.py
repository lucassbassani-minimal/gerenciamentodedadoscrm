"""App Flask unificado para todos os cron jobs — novo runtime Vercel."""
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import jwt
from flask import Flask, jsonify, make_response, redirect, request
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)

_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
_ALLOWED_DOMAINS = ('@minimalclub.com.br', '@moonventures.com.br')
_SUPABASE_URL    = 'https://aczvusdzfrmborvvfqib.supabase.co'
_SUPABASE_ANON   = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFjenZ1c2R6ZnJtYm9ydnZmcWliIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzg3ODkwNTIsImV4cCI6MjA5NDM2NTA1Mn0.hb0RjoXdmHN7wKLvhRCkJjq-ycqxE3FaJlYKtMEqumk'


def _get_auth_email() -> str | None:
    """Verifica o JWT Supabase no cookie e retorna o e-mail se autorizado."""
    token = request.cookies.get('sb_token', '')
    if not token:
        return None
    secret = os.environ.get('SUPABASE_JWT_SECRET', '')
    if not secret:
        return 'dev@minimalclub.com.br'  # dev sem secret configurado
    try:
        payload = jwt.decode(
            token, secret, algorithms=['HS256'],
            audience='authenticated',
            options={'verify_exp': True},
        )
        email = payload.get('email', '')
        if any(email.endswith(d) for d in _ALLOWED_DOMAINS):
            return email
        return None
    except Exception:
        return None


_LOGIN_HTML = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Dashboard CRM · Acesso</title>
  <script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:system-ui,sans-serif;background:#f4f6fa;display:flex;align-items:center;justify-content:center;min-height:100vh}}
    .card{{background:#fff;padding:40px;border-radius:14px;box-shadow:0 2px 20px rgba(0,0,0,.08);width:340px}}
    h2{{font-size:20px;margin-bottom:6px;color:#111;text-align:center}}
    .logo{{font-size:28px;margin-bottom:20px;text-align:center}}
    p{{color:#6b7785;font-size:13px;margin-bottom:24px;text-align:center}}
    label{{display:block;font-size:13px;font-weight:500;margin-bottom:4px;color:#374151}}
    input{{width:100%;padding:10px 12px;border:1px solid #d1d5db;border-radius:7px;font-size:14px;margin-bottom:14px;outline:none}}
    input:focus{{border-color:#111}}
    button{{width:100%;padding:12px;background:#111;color:#fff;border:none;border-radius:8px;font-size:15px;cursor:pointer;font-weight:600}}
    button:hover{{background:#333}}
    .err{{color:#dc2626;font-size:13px;margin-top:12px;text-align:center}}
  </style>
</head>
<body>
<div class="card">
  <div class="logo">📊</div>
  <h2>Dashboard CRM</h2>
  <p>Acesso restrito a @minimalclub.com.br<br>e @moonventures.com.br</p>
  <label>E-mail</label>
  <input id="email" type="email" placeholder="seu@minimalclub.com.br" autocomplete="email">
  <label>Senha</label>
  <input id="pwd" type="password" placeholder="••••••••" autocomplete="current-password">
  <button id="btn">Entrar</button>
  <div id="err" class="err"></div>
</div>
<script>
const {{createClient}} = supabase;
const _sb = createClient('{_SUPABASE_URL}', '{_SUPABASE_ANON}');
const ALLOWED = ['{_ALLOWED_DOMAINS[0]}','{_ALLOWED_DOMAINS[1]}'];

async function login() {{
  const email = document.getElementById('email').value.trim();
  const pwd   = document.getElementById('pwd').value;
  const errEl = document.getElementById('err');
  errEl.textContent = '';
  if (!ALLOWED.some(d => email.endsWith(d))) {{
    errEl.textContent = 'Use um e-mail @minimalclub.com.br ou @moonventures.com.br.';
    return;
  }}
  document.getElementById('btn').textContent = 'Entrando...';
  const {{data, error}} = await _sb.auth.signInWithPassword({{email, password: pwd}});
  document.getElementById('btn').textContent = 'Entrar';
  if (error) {{ errEl.textContent = 'E-mail ou senha incorretos.'; return; }}
  document.cookie = 'sb_token=' + data.session.access_token + '; path=/; samesite=strict; max-age=3600';
  window.location.href = '/';
}}

document.getElementById('btn').addEventListener('click', login);
document.getElementById('pwd').addEventListener('keydown', e => {{ if(e.key==='Enter') login(); }});
</script>
</body>
</html>"""


@app.route('/')
@app.route('/dashboard-crm.html')
def dashboard():
    if not _get_auth_email():
        return _LOGIN_HTML, 200, {'Content-Type': 'text/html; charset=utf-8'}
    path = os.path.join(_ROOT, 'dashboard-crm.html')
    with open(path, 'r', encoding='utf-8') as f:
        return f.read(), 200, {'Content-Type': 'text/html; charset=utf-8'}


@app.route('/auth/logout')
def logout():
    resp = make_response(redirect('/'))
    resp.set_cookie('sb_token', '', expires=0, path='/')
    return resp


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
