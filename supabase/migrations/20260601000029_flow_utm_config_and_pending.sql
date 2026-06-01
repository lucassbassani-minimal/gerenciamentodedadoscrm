-- Migration: tabelas de configuração e pendências de UTM para fluxos de e-mail
-- Reversível: sim — DROP TABLE flow_utm_config; DROP TABLE flow_utm_pending;

CREATE TABLE IF NOT EXISTS flow_utm_config (
    id           uuid        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    flow_name    text        NOT NULL UNIQUE,
    utm_campaign text,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE flow_utm_config ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon pode ler flow_utm_config"    ON flow_utm_config FOR SELECT TO anon USING (true);
CREATE POLICY "service_role pode gravar flow_utm_config" ON flow_utm_config FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE TABLE IF NOT EXISTS flow_utm_pending (
    id         uuid        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    flow_name  text,
    email_name text,
    issue      text,
    mensagem   text,
    resolved   boolean     NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE flow_utm_pending ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon pode inserir flow_utm_pending" ON flow_utm_pending FOR INSERT TO anon WITH CHECK (true);
CREATE POLICY "anon pode ler flow_utm_pending"     ON flow_utm_pending FOR SELECT TO anon USING (true);
CREATE POLICY "service_role pode gravar flow_utm_pending" ON flow_utm_pending FOR ALL TO service_role USING (true) WITH CHECK (true);
