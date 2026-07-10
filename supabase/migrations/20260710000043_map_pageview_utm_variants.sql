-- Migration: mapeia variantes de UTM de Pageview/Pageview Aquisição que não batiam com o cadastro existente
-- Reversível: sim
--   DELETE FROM dim_wpp_alia_campanha_mapping WHERE alia_campanha IN ('fluxo-pageview','pageview-30-60d','pageview-60-90d');

-- Os pedidos reais usam utm_campaign com hífen ('fluxo-pageview', 'pageview-30-60d',
-- 'pageview-60-90d'), mas o cadastro em dim_wpp_alia_campanha_mapping tinha só as
-- variantes com underscore ('fluxo_pageview') ou o valor genérico 'aquisição' — por
-- isso esses pedidos não apareciam em vw_wpp_flow_revenue. Confirmado com Daniel:
-- fluxo-pageview = Pageview; pageview-30-60d e pageview-60-90d = Pageview Aquisição.
-- As demais variantes soltas (upsell_sorteiocopa, pageview-90-120d, blackfriday2025,
-- abandoned_cart sem "_ia", welcome_geral) ficam de fora por decisão do Daniel.
INSERT INTO dim_wpp_alia_campanha_mapping (alia_campanha, flow_name, utm_campaign, is_ignored)
VALUES
  ('fluxo-pageview',    'Pageview',           'fluxo-pageview',    false),
  ('pageview-30-60d',   'Pageview Aquisição', 'pageview-30-60d',   false),
  ('pageview-60-90d',   'Pageview Aquisição', 'pageview-60-90d',   false)
ON CONFLICT (alia_campanha) DO UPDATE
    SET flow_name    = EXCLUDED.flow_name,
        utm_campaign = EXCLUDED.utm_campaign,
        is_ignored   = false;
