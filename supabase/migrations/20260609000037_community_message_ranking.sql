-- Migration: dim_community_messages + vw_community_message_revenue
-- Reversível: sim (DROP TABLE CASCADE remove dependências; DROP VIEW)
-- Objetivo: ranking de mensagens da comunidade por receita, com campo para
--           associar corpo de texto e URL de mídia a cada utm_content (msgXXX).

-- Tabela de dimensão: corpo e mídia de cada mensagem da comunidade
CREATE TABLE IF NOT EXISTS dim_community_messages (
  utm_content  TEXT        PRIMARY KEY,
  body         TEXT,
  media_url    TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE dim_community_messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon lê mensagens da comunidade"
  ON dim_community_messages FOR SELECT TO anon USING (true);

CREATE POLICY "service_role escreve mensagens da comunidade"
  ON dim_community_messages FOR ALL TO service_role USING (true);

-- View: ranking de mensagens por receita
-- Corte de fonte: fact_sessions_utm até 22/04/2026 | fact_orders a partir de 23/04/2026
-- Ambas filtradas por channel_id = wpp_community (sem pattern-match de UTM)
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
    AND s.utm_content IS NOT NULL
    AND s.utm_content <> ''
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
    AND o.utm_content IS NOT NULL
    AND o.utm_content <> ''
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
