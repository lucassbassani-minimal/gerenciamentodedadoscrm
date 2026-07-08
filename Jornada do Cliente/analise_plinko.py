"""
Analise de Atribuicao de Reativacao (Efeito Plinko) - Fase 1.

Le "Base de Touchpoints.csv" (export da Shopify, last-click por sessao) e mede,
para pedidos pagos dos ultimos ~2 meses, o que acontece quando um touchpoint de
E-mail ou WhatsApp (fluxo, campanha ou comunidade) aparece no meio do caminho de
uma compra (isto e, nao e o ultimo toque antes da compra):

  - quantos dias depois a compra acontece
  - quantos outros touchpoints aparecem entre esse toque e a compra (cascata)
  - qual canal efetivamente fecha a venda

Roda em 3 niveis de granularidade: canal completo (E-mail vs WhatsApp), os 5
canais oficiais, e fluxo individual (dentro de E-mail Fluxo / WhatsApp Fluxo).

Ver "Claude.md jornadas" nesta pasta para o blueprint completo e as decisoes de
escopo tomadas com o Daniel em 08/07/2026.
"""

import csv
import glob
import json
import os
import statistics
from collections import defaultdict
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)
TOUCHPOINTS_CSV = os.path.join(HERE, "Base de Touchpoints.csv")
UTM_CONFIG_XLSX_GLOB = os.path.join(PROJECT_ROOT, "configura*es de utm.xlsx")
OUTPUT_JSON = os.path.join(HERE, "resultado_plinko.json")

# ============================================================
# 1. Regras de classificacao (Secao 3.4 do blueprint)
# ============================================================

CANAL_MEDIUMS = {
    "email_fluxo": {"email_fluxo", "fluxos_crm"},
    "email_campanha": {"email_campanha"},
    "whatsapp_fluxo": {"whatsapp_fluxo", "whatsapp_fluxo_ia"},
    "whatsapp_campanha": {"whatsapp_campanha"},
    "whatsapp_comunidade": {"comunidade"},
}

CANAL_LABELS = {
    "email_fluxo": "E-mail Fluxo",
    "email_campanha": "E-mail Campanha",
    "whatsapp_fluxo": "WhatsApp Fluxo",
    "whatsapp_campanha": "WhatsApp Campanha",
    "whatsapp_comunidade": "WhatsApp Comunidade",
}

MACRO_OF_CANAL = {
    "email_fluxo": "email",
    "email_campanha": "email",
    "whatsapp_fluxo": "whatsapp",
    "whatsapp_campanha": "whatsapp",
    "whatsapp_comunidade": "whatsapp",
}

MACRO_LABELS = {"email": "E-mail", "whatsapp": "WhatsApp"}

MEDIUM_TO_CANAL = {}
for canal_slug, mediums in CANAL_MEDIUMS.items():
    for m in mediums:
        MEDIUM_TO_CANAL[m] = canal_slug


def classify_medium(utm_medium: str) -> str | None:
    """Retorna o canal_slug (5 canais oficiais) ou None se nao for CRM (ads/direto/organico/etc)."""
    if not utm_medium:
        return None
    return MEDIUM_TO_CANAL.get(utm_medium.strip().lower())


def normalize(value: str | None) -> str:
    if not value:
        return ""
    result = value.strip().lower()
    for ch in (" ", "_", "-", "+"):
        result = result.replace(ch, "")
    return result


# ============================================================
# 2. Referencia de nomes de fluxo (Secao 3.4)
# ============================================================

def load_email_flow_reference() -> tuple[dict, dict]:
    """Le 'configuracoes de utm.xlsx' -> dict (campaign_norm, term_norm) -> flow_name
    e dict campaign_norm -> set(flow_name) para fallback quando term nao bate."""
    import openpyxl

    matches = glob.glob(UTM_CONFIG_XLSX_GLOB)
    if not matches:
        raise FileNotFoundError(f"Nao achei a planilha de configuracao de UTM em {PROJECT_ROOT}")

    wb = openpyxl.load_workbook(matches[0], data_only=True)
    ws = wb.active

    by_campaign_term: dict[tuple[str, str], str] = {}
    by_campaign: dict[str, set[str]] = defaultdict(set)

    for row in ws.iter_rows(min_row=3, values_only=True):
        flow_name = row[0]
        campaign = row[2] if len(row) > 2 else None
        term = row[3] if len(row) > 3 else None
        if not flow_name or not campaign:
            continue
        c_norm = normalize(str(campaign))
        t_norm = normalize(str(term)) if term else ""
        by_campaign_term[(c_norm, t_norm)] = flow_name
        by_campaign[c_norm].add(flow_name)

    return by_campaign_term, by_campaign


