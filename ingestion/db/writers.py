import logging
from datetime import date, datetime, timezone

from supabase import Client

from ingestion.models.sendflow_models import (
    SendflowAction,
    SendflowAnalytics,
    SendflowRelease,
)
from ingestion.models.klaviyo_models import (
    KlaviyoCampaign,
    KlaviyoCampaignEmailMetric,
    KlaviyoCampaignMessage,
    KlaviyoEmailMetricRow,
    KlaviyoFlow,
    KlaviyoFlowEmailMetric,
    KlaviyoFlowMessage,
    KlaviyoForm,
    KlaviyoFormMetricRow,
)
from ingestion.models.sheets_models import SessionRow, SessionUtmRow
from ingestion.models.shopify_models import ShopifyOrder
from ingestion.models.order_history_models import OrderHistoryLineItem
from ingestion.models.order_history_legacy_models import OrderHistoryLegacyRow
from ingestion.models.chatflux_models import ChatfluxEvento

logger = logging.getLogger(__name__)

ACTIVE_CAMPAIGN_STATUSES = {"Sent", "Sending", "Scheduled"}

# Mapeamento utm_source+utm_medium → channel_slug (last-click, R4)
# Valores reais vindos da planilha Shopify (app de atribuição)
_UTM_TO_CHANNEL_SLUG: dict[tuple[str | None, str | None], str] = {
    ("email", "email_fluxo"): "email_flow",
    ("email", "fluxos_crm"): "email_flow",
    ("email", "email_campanha"): "email_campaign",
    ("whatsapp", "whatsapp_fluxo"): "wpp_flow",
    ("whatsapp", "whatsapp_fluxo_ia"): "wpp_flow",
    ("whatsapp", "fluxos_crm"): "wpp_flow",
    ("whatsapp", "whatsapp_campanha"): "wpp_campaign",
    ("whatsapp", "comunidade"): "wpp_community",
    # Formato padrão dim_channels (usado por outras fontes)
    ("email", "flow"): "email_flow",
    ("email", "campaign"): "email_campaign",
    ("whatsapp", "flow"): "wpp_flow",
    ("whatsapp", "campaign"): "wpp_campaign",
    ("community", None): "wpp_community",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_channel_ids(sb: Client) -> dict[str, str]:
    """Retorna {slug: uuid} de todos os canais em dim_channels."""
    resp = sb.table("dim_channels").select("id,slug").execute()
    return {row["slug"]: row["id"] for row in resp.data}


def get_asset_map(sb: Client) -> dict[str, str]:
    """Retorna {external_id: uuid} de todos os ativos Klaviyo em dim_assets."""
    resp = (
        sb.table("dim_assets")
        .select("id,external_id")
        .eq("source_tool", "klaviyo")
        .limit(10000)
        .execute()
    )
    return {row["external_id"]: row["id"] for row in resp.data}


def get_asset_item_map(sb: Client) -> dict[str, str]:
    """Retorna {external_id: uuid} de todos os itens de e-mail em dim_asset_items.

    Pagina em blocos de 1000 para contornar o limite padrão da API do Supabase.
    """
    result: dict[str, str] = {}
    page_size = 1000
    offset = 0
    while True:
        resp = (
            sb.table("dim_asset_items")
            .select("id,external_id")
            .eq("type", "email")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        for row in resp.data:
            result[row["external_id"]] = row["id"]
        if len(resp.data) < page_size:
            break
        offset += page_size
    return result


def get_synced_campaign_ids(sb: Client) -> set[str]:
    """Retorna external_ids de campanhas que já têm mensagens em dim_asset_items.

    Campanhas enviadas são imutáveis — se já temos as mensagens no banco,
    não precisamos re-buscar na API do Klaviyo.

    Usa paginação e chunks para evitar URLs longas demais no filtro .in_().
    """
    # Coleta todos os asset_ids que têm itens do tipo email (paginado)
    asset_ids_with_items: set[str] = set()
    page_size = 1000
    offset = 0
    while True:
        resp = (
            sb.table("dim_asset_items")
            .select("asset_id")
            .eq("type", "email")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        for row in resp.data:
            asset_ids_with_items.add(row["asset_id"])
        if len(resp.data) < page_size:
            break
        offset += page_size

    if not asset_ids_with_items:
        return set()

    # Divide em lotes de 100 para evitar URL muito longa no filtro .in_()
    synced: set[str] = set()
    ids_list = list(asset_ids_with_items)
    chunk_size = 100
    for i in range(0, len(ids_list), chunk_size):
        chunk = ids_list[i : i + chunk_size]
        resp = (
            sb.table("dim_assets")
            .select("external_id")
            .eq("type", "campaign")
            .eq("source_tool", "klaviyo")
            .in_("id", chunk)
            .execute()
        )
        for row in resp.data:
            synced.add(row["external_id"])
    return synced


def get_latest_dates(sb: Client) -> dict[str, date | None]:
    """Retorna a data mais recente em cada tabela fact — usada pelo sync inteligente."""
    def _latest(table: str, col: str) -> date | None:
        resp = sb.table(table).select(col).order(col, desc=True).limit(1).execute()
        if resp.data and resp.data[0].get(col):
            raw = resp.data[0][col]
            return date.fromisoformat(str(raw)[:10])
        return None

    return {
        "orders":        _latest("fact_orders",        "order_date"),
        "sessions":      _latest("fact_sessions",      "date"),
        "form_captures": _latest("fact_lead_captures", "date"),
    }


def upsert_orders(sb: Client, orders: list[ShopifyOrder], channel_ids: dict[str, str]) -> int:
    if not orders:
        return 0
    now = _now_iso()
    records = []
    for o in orders:
        slug = _UTM_TO_CHANNEL_SLUG.get((o.utm_source, o.utm_medium))
        channel_id = channel_ids.get(slug) if slug else None
        records.append({
            "order_id": o.order_id,
            "order_date": o.order_date.isoformat(),
            "customer_email": o.customer_email,
            "revenue_brl": str(o.revenue_brl),
            "is_first_purchase": o.is_first_purchase,
            "attributed_channel_id": channel_id,
            "utm_source": o.utm_source,
            "utm_medium": o.utm_medium,
            "utm_campaign": o.utm_campaign,
            "utm_content": o.utm_content,
            "utm_term": o.utm_term,
            "data_source": "shopify",
            "ingested_at": now,
        })
    sb.table("fact_orders").upsert(records, on_conflict="order_id").execute()
    unattributed = sum(1 for r in records if not r["attributed_channel_id"])
    logger.info({"event": "orders_upserted", "count": len(records), "unattributed": unattributed})
    return len(records)


def upsert_flow_assets(sb: Client, flows: list[KlaviyoFlow], channel_ids: dict[str, str]) -> int:
    if not flows:
        return 0
    now = _now_iso()
    channel_id = channel_ids["email_flow"]
    records = [{
        "external_id": f.id,
        "channel_id": channel_id,
        "name": f.name,
        "type": "flow",
        "is_active": f.status == "live",
        "source_tool": "klaviyo",
        "updated_at": now,
        "ingested_at": now,
    } for f in flows]
    sb.table("dim_assets").upsert(records, on_conflict="external_id,source_tool").execute()
    logger.info({"event": "flow_assets_upserted", "count": len(records)})
    return len(records)


def upsert_campaign_assets(sb: Client, campaigns: list[KlaviyoCampaign], channel_ids: dict[str, str]) -> int:
    if not campaigns:
        return 0
    now = _now_iso()
    channel_id = channel_ids["email_campaign"]
    records = [{
        "external_id": c.id,
        "channel_id": channel_id,
        "name": c.name,
        "type": "campaign",
        "is_active": c.status in ACTIVE_CAMPAIGN_STATUSES,
        "source_tool": "klaviyo",
        "updated_at": now,
        "ingested_at": now,
    } for c in campaigns]
    sb.table("dim_assets").upsert(records, on_conflict="external_id,source_tool").execute()
    logger.info({"event": "campaign_assets_upserted", "count": len(records)})
    return len(records)


def upsert_flow_asset_items(
    sb: Client, messages: list[KlaviyoFlowMessage], asset_map: dict[str, str]
) -> int:
    if not messages:
        return 0
    now = _now_iso()
    records = []
    skipped = 0
    for m in messages:
        asset_id = asset_map.get(m.flow_id)
        if not asset_id:
            skipped += 1
            continue
        records.append({
            "external_id": m.id,
            "asset_id": asset_id,
            "name": m.name,
            "type": "email",
            "position": m.position,
            "updated_at": now,
            "ingested_at": now,
        })
    if skipped:
        logger.warning({"event": "flow_items_skipped", "skipped": skipped})
    if not records:
        return 0
    sb.table("dim_asset_items").upsert(records, on_conflict="external_id,type").execute()
    logger.info({"event": "flow_asset_items_upserted", "count": len(records)})
    return len(records)


def upsert_campaign_asset_items(
    sb: Client, messages: list[KlaviyoCampaignMessage], asset_map: dict[str, str]
) -> int:
    if not messages:
        return 0
    now = _now_iso()
    records = []
    skipped = 0
    for m in messages:
        asset_id = asset_map.get(m.campaign_id)
        if not asset_id:
            skipped += 1
            continue
        records.append({
            "external_id": m.id,
            "asset_id": asset_id,
            "name": m.label,
            "type": "email",
            "position": None,
            "updated_at": now,
            "ingested_at": now,
        })
    if skipped:
        logger.warning({"event": "campaign_items_skipped", "skipped": skipped})
    if not records:
        return 0
    sb.table("dim_asset_items").upsert(records, on_conflict="external_id,type").execute()
    logger.info({"event": "campaign_asset_items_upserted", "count": len(records)})
    return len(records)


def upsert_email_sends(
    sb: Client,
    rows: list[KlaviyoEmailMetricRow],
    item_map: dict[str, str],
    campaign_to_item_map: dict[str, str] | None = None,
) -> int:
    """Grava métricas de e-mail em fact_email_sends.

    item_map: {message_external_id → item_uuid} — mapa primário (fluxos + campanhas novas)
    campaign_to_item_map: {campaign_external_id → item_uuid} — fallback para campanhas onde
        o Klaviyo retorna o campaign ID em vez do campaign-message ID no campo $message.
    """
    if not rows:
        return 0
    now = _now_iso()
    fallback = campaign_to_item_map or {}
    records = []
    skipped = 0
    for r in rows:
        item_id = item_map.get(r.message_id) or fallback.get(r.message_id)
        if not item_id:
            skipped += 1
            continue
        records.append({
            "date": r.date.isoformat(),
            "asset_item_id": item_id,
            "sends": r.sends,
            "opens": r.opens,
            "clicks": r.clicks,
            "bounces": r.bounces,
            "spam_complaints": r.spam_complaints,
            "unsubscribes": r.unsubscribes,
            "ingested_at": now,
        })
    if skipped:
        skipped_ids = [r.message_id for r in rows if not (item_map.get(r.message_id) or fallback.get(r.message_id))]
        logger.warning({
            "event": "email_sends_skipped",
            "skipped": skipped,
            "reason": "message_id not in item_map nem em campaign_to_item_map",
            "sample_ids": skipped_ids[:5],
        })
    if not records:
        return 0
    # Desduplicar: quando dois message_ids mapeiam para o mesmo asset_item_id,
    # soma as métricas para evitar conflito no upsert
    merged: dict[tuple[str, str], dict] = {}
    for rec in records:
        key = (rec["date"], rec["asset_item_id"])
        if key not in merged:
            merged[key] = rec.copy()
        else:
            for field in ("sends", "opens", "clicks", "bounces", "spam_complaints", "unsubscribes"):
                merged[key][field] = (merged[key].get(field) or 0) + (rec.get(field) or 0)
    deduped = list(merged.values())
    sb.table("fact_email_sends").upsert(deduped, on_conflict="date,asset_item_id").execute()
    logger.info({"event": "email_sends_upserted", "count": len(deduped)})
    return len(deduped)


def get_campaign_to_item_map(sb: Client) -> dict[str, str]:
    """Retorna {campaign_external_id: item_uuid} para campanhas com exatamente uma mensagem.

    Usado como fallback quando o metric-aggregates retorna o campaign ID em vez do
    campaign-message ID no campo $message (comportamento observado em campanhas de
    fev-mar 2026).
    """
    # Pagina em blocos para contornar o limite de 1000 linhas da API Supabase
    asset_to_item: dict[str, str] = {}
    page_size = 1000
    offset = 0
    while True:
        resp = (
            sb.table("dim_asset_items")
            .select("id,asset_id")
            .eq("type", "email")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        for row in resp.data:
            if row["asset_id"] not in asset_to_item:
                asset_to_item[row["asset_id"]] = row["id"]
        if len(resp.data) < page_size:
            break
        offset += page_size

    # converte para {campaign_external_id: item_uuid}
    asset_map = get_asset_map(sb)  # {external_id: uuid}
    result: dict[str, str] = {}
    for ext_id, asset_uuid in asset_map.items():
        if asset_uuid in asset_to_item:
            result[ext_id] = asset_to_item[asset_uuid]
    return result


def get_form_id_map(sb: Client) -> dict[str, str]:
    """Retorna {external_id: uuid} de todos os formulários em dim_forms."""
    resp = sb.table("dim_forms").select("id,external_id").limit(10000).execute()
    return {row["external_id"]: row["id"] for row in resp.data}


def upsert_form_captures(
    sb: Client, rows: list[KlaviyoFormMetricRow], form_id_map: dict[str, str]
) -> int:
    if not rows:
        return 0
    now = _now_iso()
    records = []
    skipped = 0
    for r in rows:
        form_id = form_id_map.get(r.form_external_id)
        if not form_id:
            skipped += 1
            continue
        records.append({
            "date": r.date.isoformat(),
            "form_id": form_id,
            "impressions": r.impressions,
            "submissions": r.submissions,
            "ingested_at": now,
        })
    if skipped:
        logger.warning({
            "event": "form_captures_skipped",
            "skipped": skipped,
            "reason": "form_external_id não encontrado em dim_forms",
        })
    if not records:
        return 0
    sb.table("fact_lead_captures").upsert(records, on_conflict="date,form_id").execute()
    logger.info({"event": "form_captures_upserted", "count": len(records)})
    return len(records)


def upsert_forms(sb: Client, forms: list[KlaviyoForm]) -> int:
    if not forms:
        return 0
    now = _now_iso()
    records = [{
        "external_id": f.id,
        "name": f.name,
        "type": f.form_type,
        "is_active": f.status.lower() not in ("draft", "archived"),
        "ingested_at": now,
    } for f in forms]
    sb.table("dim_forms").upsert(records, on_conflict="external_id").execute()
    logger.info({"event": "forms_upserted", "count": len(records)})
    return len(records)


def upsert_flow_email_metrics(
    sb: Client, rows: list[KlaviyoFlowEmailMetric]
) -> int:
    if not rows:
        return 0
    now = _now_iso()
    records = [{
        "flow_id":       r.flow_id,
        "flow_name":     r.flow_name,
        "message_id":    r.message_id,
        "message_name":  r.message_name,
        "data":          r.data.isoformat(),
        "email_enviado": r.email_enviado,
        "email_aberto":  r.email_aberto,
        "email_clicado": r.email_clicado,
        "updated_at":    now,
    } for r in rows]
    sb.table("flow_email_metrics").upsert(records, on_conflict="message_id,data").execute()
    logger.info({"event": "flow_email_metrics_upserted", "count": len(records)})
    return len(records)


def upsert_campaign_email_metrics(
    sb: Client, rows: list[KlaviyoCampaignEmailMetric]
) -> int:
    if not rows:
        return 0
    now = _now_iso()
    records = [{
        "campaign_id":   r.campaign_id,
        "campaign_name": r.campaign_name,
        "message_id":    r.message_id,
        "data":          r.data.isoformat(),
        "email_enviado": r.email_enviado,
        "email_aberto":  r.email_aberto,
        "email_clicado": r.email_clicado,
        "updated_at":    now,
    } for r in rows]
    sb.table("campaign_email_metrics").upsert(records, on_conflict="message_id,data").execute()
    logger.info({"event": "campaign_email_metrics_upserted", "count": len(records)})
    return len(records)


def upsert_email_health(
    sb: Client, active_base_count: int, today: date, channel_ids: dict[str, str]
) -> int:
    now = _now_iso()
    record = {
        "date": today.isoformat(),
        "channel_id": channel_ids["email_flow"],
        "active_subscribers": active_base_count,
        "ingested_at": now,
    }
    sb.table("fact_email_health").upsert([record], on_conflict="date,channel_id").execute()
    logger.info({"event": "email_health_upserted", "active_subscribers": active_base_count})
    return 1


def upsert_sessions(sb: Client, rows: list[SessionRow], channel_ids: dict[str, str]) -> int:
    if not rows:
        return 0
    now = _now_iso()
    records = []
    skipped = 0
    for r in rows:
        channel_id = channel_ids.get(r.channel_slug)
        if not channel_id:
            logger.warning({"event": "session_channel_not_found", "slug": r.channel_slug})
            skipped += 1
            continue
        # GA4 pode retornar begin_checkout > add_to_cart (checkout direto sem ATC)
        # Clampamos para manter o invariante do banco: sessions >= atc >= bco >= 0
        atc = min(r.add_to_cart, r.sessions)
        bco = min(r.begin_checkout, atc)
        if atc != r.add_to_cart or bco != r.begin_checkout:
            logger.warning({
                "event": "sessions_funnel_clamped",
                "date": r.date.isoformat(),
                "channel_slug": r.channel_slug,
                "original": {"atc": r.add_to_cart, "bco": r.begin_checkout},
                "clamped": {"atc": atc, "bco": bco},
            })
        records.append({
            "date": r.date.isoformat(),
            "channel_id": channel_id,
            "sessions": r.sessions,
            "add_to_cart": atc,
            "begin_checkout": bco,
            "orders": r.orders,
            "revenue_brl": str(r.revenue_brl),
            "ingested_at": now,
        })
    if skipped:
        logger.warning({"event": "sessions_skipped", "skipped": skipped})
    if not records:
        return 0
    sb.table("fact_sessions").upsert(records, on_conflict="date,channel_id").execute()
    logger.info({"event": "sessions_upserted", "count": len(records)})
    return len(records)


def get_flow_message_structure(sb: Client) -> list[dict]:
    """Retorna [{flow_id, flow_name, message_id, message_name}] lendo de dim_assets + dim_asset_items.

    Substitui as chamadas de estrutura à API do Klaviyo no cron de métricas.
    Só retorna fluxos com is_active=True para espelhar o comportamento original de
    buscar apenas fluxos com status 'live'.
    """
    flows_resp = (
        sb.table("dim_assets")
        .select("id,external_id,name")
        .eq("type", "flow")
        .eq("source_tool", "klaviyo")
        .eq("is_active", True)
        .limit(1000)
        .execute()
    )
    if not flows_resp.data:
        return []

    flow_uuid_to_info: dict[str, tuple[str, str]] = {
        row["id"]: (row["external_id"], row["name"])
        for row in flows_resp.data
    }

    messages: list[dict] = []
    ids_list = list(flow_uuid_to_info.keys())
    chunk_size = 50
    for i in range(0, len(ids_list), chunk_size):
        chunk = ids_list[i : i + chunk_size]
        items_resp = (
            sb.table("dim_asset_items")
            .select("external_id,asset_id,name")
            .eq("type", "email")
            .in_("asset_id", chunk)
            .limit(10000)
            .execute()
        )
        for row in items_resp.data:
            info = flow_uuid_to_info.get(row["asset_id"])
            if info:
                messages.append({
                    "flow_id":      info[0],
                    "flow_name":    info[1],
                    "message_id":   row["external_id"],
                    "message_name": row["name"],
                })

    logger.info({"event": "flow_structure_loaded_from_db", "messages": len(messages)})
    return messages


def get_sendflow_asset_map(sb: Client) -> dict[str, str]:
    """Retorna {external_id: uuid} de todos os ativos Sendflow em dim_assets."""
    resp = (
        sb.table("dim_assets")
        .select("id,external_id")
        .eq("source_tool", "sendflow")
        .limit(10000)
        .execute()
    )
    return {row["external_id"]: row["id"] for row in resp.data}


def upsert_community_assets(
    sb: Client, releases: list[SendflowRelease], channel_ids: dict[str, str]
) -> int:
    """Sincroniza releases do Sendflow como ativos em dim_assets (source_tool='sendflow')."""
    if not releases:
        return 0
    now = _now_iso()
    channel_id = channel_ids["wpp_community"]
    records = [{
        "external_id": r.id,
        "channel_id": channel_id,
        "name": r.name,
        "type": "campaign",
        "is_active": not r.archived,
        "source_tool": "sendflow",
        "updated_at": now,
        "ingested_at": now,
    } for r in releases]
    sb.table("dim_assets").upsert(records, on_conflict="external_id,source_tool").execute()
    logger.info({"event": "community_assets_upserted", "count": len(records)})
    return len(records)


def upsert_community_analytics(
    sb: Client,
    release_id: str,
    asset_id: str | None,
    channel_id: str,
    analytics: SendflowAnalytics,
    total_members: int | None,
    since: date | None = None,
    until: date | None = None,
) -> int:
    """Grava métricas de crescimento e engajamento por dia por release.

    Combina as três métricas (add/remove/clicks) num único upsert por data.
    Se since/until informados, filtra apenas as datas nesse intervalo.
    total_members é gravado apenas na data mais recente do lote (snapshot atual).
    """
    all_dates: set[str] = set()
    all_dates.update(analytics.add.dates.keys())
    all_dates.update(analytics.remove.dates.keys())
    all_dates.update(analytics.clicks.dates.keys())

    if not all_dates:
        return 0

    if since or until:
        all_dates = {
            d for d in all_dates
            if (not since or d >= since.isoformat())
            and (not until or d <= until.isoformat())
        }

    if not all_dates:
        return 0

    most_recent = max(all_dates)
    now = _now_iso()
    records = []
    for date_str in all_dates:
        records.append({
            "date": date_str,
            "release_id": release_id,
            "asset_id": asset_id,
            "channel_id": channel_id,
            "members_added": analytics.add.dates.get(date_str, 0),
            "members_removed": analytics.remove.dates.get(date_str, 0),
            "link_clicks": analytics.clicks.dates.get(date_str, 0),
            "total_members": total_members if date_str == most_recent else None,
            "ingested_at": now,
        })

    batch_size = 500
    total = 0
    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        sb.table("fact_community_analytics").upsert(
            batch, on_conflict="date,release_id"
        ).execute()
        total += len(batch)

    logger.info({
        "event": "community_analytics_upserted",
        "release_id": release_id,
        "count": total,
    })
    return total


def upsert_community_actions(
    sb: Client,
    actions: list[SendflowAction],
    asset_map: dict[str, str],
    channel_id: str,
) -> int:
    """Grava ações de disparo da comunidade em fact_community_actions."""
    if not actions:
        return 0
    now = _now_iso()
    records = [{
        "action_id":    a.id,
        "release_id":   a.release_id,
        "asset_id":     asset_map.get(a.release_id),
        "channel_id":   channel_id,
        "action_date":  a.created_at.date().isoformat(),
        "action_type":  a.type,
        "success":      a.success,
        "scheduled_to": a.scheduled_to.isoformat() if a.scheduled_to else None,
        "finished_at":  a.finished_at.isoformat() if a.finished_at else None,
        "ingested_at":  now,
    } for a in actions]
    sb.table("fact_community_actions").upsert(records, on_conflict="action_id").execute()
    logger.info({"event": "community_actions_upserted", "count": len(records)})
    return len(records)


def upsert_sessions_utm(sb: Client, rows: list[SessionUtmRow], channel_ids: dict[str, str]) -> int:
    if not rows:
        return 0
    now = _now_iso()
    records = []
    skipped = 0
    for r in rows:
        channel_id = channel_ids.get(r.channel_slug)
        if not channel_id:
            skipped += 1
            continue
        atc = min(r.add_to_cart, r.sessions)
        bco = min(r.begin_checkout, atc)
        records.append({
            "date": r.date.isoformat(),
            "channel_id": channel_id,
            "utm_source": r.utm_source,
            "utm_medium": r.utm_medium,
            "utm_campaign": r.utm_campaign,
            "utm_term": r.utm_term,
            "utm_content": r.utm_content,
            "sessions": r.sessions,
            "add_to_cart": atc,
            "begin_checkout": bco,
            "orders": r.orders,
            "revenue_brl": str(r.revenue_brl),
            "ingested_at": now,
        })
    if skipped:
        logger.warning({"event": "sessions_utm_skipped", "skipped": skipped})
    if not records:
        return 0
    # Upsert em lotes de 1000 para evitar limite de payload do Supabase
    batch_size = 1000
    total = 0
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        sb.table("fact_sessions_utm").upsert(
            batch,
            on_conflict="date,channel_id,utm_source,utm_medium,utm_campaign,utm_term,utm_content"
        ).execute()
        total += len(batch)
    logger.info({"event": "sessions_utm_upserted", "count": total})
    return total


def upsert_order_history_items(sb: Client, items: list[OrderHistoryLineItem]) -> int:
    if not items:
        return 0
    now = _now_iso()
    records = []
    for it in items:
        records.append({
            "order_name": it.order_name,
            "shopify_order_id": it.shopify_order_id,
            "line_number": it.line_number,
            "email": it.email,
            "financial_status": it.financial_status,
            "paid_at": it.paid_at.isoformat() if it.paid_at is not None else None,
            "created_at_shopify": it.created_at_shopify.isoformat(),
            "order_total_brl": str(it.order_total_brl),
            "order_subtotal_brl": str(it.order_subtotal_brl) if it.order_subtotal_brl is not None else None,
            "discount_code": it.discount_code,
            "discount_amount_brl": str(it.discount_amount_brl) if it.discount_amount_brl is not None else None,
            "shipping_method": it.shipping_method,
            "billing_province": it.billing_province,
            "lineitem_quantity": it.lineitem_quantity,
            "lineitem_name": it.lineitem_name,
            "lineitem_price": str(it.lineitem_price),
            "lineitem_sku": it.lineitem_sku,
            "ingested_at": now,
        })
    batch_size = 1000
    total = 0
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        sb.table("fact_order_history_items").upsert(batch, on_conflict="order_name,line_number").execute()
        total += len(batch)
    logger.info({"event": "order_history_items_upserted", "count": total})
    return total


def replace_order_history_legacy(sb: Client, rows: list[OrderHistoryLegacyRow]) -> int:
    """Recarrega fact_order_history_legacy por completo (truncate + insert).
    Fonte não tem chave única de pedido, então upsert incremental não se aplica —
    cada execução substitui o conteúdo inteiro pelo CSV atual."""
    sb.table("fact_order_history_legacy").delete().neq("email", "").execute()
    if not rows:
        return 0
    now = _now_iso()
    records = [{
        "email": r.email,
        "order_date": r.order_date.isoformat(),
        "revenue_brl": str(r.revenue_brl),
        "ingested_at": now,
    } for r in rows]
    batch_size = 1000
    total = 0
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        sb.table("fact_order_history_legacy").insert(batch).execute()
        total += len(batch)
    logger.info({"event": "order_history_legacy_loaded", "count": total})
    return total


def upsert_chatflux_events(sb: Client, rows: list[ChatfluxEvento]) -> int:
    """Upsert de eventos de disparo/resposta do Chatflux em fact_chatflux_events.
    Chave de dedupe: (telefone, segmento, etapa, event_timestamp)."""
    if not rows:
        return 0
    records = [{
        "event_timestamp": r.event_timestamp.isoformat(),
        "segmento": r.segmento,
        "etapa": r.etapa,
        "telefone": r.telefone,
    } for r in rows]
    batch_size = 1000
    total = 0
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        sb.table("fact_chatflux_events").upsert(
            batch, on_conflict="telefone,segmento,etapa,event_timestamp"
        ).execute()
        total += len(batch)
    logger.info({"event": "chatflux_events_upserted", "count": total})
    return total
