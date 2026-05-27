-- Migration: corrige open_rate_pct e ctor_pct usando somente o dia do envio
-- Reversível: sim (recriar com SUM total)
-- Supersede: 20260527000015
--
-- Problema: SUM(opens) acumula re-aberturas ao longo de 30+ dias, incluindo
-- Apple MPP (iOS 15+ pré-carrega o pixel de rastreamento automaticamente).
-- Resultado: taxas infladas de 94-96% que não refletem a realidade.
--
-- Correção: open_rate_pct e ctor_pct usam apenas as aberturas e cliques
-- registrados no próprio dia do envio (send_date), que é quando a grande
-- maioria das aberturas genuínas ocorre e antes que o Apple MPP acumule
-- re-disparos ao longo dos dias seguintes.

DROP VIEW IF EXISTS vw_email_asset_metrics;

CREATE VIEW vw_email_asset_metrics AS
WITH asset_send_date AS (
  -- Data de envio por asset (primeiro dia com disparos > 0)
  SELECT
    dai.asset_id,
    MIN(fes.date) FILTER (WHERE fes.sends > 0) AS send_date
  FROM fact_email_sends fes
  JOIN dim_asset_items dai ON dai.id = fes.asset_item_id
  GROUP BY dai.asset_id
),
asset_first_day AS (
  -- Aberturas e cliques somente no dia do envio
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
  -- Taxa de abertura: aberturas do dia do envio / total de disparos
  ROUND(COALESCE(afd.opens_d1, 0)::numeric  / NULLIF(SUM(fes.sends), 0)::numeric * 100, 2) AS open_rate_pct,
  -- CTOR: cliques do dia do envio / aberturas do dia do envio
  ROUND(COALESCE(afd.clicks_d1, 0)::numeric / NULLIF(COALESCE(afd.opens_d1, 0), 0)::numeric * 100, 2) AS ctor_pct,
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
