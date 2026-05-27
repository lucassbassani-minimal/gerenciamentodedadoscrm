-- Migration: corrige open_rate e ctor para fluxos usando acumulado
-- Reversível: sim (recriar com first-day global)
-- Supersede: 20260527000016 (parcialmente)
--
-- Problema: a abordagem first-day (para corrigir Apple MPP nas campanhas) foi
-- aplicada globalmente, quebrando os fluxos. Fluxos enviam continuamente para
-- novos inscritos a cada dia — não há um único "dia de envio". Usar apenas o
-- primeiro dia do fluxo captura uma fração ínfima das aberturas, resultando em
-- taxas próximas de 0.00%.
--
-- Correção:
--   Campanhas → first-day (corrige inflação Apple MPP do disparo único)
--   Fluxos    → acumulado total (opens / sends ao longo de toda a vida do fluxo)
--
-- A view vw_email_flow_item_metrics também é recriada sem first-day,
-- pela mesma razão: cada e-mail do fluxo dispara para inscritos novos todo dia.

-- ============================================================
-- vw_email_asset_metrics (campanhas first-day, fluxos acumulado)
-- ============================================================
DROP VIEW IF EXISTS vw_email_asset_metrics;

CREATE VIEW vw_email_asset_metrics AS
WITH asset_send_date AS (
  SELECT
    dai.asset_id,
    MIN(fes.date) FILTER (WHERE fes.sends > 0) AS send_date
  FROM fact_email_sends fes
  JOIN dim_asset_items dai ON dai.id = fes.asset_item_id
  GROUP BY dai.asset_id
),
asset_first_day AS (
  SELECT
    dai.asset_id,
    SUM(fes.opens)  AS opens_d1,
    SUM(fes.clicks) AS clicks_d1
  FROM fact_email_sends fes
  JOIN dim_asset_items  dai ON dai.id = fes.asset_item_id
  JOIN asset_send_date  asd ON asd.asset_id = dai.asset_id
                            AND fes.date = asd.send_date
  GROUP BY dai.asset_id
)
SELECT
  da.id                                                                              AS asset_id,
  da.name                                                                            AS asset_name,
  da.type                                                                            AS asset_type,
  da.is_active,
  dc.slug                                                                            AS channel_slug,
  MIN(fes.date)                                                                      AS first_date,
  MAX(fes.date)                                                                      AS last_date,
  MIN(CASE WHEN fes.sends > 0 THEN fes.date END)                                    AS send_date,
  SUM(fes.sends)                                                                     AS sends,
  SUM(fes.opens)                                                                     AS opens,
  SUM(fes.clicks)                                                                    AS clicks,
  SUM(fes.bounces)                                                                   AS bounces,
  SUM(fes.unsubscribes)                                                              AS unsubscribes,
  -- Campanhas: first-day (elimina re-aberturas Apple MPP pós-envio)
  -- Fluxos: acumulado (disparo contínuo para novos inscritos todo dia)
  CASE
    WHEN da.type = 'campaign' THEN
      ROUND(COALESCE(afd.opens_d1, 0)::numeric  / NULLIF(SUM(fes.sends), 0)::numeric * 100, 2)
    ELSE
      ROUND(SUM(fes.opens)::numeric / NULLIF(SUM(fes.sends), 0)::numeric * 100, 2)
  END                                                                                AS open_rate_pct,
  CASE
    WHEN da.type = 'campaign' THEN
      ROUND(COALESCE(afd.clicks_d1, 0)::numeric / NULLIF(COALESCE(afd.opens_d1, 0), 0)::numeric * 100, 2)
    ELSE
      ROUND(SUM(fes.clicks)::numeric / NULLIF(SUM(fes.opens), 0)::numeric * 100, 2)
  END                                                                                AS ctor_pct,
  ROUND(SUM(fes.sends)::numeric  / NULLIF(COUNT(DISTINCT fes.date), 0)::numeric, 1) AS sends_per_day,
  LOWER((regexp_match(da.name, '\[([a-zA-Z0-9]+)\]'))[1])                           AS utm_content_code,
  COALESCE(MAX(fo_seg.revenue_brl), 0)                                              AS revenue_brl,
  ROUND(
    COALESCE(MAX(fo_seg.revenue_brl), 0) / NULLIF(SUM(fes.sends), 0),
    4
  )                                                                                  AS revenue_per_send
FROM fact_email_sends fes
JOIN dim_asset_items  dai ON dai.id = fes.asset_item_id
JOIN dim_assets       da  ON da.id  = dai.asset_id
JOIN dim_channels     dc  ON dc.id  = da.channel_id
LEFT JOIN asset_first_day afd ON afd.asset_id = da.id
LEFT JOIN (
  SELECT
    LOWER(utm_content) AS utm_content,
    CASE
      WHEN LOWER(utm_term) LIKE '%clientes%' THEN 'clientes'
      WHEN LOWER(utm_term) LIKE '%leads%'    THEN 'leads'
      ELSE                                        'basetotal'
    END AS audience,
    SUM(revenue_brl) AS revenue_brl
  FROM fact_orders
  WHERE utm_content IS NOT NULL AND utm_content <> ''
  GROUP BY LOWER(utm_content),
    CASE
      WHEN LOWER(utm_term) LIKE '%clientes%' THEN 'clientes'
      WHEN LOWER(utm_term) LIKE '%leads%'    THEN 'leads'
      ELSE                                        'basetotal'
    END
) fo_seg ON fo_seg.utm_content = LOWER((regexp_match(da.name, '\[([a-zA-Z0-9]+)\]'))[1])
        AND fo_seg.audience = CASE
          WHEN da.name ~* '\[CLIENTES[^\]]*\]' THEN 'clientes'
          WHEN da.name ~* '\[LEADS[^\]]*\]'    THEN 'leads'
          ELSE                                      'basetotal'
        END
GROUP BY da.id, da.name, da.type, da.is_active, dc.slug, afd.opens_d1, afd.clicks_d1;

GRANT SELECT ON vw_email_asset_metrics TO anon;

-- ============================================================
-- vw_email_flow_item_metrics (acumulado — mesmo motivo dos fluxos)
-- ============================================================
DROP VIEW IF EXISTS vw_email_flow_item_metrics;

CREATE VIEW vw_email_flow_item_metrics AS
SELECT
  dai.asset_id,
  dai.id                                                                                       AS item_id,
  dai.name                                                                                     AS item_name,
  COALESCE(dai.position, 9999)                                                                 AS position,
  dai.is_active,
  SUM(fes.sends)                                                                               AS sends,
  SUM(fes.opens)                                                                               AS opens,
  SUM(fes.clicks)                                                                              AS clicks,
  SUM(fes.bounces)                                                                             AS bounces,
  SUM(fes.unsubscribes)                                                                        AS unsubscribes,
  ROUND(SUM(fes.opens)::numeric  / NULLIF(SUM(fes.sends), 0)::numeric * 100, 2)              AS open_rate_pct,
  ROUND(SUM(fes.clicks)::numeric / NULLIF(SUM(fes.opens), 0)::numeric * 100, 2)              AS ctor_pct
FROM fact_email_sends fes
JOIN dim_asset_items dai ON dai.id = fes.asset_item_id
JOIN dim_assets      da  ON da.id  = dai.asset_id
JOIN dim_channels    dc  ON dc.id  = da.channel_id
WHERE dc.slug = 'email_flow'
  AND dai.type = 'email'
GROUP BY dai.asset_id, dai.id, dai.name, dai.position, dai.is_active
HAVING SUM(fes.sends) > 0;

GRANT SELECT ON vw_email_flow_item_metrics TO anon;
