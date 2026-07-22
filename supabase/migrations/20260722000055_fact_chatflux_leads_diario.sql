-- Migration: cria fact_chatflux_leads_diario (totais diários de leads por vendedor do Chatflux)
-- Reversível: sim
--   DROP TABLE IF EXISTS fact_chatflux_leads_diario;
--
-- Contexto: /api/leads do Chatflux devolve totais agregados por (dia, vendedor), sem telefone —
-- diferente de fact_chatflux_events (1 linha = 1 evento real). Guardado à parte para: (1) sobreviver
-- ao limite de janela de 180 dias da API do Chatflux, (2) alimentar a exportação para a aba
-- "Base de Dados ChatFlux" do Google Sheets como linhas sintéticas de "necessita atenção".

CREATE TABLE IF NOT EXISTS fact_chatflux_leads_diario (
    id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    day           date        NOT NULL,
    segmento      text        NOT NULL CHECK (segmento IN ('Welcome Novos', 'Welcome Recorrentes', 'Carrinho Abandonado')),
    vendedor_id   integer,
    vendedor_nome text        NOT NULL,
    total_leads   integer     NOT NULL CHECK (total_leads > 0),
    ingested_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (day, segmento, vendedor_nome)
);

ALTER TABLE fact_chatflux_leads_diario ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_select_chatflux_leads_diario"
    ON fact_chatflux_leads_diario FOR SELECT TO anon USING (true);

CREATE POLICY "authenticated_select_chatflux_leads_diario"
    ON fact_chatflux_leads_diario FOR SELECT TO authenticated USING (true);

CREATE POLICY "service_role_all_chatflux_leads_diario"
    ON fact_chatflux_leads_diario FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE INDEX IF NOT EXISTS idx_chatflux_leads_diario_day ON fact_chatflux_leads_diario (day);