# WhatsApp: nao existe planilha equivalente. Estas linhas vem das tabelas
# dim_wpp_origem_mapping e dim_wpp_alia_campanha_mapping (Supabase, projeto
# gerenciamentodedadoscrm), consultadas em 08/07/2026. utm_campaign -> flow_name.
WPP_FLOW_REFERENCE_RAW = [
    ("fluxo_pageview", "Pageview"),
    ("aquisição", "Pageview Aquisição"),
    ("retencao", "Retenção"),
    ("upsell_imediato", "Up-Sell Perpetuo"),
    ("welcome", "Welcome Site"),
    ("fluxotof", "Welcome TOF"),
]


def load_wpp_flow_reference() -> dict[str, str]:
    return {normalize(campaign): flow_name for campaign, flow_name in WPP_FLOW_REFERENCE_RAW}


def resolve_flow_name(canal_slug: str, campaign: str, term: str,
                       email_ref: tuple[dict, dict], wpp_ref: dict) -> str:
    """Retorna o nome legivel do fluxo, ou 'Nao mapeado: <campaign>/<term>' se nao achar."""
    c_norm = normalize(campaign)
    if not c_norm:
        return "Nao mapeado: (utm_campaign vazio)"

    if canal_slug == "email_fluxo":
        by_campaign_term, by_campaign = email_ref
        t_norm = normalize(term)
        if (c_norm, t_norm) in by_campaign_term:
            return by_campaign_term[(c_norm, t_norm)]
        candidates = by_campaign.get(c_norm)
        if candidates and len(candidates) == 1:
            return next(iter(candidates))
        if candidates:
            return f"Ambiguo (campaign={campaign}, term={term}) - possiveis: {sorted(candidates)}"
        return f"Nao mapeado: {campaign}/{term or ''}"

    if canal_slug == "whatsapp_fluxo":
        if c_norm in wpp_ref:
            return wpp_ref[c_norm]
        return f"Nao mapeado: {campaign}/{term or ''}"

    return ""  # campanha/comunidade nao tem sub-fluxo


# ============================================================
# 3. Parsing da Base de Touchpoints
# ============================================================

def parse_money(value: str) -> float:
    if not value:
        return 0.0
    return float(value.replace(".", "").replace(",", "."))


def parse_datetime(date_str: str, time_str: str) -> datetime | None:
    if not date_str:
        return None
    time_str = time_str or "00:00:00"
    return datetime.strptime(f"{date_str} {time_str}", "%d/%m/%Y %H:%M:%S")


