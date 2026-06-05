"""
Sincroniza a estrutura de fluxos Klaviyo (fluxos + e-mails individuais) para
dim_assets e dim_asset_items.

Deve rodar antes do cron email_flow para garantir que o mapa de mensagens
está atualizado. Separado do cron de métricas para evitar que ~500 chamadas
de estrutura sobrecarreguem o limite de taxa da API.
"""
import logging
import time
from dataclasses import dataclass, field

import httpx
from supabase import Client

from ingestion.db import writers
from ingestion.models.klaviyo_models import KlaviyoFlow, KlaviyoFlowMessage
from ingestion.sources.klaviyo_flow_metrics import (
    GET_THROTTLE_SECS,
    MAX_RETRIES,
    _get,
    _paginate,
    make_client,
)

logger = logging.getLogger(__name__)


@dataclass
class _FlowInfo:
    flow_id: str
    flow_name: str
    messages: list["_FlowMessage"] = field(default_factory=list)


@dataclass
class _FlowMessage:
    flow_id: str
    flow_name: str
    message_id: str
    message_name: str


def _fetch_active_flows(client: httpx.Client) -> list[_FlowInfo]:
    items = _paginate(client, "/flows/", {
        "fields[flow]": "name,status",
        "filter": "and(equals(status,'live'),equals(archived,false))",
    })
    flows = [
        _FlowInfo(flow_id=item["id"], flow_name=item["attributes"]["name"])
        for item in items
    ]
    logger.info({"event": "structure_flows_fetched", "count": len(flows)})
    return flows


def _fetch_flow_messages(client: httpx.Client, flow: _FlowInfo) -> None:
    """Popula flow.messages com os e-mails individuais (flow-messages) do fluxo."""
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
    logger.info({
        "event": "structure_messages_fetched",
        "flow": flow.flow_name,
        "messages": len(flow.messages),
    })


def sync_flow_structure(sb: Client) -> tuple[int, int]:
    """Busca fluxos ativos e seus e-mails no Klaviyo e sincroniza no banco.

    Returns (flows_upserted, messages_upserted).
    """
    client = make_client()

    flows = _fetch_active_flows(client)
    if not flows:
        logger.warning({"event": "structure_no_active_flows"})
        return 0, 0

    klaviyo_flows = [
        KlaviyoFlow(id=f.flow_id, name=f.flow_name, status="live")
        for f in flows
    ]
    channel_ids = writers.get_channel_ids(sb)
    flows_n = writers.upsert_flow_assets(sb, klaviyo_flows, channel_ids)

    for flow in flows:
        _fetch_flow_messages(client, flow)

    all_msgs = [msg for f in flows for msg in f.messages]
    if not all_msgs:
        logger.warning({"event": "structure_no_messages_found"})
        return flows_n, 0

    klaviyo_messages = [
        KlaviyoFlowMessage(id=m.message_id, flow_id=m.flow_id, name=m.message_name)
        for m in all_msgs
    ]
    asset_map = writers.get_asset_map(sb)
    messages_n = writers.upsert_flow_asset_items(sb, klaviyo_messages, asset_map)

    logger.info({
        "event": "structure_sync_done",
        "flows": flows_n,
        "messages": messages_n,
    })
    return flows_n, messages_n
