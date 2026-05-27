-- Migration: adiciona coluna utm_content em fact_orders
-- Reversível: sim (DROP COLUMN utm_content)
--
-- Necessário para atribuição de receita a e-mails de campanha via código [emXXXX].

ALTER TABLE fact_orders ADD COLUMN IF NOT EXISTS utm_content TEXT;

CREATE INDEX IF NOT EXISTS idx_fact_orders_utm_content ON fact_orders (utm_content)
  WHERE utm_content IS NOT NULL;