def load_orders(csv_path: str) -> dict:
    orders: dict[str, dict] = {}
    with open(csv_path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row["financial_status"] != "PAID":
                continue
            order_id = row["order_id"]
            order = orders.setdefault(order_id, {
                "order_id": order_id,
                "order_name": row["order_name"],
                "customer_email": row["customer_email"],
                "customer_type": row["customer_type"],
                "net_revenue": parse_money(row["net_revenue"]),
                "processed_at": parse_datetime(row["processed_at_data"], row["processed_at_hora"]),
                "touches": [],
            })
            touch_dt = parse_datetime(row["touchpoint_at_data"], row["touchpoint_at_hora"])
            if touch_dt is None:
                continue  # pedido sem sessao de navegacao registrada (so UTM de checkout)
            order["touches"].append({
                "touch_dt": touch_dt,
                "utm_source": row["utm_source"],
                "utm_medium": row["utm_medium"],
                "utm_campaign": row["utm_campaign"],
                "utm_term": row["utm_term"],
                "is_last_before_purchase": row["is_last_before_purchase"] == "true",
            })
    return orders


# ============================================================
# 4. Construcao dos eventos qualificados (Secao 4.2 do blueprint)
# ============================================================

def build_events(orders: dict, email_ref, wpp_ref) -> tuple[list, dict]:
    events = []
    stats = {"total_orders": len(orders), "orders_sem_touchpoint": 0,
             "orders_sem_flag_last": 0, "orders_analisados": 0}

    for order in orders.values():
        touches = sorted(order["touches"], key=lambda t: t["touch_dt"])
        if not touches:
            stats["orders_sem_touchpoint"] += 1
            continue

        closing_idx = next((i for i, t in enumerate(touches) if t["is_last_before_purchase"]), None)
        if closing_idx is None:
            stats["orders_sem_flag_last"] += 1
            closing_idx = len(touches) - 1

        stats["orders_analisados"] += 1
        closing_touch = touches[closing_idx]
        canal_fecha = classify_medium(closing_touch["utm_medium"]) or "outro"
        canal_fecha_label = CANAL_LABELS.get(canal_fecha, "Outro (ads/direto/organico)")

        for i in range(closing_idx):
            touch = touches[i]
            canal_slug = classify_medium(touch["utm_medium"])
            if canal_slug is None:
                continue  # nao e um dos 5 canais de CRM - nao qualifica como toque de reativacao

            dias_ate_compra = (order["processed_at"] - touch["touch_dt"]).total_seconds() / 86400
            fluxo_name = resolve_flow_name(canal_slug, touch["utm_campaign"], touch["utm_term"],
                                            email_ref, wpp_ref)

            events.append({
                "order_id": order["order_id"],
                "customer_email": order["customer_email"],
                "customer_type": order["customer_type"],
                "net_revenue": order["net_revenue"],
                "touch_dt": touch["touch_dt"],
                "canal_slug": canal_slug,
                "macro": MACRO_OF_CANAL[canal_slug],
                "fluxo_name": fluxo_name,
                "dias_ate_compra": dias_ate_compra,
                "qtd_touchpoints_entre": closing_idx - i - 1,
                "canal_fecha_slug": canal_fecha,
                "canal_fecha_label": canal_fecha_label,
                "fechou_mesmo_canal": canal_fecha == canal_slug,
            })

    return events, stats


# ============================================================
# 4b. Segmentacao por tipo de cliente (pedido novo aberto pelo Daniel em 08/07/2026)
# ============================================================

SEGMENTS = {
    "geral": lambda customer_type: True,
    "primeira_compra": lambda customer_type: customer_type == "Primeira Compra",
    "recompra": lambda customer_type: customer_type == "Recompra",
}

# Buckets de dias-ate-compra para o histograma (Seção "quanto tempo demorou de fato")
DIA_BUCKETS = [
    (0, 1, "0-1d"), (1, 3, "1-3d"), (3, 7, "3-7d"), (7, 14, "7-14d"),
    (14, 21, "14-21d"), (21, 30, "21-30d"), (30, None, "30d+"),
]


def bucketize_dias(dias: list[float]) -> dict[str, int]:
    counts = {label: 0 for _, _, label in DIA_BUCKETS}
    for d in dias:
        for lo, hi, label in DIA_BUCKETS:
            if (hi is None and d >= lo) or (hi is not None and lo <= d < hi):
                counts[label] += 1
                break
    return counts


def count_orders_by_segment(orders: dict) -> dict[str, int]:
    return {
        seg_name: sum(1 for o in orders.values() if seg_fn(o["customer_type"]))
        for seg_name, seg_fn in SEGMENTS.items()
    }


# ============================================================
# 5. Agregacao por nivel (macro / canal / fluxo)
# ============================================================

def first_touch_per_order(events: list, key_fn) -> list:
    """Para cada (order_id, chave), mantem so o evento mais antigo (Secao 8, pegadinha do doc)."""
    best: dict[tuple, dict] = {}
    for e in events:
        key = (e["order_id"], key_fn(e))
        if key not in best or e["touch_dt"] < best[key]["touch_dt"]:
            best[key] = e
    return list(best.values())


def percentiles(values: list[float]) -> dict:
    if not values:
        return {"p50": None, "p80": None, "p90": None, "media": None, "mediana": None, "n": 0}
    values_sorted = sorted(values)
    q = statistics.quantiles(values_sorted, n=100, method="inclusive") if len(values_sorted) >= 2 else None

    def pct(p):
        if len(values_sorted) < 2:
            return values_sorted[0]
        return q[p - 1]

    return {
        "n": len(values_sorted),
        "media": round(statistics.mean(values_sorted), 1),
        "mediana": round(statistics.median(values_sorted), 1),
        "p50": round(pct(50), 1),
        "p80": round(pct(80), 1),
        "p90": round(pct(90), 1),
    }


def summarize_group(group_events: list, total_orders_denom: int) -> dict:
    dias = [e["dias_ate_compra"] for e in group_events]
    qtd_entre = [e["qtd_touchpoints_entre"] for e in group_events]
    revenue = sum(e["net_revenue"] for e in group_events)

    canal_fecha_counter: dict[str, int] = defaultdict(int)
    for e in group_events:
        canal_fecha_counter[e["canal_fecha_label"]] += 1

    n = len(group_events)
    fechou_mesmo_canal = sum(1 for e in group_events if e["fechou_mesmo_canal"])
    qtd_zero = sum(1 for q in qtd_entre if q == 0)

    return {
        "n_pedidos": n,
        "pct_do_total_de_vendas": round(100 * n / total_orders_denom, 2) if total_orders_denom else None,
        "receita_associada": round(revenue, 2),
        "dias_ate_compra": percentiles(dias),
        "histograma_dias": bucketize_dias(dias),
        "qtd_touchpoints_entre_media": round(statistics.mean(qtd_entre), 1) if qtd_entre else None,
        "pct_sem_toque_no_meio": round(100 * qtd_zero / n, 1) if n else None,
        "pct_fechou_mesmo_canal": round(100 * fechou_mesmo_canal / n, 1) if n else None,
        "canal_que_fecha": dict(sorted(canal_fecha_counter.items(), key=lambda kv: -kv[1])),
    }


def build_report(events: list, total_orders_denom: int) -> dict:
    report: dict = {"nivel_1_macro": {}, "nivel_2_canal": {}, "nivel_3_fluxo": {}}

    for macro_slug, macro_label in MACRO_LABELS.items():
        group = first_touch_per_order(
            [e for e in events if e["macro"] == macro_slug], key_fn=lambda e: e["macro"]
        )
        report["nivel_1_macro"][macro_label] = summarize_group(group, total_orders_denom)

    for canal_slug, canal_label in CANAL_LABELS.items():
        group = first_touch_per_order(
            [e for e in events if e["canal_slug"] == canal_slug], key_fn=lambda e: e["canal_slug"]
        )
        report["nivel_2_canal"][canal_label] = summarize_group(group, total_orders_denom)

    for canal_slug in ("email_fluxo", "whatsapp_fluxo"):
        canal_events = [e for e in events if e["canal_slug"] == canal_slug]
        group = first_touch_per_order(canal_events, key_fn=lambda e: e["fluxo_name"])
        by_fluxo: dict[str, list] = defaultdict(list)
        for e in group:
            by_fluxo[e["fluxo_name"]].append(e)
        report["nivel_3_fluxo"][CANAL_LABELS[canal_slug]] = {
            fluxo_name: summarize_group(g, total_orders_denom) for fluxo_name, g in
            sorted(by_fluxo.items(), key=lambda kv: -len(kv[1]))
        }

    return report


# ============================================================
# main
# ============================================================

def main() -> None:
    email_ref = load_email_flow_reference()
    wpp_ref = load_wpp_flow_reference()

    orders = load_orders(TOUCHPOINTS_CSV)
    events, stats = build_events(orders, email_ref, wpp_ref)
    orders_by_segment = count_orders_by_segment(orders)

    segments_out = {}
    for seg_name, seg_fn in SEGMENTS.items():
        seg_events = [e for e in events if seg_fn(e["customer_type"])]
        touched_order_ids = {e["order_id"] for e in seg_events}
        revenue_touched = sum(orders[oid]["net_revenue"] for oid in touched_order_ids)
        denom = orders_by_segment[seg_name]
        segments_out[seg_name] = {
            "total_orders": denom,
            "pedidos_tocados_crm": len(touched_order_ids),
            "pct_pedidos_tocados_crm": round(100 * len(touched_order_ids) / denom, 2) if denom else None,
            "receita_tocada_crm": round(revenue_touched, 2),
            "relatorio": build_report(seg_events, denom),
        }

    nao_mapeados: dict[str, int] = defaultdict(int)
    for e in events:
        if e["fluxo_name"].startswith("Nao mapeado") or e["fluxo_name"].startswith("Ambiguo"):
            nao_mapeados[e["fluxo_name"]] += 1

    output = {
        "gerado_em": datetime.now().isoformat(),
        "stats_carregamento": stats,
        "orders_by_segment": orders_by_segment,
        "total_eventos_qualificados": len(events),
        "segments": segments_out,
        "nao_mapeados": dict(sorted(nao_mapeados.items(), key=lambda kv: -kv[1])),
    }

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)

    print(f"Pedidos pagos carregados: {stats['total_orders']}")
    print(f"Por segmento: {orders_by_segment}")
    print(f"Pedidos sem touchpoint de sessao: {stats['orders_sem_touchpoint']}")
    print(f"Pedidos sem flag is_last_before_purchase (fallback usado): {stats['orders_sem_flag_last']}")
    print(f"Eventos qualificados (toque de CRM no meio do caminho): {len(events)}")
    print(f"\nResultado salvo em: {OUTPUT_JSON}")
    print("\n=== Nivel 1 - Canal completo (GERAL) ===")
    for label, data in segments_out["geral"]["relatorio"]["nivel_1_macro"].items():
        print(f"{label}: {data['n_pedidos']} pedidos ({data['pct_do_total_de_vendas']}% do total), "
              f"mediana {data['dias_ate_compra']['mediana']}d, P80={data['dias_ate_compra']['p80']}d, "
              f"{data['pct_sem_toque_no_meio']}% sem toque no meio, "
              f"{data['pct_fechou_mesmo_canal']}% fecha pelo mesmo canal")


if __name__ == "__main__":
    main()
