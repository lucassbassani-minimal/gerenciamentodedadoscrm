-- Migration: cria tabela flow_email_metrics para métricas diárias de e-mails de fluxos Klaviyo
-- Reversível: sim — DROP TABLE flow_email_metrics;

CREATE TABLE IF NOT EXISTS flow_email_metrics (
    id            uuid          NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    flow_id       text          NOT NULL,
    flow_name     text          NOT NULL,
    message_id    text          NOT NULL,
    message_name  text          NOT NULL,
    data          date          NOT NULL,
    email_enviado integer       NOT NULL DEFAULT 0,
    email_aberto  integer       NOT NULL DEFAULT 0,
    email_clicado integer       NOT NULL DEFAULT 0,
    updated_at    timestamptz   NOT NULL DEFAULT now(),
    ingested_at   timestamptz   NOT NULL DEFAULT now(),

    CONSTRAINT flow_email_metrics_message_id_data_key UNIQUE (message_id, data)
);

ALTER TABLE flow_email_metrics ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon pode ler flow_email_metrics"
    ON flow_email_metrics FOR SELECT TO anon USING (true);

CREATE POLICY "service_role pode gravar flow_email_metrics"
    ON flow_email_metrics FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE INDEX IF NOT EXISTS idx_flow_email_metrics_flow_id
    ON flow_email_metrics (flow_id);

CREATE INDEX IF NOT EXISTS idx_flow_email_metrics_message_id
    ON flow_email_metrics (message_id);

CREATE INDEX IF NOT EXISTS idx_flow_email_metrics_data
    ON flow_email_metrics (data);
