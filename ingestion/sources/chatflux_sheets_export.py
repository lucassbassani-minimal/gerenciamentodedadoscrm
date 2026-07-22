"""Exporta fact_chatflux_events + fact_chatflux_leads_diario (Supabase) para a aba
"Base de Dados ChatFlux" da planilha Google Sheets (mesma planilha do Vekta,
GOOGLE_SHEETS_LEADS_SPREADSHEET_ID), espelhando as colunas de 'Página1' (Vekta).

Segurança: só escreve na aba cujo nome contenha "chatflux" — nunca em 'Página1'
ou 'Necessita atenção'. Se o nome não bater, aborta sem escrever nada."""

import json
import logging
import os

import gspread
from dotenv import load_dotenv

from ingestion.db.client import get_supabase_client

load_dotenv()
logger = logging.getLogger(__name__)

WORKSHEET_NAME = "Base de Dados ChatFlux"
HEADERS = ["Data", "Telefone", "Origem", "Funil", "Vendedor"]
BATCH_SIZE = 1000


def _get_worksheet() -> gspread.Worksheet:
    spreadsheet_id = os.environ["GOOGLE_SHEETS_LEADS_SPREADSHEET_ID"]

    json_env = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if json_env:
        gc = gspread.service_account_from_dict(json.loads(json_env))
    else:
        json_path = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON_PATH"]
        gc = gspread.service_account(filename=json_path)

    ws = gc.open_by_key(spreadsheet_id).worksheet(WORKSHEET_NAME)
    if "chatflux" not in ws.title.lower():
        raise RuntimeError(
            f"Trava de segurança: aba resolvida foi '{ws.title}', esperado nome contendo 'chatflux'. "
            "Abortando sem escrever para não arriscar sobrescrever outra aba da planilha."
        )
    return ws


def _fetch_events(sb) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        resp = (
            sb.table("fact_chatflux_events")
            .select("event_timestamp,telefone,segmento,etapa")
            .order("event_timestamp", desc=False)
            .range(offset, offset + BATCH_SIZE - 1)
            .execute()
        )
        batch = resp.data or []
        rows.extend(batch)
        if len(batch) < BATCH_SIZE:
            break
        offset += BATCH_SIZE
    return [
        [
            (r["event_timestamp"] or "")[:19].replace("T", " "),
            r["telefone"] or "",
            r["segmento"] or "",
            r["etapa"] or "",
            "",
        ]
        for r in rows
    ]


def _fetch_leads_diario(sb) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        resp = (
            sb.table("fact_chatflux_leads_diario")
            .select("day,segmento,vendedor_nome,total_leads")
            .order("day", desc=False)
            .range(offset, offset + BATCH_SIZE - 1)
            .execute()
        )
        batch = resp.data or []
        rows.extend(batch)
        if len(batch) < BATCH_SIZE:
            break
        offset += BATCH_SIZE

    expanded: list[list[str]] = []
    for r in rows:
        line = [f"{r['day']} 00:00:00", "", r["segmento"] or "", "necessita atenção", r["vendedor_nome"] or ""]
        expanded.extend([line] * int(r["total_leads"]))
    return expanded


def export_chatflux_to_sheets() -> int:
    sb = get_supabase_client()
    values = _fetch_events(sb) + _fetch_leads_diario(sb)
    values.sort(key=lambda row: row[0])

    ws = _get_worksheet()
    ws.clear()
    ws.update([HEADERS] + values, "A1")

    logger.info({"event": "chatflux_sheets_exported", "rows": len(values)})
    return len(values)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    total = export_chatflux_to_sheets()
    print(f"{total} linhas exportadas para a aba '{WORKSHEET_NAME}'.")
