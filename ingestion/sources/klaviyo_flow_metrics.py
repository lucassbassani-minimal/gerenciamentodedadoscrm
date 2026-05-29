import os
import time
import logging
from dataclasses import dataclass, field
from datetime import date, timedelta

import httpx

from ingestion.models.klaviyo_models import KlaviyoFlowEmailMetric

logger = logging.getLogger(__name__)

BASE_URL = "https://a.klaviyo.com/api"
REVISION = "2024-10-15"
MAX_RETRIES = 6
GET_THROTTLE_SECS = 0.2
METRIC_THROTTLE_SECS = 2.0  # mesmo intervalo do N8N

# Coluna do banco -> nome do evento no Klaviyo
FLOW_METRIC_MAP: dict[str, str] = {
    "email_enviado": "Received Email",
    "email_aberto":  "Opened Email",
    "email_clicado": "Clicked Email",
}


@dataclass
class _FlowMessage:
    flow_id: str
    flow_name: str
    message_id: str
    message_name: str


@dataclass
class _FlowInfo:
    flow_id: str
    flow_name: str
    messages: list[_FlowMessage] = field(default_factory=list)


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
    target_names = set(FLOW_METRIC_MAP.values())
    mapping: dict[str, str] = {}
    for item in _paginate(client, "/metrics/", {"fields[metric]": "name"}):
        name = item["attributes"].get("name", "")
        if name in target_names:
            mapping[name] = item["id"]
    missing = target_names - set(mapping.keys())
    if missing:
        logger.warning({"event": "metrics_not_found", "missing": list(missing)})
    return mapping


def _fetch_active_flows(client: httpx.Client) -> list[_FlowInfo]:
    items = _paginate(client, "/flows/", {
        "fields[flow]": "name,status",
        "filter": "and(equals(status,'live'),equals(archived,false))",
    })
    flows = []
    for item in items:
        flows.append(_FlowInfo(
            flow_id=item["id"],
            flow_name=item["attributes"]["name"],
        ))
    logger.info({"event": "active_flows_fetched", "count": len(flows)})
    return flows


def _fetch_flow_messages(client: httpx.Client, flow: _FlowInfo) -> None:
    """Popula flow.messages com todos os e-mails (flow-messages) do fluxo.

    Hierarquia: Fluxo -> SEND_EMAIL actions -> flow-messages (e-mails individuais).
    O filtro de métrica usa o message_id (ID da flow-message), igual ao N8N.
    """
    actions = _paginate(client, f"/flows/{flow.flow_id}/flow-actions/", {
        "fields[flow-action]": "action_type",
        "filter": "equals(action_type,'SEND_EMAIL')",
    })
    for action in actions:
        messages = _paginate(client, f"/flow-actions/{action['id']}/flow-messages/", {
            "fields[flow-message]": "name",
        })
        for msg in messages:
            flow.messages.append(_FlowMessage(
                flow_id=flow.flow_id,
                flow_name=flow.flow_name,
                message_id=msg["id"],
                message_name=msg["attributes"].get("name") or msg["id"],
            ))


def _aggregate_for_message(
    client: httpx.Client,
    metric_id: str,
    message_id: str,
    date_from: date,
    date_to: date,
) -> dict[str, int]:
    """Retorna {date_iso: count} para uma métrica de uma flow-message específica."""
    body = {"data": {"type": "metric-aggregate", "attributes": {
        "metric_id": metric_id,
        "measurements": ["count"],
        "interval": "day",
        "page_size": 500,
        "filter": (
            f"and("
            f"greater-or-equal(datetime,{date_from.isoformat()}T00:00:00+00:00),"
            f"less-than(datetime,{(date_to + timedelta(days=1)).isoformat()}T00:00:00+00:00),"
            f"equals($message,\"{message_id}\")"
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


def fetch_flow_email_metrics(
    client: httpx.Client,
    date_from: date,
    date_to: date,
) -> list[KlaviyoFlowEmailMetric]:
    """Busca métricas diárias de e-mails de todos os fluxos ativos.

    Para cada fluxo ativo:
      1. Busca SEND_EMAIL actions
      2. Para cada action, busca flow-messages (e-mails individuais)
      3. Para cada message x 3 métricas, chama metric-aggregates filtrando por message_id
      4. Grava uma linha por (message_id, date)
    """
    flows = _fetch_active_flows(client)
    if not flows:
        return []

    for flow in flows:
        _fetch_flow_messages(client, flow)
        logger.info({
            "event": "flow_messages_fetched",
            "flow_name": flow.flow_name,
            "messages": len(flow.messages),
        })

    all_messages = [msg for flow in flows for msg in flow.messages]
    if not all_messages:
        logger.warning({"event": "no_flow_messages_found"})
        return []

    logger.info({
        "event": "flow_metrics_start",
        "flows": len(flows),
        "messages": len(all_messages),
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
    })

    metric_ids = _fetch_metric_ids(client)
    rows: dict[tuple[str, str], dict] = {}  # (message_id, date_str) -> row

    for msg in all_messages:
        for col_name, metric_name in FLOW_METRIC_MAP.items():
            metric_id = metric_ids.get(metric_name)
            if not metric_id:
                continue
            counts = _aggregate_for_message(client, metric_id, msg.message_id, date_from, date_to)
            for date_str, count in counts.items():
                if count == 0:
                    continue
                key = (msg.message_id, date_str)
                if key not in rows:
                    rows[key] = {
                        "flow_id":       msg.flow_id,
                        "flow_name":     msg.flow_name,
                        "message_id":    msg.message_id,
                        "message_name":  msg.message_name,
                        "data":          date.fromisoformat(date_str),
                        "email_enviado": 0,
                        "email_aberto":  0,
                        "email_clicado": 0,
                    }
                rows[key][col_name] = count

        logger.info({"event": "message_processed", "flow_name": msg.flow_name, "message_id": msg.message_id})

    result = [KlaviyoFlowEmailMetric.model_validate(r) for r in rows.values()]
    logger.info({"event": "flow_metrics_done", "rows": len(result)})
    return result
