"""Backfill único (não-cron): carrega a planilha de pedidos por e-mail
(Google Sheets/BigQuery export, sem produto) em fact_order_history_legacy.

Uso:
    python -m ingestion.backfill.load_order_history_legacy --csv <caminho> [--dry-run]
"""

import argparse
import csv
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation

from dotenv import load_dotenv
from pydantic import ValidationError

from ingestion.db.client import get_supabase_client
from ingestion.db.writers import replace_order_history_legacy
from ingestion.models.order_history_legacy_models import OrderHistoryLegacyRow

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _parse_valor(raw: str) -> Decimal | None:
    s = raw.replace(".", "").replace(",", ".") if "," in raw else raw
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def parse_csv(path: str) -> tuple[list[OrderHistoryLegacyRow], int]:
    rows: list[OrderHistoryLegacyRow] = []
    skipped = 0
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            email = (raw.get("e_mail") or "").strip().lower()
            data_str = raw.get("data_de_fechamento") or ""
            valor_str = raw.get("valor") or ""
            try:
                order_date = datetime.strptime(data_str, "%d/%m/%Y").date()
            except ValueError:
                skipped += 1
                continue
            valor = _parse_valor(valor_str)
            if valor is None or not email:
                skipped += 1
                continue
            try:
                rows.append(OrderHistoryLegacyRow(email=email, order_date=order_date, revenue_brl=valor))
            except ValidationError as e:
                skipped += 1
                logger.warning({"event": "legacy_row_invalid", "error": str(e)})
    return rows, skipped


def run(csv_path: str, dry_run: bool) -> None:
    rows, skipped = parse_csv(csv_path)
    logger.info({"event": "legacy_csv_parsed", "valid_rows": len(rows), "skipped": skipped})
    if dry_run:
        return
    sb = get_supabase_client()
    written = replace_order_history_legacy(sb, rows)
    logger.info({"event": "legacy_backfill_done", "written": written, "skipped": skipped})


if __name__ == "__main__":
    load_dotenv()
    parser = argparse.ArgumentParser(description="Backfill de fact_order_history_legacy a partir da planilha de pedidos por e-mail")
    parser.add_argument("--csv", required=True, help="Caminho do CSV (colunas: data_de_fechamento, valor, e_mail)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    run(args.csv, args.dry_run)
