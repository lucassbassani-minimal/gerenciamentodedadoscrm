"""Exporta leads_webhook do Supabase para Google Sheets (atualização horária)."""

import json
import logging
import os

import gspread
from dotenv import load_dotenv

from ingestion.db.client import get_supabase_client

load_dotenv()
logger = logging.getLogger(__name__)

CUTOFF_DATE = "2026-06-12"
HEADERS = ["Data", "Telefone", "Origem", "Funil", "Vendedor"]


def _get_worksheet() -> gspread.Worksheet:
    spreadsheet_id = os.environ["GOOGLE_SHEETS_LEADS_SPREADSHEET_ID"]

    # Vercel: conteúdo do JSON como variável de ambiente
    # Local: caminho para o arquivo JSON
    json_env = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if json_env:
        gc = gspread.service_account_from_dict(json.loads(json_env))
    else:
        json_path = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON_PATH"]
        gc = gspread.service_account(filename=json_path)

    return gc.open_by_key(spreadsheet_id).get_worksheet(0)


BATCH_SIZE = 1000


def _fetch_all_leads(sb) -> list:
    all_rows: list = []
    offset = 0
    while True:
        resp = (
            sb.table("leads_webhook")
            .select("data,telefone,origem,funil,nome_do_vendedor")
            .gte("data", CUTOFF_DATE)
            .order("data", desc=False)
            .range(offset, offset + BATCH_SIZE - 1)
            .execute()
        )
        batch = resp.data or []
        all_rows.extend(batch)
        if len(batch) < BATCH_SIZE:
            break
        offset += BATCH_SIZE
    return all_rows


def export_leads_to_sheets() -> int:
    sb = get_supabase_client()
    rows = _fetch_all_leads(sb)

    values = [HEADERS] + [
        [
            (r.get("data") or "")[:19].replace("T", " "),
            r.get("telefone") or "",
            r.get("origem") or "",
            r.get("funil") or "",
            r.get("nome_do_vendedor") or "",
        ]
        for r in rows
    ]

    ws = _get_worksheet()
    ws.clear()
    ws.update(values, "A1")

    logger.info({"event": "leads_sheets_exported", "rows": len(rows)})
    return len(rows)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    total = export_leads_to_sheets()
    print(f"{total} leads exportados para o Sheets.")
