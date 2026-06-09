-- Migration: filtra vw_community_message_revenue para exibir apenas msgN (msg1, msg2, msg3...)
-- Reversível: sim (CREATE OR REPLACE VIEW)
-- Motivo: outros utm_content atribuídos ao canal wpp_community (temp*, clientes, leads...)
--         não são disparos da comunidade e não devem aparecer no ranking.

CREATE OR REPLACE VIEW vw_community_message_revenue AS
WITH community_channel AS (
  SELECT id FROM dim_channels WHERE slug = 'wpp_community'
),
sessions_src AS (
  SELECT
    s.utm_content,
    SUM(s.sessions)    AS sessions,
    SUM(s.orders)      AS orders,
    SUM(s.revenue_brl) AS revenue_brl
  FROM fact_sessions_utm s
  JOIN community_channel cc ON cc.id = s.channel_id
  WHERE s.date < '2026-04-23'
    AND s.utm_content ~ '^msg\d+$'
  GROUP BY s.utm_content
),
orders_src AS (
  SELECT
    o.utm_content,
    0                          AS sessions,
    COUNT(DISTINCT o.order_id) AS orders,
    SUM(o.revenue_brl)         AS revenue_brl
  FROM fact_orders o
  JOIN community_channel cc ON cc.id = o.attributed_channel_id
  WHERE o.order_date >= '2026-04-23'
    AND o.utm_content ~ '^msg\d+$'
  GROUP BY o.utm_content
),
combined AS (
  SELECT utm_content, sessions, orders, revenue_brl FROM sessions_src
  UNION ALL
  SELECT utm_content, sessions, orders, revenue_brl FROM orders_src
),
aggregated AS (
  SELECT
    utm_content,
    SUM(sessions)    AS sessions,
    SUM(orders)      AS orders,
    SUM(revenue_brl) AS revenue_brl
  FROM combined
  GROUP BY utm_content
)
SELECT
  a.utm_content,
  a.sessions,
  a.orders,
  a.revenue_brl,
  CASE WHEN a.orders > 0 THEN a.revenue_brl / a.orders ELSE NULL END AS ticket_medio,
  m.body,
  m.media_url,
  m.updated_at AS message_updated_at,
  RANK() OVER (ORDER BY a.revenue_brl DESC) AS revenue_rank
FROM aggregated a
LEFT JOIN dim_community_messages m ON m.utm_content = a.utm_content
ORDER BY a.revenue_brl DESC;

GRANT SELECT ON vw_community_message_revenue TO anon;
