"""Helper compartilhado: envia e-mail de alerta quando um cron falha."""
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

ALERT_TO = "daniel.magalhaes@minimalclub.com.br"
VERCEL_LOGS_URL = "https://vercel.com/lucasbassani-8576s-projects/gerenciamentodedadoscrm/logs"

logger = logging.getLogger(__name__)


def send_failure_alert(job: str, error: str) -> None:
    """Envia e-mail de alerta para ALERT_TO quando um cron falha.

    Requer as variáveis de ambiente:
      ALERT_SMTP_USER     → e-mail remetente (ex: daniel.magalhaes@minimalclub.com.br)
      ALERT_SMTP_PASSWORD → senha de app do Google Workspace
    """
    smtp_user = os.environ.get("ALERT_SMTP_USER", "")
    smtp_pass = os.environ.get("ALERT_SMTP_PASSWORD", "")

    if not smtp_user or not smtp_pass:
        logger.warning("ALERT_SMTP_USER ou ALERT_SMTP_PASSWORD não configurados — alerta ignorado")
        return

    msg = MIMEMultipart()
    msg["From"] = smtp_user
    msg["To"] = ALERT_TO
    msg["Subject"] = f"[CRM] Falha no cron: {job}"
    msg.attach(MIMEText(
        f"O cron '{job}' falhou.\n\n"
        f"Erro:\n{error}\n\n"
        f"Ver logs: {VERCEL_LOGS_URL}",
        "plain",
    ))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, ALERT_TO, msg.as_string())
        logger.info({"event": "alert_sent", "job": job, "to": ALERT_TO})
    except Exception as e:
        logger.error({"event": "alert_failed", "error": str(e)})
