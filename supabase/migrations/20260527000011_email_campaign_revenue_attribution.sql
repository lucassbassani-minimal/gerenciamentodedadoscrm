-- Migration: adiciona atribuição de receita por utm_content em vw_email_asset_metrics
-- Reversível: sim (recriar versão anterior sem revenue_brl / revenue_per_send / utm_content_code)
--
-- Regra de atribuição:
--   O nome do e-mail de campanha contém um código entre colchetes, ex: [em1234]
--   Esse código corresponde ao valor de utm_content nos pedidos do Shopify.
--   SUM(revenue_brl) de fact_orders WHERE utm_content = código extraído.

CREATE OR REPLACE VIEW vw_email_asset_metrics AS
SELECT
  da.id                                                                              AS asset_id,
  da.name                                                                            AS asset_name,
  da.type                                                                            AS asset_type,
  da.is_active,
  dc.slug                                                                            AS channel_slug,
  MIN(fes.date)                                                                      AS first_date,
  MAX(fes.date)                                                                      AS last_date,
  SUM(fes.sends)                                                                     AS sends,
  SUM(fes.opens)                                                                     AS opens,
  SUM(fes.clicks)                                                                    AS clicks,
  SUM(fes.bounces)                                                                   AS bounces,
  SUM(fes.unsubscribes)                                                              AS unsubscribes,
  ROUND(SUM(fes.opens)::numeric  / NULLIF(SUM(fes.sends), 0)::numeric * 100, 2)    AS open_rate_pct,
  ROUND(SUM(fes.clicks)::numeric / NULLIF(SUM(fes.opens), 0)::numeric * 100, 2)    AS ctor_pct,
  ROUND(SUM(fes.sends)::numeric  / NULLIF(COUNT(DISTINCT fes.date), 0)::numeric, 1) AS sends_per_day,
  -- Código extraído entre [] no nome do e-mail: "[em1234] Assunto" → "em1234"
  (regexp_match(da.name, '\[([a-zA-Z0-9]+)\]'))[1]                                  AS utm_content_code,
  -- Receita total atribuída a esse e-mail via utm_content nos pedidos Shopify
  COALESCE(MAX(fo_agg.revenue_brl), 0)                                              AS revenue_brl,
  -- Receita por disparo
  ROUND(
    COALESCE(MAX(fo_agg.revenue_brl), 0) / NULLIF(SUM(fes.sends), 0),
    4
  )                                                                                  AS revenue_per_send
FROM fact_email_sends fes
JOIN dim_asset_items  dai ON dai.id = fes.asset_item_id
JOIN dim_assets       da  ON da.id  = dai.asset_id
JOIN dim_channels     dc  ON dc.id  = da.channel_id
LEFT JOIN (
  SELECT utm_content, SUM(revenue_brl) AS revenue_brl
  FROM fact_orders
  WHERE utm_content IS NOT NULL AND utm_content <> ''
  GROUP BY utm_content
) fo_agg ON fo_agg.utm_content = (regexp_match(da.name, '\[([a-zA-Z0-9]+)\]'))[1]
GROUP BY da.id, da.name, da.type, da.is_active, dc.slug;

GRANT SELECT ON vw_email_asset_metrics TO anon;
