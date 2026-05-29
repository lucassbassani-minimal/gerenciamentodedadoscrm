import os
import time
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import httpx

from ingestion.models.klaviyo_models import KlaviyoCampaignEmailMetric

logger = logging.getLogger(__name__)

BASE_URL = "https://a.klaviyo.com/api"
REVISION = "2024-10-15"
MAX_RETRIES = 6
GET_THROTTLE_SECS = 0.2
METRIC_THROTTLE_SECS = 2.0  # mesmo intervalo do N8N para evitar rate limit em aggregates

CAMPAIGN_METRIC_WINDOW_DAYS = 7

# Coluna do banco → nome do evento no Klaviyo
CAMPAIGN_METRIC_MAP: dict[str, str] = {
    "email_enviado": "Received Email",
    "email_aberto":  "Opened Email",
    "email_clicado": "Clicked Email",
}


@dataclass
class _CampaignInfo:
    campaign_id: str
    campaign_name: str
    message_id: str   # campaign-message ID (primeiro e-mail da campanha)
    send_time: date | None


def make_client() -> httpx.Client:
    key = os.environ["KLAVIYO_PRIVATE_API_KEY"]
    return httpx.Client(
        base_url=BASE_URL,
        headers={"Authorization": f"Klaviyo-API-Key {key}", "revision": REVISION},
        timeout=60.0,
    )


def _get(client: httpx.Client, path: str, params: dict | None = None) -> dict:
    time.sleep(GET_THROTTLE_SECS)
    for attempt in range(MAX_RETRIES):
        try:
            resp = client.get(path, params=params)
        except (httpx.ReadTimeout, httpx.ConnectTimeout):
            wait = 2 ** (attempt + 1)
            logger.warning({"event": "timeout_retry", "path": path, "wait_secs": wait})
            time.sleep(wait)
            continue
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 2 ** (attempt + 1)))
            logger.warning({"event": "rate_limit", "path": path, "wait_secs": retry_after})
            time.sleep(retry_after)
            continue
        resp.raise_for_status()
        return resp.json()
    raise RuntimeError(f"Max retries exceeded: GET {path}")


def _post_aggregate(client: httpx.Client, body: dict) -> dict:
    time.sleep(METRIC_THROTTLE_SECS)
    for attempt in range(MAX_RETRIES):
        try:
            resp = client.post("/metric-aggregates/", json=body)
        except (httpx.ReadTimeout, httpx.ConnectTimeout):
            wait = 2 ** (attempt + 1)
            logger.warning({"event": "timeout_retry_post", "wait_secs": wait})
            time.sleep(wait)
            continue
        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", 2 ** attempt))
            logger.warning({"event": "rate_limit_post", "wait_secs": wait})
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()
    raise RuntimeError("Max retries exceeded: POST /metric-aggregates/")


def _paginate(client: httpx.Client, path: str, params: dict) -> list[dict]:
    result: list[dict] = []
    body = _get(client, path, params)
    result.extend(body.get("data", []))
    next_url = (body.get("links") or {}).get("next")
    while next_url:
        body = _get(client, next_url)
        result.extend(body.get("data", []))
        next_url = (body.get("links") or {}).get("next")
    return result


def _fetch_metric_ids(client: httpx.Client) -> dict[str, str]:
    """Retorna {nome_do_evento: metric_id} para as métricas de campanha."""
    target_names = set(CAMPAIGN_METRIC_MAP.values())
    mapping: dict[str, str] = {}
    for item in _paginate(client, "/metrics/", {"fields[metric]": "name"}):
        name = item["attributes"].get("name", "")
        if name in target_names:
            mapping[name] = item["id"]
    missing = target_names - set(mapping.keys())
    if missing:
        logger.warning({"event": "metrics_not_found", "missing": list(missing)})
    return mapping


