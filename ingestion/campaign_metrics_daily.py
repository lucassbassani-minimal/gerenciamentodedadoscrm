"""
Ingestão diária de métricas de e-mail de campanhas Klaviyo → campaign_email_metrics.

Modos de uso:
  python -m ingestion.campaign_metrics_daily              # dia anterior (uso normal)
  python -m ingestion.campaign_metrics_daily --backfill   # histórico desde 2026-03-01
  python -m ingestion.campaign_metrics_daily --since 2026-04-01  # data inicial customizada
  python -m ingestion.campaign_metrics_daily --schedule   # daemon — roda todo dia às 02:00
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
from ingestion.sources.klaviyo_campaign_metrics import fetch_campaign_email_metrics, make_client

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
        rows = fetch_campaign_email_metrics(client, date_from, date_to)
        count = writers.upsert_campaign_email_metrics(sb, rows)
        logger.info({"event": "run_done", "rows_upserted": count})
    except Exception as e:
        logger.error({"event": "run_failed", "error": str(e)})
        raise


def run_yesterday() -> None:
    yesterday = date.today() - timedelta(days=1)
    run_for_period(yesterday, yesterday)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingestão de métricas de campanhas Klaviyo → campaign_email_metrics"
    )
    parser.add_argument(
        "--backfill", action="store_true",
        help=f"Carrega histórico completo desde {BACKFILL_START}",
    )
    parser.add_argument(
        "--since", type=str, default=None,
        help="Data inicial customizada (YYYY-MM-DD) — carrega até ontem",
    )
    parser.add_argument(
        "--schedule", action="store_true",
        help="Roda como daemon: executa todo dia às 02:00",
    )
    args = parser.parse_args()

    if args.schedule:
        schedule.every().day.at("02:00").do(run_yesterday)
        logger.info("Agendador iniciado — executa todo dia às 02:00")
        while True:
            schedule.run_pending()
            time.sleep(60)
    elif args.backfill:
        date_to = date.today() - timedelta(days=1)
        run_for_period(BACKFILL_START, date_to)
    elif args.since:
        date_from = date.fromisoformat(args.since)
        date_to = date.today() - timedelta(days=1)
        run_for_period(date_from, date_to)
    else:
        run_yesterday()


if __name__ == "__main__":
    main()
