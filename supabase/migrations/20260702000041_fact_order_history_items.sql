-- Migration: fact_order_history_items — histórico de pedidos com produto, via export manual do Shopify
-- Reversível: sim
--   DROP TABLE IF EXISTS fact_order_history_items;
--
-- Contexto: tabela nova e isolada, não substitui nem altera fact_orders (receita/atribuição de canal).
-- Alimentada por backfill manual (ingestion/backfill/load_order_history.py), não por cron.
-- Cobertura inicial: pedidos pagos de 2025-01-06 a 2026-07-01 (export "Todos os pedidos Minimal").
-- Granularidade: uma linha por item de pedido (lineitem) — campos de cabeçalho do pedido
-- (paid_at, total, desconto, frete, estado) vêm repetidos em cada linha do mesmo pedido.

CREATE TABLE IF NOT EXISTS fact_order_history_items (
    id                    uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    order_name            text        NOT NULL,
    shopify_order_id      text,
    line_number           integer     NOT NULL,
    email                 text,
    financial_status      text        NOT NULL,
    paid_at               timestamptz,
    created_at_shopify    timestamptz NOT NULL,
    order_total_brl       numeric(12,2) NOT NULL,
    order_subtotal_brl    numeric(12,2),
    discount_code         text,
    discount_amount_brl   numeric(12,2),
    shipping_method       text,
    billing_province      text,
    lineitem_quantity     integer     NOT NULL,
    lineitem_name         text        NOT NULL,
    lineitem_price        numeric(12,2) NOT NULL,
    lineitem_sku          text,
    ingested_at           timestamptz NOT NULL DEFAULT now(),
    UNIQUE (order_name, line_number)
);

ALTER TABLE fact_order_history_items ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_select_order_history_items"
    ON fact_order_history_items FOR SELECT TO anon USING (true);

CREATE POLICY "service_role_all_order_history_items"
    ON fact_order_history_items FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE INDEX IF NOT EXISTS idx_order_history_items_email   ON fact_order_history_items (email);
CREATE INDEX IF NOT EXISTS idx_order_history_items_paid_at ON fact_order_history_items (paid_at);
CREATE INDEX IF NOT EXISTS idx_order_history_items_order   ON fact_order_history_items (order_name);
