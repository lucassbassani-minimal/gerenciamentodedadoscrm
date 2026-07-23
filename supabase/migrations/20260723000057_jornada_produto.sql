-- Migration: cria as tabelas e views da análise de Jornada de Produto (aba Recompra)
-- Reversível: sim
--   DROP VIEW IF EXISTS vw_jornada_afinidade;
--   DROP VIEW IF EXISTS vw_jornada_retencao;
--   DROP TABLE IF EXISTS fact_jornada_arvore;
--   DROP TABLE IF EXISTS fact_jornada_tempo;
--   DROP TABLE IF EXISTS fact_jornada_afinidade;
--   DROP TABLE IF EXISTS fact_jornada_metricas;
--
-- Contexto: análise de comportamento sequencial de compra (produto de entrada -> o que se
-- compra na 2ª/3ª/4ª/5ª compra), construída em mc-growth/jornada_produto.py a partir de
-- bases locais (BigQuery/HubSpot, atualizadas manualmente pelo Daniel — não há API
-- automática ainda). Ingestão feita por ingestion/analytics/jornada_produto_ingest.py,
-- rodada manualmente sempre que a base local for atualizada (não é um cron contínuo,
-- igual à recompra mensal). Achado central: cross-sell é fraco — a recompra tende a
-- repetir o produto de entrada ou "Camiseta Minimal", quase nunca uma categoria nova
-- (ver Gerenciador de CRM/docs/specs/jornada-de-produto-cross-sell-resumo.md).

-- ---------------------------------------------------------------------------
-- fact_jornada_metricas: 1 linha por entrada — LTV, taxas de repetição/reativação,
-- status atual (recente/ativo/inativo). Substituída inteira a cada ingestão (upsert
-- por `entrada`, sem histórico de série temporal ainda).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fact_jornada_metricas (
    entrada             text        PRIMARY KEY,
    n_clientes          integer     NOT NULL CHECK (n_clientes >= 0),
    linhas_requeridas   text[]      NOT NULL,
    ltv_180d_media      numeric     NOT NULL,
    ltv_180d_mediana    numeric     NOT NULL,
    taxa_repeticao      numeric,
    taxa_reativacao     numeric,
    pct_recente_hoje    numeric,
    pct_ativo_hoje      numeric,
    pct_inativo_hoje    numeric,
    ingested_at         timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE fact_jornada_metricas ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_select_jornada_metricas"
    ON fact_jornada_metricas FOR SELECT TO anon USING (true);
CREATE POLICY "authenticated_select_jornada_metricas"
    ON fact_jornada_metricas FOR SELECT TO authenticated USING (true);
CREATE POLICY "service_role_all_jornada_metricas"
    ON fact_jornada_metricas FOR ALL TO service_role USING (true) WITH CHECK (true);

-- ---------------------------------------------------------------------------
-- fact_jornada_afinidade: "o que se compra em cada passo" — por presença de produto,
-- não classificação exclusiva (decisão 2026-07-23: Multiprodutos/Produto desconhecido
-- escondiam a oferta real). A linha com produto = '__RETENCAO__' guarda o número do
-- gráfico de retenção (ver vw_jornada_retencao); o resto é a lista de oferta real
-- (ver vw_jornada_afinidade).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fact_jornada_afinidade (
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    entrada             text        NOT NULL,
    compra              text        NOT NULL CHECK (compra IN ('2a', '3a', '4a', '5a')),
    produto             text        NOT NULL,
    clientes            integer     NOT NULL CHECK (clientes >= 0),
    pct_da_entrada      numeric     NOT NULL,
    n_base_da_compra    integer     NOT NULL CHECK (n_base_da_compra >= 0),
    ingested_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (entrada, compra, produto)
);

ALTER TABLE fact_jornada_afinidade ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_select_jornada_afinidade"
    ON fact_jornada_afinidade FOR SELECT TO anon USING (true);
CREATE POLICY "authenticated_select_jornada_afinidade"
    ON fact_jornada_afinidade FOR SELECT TO authenticated USING (true);
CREATE POLICY "service_role_all_jornada_afinidade"
    ON fact_jornada_afinidade FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE INDEX IF NOT EXISTS idx_jornada_afinidade_entrada ON fact_jornada_afinidade (entrada);

-- ---------------------------------------------------------------------------
-- fact_jornada_tempo: mediana/média de dias até cada compra (acumulado e entre
-- recompras), por entrada.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fact_jornada_tempo (
    id                              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    entrada                         text        NOT NULL,
    compra                          text        NOT NULL CHECK (compra IN ('2a', '3a', '4a', '5a')),
    clientes                        integer     NOT NULL CHECK (clientes >= 0),
    dias_acumulado_mediana          numeric     NOT NULL,
    dias_acumulado_media            numeric     NOT NULL,
    dias_entre_recompras_mediana    numeric     NOT NULL,
    dias_entre_recompras_media      numeric     NOT NULL,
    ingested_at                     timestamptz NOT NULL DEFAULT now(),
    UNIQUE (entrada, compra)
);

ALTER TABLE fact_jornada_tempo ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_select_jornada_tempo"
    ON fact_jornada_tempo FOR SELECT TO anon USING (true);
CREATE POLICY "authenticated_select_jornada_tempo"
    ON fact_jornada_tempo FOR SELECT TO authenticated USING (true);
CREATE POLICY "service_role_all_jornada_tempo"
    ON fact_jornada_tempo FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE INDEX IF NOT EXISTS idx_jornada_tempo_entrada ON fact_jornada_tempo (entrada);

-- ---------------------------------------------------------------------------
-- fact_jornada_arvore: a árvore de drill-down (2ª->5ª compra), 1 linha por entrada,
-- guardada como JSONB (estrutura aninhada e sempre lida inteira — não faz sentido
-- normalizar em linhas). Reconstruída em mc-growth/construir_arvore_dashboard.py a
-- partir da classificação exclusiva de produto (não a de presença — árvore precisa
-- de ramos mutuamente exclusivos).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fact_jornada_arvore (
    entrada     text        PRIMARY KEY,
    n_clientes  integer     NOT NULL CHECK (n_clientes >= 0),
    arvore      jsonb       NOT NULL,
    ingested_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE fact_jornada_arvore ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_select_jornada_arvore"
    ON fact_jornada_arvore FOR SELECT TO anon USING (true);
CREATE POLICY "authenticated_select_jornada_arvore"
    ON fact_jornada_arvore FOR SELECT TO authenticated USING (true);
CREATE POLICY "service_role_all_jornada_arvore"
    ON fact_jornada_arvore FOR ALL TO service_role USING (true) WITH CHECK (true);

-- ---------------------------------------------------------------------------
-- Views de leitura — a mesma separação que já existe no painel local: a tabela de
-- oferta (sem o sentinela de retenção) e o número de retenção isolado.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_jornada_afinidade AS
SELECT entrada, compra, produto, clientes, pct_da_entrada, n_base_da_compra, ingested_at
FROM fact_jornada_afinidade
WHERE produto <> '__RETENCAO__'
ORDER BY entrada, compra, clientes DESC;

CREATE OR REPLACE VIEW vw_jornada_retencao AS
SELECT entrada, compra, clientes AS clientes_retencao, pct_da_entrada AS pct_retencao, ingested_at
FROM fact_jornada_afinidade
WHERE produto = '__RETENCAO__';

GRANT SELECT ON vw_jornada_afinidade TO anon, authenticated;
GRANT SELECT ON vw_jornada_retencao TO anon, authenticated;
