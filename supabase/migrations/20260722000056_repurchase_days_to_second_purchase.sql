-- Migration: histograma de dias até a 2ª compra (recompra)
-- Reversível: sim
--   DROP VIEW IF EXISTS vw_repurchase_days_to_second_histogram;
--   DROP MATERIALIZED VIEW IF EXISTS mv_repurchase_days_to_second_purchase;
--   (recriar refresh_repurchase_materialized_views sem o REFRESH desta mv)
--
-- Contexto: quantos dias depois da 1ª compra a 2ª compra acontece, para responder
-- "em quantos dias 80% das segundas compras já ocorreram". Base: 1 linha por cliente
-- com 2ª compra (join entre mv_repurchase_deals_dedup e mv_repurchase_customer_first_purchase,
-- pegando a 1ª data de fechamento estritamente posterior à 1ª compra). Bucket final (730)
-- agrupa "730 dias ou mais" — validado com os dados reais: P80 real = 370 dias.

CREATE MATERIALIZED VIEW mv_repurchase_days_to_second_purchase AS
WITH second_purchase AS (
    SELECT d.email, MIN(d.closed_at) AS second_purchase_date
    FROM mv_repurchase_deals_dedup d
    JOIN mv_repurchase_customer_first_purchase fp USING (email)
    WHERE d.closed_at > fp.first_purchase_date
    GROUP BY d.email
)
SELECT
    fp.email,
    (sp.second_purchase_date - fp.first_purchase_date)::int AS dias_ate_segunda_compra
FROM mv_repurchase_customer_first_purchase fp
JOIN second_purchase sp USING (email);

CREATE UNIQUE INDEX idx_rd_days_to_second_email ON mv_repurchase_days_to_second_purchase (email);

GRANT SELECT ON mv_repurchase_days_to_second_purchase TO anon;
GRANT SELECT ON mv_repurchase_days_to_second_purchase TO authenticated;

-- Bucket final em 730 dias (~2 anos) agrupa a cauda longa (~20% dos clientes levam
-- mais de 1 ano para a 2ª compra — R11: cálculo aqui, JS só renderiza).
CREATE OR REPLACE VIEW vw_repurchase_days_to_second_histogram AS
WITH bucketed AS (
    SELECT LEAST(dias_ate_segunda_compra, 730) AS dias
    FROM mv_repurchase_days_to_second_purchase
),
counts AS (
    SELECT dias, COUNT(*) AS clientes
    FROM bucketed
    GROUP BY dias
)
SELECT
    dias,
    clientes,
    SUM(clientes) OVER (ORDER BY dias) AS clientes_acumulado,
    ROUND(100.0 * SUM(clientes) OVER (ORDER BY dias) / SUM(clientes) OVER (), 2) AS pct_acumulado
FROM counts
ORDER BY dias;

GRANT SELECT ON vw_repurchase_days_to_second_histogram TO anon;
GRANT SELECT ON vw_repurchase_days_to_second_histogram TO authenticated;

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
    REFRESH MATERIALIZED VIEW mv_repurchase_days_to_second_purchase;
END;
$$;

GRANT EXECUTE ON FUNCTION refresh_repurchase_materialized_views() TO service_role;
