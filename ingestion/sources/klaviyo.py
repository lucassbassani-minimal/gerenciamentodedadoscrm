import os
import time
import logging
from datetime import date
from typing import Generator

import httpx

from ingestion.models.klaviyo_models import (
    KlaviyoFlow,
    KlaviyoFlowMessage,
    KlaviyoCampaign,
    KlaviyoCampaignMessage,
    KlaviyoEmailMetricRow,
    KlaviyoForm,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://a.klaviyo.com/api"
REVISION = "2024-10-15"
MAX_RETRIES = 6
REQUEST_THROTTLE_SECS = 0.15  # pausa entre requisições para evitar rate limit

# Nomes exatos dos eventos de e-mail no Klaviyo
METRIC_FIELDS: dict[str, str] = {
    "sends": "Received Email",
    "opens": "Opened Email",
    "clicks": "Clicked Email",
    "bounces": "Bounced Email",
    "spam_complaints": "Marked Email as Spam",
    "unsubscribes": "Unsubscribed from Email Marketing",
}

# Tipos de ação de fluxo que representam envio de e-mail
EMAIL_ACTION_TYPES = {"SEND_EMAIL", "EMAIL"}

# Mapeamento de form_type do Klaviyo para o schema do banco
FORM_TYPE_MAP: dict[str, str] = {
    "POPUP": "popup",
    "FLYOUT": "popup",
    "EMBED": "embed",
    "FULL_PAGE": "form",
}


def make_client() -> httpx.Client:
    key = os.environ["KLAVIYO_PRIVATE_API_KEY"]
    return httpx.Client(
        base_url=BASE_URL,
        headers={"Authorization": f"Klaviyo-API-Key {key}", "revision": REVISION},
        timeout=30.0,
    )


def _get(client: httpx.Client, path: str, params: dict | None = None) -> dict:
    time.sleep(REQUEST_THROTTLE_SECS)
    for attempt in range(MAX_RETRIES):
        resp = client.get(path, params=params)
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 2 ** (attempt + 1)))
            logger.warning({"event": "rate_limit", "path": path, "wait_secs": retry_after})
            time.sleep(retry_after)
            continue
        if resp.status_code >= 400:
            logger.error({"event": "klaviyo_error", "status": resp.status_code, "body": resp.text[:500]})
        resp.raise_for_status()
        return resp.json()
    raise RuntimeError(f"Max retries exceeded: GET {path}")


def _post(client: httpx.Client, path: str, body: dict) -> dict:
    for attempt in range(MAX_RETRIES):
        resp = client.post(path, json=body)
        if resp.status_code == 429:
            wait = 2 ** attempt
            logger.warning({"event": "rate_limit_post", "path": path, "wait_secs": wait})
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()
    raise RuntimeError(f"Max retries exceeded: POST {path}")


def _paginate(client: httpx.Client, path: str, params: dict) -> Generator[dict, None, None]:
    body = _get(client, path, params)
    yield from body.get("data", [])
    next_url = (body.get("links") or {}).get("next")
    while next_url:
        # next_url é a URL completa retornada pelo Klaviyo
        body = _get(client, next_url)
        yield from body.get("data", [])
        next_url = (body.get("links") or {}).get("next")


def fetch_flows(client: httpx.Client) -> list[KlaviyoFlow]:
    logger.info("klaviyo: buscando fluxos")
    result = []
    for item in _paginate(client, "/flows/", {
        "fields[flow]": "name,status,trigger_type,created,updated",
        "filter": "equals(archived,false)",
        "page[size]": "50",
    }):
        a = item["attributes"]
        result.append(KlaviyoFlow.model_validate({
            "id": item["id"],
            "name": a["name"],
            "status": a["status"],
            "trigger_type": a.get("trigger_type") or "Unconfigured",
            "created": a["created"],
            "updated": a["updated"],
        }))
    logger.info({"event": "flows_fetched", "count": len(result)})
    return result


def fetch_flow_messages(client: httpx.Client, flow_id: str) -> list[KlaviyoFlowMessage]:
    messages = []
    email_pos = 0
    for action in _paginate(client, f"/flows/{flow_id}/flow-actions/", {
        "fields[flow-action]": "action_type",
    }):
        if action["attributes"].get("action_type") not in EMAIL_ACTION_TYPES:
            continue
        email_pos += 1
        for item in _paginate(client, f"/flow-actions/{action['id']}/flow-messages/", {
            "fields[flow-message]": "name,created,updated",
        }):
            a = item["attributes"]
            messages.append(KlaviyoFlowMessage.model_validate({
                "id": item["id"],
                "flow_id": flow_id,
                "name": a.get("name") or f"Email {email_pos}",
                "position": email_pos,
                "created": a["created"],
                "updated": a["updated"],
            }))
    return messages


