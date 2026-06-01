-- Migration: atribuição de receita por fluxo e e-mail individual via UTM
-- Reversível: sim — DROP FUNCTION get_email_flow_asset_metrics(date,date); etc.

DROP FUNCTION IF EXISTS get_email_flow_asset_metrics(date,date);
DROP FUNCTION IF EXISTS get_email_flow_item_metrics(date,date);

CREATE OR REPLACE FUNCTION get_email_flow_asset_metrics(p_start date, p_end date)
RETURNS TABLE(
  asset_id uuid, asset_name text, asset_type text, is_active boolean,
  sends bigint, opens bigint, clicks bigint, bounces bigint, unsubscribes bigint,
  open_rate_pct numeric, ctor_pct numeric, sends_per_day numeric,
  revenue_brl numeric, utm_campaign text, has_utm boolean
)
LANGUAGE sql STABLE AS $$
  SELECT
    da.id, fem.flow_name, 'flow'::text, COALESCE(da.is_active, true),
    SUM(fem.email_enviado)::bigint, SUM(fem.email_aberto)::bigint, SUM(fem.email_clicado)::bigint,
    0::bigint, 0::bigint,
    ROUND(SUM(fem.email_aberto)::numeric / NULLIF(SUM(fem.email_enviado),0) * 100, 2),
    CASE WHEN SUM(fem.email_aberto)=0 OR SUM(fem.email_clicado)>SUM(fem.email_aberto) THEN NULL
         ELSE ROUND(SUM(fem.email_clicado)::numeric / SUM(fem.email_aberto) * 100, 2) END,
    ROUND(SUM(fem.email_enviado)::numeric / NULLIF(COUNT(DISTINCT fem.data),0), 1),
    COALESCE((
      SELECT SUM(fo.revenue_brl) FROM fact_orders fo
      WHERE LOWER(fo.utm_source) = 'email'
        AND LOWER(fo.utm_medium) IN ('email_fluxo','fluxos_crm')
        AND LOWER(fo.utm_campaign) = LOWER(fuc.utm_campaign)
        AND fo.order_date BETWEEN p_start AND p_end
    ), 0),
    fuc.utm_campaign,
    (fuc.utm_campaign IS NOT NULL)
  FROM flow_email_metrics fem
  LEFT JOIN dim_assets da ON da.external_id = fem.flow_id AND da.source_tool = 'klaviyo' AND da.type = 'flow'
  LEFT JOIN flow_utm_config fuc ON fuc.flow_name = fem.flow_name
  WHERE fem.data BETWEEN p_start AND p_end
  GROUP BY da.id, da.is_active, fem.flow_id, fem.flow_name, fuc.utm_campaign
  ORDER BY SUM(fem.email_enviado) DESC, fem.flow_name;
$$;

CREATE OR REPLACE FUNCTION get_email_flow_item_metrics(p_start date, p_end date)
RETURNS TABLE(
  asset_id uuid, item_id uuid, item_name text, item_position integer, is_active boolean,
  sends bigint, opens bigint, clicks bigint, bounces bigint, unsubscribes bigint,
  open_rate_pct numeric, ctor_pct numeric, revenue_brl numeric, has_utm boolean
)
LANGUAGE sql STABLE AS $$
  SELECT
    da.id, dai.id, COALESCE(dai.name, fem.message_name), COALESCE(dai.position, 9999),
    COALESCE(dai.is_active, true),
    SUM(fem.email_enviado)::bigint, SUM(fem.email_aberto)::bigint, SUM(fem.email_clicado)::bigint,
    0::bigint, 0::bigint,
    ROUND(SUM(fem.email_aberto)::numeric / NULLIF(SUM(fem.email_enviado),0) * 100, 2),
    CASE WHEN SUM(fem.email_aberto)=0 THEN NULL
         ELSE ROUND(SUM(fem.email_clicado)::numeric / SUM(fem.email_aberto) * 100, 2) END,
    CASE
      WHEN fuc.utm_campaign IS NULL THEN 0
      WHEN fem.message_name !~* 'LEADS|CLIENTES' THEN NULL
      ELSE COALESCE((
        SELECT SUM(fo.revenue_brl) FROM fact_orders fo
        WHERE LOWER(fo.utm_source) = 'email'
          AND LOWER(fo.utm_medium) IN ('email_fluxo','fluxos_crm')
          AND LOWER(fo.utm_campaign) = LOWER(fuc.utm_campaign)
          AND LOWER(fo.utm_term) = CASE
                WHEN fem.message_name ~* 'LEADS'    THEN 'leads'
                WHEN fem.message_name ~* 'CLIENTES' THEN 'clientes' END
          AND LOWER(fo.utm_content) = 'em' || LPAD(
                (regexp_match(fem.message_name, 'EM(\d+)', 'i'))[1], 3, '0')
          AND fo.order_date BETWEEN p_start AND p_end
      ), 0)
    END,
    (fuc.utm_campaign IS NOT NULL AND fem.message_name ~* 'LEADS|CLIENTES')
  FROM flow_email_metrics fem
  LEFT JOIN dim_asset_items dai ON dai.external_id = fem.message_id AND dai.type = 'email'
  LEFT JOIN dim_assets da ON da.external_id = fem.flow_id AND da.source_tool = 'klaviyo' AND da.type = 'flow'
  LEFT JOIN flow_utm_config fuc ON fuc.flow_name = fem.flow_name
  WHERE fem.data BETWEEN p_start AND p_end
  GROUP BY da.id, dai.id, dai.name, dai.position, dai.is_active,
           fem.message_id, fem.message_name, fuc.utm_campaign
  HAVING SUM(fem.email_enviado) > 0
  ORDER BY da.id NULLS LAST, COALESCE(dai.position,9999), COALESCE(dai.name, fem.message_name);
$$;

GRANT EXECUTE ON FUNCTION get_email_flow_asset_metrics(date,date) TO anon;
GRANT EXECUTE ON FUNCTION get_email_flow_item_metrics(date,date) TO anon;
