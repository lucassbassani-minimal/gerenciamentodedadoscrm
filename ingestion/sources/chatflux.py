"""Ingestão de eventos de disparo/resposta do Chatflux (WhatsApp) via API própria."""

import logging
import os
import time
from datetime import date, timedelta

import httpx
from dotenv import load_dotenv
from pydantic import ValidationError

from ingestion.models.chatflux_models import ChatfluxEvento

load_dotenv()
logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://minimal-disparos-production-b9a1.up.railway.app"
PAGE_LIMIT = 5000
MAX_RETRIES = 6


def _get(client: httpx.Client, params: dict) -> dict:
    for attempt in range(MAX_RETRIES):
        try:
            resp = client.get("/api/eventos", params=params)
        except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.TimeoutException):
            wait = 2 ** (attempt + 1)
            logger.warning({"event": "chatflux_timeout_retry", "attempt": attempt + 1, "wait_secs": wait})
            time.sleep(wait)
            continue
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 2 ** (attempt + 1)))
            logger.warning({"event": "chatflux_rate_limit", "wait_secs": retry_after})
            time.sleep(retry_after)
            continue
        if resp.status_code >= 400:
            logger.error({"event": "chatflux_error", "status": resp.status_code, "body": resp.text[:500]})
        resp.raise_for_status()
        return resp.json()
    raise RuntimeError(f"Max retries exceeded: GET /api/eventos {params}")


def fetch_chatflux_eventos_since(start_date: date, end_date: date) -> list[ChatfluxEvento]:
    token = os.environ["CHATFLUX_API_TOKEN"]
    base_url = os.environ.get("CHATFLUX_API_BASE_URL", DEFAULT_BASE_URL)

    logger.info({
        "event": "chatflux_fetch_start",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    })

    rows: list[ChatfluxEvento] = []
    skipped = 0
    offset = 0

    with httpx.Client(base_url=base_url, headers={"Authorization": f"Bearer {token}"}, timeout=60.0) as client:
        while True:
            payload = _get(client, {
                "startDate": start_date.isoformat(),
                "endDate": end_date.isoformat(),
                "segment": "todos",
                "etapa": "todas",
                "format": "json",
                "limit": PAGE_LIMIT,
                "offset": offset,
            })
            events = payload.get("events", [])

            for raw in events:
                try:
                    rows.append(ChatfluxEvento.model_validate(raw))
                except ValidationError as e:
                    logger.warning({"event": "chatflux_parse_error", "row": raw, "error": str(e)})
                    skipped += 1

            if len(events) < PAGE_LIMIT:
                break
            offset += PAGE_LIMIT

    logger.info({"event": "chatflux_fetch_done", "rows": len(rows), "skipped": skipped})
    return rows


def run_chatflux_ingestion(days_back: int = 3) -> int:
    from ingestion.db.client import get_supabase_client
    from ingestion.db.writers import upsert_chatflux_events

    end_date = date.today()
    start_date = end_date - timedelta(days=days_back)
    rows = fetch_chatflux_eventos_since(start_date, end_date)
    sb = get_supabase_client()
    return upsert_chatflux_events(sb, rows)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    total = run_chatflux_ingestion()
    print(f"{total} eventos Chatflux upsertados.")
