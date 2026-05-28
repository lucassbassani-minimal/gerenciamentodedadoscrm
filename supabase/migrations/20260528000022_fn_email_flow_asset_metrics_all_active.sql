-- Migration: corrige get_email_flow_asset_metrics para exibir todos os fluxos ativos
-- Reversível: sim (restaurar versão anterior da função)
--
-- Problema: função anterior filtrava com HAVING SUM(sends) > 0, ocultando fluxos
-- ativos que não tiveram disparos no período selecionado. O resultado era que apenas
-- fluxos com dados recentes apareciam na tabela, mesmo com fluxos ativos no catálogo.
--
-- Correção: partir de dim_assets (catálogo) com LEFT JOIN nas métricas filtradas
-- pelo período. Fluxos sem disparos no período aparecem com métricas zeradas.
-- Só exibe fluxos com is_active = true.

CREATE OR REPLACE FUNCTION get_email_flow_asset_metrics(p_start date, p_end date)
RETURNS TABLE(
  asset_id      uuid,
  asset_name    text,
  asset_type    text,
  is_active     boolean,
  sends         bigint,
  opens         bigint,
  clicks        bigint,
  bounces       bigint,
  unsubscribes  bigint,
  open_rate_pct numeric,
  ctor_pct      numeric,
  sends_per_day numeric
)
LANGUAGE sql STABLE SECURITY DEFINER
AS $$
  SELECT
    da.id                                                                                          AS asset_id,
    da.name                                                                                        AS asset_name,
    da.type                                                                                        AS asset_type,
    da.is_active,
    COALESCE(SUM(fes.sends), 0)                                                                    AS sends,
    COALESCE(SUM(fes.opens), 0)                                                                    AS opens,
    COALESCE(SUM(fes.clicks), 0)                                                                   AS clicks,
    COALESCE(SUM(fes.bounces), 0)                                                                  AS bounces,
    COALESCE(SUM(fes.unsubscribes), 0)                                                             AS unsubscribes,
    ROUND(
      COALESCE(SUM(fes.opens), 0)::numeric
      / NULLIF(COALESCE(SUM(fes.sends), 0), 0)::numeric * 100, 2
    )                                                                                              AS open_rate_pct,
    CASE
      WHEN COALESCE(SUM(fes.opens), 0) = 0
        OR COALESCE(SUM(fes.clicks), 0) > COALESCE(SUM(fes.opens), 0) THEN NULL
      ELSE ROUND(
        COALESCE(SUM(fes.clicks), 0)::numeric
        / COALESCE(SUM(fes.opens), 0)::numeric * 100, 2
      )
    END                                                                                            AS ctor_pct,
    ROUND(
      COALESCE(SUM(fes.sends), 0)::numeric
      / NULLIF(COUNT(DISTINCT fes.date), 0)::numeric, 1
    )                                                                                              AS sends_per_day
  FROM dim_assets da
  JOIN dim_channels dc ON dc.id = da.channel_id
  LEFT JOIN dim_asset_items dai
    ON dai.asset_id = da.id AND dai.type = 'email'
  LEFT JOIN fact_email_sends fes
    ON fes.asset_item_id = dai.id
    AND fes.date >= p_start
    AND fes.date <= p_end
  WHERE dc.slug    = 'email_flow'
    AND da.is_active = true
  GROUP BY da.id, da.name, da.type, da.is_active
  ORDER BY COALESCE(SUM(fes.sends), 0) DESC, da.name;
$$;

GRANT EXECUTE ON FUNCTION get_email_flow_asset_metrics(date, date) TO anon;
