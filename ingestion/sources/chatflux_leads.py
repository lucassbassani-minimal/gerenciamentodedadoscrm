"""Ingestão dos totais diários de leads por vendedor do Chatflux (/api/leads).

A API não marca o segmento por linha na resposta — é preciso chamar uma vez por
segmento (novos/recorrentes/carrinho) e rotular manualmente."""

import logging
import os
import time
from datetime import date, timedelta

import httpx
from dotenv import load_dotenv
from pydantic import ValidationError

from ingestion.models.chatflux_leads_models import ChatfluxLeadDiario

load_dotenv()
logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://minimal-disparos-production-b9a1.up.railway.app"
MAX_RETRIES = 6

SEGMENT_PARAM_TO_LABEL: dict[str, str] = {
    "novos": "Welcome Novos",
    "recorrentes": "Welcome Recorrentes",
    "carrinho": "Carrinho Abandonado",
}


def _get(client: httpx.Client, params: dict) -> dict:
    for attempt in range(MAX_RETRIES):
        try:
            resp = client.get("/api/leads", params=params)
        except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.TimeoutException):
            wait = 2 ** (attempt + 1)
            logger.warning({"event": "chatflux_leads_timeout_retry", "attempt": attempt + 1, "wait_secs": wait})
            time.sleep(wait)
            continue
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 2 ** (attempt + 1)))
            logger.warning({"event": "chatflux_leads_rate_limit", "wait_secs": retry_after})
            time.sleep(retry_after)
            continue
        if resp.status_code >= 400:
            logger.error({"event": "chatflux_leads_error", "status": resp.status_code, "body": resp.text[:500]})
        resp.raise_for_status()
        return resp.json()
    raise RuntimeError(f"Max retries exceeded: GET /api/leads {params}")


def _fetch_segment(client: httpx.Client, start_date: date, end_date: date, segment_param: str) -> list[ChatfluxLeadDiario]:
    segmento_label = SEGMENT_PARAM_TO_LABEL[segment_param]
    payload = _get(client, {
        "startDate": start_date.isoformat(),
        "endDate": end_date.isoformat(),
        "segment": segment_param,
    })

    vendedor_id_by_nome = {
        v["vendedor_nome"]: v.get("vendedor_id")
        for v in payload.get("byVendor", [])
    }

    rows: list[ChatfluxLeadDiario] = []
    for raw in payload.get("daily", []):
        try:
            rows.append(ChatfluxLeadDiario(
                day=raw["day"],
                segmento=segmento_label,
                vendedor_id=vendedor_id_by_nome.get(raw.get("vendedor_nome")),
                vendedor_nome=raw.get("vendedor_nome"),
                total_leads=raw.get("total"),
            ))
        except ValidationError as e:
            logger.warning({"event": "chatflux_leads_parse_error", "row": raw, "error": str(e)})
    return rows


def fetch_chatflux_leads_since(start_date: date, end_date: date) -> list[ChatfluxLeadDiario]:
    token = os.environ["CHATFLUX_API_TOKEN"]
    base_url = os.environ.get("CHATFLUX_API_BASE_URL", DEFAULT_BASE_URL)

    logger.info({
        "event": "chatflux_leads_fetch_start",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    })

    rows: list[ChatfluxLeadDiario] = []
    with httpx.Client(base_url=base_url, headers={"Authorization": f"Bearer {token}"}, timeout=60.0) as client:
        for segment_param in SEGMENT_PARAM_TO_LABEL:
            rows.extend(_fetch_segment(client, start_date, end_date, segment_param))

    logger.info({"event": "chatflux_leads_fetch_done", "rows": len(rows)})
    return rows


def run_chatflux_leads_ingestion(days_back: int = 3) -> int:
    from ingestion.db.client import get_supabase_client
    from ingestion.db.writers import upsert_chatflux_leads_diario

    end_date = date.today()
    start_date = end_date - timedelta(days=days_back)
    rows = fetch_chatflux_leads_since(start_date, end_date)
    sb = get_supabase_client()
    return upsert_chatflux_leads_diario(sb, rows)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    total = run_chatflux_leads_ingestion()
    print(f"{total} linhas de leads diários do Chatflux upsertadas.")
