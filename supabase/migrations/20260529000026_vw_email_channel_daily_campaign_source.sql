-- Atualiza vw_email_channel_daily: campanhas agora leem de campaign_email_metrics
-- Fluxos continuam lendo de fact_email_sends

CREATE OR REPLACE VIEW vw_email_channel_daily AS

-- E-mail Fluxo: mantém fact_email_sends
SELECT
    fes.date,
    dc.slug  AS channel_slug,
    dc.name  AS channel_name,
    SUM(fes.sends)                                                                        AS sends,
    SUM(fes.opens)                                                                        AS opens,
    SUM(fes.clicks)                                                                       AS clicks,
    SUM(fes.bounces)                                                                      AS bounces,
    SUM(fes.unsubscribes)                                                                 AS unsubscribes,
    ROUND(SUM(fes.opens)::numeric  / NULLIF(SUM(fes.sends), 0) * 100, 2)                AS open_rate_pct,
    ROUND(SUM(fes.clicks)::numeric / NULLIF(SUM(fes.opens), 0) * 100, 2)                AS ctor_pct,
    MAX(fes.ingested_at)                                                                  AS ingested_at
FROM fact_email_sends fes
JOIN dim_asset_items dai ON dai.id = fes.asset_item_id
JOIN dim_assets      da  ON da.id  = dai.asset_id
JOIN dim_channels    dc  ON dc.id  = da.channel_id
WHERE dc.slug = 'email_flow'
GROUP BY fes.date, dc.slug, dc.name

UNION ALL

-- E-mail Campanha: nova fonte campaign_email_metrics
SELECT
    cem.data                                                                              AS date,
    dc.slug                                                                               AS channel_slug,
    dc.name                                                                               AS channel_name,
    SUM(cem.email_enviado)                                                                AS sends,
    SUM(cem.email_aberto)                                                                 AS opens,
    SUM(cem.email_clicado)                                                                AS clicks,
    0                                                                                     AS bounces,
    0                                                                                     AS unsubscribes,
    ROUND(SUM(cem.email_aberto)::numeric  / NULLIF(SUM(cem.email_enviado), 0) * 100, 2) AS open_rate_pct,
    ROUND(SUM(cem.email_clicado)::numeric / NULLIF(SUM(cem.email_aberto),  0) * 100, 2) AS ctor_pct,
    MAX(cem.updated_at)                                                                   AS ingested_at
FROM campaign_email_metrics cem
CROSS JOIN (SELECT slug, name FROM dim_channels WHERE slug = 'email_campaign') dc
GROUP BY cem.data, dc.slug, dc.name;

GRANT SELECT ON vw_email_channel_daily TO anon;
