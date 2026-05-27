-- Migration: corrige CTOR > 100% em e-mails individuais de fluxos
-- Reversível: sim (remover o CASE WHEN e usar divisão direta)
--
-- Problema: alguns e-mails de fluxo têm cliques > aberturas porque o pixel de
-- rastreamento de abertura do Klaviyo não registra a propriedade $message em
-- eventos mais antigos, enquanto o rastreamento de cliques via URL sempre captura.
-- Resultado: CTOR = cliques / aberturas = valores impossíveis como 446.81%.
--
-- Correção: quando opens = 0 ou clicks > opens, retornar NULL (exibido como "—").

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
  CASE
    WHEN SUM(fes.opens) = 0 OR SUM(fes.clicks) > SUM(fes.opens) THEN NULL
    ELSE ROUND(SUM(fes.clicks)::numeric / SUM(fes.opens)::numeric * 100, 2)
  END                                                                                          AS ctor_pct
FROM fact_email_sends fes
JOIN dim_asset_items dai ON dai.id = fes.asset_item_id
JOIN dim_assets      da  ON da.id  = dai.asset_id
JOIN dim_channels    dc  ON dc.id  = da.channel_id
WHERE dc.slug = 'email_flow'
  AND dai.type = 'email'
GROUP BY dai.asset_id, dai.id, dai.name, dai.position, dai.is_active
HAVING SUM(fes.sends) > 0;

GRANT SELECT ON vw_email_flow_item_metrics TO anon;
