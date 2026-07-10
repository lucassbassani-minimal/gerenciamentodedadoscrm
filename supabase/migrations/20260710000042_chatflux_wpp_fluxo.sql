-- Migration: integra Chatflux (2ª ferramenta de disparo WhatsApp) ao WPP Fluxo
-- Reversível: sim
--   DROP TABLE IF EXISTS fact_chatflux_events;
--   DELETE FROM dim_wpp_alia_campanha_mapping WHERE alia_campanha = 'chatflux_abandoned_cart_ia';
--   (recriar vw_wpp_flow_leads / vw_wpp_flow_revenue / vw_wpp_flow_inscritos na versão anterior a esta migration)

-- 1. Log de eventos do Chatflux (1 linha = 1 disparo ou 1 resposta, por telefone)
CREATE TABLE IF NOT EXISTS fact_chatflux_events (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    event_timestamp  timestamptz NOT NULL,
    segmento         text        NOT NULL CHECK (segmento IN ('Welcome Novos', 'Welcome Recorrentes', 'Carrinho Abandonado')),
    etapa            text        NOT NULL CHECK (etapa IN ('disparo', 'resposta')),
    telefone         text        NOT NULL,
    ingested_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (telefone, segmento, etapa, event_timestamp)
);

ALTER TABLE fact_chatflux_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_select_chatflux_events"
    ON fact_chatflux_events FOR SELECT TO anon USING (true);

CREATE POLICY "service_role_all_chatflux_events"
    ON fact_chatflux_events FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE INDEX IF NOT EXISTS idx_chatflux_events_timestamp ON fact_chatflux_events (event_timestamp);
CREATE INDEX IF NOT EXISTS idx_chatflux_events_segmento  ON fact_chatflux_events (segmento);

-- 2. Mapeamento sintético para a receita do Carrinho Abandonado entrar em vw_wpp_flow_revenue.
--    Chatflux não tem "alia_campanha" (isso é um conceito do CSV da Vekta) — reaproveita a tabela
--    só pelo par (utm_campaign, flow_name) que a view de receita já consome.
INSERT INTO dim_wpp_alia_campanha_mapping (alia_campanha, flow_name, utm_campaign, is_ignored)
VALUES ('chatflux_abandoned_cart_ia', 'Carrinho Abandonado', 'abandoned_cart_ia', false)
ON CONFLICT (alia_campanha) DO UPDATE
    SET flow_name    = EXCLUDED.flow_name,
        utm_campaign = EXCLUDED.utm_campaign,
        is_ignored   = false;

-- 3. vw_wpp_flow_leads passa a somar Vekta (leads_webhook, como já era) + Chatflux (fact_chatflux_events),
--    com a nova coluna `ferramenta` para o dashboard poder filtrar.
--    Chatflux não tem "destravar objeção" / "necessita atenção" (fica 0) nem "Welcome Novos vs Recorrentes"
--    diferenciado (ambos somam em "Welcome Site", por decisão de produto).
DROP VIEW IF EXISTS vw_wpp_flow_leads;
CREATE VIEW vw_wpp_flow_leads AS
SELECT
    m.flow_name,
    (l.data)::date AS data,
    COUNT(CASE WHEN l.funil = 'resposta'          THEN 1 END) AS respostas,
    COUNT(CASE WHEN l.funil = 'destravar objeção'  THEN 1 END) AS destravar_objecao,
    COUNT(CASE WHEN l.funil = 'necessita atenção'  THEN 1 END) AS necessita_atencao,
    COUNT(DISTINCT l.telefone) AS total_leads,
    MAX(l.created_at) AS ingested_at,
    'vekta'::text AS ferramenta
FROM leads_webhook l
JOIN dim_wpp_origem_mapping m ON m.origem = l.origem
WHERE m.flow_name IS NOT NULL AND NOT m.is_ignored
GROUP BY m.flow_name, (l.data)::date

UNION ALL

SELECT
    CASE
        WHEN e.segmento IN ('Welcome Novos', 'Welcome Recorrentes') THEN 'Welcome Site'
        WHEN e.segmento = 'Carrinho Abandonado' THEN 'Carrinho Abandonado'
    END AS flow_name,
    (e.event_timestamp AT TIME ZONE 'America/Sao_Paulo')::date AS data,
    COUNT(*) FILTER (WHERE e.etapa = 'resposta') AS respostas,
    0 AS destravar_objecao,
    0 AS necessita_atencao,
    COUNT(DISTINCT e.telefone) FILTER (WHERE e.etapa = 'disparo') AS total_leads,
    MAX(e.ingested_at) AS ingested_at,
    'chatflux'::text AS ferramenta
FROM fact_chatflux_events e
GROUP BY 1, 2;

GRANT SELECT ON vw_wpp_flow_leads TO anon;

-- 4. vw_wpp_flow_revenue ganha a coluna `ferramenta`, derivada do par utm_campaign/utm_content
--    já usado pelo Chatflux nos links das mensagens (last-click UTM continua sendo a regra de
--    atribuição — isto é só uma subclassificação da receita já atribuída ao canal wpp_flow).
DROP VIEW IF EXISTS vw_wpp_flow_revenue;
CREATE VIEW vw_wpp_flow_revenue AS
WITH utm_map AS (
  SELECT DISTINCT ON (utm_campaign) utm_campaign, flow_name
  FROM (
    SELECT utm_campaign, flow_name
    FROM dim_wpp_alia_campanha_mapping
    WHERE utm_campaign IS NOT NULL AND flow_name IS NOT NULL AND is_ignored = false
    UNION ALL
    SELECT utm_campaign, flow_name
    FROM dim_wpp_origem_mapping
    WHERE utm_campaign IS NOT NULL AND flow_name IS NOT NULL AND is_ignored = false
  ) combined
  ORDER BY utm_campaign
)
SELECT
  m.flow_name,
  o.order_date AS data,
  COUNT(*)           AS orders,
  SUM(o.revenue_brl) AS revenue_brl,
  CASE
    WHEN o.utm_campaign = 'abandoned_cart_ia' THEN 'chatflux'
    WHEN o.utm_campaign ILIKE '%welcome%' AND o.utm_content = 'chatflux' THEN 'chatflux'
    ELSE 'vekta'
  END AS ferramenta
FROM fact_orders o
JOIN dim_channels c   ON c.id = o.attributed_channel_id AND c.slug = 'wpp_flow'
JOIN utm_map m        ON m.utm_campaign = o.utm_campaign
GROUP BY m.flow_name, o.order_date, ferramenta;

GRANT SELECT ON vw_wpp_flow_revenue TO anon;

-- 5. vw_wpp_flow_inscritos ganha `ferramenta` fixo em 'vekta' — Chatflux não expõe lista de
--    inscritos na API dele (só o log de eventos), então some ao filtrar por 'chatflux'.
DROP VIEW IF EXISTS vw_wpp_flow_inscritos;
CREATE VIEW vw_wpp_flow_inscritos AS
SELECT
    m.flow_name,
    COUNT(DISTINCT s.telefone) AS total_inscritos,
    MAX(s.ingested_at) AS ingested_at,
    'vekta'::text AS ferramenta
FROM fact_wpp_flow_subscribers s
JOIN dim_wpp_alia_campanha_mapping m ON m.alia_campanha = s.alia_campanha
WHERE m.flow_name IS NOT NULL AND NOT m.is_ignored
GROUP BY m.flow_name;

GRANT SELECT ON vw_wpp_flow_inscritos TO anon;
