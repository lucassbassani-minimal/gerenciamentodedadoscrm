"""
Ingestão diária de métricas de e-mail de fluxos Klaviyo -> flow_email_metrics.

Modos de uso:
  python -m ingestion.flow_metrics_daily              # dia anterior (uso normal)
  python -m ingestion.flow_metrics_daily --backfill   # histórico desde 2026-03-01
  python -m ingestion.flow_metrics_daily --since 2026-04-01  # data inicial customizada
  python -m ingestion.flow_metrics_daily --schedule   # daemon — roda todo dia às 02:30
"""

import argparse
import logging
import sys
import time
from datetime import date, timedelta

import schedule
from dotenv import load_dotenv

from ingestion.db import writers
from ingestion.db.client import get_supabase_client
from ingestion.sources.klaviyo_flow_metrics import fetch_flow_email_metrics, make_client

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

BACKFILL_START = date(2026, 3, 1)


def run_for_period(date_from: date, date_to: date) -> None:
    logger.info({
        "event": "run_start",
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
    })
    try:
        sb = get_supabase_client()
        client = make_client()
        rows = fetch_flow_email_metrics(client, sb, date_from, date_to)
        count = writers.upsert_flow_email_metrics(sb, rows)
        logger.info({"event": "run_done", "rows_upserted": count})
    except Exception as e:
        logger.error({"event": "run_failed", "error": str(e)})
        raise


def run_yesterday() -> None:
    # Rebusca os últimos 2 dias para recuperar automaticamente falhas do dia anterior
    two_days_ago = date.today() - timedelta(days=2)
    yesterday    = date.today() - timedelta(days=1)
    run_for_period(two_days_ago, yesterday)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingesta metricas de e-mail de fluxos Klaviyo -> flow_email_metrics"
    )
    parser.add_argument(
        "--backfill", action="store_true",
        help=f"Carrega historico completo desde {BACKFILL_START}",
    )
    parser.add_argument(
        "--since", type=str, default=None,
        help="Data inicial customizada (YYYY-MM-DD) — carrega ate ontem",
    )
    parser.add_argument(
        "--schedule", action="store_true",
        help="Roda como daemon: executa todo dia as 02:30",
    )
    args = parser.parse_args()

    if args.schedule:
        schedule.every().day.at("02:30").do(run_yesterday)
        logger.info("Agendador iniciado — executa todo dia as 02:30")
        while True:
            schedule.run_pending()
            time.sleep(60)
    elif args.backfill:
        run_for_period(BACKFILL_START, date.today() - timedelta(days=1))
    elif args.since:
        run_for_period(date.fromisoformat(args.since), date.today() - timedelta(days=1))
    else:
        run_yesterday()


if __name__ == "__main__":
    main()
