-- Migration: aumenta o statement_timeout do refresh das materialized views de recompra de 5min para 8min
-- Reversível: sim
--   CREATE OR REPLACE FUNCTION refresh_repurchase_materialized_views() ... SET statement_timeout = '5min'
--
-- Contexto: o cron diário (api/cron/repurchase.py, maxDuration 800s na Vercel) falhou em
-- 2026-07-22 05:01 UTC com "canceling statement due to statement timeout" — o REFRESH
-- MATERIALIZED VIEW sempre recalcula a view inteira do zero (não existe refresh
-- incremental no Postgres), então o custo cresce com o total histórico em
-- fact_repurchase_deals (~470 mil linhas), não com quantas linhas novas chegaram no dia.
-- A ingestão diária da planilha foi tornada incremental (commit relacionado), mas isso
-- não reduz o custo do REFRESH em si. 8min dá margem segura dentro dos 800s da function
-- Vercel, mantendo espaço para os demais passos do cron (leitura da planilha, recálculo
-- mensal em Python, etc.).

CREATE OR REPLACE FUNCTION refresh_repurchase_materialized_views()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET statement_timeout = '8min'
AS $$
BEGIN
    REFRESH MATERIALIZED VIEW mv_repurchase_deals_dedup;
    REFRESH MATERIALIZED VIEW mv_repurchase_customer_first_purchase;
    REFRESH MATERIALIZED VIEW mv_repurchase_cohort_matrix;
    REFRESH MATERIALIZED VIEW mv_repurchase_ltv180;
END;
$$;

GRANT EXECUTE ON FUNCTION refresh_repurchase_materialized_views() TO service_role;