def fetch_campaigns(client: httpx.Client) -> list[KlaviyoCampaign]:
    logger.info("klaviyo: buscando campanhas")
    result = []
    for item in _paginate(client, "/campaigns/", {
        "fields[campaign]": "name,status,created_at,send_time",
        "filter": "equals(messages.channel,'email'),equals(archived,false)",
    }):
        a = item["attributes"]
        result.append(KlaviyoCampaign.model_validate({
            "id": item["id"],
            "name": a["name"],
            "status": a["status"],
            "created_at": a["created_at"],
            "send_time": a.get("send_time"),
        }))
    logger.info({"event": "campaigns_fetched", "count": len(result)})
    return result


def fetch_campaign_messages(client: httpx.Client, campaign_id: str) -> list[KlaviyoCampaignMessage]:
    result = []
    for item in _paginate(client, f"/campaigns/{campaign_id}/campaign-messages/", {
        "fields[campaign-message]": "label,created_at,updated_at",
    }):
        a = item["attributes"]
        result.append(KlaviyoCampaignMessage.model_validate({
            "id": item["id"],
            "campaign_id": campaign_id,
            "label": a.get("label") or "Campaign Email",
            "created_at": a["created_at"],
            "updated_at": a["updated_at"],
        }))
    return result


def _fetch_metric_ids(client: httpx.Client) -> dict[str, str]:
    target_names = set(METRIC_FIELDS.values())
    mapping: dict[str, str] = {}
    for item in _paginate(client, "/metrics/", {"fields[metric]": "name"}):
        name = item["attributes"].get("name", "")
        if name in target_names:
            mapping[name] = item["id"]
    return mapping


def _aggregate_metric(client: httpx.Client, metric_id: str, since: date) -> dict[tuple[str, str], int]:
    """Retorna {(message_id, date_iso): count} para um único tipo de evento."""
    until = date.today()
    body = {"data": {"type": "metric-aggregate", "attributes": {
        "metric_id": metric_id,
        "measurements": ["count"],
        "interval": "day",
        "page_size": 500,
        "filter": [
            f"greater-or-equal(datetime,{since.isoformat()}T00:00:00+00:00)",
            f"less-than(datetime,{until.isoformat()}T23:59:59+00:00)",
        ],
        "by": ["$message"],
    }}}
    result = _post(client, "/metric-aggregates/", body)
    counts: dict[tuple[str, str], int] = {}
    attrs = result["data"]["attributes"]
    # dates vêm como "2026-05-12T00:00:00+00:00" — extraímos só a data
    raw_dates: list[str] = attrs.get("dates", [])
    date_strs = [d[:10] for d in raw_dates]
    for row in attrs.get("data", []):
        msg_id = row["dimensions"][0]
        for i, count in enumerate(row["measurements"].get("count", [])):
            if count and i < len(date_strs):
                counts[(msg_id, date_strs[i])] = int(count)
    return counts


def fetch_email_metrics_since(client: httpx.Client, since: date) -> list[KlaviyoEmailMetricRow]:
    logger.info({"event": "email_metrics_start", "since": since.isoformat()})
    metric_ids = _fetch_metric_ids(client)
    rows: dict[tuple[str, str], KlaviyoEmailMetricRow] = {}

    for field, metric_name in METRIC_FIELDS.items():
        metric_id = metric_ids.get(metric_name)
        if not metric_id:
            logger.warning({"event": "metric_not_found", "metric_name": metric_name})
            continue
        counts = _aggregate_metric(client, metric_id, since)
        for (msg_id, date_str), count in counts.items():
            key = (msg_id, date_str)
            if key not in rows:
                rows[key] = KlaviyoEmailMetricRow(
                    message_id=msg_id, date=date.fromisoformat(date_str)
                )
            setattr(rows[key], field, count)

    result = list(rows.values())
    logger.info({"event": "email_metrics_fetched", "rows": len(result)})
    return result


def fetch_forms(client: httpx.Client) -> list[KlaviyoForm]:
    logger.info("klaviyo: buscando formulários")
    result = []
    for item in _paginate(client, "/forms/", {
        "fields[form]": "name,status,archived,form_type,created,updated",
    }):
        a = item["attributes"]
        if a.get("archived"):
            continue
        result.append(KlaviyoForm.model_validate({
            "id": item["id"],
            "name": a["name"],
            "status": a.get("status", "active"),
            "form_type": FORM_TYPE_MAP.get((a.get("form_type") or "POPUP").upper(), "form"),
            "created": a["created"],
            "updated": a["updated"],
        }))
    logger.info({"event": "forms_fetched", "count": len(result)})
    return result


def fetch_active_base_count(client: httpx.Client) -> int:
    segment_id = os.environ.get("KLAVIYO_SEGMENT_ENGAGED_90D", "")
    if not segment_id:
        logger.warning("KLAVIYO_SEGMENT_ENGAGED_90D não configurado — active_base_count = 0")
        return 0
    body = _get(client, f"/segments/{segment_id}/", {
        "additional-fields[segment]": "profile_count",
    })
    count = body["data"]["attributes"].get("profile_count", 0)
    logger.info({"event": "active_base_fetched", "count": count})
    return count
