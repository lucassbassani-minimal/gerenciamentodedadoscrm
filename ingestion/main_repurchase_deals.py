"""Orquestra a recarga diária de fact_repurchase_deals (source='sheets_diario')
a partir da aba "Base de Dados" da planilha de recompra, seguida do recálculo
da série mensal de métricas (fact_repurchase_monthly_metrics)."""

import logging

from ingestion.analytics.repurchase_monthly_metrics import compute_monthly_metrics
from ingestion.db.client import get_supabase_client
from ingestion.db.writers import (
    get_last_ingested_closed_at,
    replace_repurchase_deals,
    replace_repurchase_monthly_metrics,
)
from ingestion.sources.repurchase_deals_sheets import fetch_repurchase_deals_diario

logger = logging.getLogger(__name__)


def run_repurchase_deals_diario() -> dict:
    sb = get_supabase_client()
    since_date = get_last_ingested_closed_at(sb, source="sheets_diario")
    rows, skipped, reasons = fetch_repurchase_deals_diario(since_date=since_date)
    written = replace_repurchase_deals(sb, rows, source="sheets_diario", since_date=since_date)
    logger.info({"event": "repurchase_deals_diario_done", "written": written, "skipped": skipped, "reasons": reasons})

    metrics_rows = compute_monthly_metrics(sb)
    metrics_written = replace_repurchase_monthly_metrics(sb, metrics_rows)
    logger.info({"event": "repurchase_monthly_metrics_done", "months_written": metrics_written})

    sb.rpc("refresh_repurchase_materialized_views").execute()
    logger.info({"event": "repurchase_materialized_views_refreshed"})

    return {"deals_written": written, "deals_skipped": skipped, "months_written": metrics_written}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    from dotenv import load_dotenv
    load_dotenv()
    result = run_repurchase_deals_diario()
    print(result)
