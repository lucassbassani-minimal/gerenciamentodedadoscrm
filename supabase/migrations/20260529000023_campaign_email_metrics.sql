-- Migration: cria tabela campaign_email_metrics para métricas diárias de campanhas Klaviyo
-- Reversível: sim — DROP TABLE campaign_email_metrics;

CREATE TABLE IF NOT EXISTS campaign_email_metrics (
    id              uuid          NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    campaign_id     text          NOT NULL,
    campaign_name   text          NOT NULL,
    message_id      text          NOT NULL,
    data            date          NOT NULL,
    email_enviado   integer       NOT NULL DEFAULT 0,
    email_aberto    integer       NOT NULL DEFAULT 0,
    email_clicado   integer       NOT NULL DEFAULT 0,
    updated_at      timestamptz   NOT NULL DEFAULT now(),
    ingested_at     timestamptz   NOT NULL DEFAULT now(),

    CONSTRAINT campaign_email_metrics_message_id_data_key UNIQUE (message_id, data)
);

ALTER TABLE campaign_email_metrics ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon pode ler campaign_email_metrics"
    ON campaign_email_metrics FOR SELECT TO anon USING (true);

CREATE POLICY "service_role pode gravar campaign_email_metrics"
    ON campaign_email_metrics FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE INDEX IF NOT EXISTS idx_campaign_email_metrics_campaign_id
    ON campaign_email_metrics (campaign_id);

CREATE INDEX IF NOT EXISTS idx_campaign_email_metrics_data
    ON campaign_email_metrics (data);
