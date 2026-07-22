"""Lê a aba "Base de Dados" da planilha de recompra (atualizada de madrugada por
BigQuery Connected Sheet) e retorna as linhas validadas para fact_repurchase_deals
(source='sheets_diario').

Mesmas regras do backfill histórico (Instrução — Gerar Tabela de Coortes de Recompra):
mantém somente etapa_do_negocio in {"Shipped", "Negócio Fechado - Comercial"}, descarta
linhas sem e-mail ou sem valor. Formato de data/decimal aqui é BR (DD/MM/YYYY, "1.234,56"),
diferente do export histórico em CSV (ISO, decimal com ponto).
"""

import json
import logging
import os
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import gspread

from ingestion.models.repurchase_deals_models import RepurchaseDealRow

logger = logging.getLogger(__name__)

VALID_STAGES = {"Shipped", "Negócio Fechado - Comercial"}
_TIPO_TO_IS_FIRST = {"Primeira Compra": True, "Recompra": False}

WORKSHEET_NAME = "Base de Dados"


def _get_worksheet() -> gspread.Worksheet:
    spreadsheet_id = os.environ["GOOGLE_SHEETS_REPURCHASE_SPREADSHEET_ID"]

    json_env = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if json_env:
        gc = gspread.service_account_from_dict(json.loads(json_env))
    else:
        json_path = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON_PATH"]
        gc = gspread.service_account(filename=json_path)

    return gc.open_by_key(spreadsheet_id).worksheet(WORKSHEET_NAME)


def _parse_date_br(raw: str) -> "datetime.date | None":
    try:
        return datetime.strptime(raw.strip(), "%d/%m/%Y").date()
    except (ValueError, AttributeError):
        return None


def _parse_valor_br(raw: str) -> Decimal | None:
    try:
        normalized = raw.strip().replace(".", "").replace(",", ".")
        return Decimal(normalized)
    except (InvalidOperation, AttributeError):
        return None


def fetch_repurchase_deals_diario(
    since_date: date | None = None,
) -> tuple[list[RepurchaseDealRow], int, dict[str, int]]:
    """since_date: se informado, descarta linhas com data_de_fechamento anterior
    a essa data — usado para carregar só a janela recente (última data já
    ingerida no banco em diante) em vez da planilha inteira a cada execução."""
    ws = _get_worksheet()
    values = ws.get_all_values()
    if not values:
        return [], 0, {}

    header, data_rows = values[0], values[1:]
    idx = {name: i for i, name in enumerate(header)}

    rows: list[RepurchaseDealRow] = []
    skipped_reasons: dict[str, int] = {"etapa_fora_escopo": 0, "sem_email": 0, "sem_valor": 0, "data_invalida": 0, "fora_da_janela": 0, "validacao": 0}

    for raw_row in data_rows:
        etapa = raw_row[idx["etapa_do_negocio"]].strip()
        if etapa not in VALID_STAGES:
            skipped_reasons["etapa_fora_escopo"] += 1
            continue

        email = raw_row[idx["e_mail"]].strip().lower()
        if not email:
            skipped_reasons["sem_email"] += 1
            continue

        valor = _parse_valor_br(raw_row[idx["valor"]])
        if valor is None:
            skipped_reasons["sem_valor"] += 1
            continue

        closed_at = _parse_date_br(raw_row[idx["data_de_fechamento"]])
        if closed_at is None:
            skipped_reasons["data_invalida"] += 1
            continue

        if since_date is not None and closed_at < since_date:
            skipped_reasons["fora_da_janela"] += 1
            continue

        first_purchase_raw = _parse_date_br(raw_row[idx["data_primeira_compra"]])
        is_first = _TIPO_TO_IS_FIRST.get(raw_row[idx["tipo_de_venda"]].strip())

        try:
            rows.append(RepurchaseDealRow(
                email=email,
                closed_at=closed_at,
                amount_brl=valor,
                is_first_purchase=is_first,
                deal_stage=etapa,
                first_purchase_date_raw=first_purchase_raw,
                source="sheets_diario",
            ))
        except Exception as e:
            skipped_reasons["validacao"] += 1
            logger.warning({"event": "repurchase_deal_diario_row_invalid", "error": str(e)})

    total_skipped = sum(skipped_reasons.values())
    logger.info({
        "event": "repurchase_deals_diario_parsed",
        "valid_rows": len(rows),
        "skipped": total_skipped,
        "reasons": skipped_reasons,
    })
    return rows, total_skipped, skipped_reasons