def _fetch_campaigns(client: httpx.Client, since: date) -> list[_CampaignInfo]:
    since_iso = f"{since.isoformat()}T00:00:00+00:00"
    items = _paginate(client, "/campaigns/", {
        "fields[campaign]": "name,status,created_at,send_time",
        "filter": f"and(equals(messages.channel,'email'),greater-or-equal(scheduled_at,{since_iso}))",
    })
    result = []
    for item in items:
        a = item["attributes"]
        rel = item.get("relationships", {})
        messages_data = rel.get("campaign-messages", {}).get("data", [])
        # Usa o campaign-message ID como chave de upsert (igual ao N8N); fallback para campaign_id
        message_id = messages_data[0]["id"] if messages_data else item["id"]
        raw_send_time = a.get("send_time")
        send_date: date | None = None
        if raw_send_time:
            send_date = datetime.fromisoformat(raw_send_time).astimezone(timezone.utc).date()
        result.append(_CampaignInfo(
            campaign_id=item["id"],
            campaign_name=a["name"],
            message_id=message_id,
            send_time=send_date,
        ))
    logger.info({"event": "campaigns_fetched", "count": len(result), "since": since.isoformat()})
    return result


def _aggregate_for_campaign(
    client: httpx.Client,
    metric_id: str,
    campaign_id: str,
    date_from: date,
    date_to: date,
) -> dict[str, int]:
    """Retorna {date_iso: count} para uma métrica de uma campanha específica."""
    body = {"data": {"type": "metric-aggregate", "attributes": {
        "metric_id": metric_id,
        "measurements": ["count"],
        "interval": "day",
        "page_size": 500,
        "filter": (
            f"and("
            f"greater-or-equal(datetime,{date_from.isoformat()}T00:00:00+00:00),"
            f"less-than(datetime,{(date_to + timedelta(days=1)).isoformat()}T00:00:00+00:00),"
            f"equals($message,\"{campaign_id}\")"
            f")"
        ),
    }}}
    resp = _post_aggregate(client, body)
    attrs = resp["data"]["attributes"]
    raw_dates: list[str] = attrs.get("dates", [])
    date_strs = [d[:10] for d in raw_dates]
    counts: dict[str, int] = {}
    for row in attrs.get("data", []):
        for i, count in enumerate(row["measurements"].get("count", [])):
            if count and i < len(date_strs):
                counts[date_strs[i]] = int(count)
    return counts


def fetch_campaign_email_metrics(
    client: httpx.Client,
    date_from: date,
    date_to: date,
) -> list[KlaviyoCampaignEmailMetric]:
    """Busca métricas de campanhas de e-mail para o período [date_from, date_to].

    Cada campanha usa uma janela de 7 dias a partir do send_time — métricas
    fora dessa janela são descartadas (padrão do N8N original).
    """
    # Busca campanhas agendadas no período + buffer da janela de métricas
    lookback_since = date_from - timedelta(days=CAMPAIGN_METRIC_WINDOW_DAYS)
    campaigns = _fetch_campaigns(client, lookback_since)
    if not campaigns:
        return []

    metric_ids = _fetch_metric_ids(client)
    rows: dict[tuple[str, str], dict] = {}  # (message_id, date_str) → row

    for campaign in campaigns:
        # Determina janela válida para esta campanha
        if campaign.send_time:
            window_from = max(date_from, campaign.send_time)
            window_to = min(date_to, campaign.send_time + timedelta(days=CAMPAIGN_METRIC_WINDOW_DAYS))
            if window_from > window_to:
                continue  # campanha fora do período solicitado
        else:
            window_from, window_to = date_from, date_to

        for col_name, metric_name in CAMPAIGN_METRIC_MAP.items():
            metric_id = metric_ids.get(metric_name)
            if not metric_id:
                continue

            counts = _aggregate_for_campaign(
                client, metric_id, campaign.campaign_id, window_from, window_to
            )
            for date_str, count in counts.items():
                if count == 0:
                    continue
                key = (campaign.message_id, date_str)
                if key not in rows:
                    rows[key] = {
                        "campaign_id":   campaign.campaign_id,
                        "campaign_name": campaign.campaign_name,
                        "message_id":    campaign.message_id,
                        "data":          date.fromisoformat(date_str),
                        "email_enviado": 0,
                        "email_aberto":  0,
                        "email_clicado": 0,
                    }
                rows[key][col_name] = count

        logger.info({
            "event": "campaign_processed",
            "campaign_id": campaign.campaign_id,
            "name": campaign.campaign_name,
            "window": f"{window_from} -> {window_to}",
        })

    result = [KlaviyoCampaignEmailMetric.model_validate(r) for r in rows.values()]
    logger.info({"event": "campaign_metrics_done", "rows": len(result)})
    return result
