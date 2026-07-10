"""Backfill único (não-cron): carrega export manual de pedidos do Shopify
(linha por item, arquivos zip em "Todos os pedidos Minimal/") em fact_order_history_items.

Uso:
    python -m ingestion.backfill.load_order_history [--folder "Todos os pedidos Minimal"] [--dry-run]
"""

import argparse
import csv
import io
import logging
import zipfile
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from dateutil import parser as date_parser
from dotenv import load_dotenv
from pydantic import ValidationError

from ingestion.db.client import get_supabase_client
from ingestion.db.writers import upsert_order_history_items
from ingestion.models.order_history_models import OrderHistoryLineItem

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_HEADER_FIELDS = [
    "Id", "Financial Status", "Paid at", "Created at", "Total", "Subtotal",
    "Discount Code", "Discount Amount", "Shipping Method", "Billing Province Name", "Email",
]


def _blank(value: str | None) -> str | None:
    return value if value else None


def _parse_decimal(value: str | None) -> Decimal | None:
    if not value:
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def _parse_int(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return date_parser.parse(value)


def parse_csv_rows(rows: csv.DictReader) -> tuple[list[OrderHistoryLineItem], int, int]:
    """Agrupa linhas consecutivas do mesmo pedido, propaga campos de cabeçalho
    (Paid at, Total etc. só vêm preenchidos na 1ª linha do pedido no export do Shopify)
    e valida cada item. Retorna (itens válidos, pulados por não-pago, pulados por inválido).
    """
    items: list[OrderHistoryLineItem] = []
    skipped_not_paid = 0
    skipped_invalid = 0

    current_name: str | None = None
    header: dict[str, str | None] = {}
    line_number = 0

    for row in rows:
        name = row["Name"]
        if name != current_name:
            current_name = name
            header = {}
            line_number = 0
        for field in _HEADER_FIELDS:
            value = _blank(row.get(field))
            if value:
                header[field] = value
        line_number += 1

        if header.get("Financial Status") != "paid":
            skipped_not_paid += 1
            continue

        try:
            item = OrderHistoryLineItem(
                order_name=name,
                shopify_order_id=header.get("Id"),
                line_number=line_number,
                email=_blank(row.get("Email")) or header.get("Email"),
                financial_status="paid",
                paid_at=_parse_datetime(header.get("Paid at")),
                created_at_shopify=_parse_datetime(row.get("Created at")),
                order_total_brl=_parse_decimal(header.get("Total")),
                order_subtotal_brl=_parse_decimal(header.get("Subtotal")),
                discount_code=header.get("Discount Code"),
                discount_amount_brl=_parse_decimal(header.get("Discount Amount")),
                shipping_method=header.get("Shipping Method"),
                billing_province=header.get("Billing Province Name"),
                lineitem_quantity=_parse_int(row.get("Lineitem quantity")) or 0,
                lineitem_name=row.get("Lineitem name") or "",
                lineitem_price=_parse_decimal(row.get("Lineitem price")) or Decimal("0"),
                lineitem_sku=_blank(row.get("Lineitem sku")),
            )
        except ValidationError as e:
            skipped_invalid += 1
            logger.warning({"event": "order_history_row_invalid", "order_name": name, "line_number": line_number, "error": str(e)})
            continue

        items.append(item)

    return items, skipped_not_paid, skipped_invalid


def iter_zip_csv_readers(folder: Path):
    for zip_path in sorted(folder.glob("*.zip")):
        with zipfile.ZipFile(zip_path) as zf:
            csv_names = [n for n in zf.namelist() if n.endswith(".csv")]
            for csv_name in csv_names:
                with zf.open(csv_name) as raw:
                    text = io.TextIOWrapper(raw, encoding="utf-8")
                    yield zip_path.name, csv.DictReader(text)


def run(folder: Path, dry_run: bool) -> None:
    sb = None if dry_run else get_supabase_client()

    total_loaded = 0
    total_not_paid = 0
    total_invalid = 0
    total_files = 0

    for zip_name, reader in iter_zip_csv_readers(folder):
        items, skipped_not_paid, skipped_invalid = parse_csv_rows(reader)
        total_not_paid += skipped_not_paid
        total_invalid += skipped_invalid
        total_files += 1

        if dry_run:
            logger.info({"event": "dry_run_file_parsed", "file": zip_name, "valid_items": len(items), "skipped_not_paid": skipped_not_paid, "skipped_invalid": skipped_invalid})
        else:
            written = upsert_order_history_items(sb, items)
            total_loaded += written
            logger.info({"event": "file_loaded", "file": zip_name, "written": written, "skipped_not_paid": skipped_not_paid, "skipped_invalid": skipped_invalid})

    logger.info({
        "event": "order_history_backfill_done",
        "files": total_files,
        "loaded": total_loaded,
        "skipped_not_paid": total_not_paid,
        "skipped_invalid": total_invalid,
        "dry_run": dry_run,
    })


if __name__ == "__main__":
    load_dotenv()
    parser = argparse.ArgumentParser(description="Backfill de fact_order_history_items a partir do export manual do Shopify")
    parser.add_argument("--folder", default="Todos os pedidos Minimal", help="Pasta com os arquivos .zip exportados do Shopify")
    parser.add_argument("--dry-run", action="store_true", help="Só parseia e reporta contagens, sem gravar no Supabase")
    args = parser.parse_args()

    run(Path(args.folder), args.dry_run)
