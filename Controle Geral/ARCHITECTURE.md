# ARCHITECTURE.md — Dashboard CRM · Minimal Club

> Mapa vivo do sistema. Lido em TODA sessão. Atualizado ao FIM de toda sessão.
> Última atualização: 2026-06-09

---

## 1. Visão geral em 1 página

O sistema é composto por três partes que se encaixam como esteiras de uma fábrica.

**Parte 1 — Ingestão (esteira de entrada):** Scripts Python são executados automaticamente via **Vercel Cron Jobs**. Cada cron é responsável por uma fonte: Shopify a cada 35 minutos, Google Sheets a cada hora, E-mail Fluxo todo dia às 04:00 BRT, E-mail Campanha às 00:30 BRT, Formulários às 06:00 BRT. Os resultados de cada execução são registrados na tabela `cron_logs`. Para recuperação de dados perdidos existe o endpoint `/admin/backfill/<job>` acessível via browser. Os dados de sessão (GA4 via BigQuery) chegam por um caminho diferente: uma planilha Google Sheets atualizada de hora em hora recebe o export do BigQuery, e o script Python a lê via CSV público.

**Parte 2 — Banco de dados (coração do sistema):** O Supabase (PostgreSQL) armazena tudo. Tabelas de dimensão guardam referências estáticas (canais, ativos, formulários). Tabelas de fatos acumulam os dados diários de cada fonte. Views calculadas combinam essas tabelas e entregam os KPIs prontos — receita por canal, funil, leads, saúde da base — sem que o frontend precise fazer nenhum cálculo.

**Parte 3 — Dashboard (esteira de saída):** O arquivo `dashboard-crm.html` — com layout e visual aprovados — conecta ao Supabase via `supabase-js`. Cada seção lê a view ou tabela correspondente diretamente. O acesso é protegido por autenticação server-side via Flask + JWT Supabase (cookie `sb_token`). **AUTH_ENABLED está temporariamente em False** — reativar em breve. O dashboard está deployado na Vercel em **`gerenciadorcrm.vercel.app`** (projeto `gerenciamentodedadoscrmoficial`).

O resultado: dados de Shopify, Klaviyo e GA4 aparecem unificados num único painel, atualizados automaticamente. Vekta (WhatsApp) e Sendflow (Comunidade) ainda sem integração — aguardam Fase 2.

---

## 2. Diagrama de módulos

### Módulos ativos em produção

#### ingestion-shopify
- **Responsabilidade:** Buscar pedidos pagos do Shopify e gravá-los em `fact_orders`
- **Entry point:** `api/cron/revenue.py` → `ingestion/main.py:run_smart_shopify_ingestion()`
- **Fontes:** `ingestion/sources/shopify.py`, `ingestion/models/shopify_models.py`
- **Cron:** `*/35 * * * *` — a cada 35 minutos
- **Estado:** ✅ ativo — 103 execuções ok nos últimos 7 dias

#### ingestion-sessions
- **Responsabilidade:** Ler CSV do Google Sheets (export BigQuery) e gravar em `fact_sessions` e `fact_sessions_utm`
- **Entry point:** `api/cron/sessions.py` → `ingestion/main.py:run_sheets_ingestion()`
- **Fontes:** `ingestion/sources/google_sheets.py`, `ingestion/models/sheets_models.py`
- **Cron:** `10 * * * *` — a cada hora aos :10
- **Estado:** ✅ ativo

#### ingestion-email-structure
- **Responsabilidade:** Sincronizar estrutura de fluxos ativos (fluxos + e-mails individuais) do Klaviyo para `dim_assets` e `dim_asset_items`
- **Entry point:** `api/cron/email_structure.py` → `ingestion/flow_structure_daily.py:run_structure_sync()`
- **Fontes:** `ingestion/sources/klaviyo_structure_sync.py`
- **Cron:** `0 6 * * *` — todo dia às 03:00 BRT (06:00 UTC) — 1h antes do email_flow
- **maxDuration:** 600s
- **Por que existe:** elimina ~500 chamadas GET de estrutura do cron email_flow, que causavam 429s e timeout na Vercel
- **Estado:** ✅ ativo

#### ingestion-email-flow
- **Responsabilidade:** Buscar métricas diárias de e-mails de fluxos Klaviyo e gravar em `flow_email_metrics`
- **Entry point:** `api/cron/email_flow.py` → `ingestion/flow_metrics_daily.py:run_yesterday()`
- **Fontes:** `ingestion/sources/klaviyo_flow_metrics.py`
- **Cron:** `0 7 * * *` — todo dia às 04:00 BRT (07:00 UTC)
- **Lookback:** D-2 a D-1 (recupera automaticamente se falhou no dia anterior)
- **maxDuration:** 800s (reduzido de 900s em 2026-06-09 — limite do plano Vercel; email_flow roda em ~75s, folga suficiente)
- **Estratégia de chamadas:** por fluxo × 3 métricas com `by=['$message']` — ~99 POSTs por execução (~75s). Versão anterior fazia 1 POST por mensagem × 3 métricas (~1.566 chamadas, causava timeout)
- **Depende de:** cron `email_structure` ter rodado antes para popular `dim_asset_items`
- **Fallback manual:** botão "↻ Atualizar D-1" na aba E-mail Fluxo do dashboard chama `/admin/backfill/email_flow?since=D-1&until=D-1` — substitui o cron quando há rate limit
- **Estado:** ✅ ativo

#### ingestion-email-campaign
- **Responsabilidade:** Buscar métricas diárias de campanhas Klaviyo e gravar em `campaign_email_metrics`
- **Entry point:** `api/cron/email_campaign.py` → `ingestion/campaign_metrics_daily.py:run_yesterday()`
- **Fontes:** `ingestion/sources/klaviyo_campaign_metrics.py`
- **Cron:** `30 3 * * *` — todo dia às 00:30 BRT (03:30 UTC)
- **Lookback:** D-2 a D-1
- **Estado:** ✅ ativo

#### ingestion-forms
- **Responsabilidade:** Buscar métricas de formulários + saúde da base Klaviyo → `fact_lead_captures`, `dim_forms`, `fact_email_health`
- **Entry point:** `api/cron/forms.py` → `ingestion/main.py:run_forms_ingestion()`
- **Fontes:** `ingestion/sources/klaviyo.py` (fetch_forms, fetch_active_base_count, fetch_form_metrics_since)
- **Cron:** `0 9 * * *` — todo dia às 06:00 BRT (09:00 UTC)
- **Lookback:** sempre rebusca D-1 completo (dados Klaviyo têm lag de ~24h)
- **Estado:** ✅ ativo

#### vercel-crons
- **Responsabilidade:** Orquestrar e executar todos os crons automaticamente
- **Configuração:** `vercel.json` — 7 crons + routing + maxDuration + includeFiles
- **Projeto Vercel:** `gerenciamentodedadoscrmoficial` → `gerenciadorcrm.vercel.app`
- **Deploy:** obrigatório via `vercel --prod` (CLI) — auto-deploy do GitHub não está ativo; push no GitHub não atualiza produção sozinho
- **includeFiles:** `dashboard-crm.html` explicitamente incluído no bundle de `api/cron/app.py` — sem isso o Flask servia versão antiga cacheada
- **Estado:** ✅ ativo

#### backfill-admin
- **Responsabilidade:** Permitir recuperação manual de dados perdidos via browser
- **Entry point:** `api/cron/app.py` rota `/admin/backfill/<job>`
- **Jobs disponíveis:** `email_structure`, `email_flow`, `email_campaign`, `sessions`, `forms`, `revenue`
- **Parâmetros:** `?since=YYYY-MM-DD`, `?until=YYYY-MM-DD`
- **Exemplo:** `https://gerenciadorcrm.vercel.app/admin/backfill/email_flow?since=2026-06-02`
- **Estado:** ✅ ativo (acessível enquanto AUTH_ENABLED=False)

#### utm-config-admin
- **Responsabilidade:** Gravar ou atualizar `utm_campaign` de um fluxo diretamente em `flow_utm_config`
- **Entry point:** `api/cron/app.py` rota `POST /admin/utm-config`
- **Body:** `{ "flow_name": "...", "utm_campaign": "..." }`
- **Escrita:** upsert via `service_role_key` — segue R3
- **Chamado por:** botão "Salvar" no formulário de UTM da aba E-mail Fluxo do dashboard
- **Estado:** ✅ ativo

#### supabase-schema
- **Responsabilidade:** Definir e versionar schema do banco via migrations SQL
- **Localização:** `supabase/migrations/` — 32 migrations aplicadas
- **Estado:** ✅ ativo

#### dashboard-frontend
- **Responsabilidade:** Renderizar dados do Supabase no dashboard HTML
- **Arquivo:** `dashboard-crm.html`
- **Lê:** views `vw_*` exclusivamente — incluindo `vw_flow_email_assets` e `vw_flow_email_items` para E-mail Fluxo, `fact_orders` para receita por fluxo
- **Botão "↻ Atualizar D-1":** presente na aba E-mail Fluxo; chama `/admin/backfill/email_flow` com a data de ontem e re-renderiza a aba após ~75s
- **Formulário de UTM:** na aba E-mail Fluxo, exibe cada fluxo sem `utm_campaign` como linha com input + botão Salvar; salva via `POST /admin/utm-config`; e-mails sem `[LEADS]/[CLIENTES]` aparecem em seção informativa separada
- **Estado:** ✅ ativo

### Módulos planejados (Fase 2)

#### ingestion-community (implementado — aguardando chave API válida)
- **Responsabilidade:** Buscar releases, analytics e ações de disparo do Sendflow → `dim_assets`, `fact_community_actions`, `fact_community_analytics`
- **Entry point:** `api/cron/community.py` → `ingestion/community_daily.py:run_yesterday()`
- **Fontes:** `ingestion/sources/sendflow.py`, `ingestion/models/sendflow_models.py`
- **Cron:** `0 8 * * *` — todo dia às 05:00 BRT (08:00 UTC)
- **Backfill:** `/admin/backfill/community?since=2026-01-01` ou `python -m ingestion.community_daily --since 2026-01-01`
- **Bloqueio:** `SENDFLOW_API_KEY` no `.env` retorna 401 — verificar chave no painel do Sendflow
- **Estado:** ⏳ aguardando chave API válida

#### ingestion-vekta (implementado — via CSV + planilha, não API)
- **Responsabilidade:** Inscritos de WhatsApp Fluxo (Vekta/Alia) → `fact_wpp_flow_subscribers`; disparos/respostas por fluxo → `leads_webhook` (mapeado via `dim_wpp_origem_mapping`)
- **Entry point:** `api/cron/wpp_flow.py` → `ingestion/sources/wpp_flow_subscribers.py:run_wpp_flow_subscribers_ingestion()`
- **Fontes:** CSV público (Google Sheets export Vekta/Alia) via `WPP_FLOW_SUBSCRIBERS_CSV_URL`; `leads_webhook` alimentado por `ingestion/sources/leads_sheets_export.py` (cron `api/cron/leads_sheets.py`)
- **Cron:** `30 * * * *` (wpp_flow) e `0 * * * *` (leads_sheets)
- **Mapeamento fluxo:** `dim_wpp_alia_campanha_mapping` (por `alia_campanha`) e `dim_wpp_origem_mapping` (por `origem`) → `flow_name`; painel de conferência de UTM pendente no dashboard (`vw_wpp_flow_utm_pending`)
- **Nota:** este item do documento estava desatualizado (marcado "não iniciado"); corrigido em 2026-07-10 ao implementar o Chatflux, que depende do mesmo conjunto de views
- **Estado:** ✅ implementado

#### ingestion-chatflux (implementado — 2026-07-10)
- **Responsabilidade:** Disparos/respostas de WhatsApp da 2ª ferramenta (Chatflux) → `fact_chatflux_events`. Atua no fluxo Welcome (dividido com a Vekta, somado sob `flow_name='Welcome Site'`, sem diferenciar Novos/Recorrentes) e sozinha no fluxo novo `Carrinho Abandonado`.
- **Entry point:** `api/cron/chatflux.py` → `ingestion/sources/chatflux.py:run_chatflux_ingestion()`
- **Fonte:** API própria do Chatflux (`GET /api/eventos`, Bearer token), janela incremental de 3 dias por execução
- **Cron:** `5,35 * * * *`
- **Views atualizadas:** `vw_wpp_flow_leads`, `vw_wpp_flow_revenue`, `vw_wpp_flow_inscritos` — ganharam coluna `ferramenta` (`vekta`/`chatflux`) que alimenta o seletor Vekta/Chatflux/Ambos no dashboard (páginas "Métricas Específicas" e "Detalhamento por Fluxo" do WhatsApp Fluxo)
- **Receita por ferramenta (R4 — last-click UTM continua a regra; isto é subclassificação por cima):** `utm_campaign='abandoned_cart_ia'` → Chatflux; dentro do fluxo `welcome`, `utm_content='chatflux'` vs `utm_content='vekta'`
- **Migration:** `supabase/migrations/20260710000042_chatflux_wpp_fluxo.sql`
- **Spec:** `Gerenciador de CRM/docs/specs/chatflux-wpp-fluxo.md`
- **Estado:** ✅ implementado e validado (ingestão local + views conferidas no banco)

### Diagrama (ASCII)

```
[Shopify API]    ──→ [Cron: revenue, a cada 35min]           ──┐
[Google Sheets]  ──→ [Cron: sessions, a cada 1h]             ──┤
[Klaviyo API]    ──→ [Cron: email_structure, 03:00 BRT] ──→ dim_assets/dim_asset_items
                 ──→ [Cron: email_flow, 04:00 BRT] (lê ↑ do banco) ──┤→ [Supabase PostgreSQL]
                 ──→ [Cron: email_campaign, 00:30 BRT]       ──┤    │
                 ──→ [Cron: forms, 06:00 BRT]                ──┘    │ [views vw_*]
                                                                      │ [tabelas diretas]
[Input manual]   ──────────────────────────────────────────────→ [fact_monthly_goals]
[Admin backfill] ──→ [/admin/backfill/<job>]                 ──→     │
                                                                      ↓
                                                            [api/cron/app.py Flask]
                                                            (auth JWT Supabase — temp. desativado)
                                                                      │
                                                                      ↓
                                                            [dashboard-crm.html]
                                                            (supabase-js lê views e tabelas)
```

---

## 3. Entidades e modelo de dados

### Tabelas em produção com dados ativos

#### dim_channels
Tabela de referência dos 5 canais. Criada uma vez, raramente alterada.

| Coluna | Tipo | Notas |
|---|---|---|
| id | uuid | PK |
| name | text | Ex: "E-mail Fluxo" |
| slug | text | Ex: "email_flow" — UNIQUE |
| utm_source | text | Ex: "email" |
| utm_medium | text | Ex: "flow" — null para Comunidade |
| primary_kpi | text | "receita_inscrito" ou "receita_disparo" |
| created_at | timestamptz | — |

- **Slugs canônicos (nunca mudam sem ADR):** `email_flow`, `email_campaign`, `wpp_flow`, `wpp_campaign`, `wpp_community`
- **RLS:** SELECT para anon; sem escrita externa

---

#### dim_assets
Ativos pai: fluxos e campanhas sincronizados das ferramentas de origem.

| Coluna | Tipo | Notas |
|---|---|---|
| id | uuid | PK |
| external_id | text | ID no Klaviyo/Vekta/Sendflow |
| channel_id | uuid | FK → dim_channels |
| name | text | Nome na ferramenta de origem |
| type | text | "flow" ou "campaign" |
| is_active | boolean | false = desativado na ferramenta |
| source_tool | text | "klaviyo" \| "vekta" \| "sendflow" |
| created_at / updated_at / ingested_at | timestamptz | — |

- **Índices:** `(external_id, source_tool)` UNIQUE
- **RLS:** SELECT anon; INSERT/UPDATE service_role

---

#### dim_asset_items
Ativos filho: e-mails individuais dentro de fluxos/campanhas.

| Coluna | Tipo | Notas |
|---|---|---|
| id | uuid | PK |
| external_id | text | ID na ferramenta de origem |
| asset_id | uuid | FK → dim_assets |
| name | text | Subject line ou preview do template |
| type | text | "email" ou "wpp_template" |
| position | integer | Posição no fluxo (1, 2, 3…) |
| created_at / updated_at / ingested_at | timestamptz | — |

- **Índices:** `(external_id, type)` UNIQUE

---

#### dim_forms
Formulários e popups de captação de leads do Klaviyo.

| Coluna | Tipo | Notas |
|---|---|---|
| id | uuid | PK |
| external_id | text | Klaviyo Form ID — UNIQUE |
| name | text | Nome do formulário |
| type | text | "popup" \| "form" \| "embed" |
| position | text | Ex: "Home", "Footer" |
| is_active | boolean | — |
| created_at / ingested_at | timestamptz | — |

---

#### fact_orders
Pedidos pagos do Shopify com atribuição de canal por UTM.

| Coluna | Tipo | Notas |
|---|---|---|
| id | uuid | PK |
| order_id | text | Shopify Order ID — UNIQUE |
| order_date | date | Data do pedido |
| revenue_brl | numeric(12,2) | Valor em reais |
| attributed_channel_id | uuid | FK → dim_channels — null se sem UTM de CRM |
| utm_source / utm_medium / utm_campaign / utm_term / utm_content | text | Valores brutos da UTM |
| shopify_customer_id | text | ID do cliente |
| is_first_purchase | boolean | true se orders_count = 1 |
| ingested_at | timestamptz | — |

- **Invariante:** `revenue_brl > 0`; pedidos sem UTM de CRM ficam com `attributed_channel_id = null`

---

#### fact_sessions
Sessões, ATC e BCO por canal por dia — origem: Google Sheets / BigQuery.

| Coluna | Tipo | Notas |
|---|---|---|
| id | uuid | PK |
| date | date | — |
| channel_id | uuid | FK → dim_channels |
| sessions | integer | — |
| add_to_cart | integer | ATC |
| begin_checkout | integer | BCO |
| orders | integer | Compras atribuídas |
| revenue_brl | numeric | Receita atribuída |
| ingested_at | timestamptz | — |

- **Índices:** `(date, channel_id)` UNIQUE

---

#### fact_sessions_utm
Versão granular de `fact_sessions` — quebrada por UTM completa. Alimentada pelo cron de sessões. **Reservada para Fase 3 (mapeamento de UTMs)** — não consumida atualmente.

---

#### flow_email_metrics
Métricas diárias por e-mail individual de fluxo Klaviyo — **tabela principal do E-mail Fluxo**.

| Coluna | Tipo | Notas |
|---|---|---|
| id | uuid | PK |
| flow_id | text | ID do fluxo no Klaviyo |
| flow_name | text | Nome do fluxo |
| message_id | text | ID da flow-message |
| message_name | text | Nome da mensagem |
| data | date | Data da métrica |
| email_enviado | integer | Disparos |
| email_aberto | integer | Aberturas |
| email_clicado | integer | Cliques |
| updated_at | timestamptz | — |

- **Índices:** `(message_id, data)` UNIQUE
- **Lida por:** dashboard direto + `vw_email_channel_daily`

---

#### campaign_email_metrics
Métricas diárias por campanha Klaviyo — **tabela principal do E-mail Campanha**. Estrutura idêntica a `flow_email_metrics`.

- **Lida por:** `vw_campaign_email_metrics`

---

#### flow_utm_config
Mapeamento de `flow_name` → `utm_campaign` para atribuição de receita por fluxo.

| Coluna | Tipo | Notas |
|---|---|---|
| id | uuid | PK |
| flow_name | text | Join com flow_email_metrics |
| utm_campaign | text | Valor de utm_campaign nos links |

- **Lida por:** dashboard (cálculo de receita por fluxo)

---

#### fact_lead_captures
Performance de formulários e popups por dia — origem: Klaviyo Forms API.

| Coluna | Tipo | Notas |
|---|---|---|
| id | uuid | PK |
| date | date | — |
| form_id | uuid | FK → dim_forms |
| impressions | integer | Visualizações |
| submissions | integer | Inscrições |
| ingested_at | timestamptz | — |

- **Índices:** `(date, form_id)` UNIQUE
- **Lida por:** `vw_leads_daily`, `vw_form_performance`

---

#### fact_email_health
Saúde da base de e-mail por canal — origem: Klaviyo API (segmento Engaged 90d).

| Coluna | Tipo | Notas |
|---|---|---|
| id | uuid | PK |
| date | date | — |
| channel_id | uuid | FK → dim_channels (apenas e-mail) |
| active_base_count | integer | Engajados 90d |
| delivery_rate / bounce_rate / spam_complaint_rate / opt_out_rate | numeric | Taxas |
| ingested_at | timestamptz | — |

- **Estado:** dados gravados pelo cron `forms` — **ainda não conectada ao dashboard** (dashboard usa mock). Próxima versão substituirá o mock por `vw_email_health`.

---

#### cron_logs
Registro de execuções dos cron jobs — usado pelo banner de alertas no dashboard.

| Coluna | Tipo | Notas |
|---|---|---|
| id | uuid | PK |
| job | text | revenue, sessions, email_flow, email_campaign, forms |
| status | text | "ok" ou "error" |
| message | text | Mensagem de erro |
| ran_at | timestamptz | Timestamp da execução |

---

#### fact_order_history_items
Histórico de pedidos pagos do Shopify com **item de linha (produto)** — origem: export manual do Shopify (CSV), não API/cron. Tabela isolada para análise de recompra/LTV por produto; não alimenta o dashboard e não substitui `fact_orders`.

| Coluna | Tipo | Notas |
|---|---|---|
| id | uuid | PK |
| order_name | text | Número do pedido no Shopify (não UUID) |
| shopify_order_id | text | Id interno do Shopify |
| line_number | integer | Posição do item dentro do pedido |
| email | text | E-mail do cliente |
| financial_status | text | Sempre "paid" — únicos carregados (R5) |
| paid_at | timestamptz | Nulo em ~0,07% dos pedidos pagos (pedidos sem esse campo no export do Shopify) |
| created_at_shopify | timestamptz | Data de criação do pedido |
| order_total_brl / order_subtotal_brl | numeric | Repetido em todas as linhas do mesmo pedido |
| discount_code / discount_amount_brl | text / numeric | — |
| shipping_method | text | — |
| billing_province | text | Estado de cobrança |
| lineitem_quantity / lineitem_name / lineitem_price / lineitem_sku | — | Dados do produto da linha |
| ingested_at | timestamptz | — |

- **Índice único:** `(order_name, line_number)`
- **Cobertura:** pedidos pagos de 2025-01-06 a 2026-07-01 (limite do export disponível — não é histórico completo desde 2021, diferente da planilha `vendas_historico` usada na análise de recompra)
- **Carga:** `python -m ingestion.backfill.load_order_history` — script avulso, não cron. Fonte: pasta local `Todos os pedidos Minimal/` (fora do git)
- **RLS:** SELECT anon; INSERT/UPDATE/UPSERT service_role

---

#### mv_order_history_category
Materialized view sobre `fact_order_history_items` — categoria de produto dominante (maior valor) por pedido. Existe como view materializada (não view normal) porque a versão original com `row_number() OVER` estourava `statement_timeout` em leitura paginada externa.

- **Colunas:** `order_name, email, paid_at, created_at_shopify, order_total_brl, categoria_dominante`
- **Categorias:** Camiseta, Calça, Camisa Social/Polo, Jaqueta/Overshirt, Tricot/Henley, Cueca, Acessório (Carteira/Perfume), Cuidado Facial, Outro — classificação por `ILIKE` no `lineitem_name`
- **Precisa `REFRESH MATERIALIZED VIEW` manual** se `fact_order_history_items` receber nova carga
- **RLS:** GRANT SELECT para anon e service_role

---

#### Materialized views de análise de recompra/LTV (não usadas pelo dashboard)
Construídas na sessão de 02/07/2026 para o diagnóstico "como aumentar o LTV de 30 dias via recompra". Todas em cima de `fact_order_history_legacy` e/ou `fact_order_history_items` — nenhuma toca `fact_orders` ou views do dashboard.

| View | O que entrega |
|---|---|
| `mv_customer_purchase_sequence` | Cada pedido de cada cliente numerado por ordem (seq), com dias desde o pedido anterior |
| `mv_customer_ltv_windows` | Por cliente: LTV e nº de recompras nas janelas 7/15/30/45/60/90/180d e total — recompra exige `order_date > first_purchase_date` (pedidos duplicados no mesmo dia não contam) |
| `mv_order_dominant_product` | Produto (modelo, sem cor/tamanho — `split_part(lineitem_name,' - ',1)`) de maior valor por pedido |
| `mv_purchase_sequence_product` | Produto de cada compra (não só a 1ª) onde há dado de produto disponível |
| `mv_first_purchase_category` / `mv_first_purchase_product` | Categoria/produto da 1ª compra de cada cliente, cruzando `fact_order_history_legacy` com `mv_order_history_category`/`mv_order_dominant_product` por e-mail+data (fuso America/Sao_Paulo), com desempate por proximidade de valor quando há 2 pedidos no mesmo dia |

- **Precisam `REFRESH MATERIALIZED VIEW` manual** em cadeia se as tabelas-fonte receberem nova carga (`mv_customer_purchase_sequence` → `mv_customer_ltv_windows`/`mv_purchase_sequence_product` → `mv_first_purchase_*`)
- **RLS:** GRANT SELECT para anon e service_role, mesmo padrão de `mv_order_history_category`

---

#### fact_order_history_legacy
Histórico de pedidos por e-mail desde 2021 (planilha Google Sheets/BigQuery, sem produto) — usada para funil de recompra, LTV e cohorts de base inteira. Complementa `fact_order_history_items` (que só tem produto a partir de 2025-01).

| Coluna | Tipo | Notas |
|---|---|---|
| id | uuid | PK |
| email | text | — |
| order_date | date | — |
| revenue_brl | numeric(12,2) | — |
| ingested_at | timestamptz | — |

- **Sem chave única de pedido** (fonte não tem order_id) — carga é truncate + insert completo, não upsert incremental
- **Cobertura:** 25/10/2021 a 01/07/2026 — 499.280 linhas válidas de 500.000 (720 descartadas por data/valor/e-mail inválido)
- **Carga:** `python -m ingestion.backfill.load_order_history_legacy --csv <caminho>` — script avulso, não cron
- **RLS:** SELECT anon; INSERT/UPDATE/DELETE service_role

---

### Tabelas de comunidade (criadas — aguardando dados)

#### fact_community_actions
Ações de disparo da comunidade (sendMessages) — uma linha por ação no Sendflow.

| Coluna | Tipo | Notas |
|---|---|---|
| id | uuid | PK |
| action_id | text | ID da ação no Sendflow — UNIQUE |
| release_id | text | ID da release (campanha) no Sendflow |
| asset_id | uuid | FK → dim_assets |
| channel_id | uuid | FK → dim_channels (wpp_community) |
| action_date | date | Data da ação (de createdAt) |
| action_type | text | 'sendMessages' etc. |
| success | boolean | — |
| scheduled_to | timestamptz | — |
| finished_at | timestamptz | — |
| ingested_at | timestamptz | — |

#### fact_community_analytics
Analytics de crescimento por release por dia — entradas, saídas e cliques.

| Coluna | Tipo | Notas |
|---|---|---|
| id | uuid | PK |
| date | date | — |
| release_id | text | — |
| asset_id | uuid | FK → dim_assets |
| channel_id | uuid | FK → dim_channels (wpp_community) |
| members_added | integer | Entradas no dia |
| members_removed | integer | Saídas no dia |
| link_clicks | integer | Cliques no link de entrada |
| total_members | integer | Snapshot atual (só data mais recente) |
| ingested_at | timestamptz | — |

- **Chave única:** `(date, release_id)`

### Tabelas para fases futuras (vazias)

| Tabela | Fase | Aguarda |
|---|---|---|
| `fact_wpp_sends` | 2 | Integração Vekta |
| `fact_wpp_subscribers` | 2 | Integração Vekta |
| `fact_monthly_goals` | 2 | Input manual das metas (estrutura pronta, dashboard tem placeholder) |
| `dim_utm_mappings` | 3 | Classificação manual de UTMs não reconhecidas |
| `flow_utm_pending` | 3 | Processamento de UTMs pendentes (dashboard já escreve, nada processa) |

---

### Views em produção

| View | O que entrega | Lida por |
|---|---|---|
| `vw_channel_daily` | Receita, compras, sessões, conversão, TKM, RPS por canal e dia | Dashboard (Resumo + todas as abas de canal) |
| `vw_revenue_first_repeat` | Receita por (data, tipo) — 1ª compra vs recompra | Dashboard (gráfico diário 1ª vs Recompra) |
| `vw_revenue_by_channel_type` | Receita por (data, canal, tipo) | Dashboard (filtro Tipo de Cliente) |
| `vw_leads_daily` | Leads por dia por formulário | Dashboard (Captação de Leads) |
| `vw_form_performance` | Performance acumulada por formulário | Dashboard (tabela Formulários e Popups) |
| `vw_email_channel_daily` | Disparos, aberturas, cliques por canal de e-mail por dia | Dashboard (Métricas específicas E-mail Fluxo/Campanha) |
| `vw_campaign_email_metrics` | Performance por campanha com receita atribuída | Dashboard (tabela E-mail Campanha) |
| `vw_flow_email_assets` | Disparos/aberturas/cliques por `(flow_id, flow_name, data)` + `utm_campaign` via JOIN com `flow_utm_config` | Dashboard (Detalhamento por Fluxo, Rankings, Receita/Inscrito) |
| `vw_flow_email_items` | Disparos/aberturas/cliques por `(message_id, message_name, data)` — para drill-down por e-mail dentro do fluxo | Dashboard (tabela de e-mails ao clicar num fluxo, cálculo de inscritos) |

### Views prontas mas não conectadas ao dashboard (próxima versão)

| View | O que entrega | Quando conectar |
|---|---|---|
| `vw_email_health` | Saúde da base (entregabilidade, base ativa) | Quando substituir o mock de saúde da base no Resumo CRM |
| `vw_pace_vs_goals` | % atingido, projeção de fechamento vs meta | Quando `fact_monthly_goals` for preenchida |
| `vw_community_daily` | Disparos, membros, cliques, receita, Receita/Disparo por dia | Quando backfill do Sendflow for executado com chave válida |

### Funções do banco

| Função | Tipo | Uso |
|---|---|---|
| `rls_auto_enable` | utilitário | Ativa RLS automaticamente em novas tabelas |
| `fn_check_wpp_subscriber_asset` | trigger | Validação de subscribers WhatsApp — ativa quando Fase 2 entrar |

---

## 4. Fluxos de dados

### Fluxo 1 — Cron de receita (Shopify, a cada 35min)

1. **Trigger:** Vercel Cron → `GET /api/cron/revenue`
2. **Executa:** `run_smart_shopify_ingestion()` — busca pedidos desde MAX(order_date) - 2 dias
3. **Validações:** apenas `financial_status = "paid"`; UTM mapeada para `channel_id`
4. **Grava:** upsert em `fact_orders` por `order_id`
5. **Log:** `cron_logs` com status ok/error

---

### Fluxo 2 — Cron de sessões (Google Sheets, horário)

1. **Trigger:** Vercel Cron → `GET /api/cron/sessions`
2. **Executa:** `run_sheets_ingestion()` — lê CSV completo de `GOOGLE_SHEETS_CSV_URL`
3. **Validações:** colunas obrigatórias, parse de data BR, tipos Pydantic
4. **Grava:** upsert em `fact_sessions` + `fact_sessions_utm` por `(date, channel_id)`
5. **Log:** `cron_logs`

---

### Fluxo 3a — Cron de estrutura de fluxos (Klaviyo, diário às 03h BRT)

1. **Trigger:** Vercel Cron → `GET /api/cron/email_structure`
2. **Executa:** `run_structure_sync()` — busca fluxos ativos e seus e-mails individuais
3. **Processo:** lista fluxos `status=live` → para cada fluxo, busca flow-actions → flow-messages
4. **Grava:** upsert em `dim_assets` (fluxos) e `dim_asset_items` (e-mails) por `external_id`
5. **Duração:** ~8-10 minutos — maxDuration: 600s

### Fluxo 3b — Cron de e-mail fluxo (Klaviyo, diário às 04h BRT)

1. **Trigger:** Vercel Cron → `GET /api/cron/email_flow`
2. **Executa:** `run_yesterday()` — busca D-2 a D-1
3. **Processo:** lê estrutura de `dim_assets` + `dim_asset_items` (zero chamadas GET ao Klaviyo) → agrupa mensagens por fluxo → para cada fluxo × 3 métricas, chama `metric-aggregates` com `by=['$message']` recebendo breakdown de todas as mensagens numa chamada
4. **Grava:** upsert em `flow_email_metrics` por `(message_id, data)`
5. **Duração:** ~75s (~99 chamadas POST) — maxDuration: 900s

---

### Fluxo 4 — Cron de e-mail campanha (Klaviyo, diário às 00h30 BRT)

1. **Trigger:** Vercel Cron → `GET /api/cron/email_campaign`
2. **Executa:** `run_yesterday()` — busca D-2 a D-1
3. **Grava:** upsert em `campaign_email_metrics` por `(message_id, data)`

---

### Fluxo 5 — Cron de formulários (Klaviyo, diário às 06h BRT)

1. **Trigger:** Vercel Cron → `GET /api/cron/forms`
2. **Executa:** `run_forms_ingestion()` — sempre rebusca desde D-1 (corrige parciais do Klaviyo)
3. **Grava:** `dim_forms` + `fact_lead_captures` + `fact_email_health`

---

### Fluxo 6 — Consulta ao dashboard (tempo real, sob demanda)

1. **Trigger:** usuário abre `gerenciadorcrm.vercel.app` ou aplica filtro
2. **Auth:** Flask verifica cookie `sb_token` (temporariamente desativado)
3. **Queries:** `supabase-js` consulta views e tabelas com filtros de data e channel_slug
4. **Renderização:** JavaScript recebe JSON e renderiza — sem cálculo de KPI no frontend

---

### Fluxo 7 — Backfill manual (sob demanda)

1. **Trigger:** abrir URL no browser → `GET /admin/backfill/<job>?since=YYYY-MM-DD`
2. **Executa:** a função de ingestão correspondente com a data informada
3. **Exemplos de uso:**
   - `/admin/backfill/email_flow?since=2026-06-02` — recupera dia específico
   - `/admin/backfill/forms?since=2026-06-02` — corrige dados parciais
   - `/admin/backfill/sessions` — refaz última leitura do Sheets
4. **Log:** registra em `cron_logs` ao terminar

---

## 5. Decisões arquiteturais já tomadas

| Data | Decisão | Por quê | Impede no futuro |
|---|---|---|---|
| 2026-05-14 | Atribuição last-click via UTM | Única regra implementável com os dados disponíveis | Atribuição multi-touch exige refatoração de `fact_orders` e views |
| 2026-05-14 | Frontend em HTML puro (sem framework) | Dashboard aprovado; sem motivo para reescrever | Funcionalidades avançadas exigirão framework |
| 2026-05-14 | BigQuery → Google Sheets → Supabase para sessões | Acesso direto ao BigQuery indisponível na V1 | Migração para BigQuery direto exige service account |
| 2026-05-14 | Apenas pedidos pagos no sistema | Bases da Minimal Club só expõem pedidos pagos | Reembolsos exigirão campo `status` em `fact_orders` |
| 2026-05-26 | Railway removido — ingestão via Edge Function | Scheduler no Railway ficou instável | — |
| 2026-06-01 | Migração para Vercel Cron Jobs | Crons nativos da Vercel; sem servidor externo; logs em `cron_logs` | Muitas fontes simultâneas podem exigir Vercel Queues |
| 2026-06-01 | Autenticação server-side via Flask + JWT Supabase | Dashboard interno; cookie `sb_token` | Usuários externos exigiriam Supabase Auth flow completo |
| 2026-06-01 | `flow_email_metrics` separada de `fact_email_sends` | Granularidade de flow-message × dia; evita mistura com campanhas | Unificação futura exige migration |
| 2026-06-03 | Dashboard consulta `vw_flow_email_assets` e `vw_flow_email_items` (views) em vez de `flow_email_metrics` direto | Queries diretas à tabela via supabase-js retornavam array vazio no browser; views (security definer) contornam o problema. Segue R11. | Queries diretas a `flow_email_metrics` via anon key são instáveis — sempre usar view |
| 2026-06-03 | Crons com lookback D-2 a D-1 | Auto-recuperação: se cron falhar um dia, a próxima execução recupera automaticamente | — |
| 2026-06-05 | Estrutura de fluxos cacheada em `dim_assets`/`dim_asset_items` via cron separado | Eliminação de ~500 chamadas GET/dia que causavam 429s e timeout no cron email_flow | Novas métricas de fluxo exigem atualização do cron email_structure |
| 2026-06-08 | email_flow usa `by=['$message']` por fluxo (não por mensagem) | Reduz ~1.566 para ~99 POSTs; execução de ~15min para ~75s; resolve timeout Vercel | — |
| 2026-06-03 | Endpoint `/admin/backfill/<job>` para recuperação manual | Permite backfill via browser sem precisar de CRON_SECRET ou CLI | Requer AUTH_ENABLED=True para segurança em produção |
| 2026-06-09 | maxDuration do email_flow reduzido de 900 para 800s | 900s excedia o limite do plano Vercel e bloqueava todos os deploys; email_flow roda em ~75s, folga suficiente | — |
| 2026-06-09 | Deploy obrigatório via `vercel --prod` | Auto-deploy do GitHub não está configurado no projeto; push no GitHub não atualiza produção | Configurar GitHub Integration no painel Vercel para eliminar passo manual |
| 2026-06-09 | `includeFiles: dashboard-crm.html` em `vercel.json` | Sem isso, Vercel servia versão cacheada do HTML mesmo após deploy com código novo | Qualquer novo arquivo lido em runtime por Flask precisa de entrada em includeFiles |
| 2026-06-09 | Botão manual "↻ Atualizar D-1" no dashboard (E-mail Fluxo) | Cron email_flow continua recebendo rate limit do Klaviyo; botão permite atualização sob demanda sem depender do cron | — |
| 2026-06-09 | Configuração de UTM via formulário estruturado no dashboard | Substituiu textarea freeform + dependência de sessão com Claude; grava direto em `flow_utm_config` via `POST /admin/utm-config` com service_role_key | — |
| 2026-07-02 | `fact_order_history_items` como tabela isolada, alimentada por backfill manual de CSV (não API/cron) | Análise de recompra/LTV precisa de produto por pedido, que `fact_orders` não guarda; evitar tocar na tabela de receita/atribuição já validada | Se precisar de produto em tempo real no dashboard, exigirá cron dedicado lendo a API de Orders do Shopify (não só o webhook/API atual usada por `fact_orders`) |

---

## 6. Pontos frágeis conhecidos

### Google Sheets como intermediário de sessões
- **Risco:** mudança no nome de coluna da planilha quebra a ingestão silenciosamente
- **Sinal de falha:** dashboard sem dados de Sessões/RPS/Conversão; banner vermelho
- **Plano:** aceitar na V1; migrar para BigQuery API direto na V2

### Cron de e-mail fluxo — volume de chamadas API
- **Risco:** se novos fluxos forem criados, o número de chamadas POST aumenta proporcionalmente (~3 por fluxo)
- **Sinal de falha:** ausência de log em `cron_logs` para `email_flow`; ou `email_flow` logando "no_flow_messages_in_db" (indica que `email_structure` falhou antes)
- **Mitigação aplicada (2026-06-05):** estrutura cacheada em `dim_assets`/`dim_asset_items` — elimina ~500 chamadas GET por execução
- **Mitigação aplicada (2026-06-08):** por fluxo com `by=['$message']` — reduz de ~1.566 para ~99 POSTs; execução caiu de ~15min para ~75s; resolve o timeout que causou falhas desde 05/06

### Cron de estrutura de fluxos — risco de timeout na Vercel
- **Risco:** localmenteo cron email_structure levou ~499s (dentro do limite de 600s), mas com mais 429s pode ultrapassar
- **Sinal de falha:** `email_flow` logando "no_flow_messages_in_db" mesmo com `email_structure` aparentemente executando
- **Monitoramento:** verificar duração real nos logs da Vercel se os 429s se tornarem mais frequentes

### AUTH_ENABLED=False temporariamente
- **Risco:** dashboard e endpoint `/admin/backfill/*` acessíveis publicamente
- **Plano:** reativar assim que as contas de acesso forem criadas (endpoint `/auth/create-user` disponível)

### UTMs inconsistentes nos links de CRM
- **Risco:** pedidos sem UTM ficam fora do dashboard (`attributed_channel_id = null`)
- **Plano:** auditar todos os links ativos antes de qualquer análise de atribuição

### fact_email_health não conectada ao dashboard
- **Risco:** dados de saúde da base são coletados mas não exibidos (dashboard usa valores hardcoded)
- **Plano:** substituir mock por `vw_email_health` na próxima versão

---

## 7. Inventário de arquivos críticos

| Caminho | Responsabilidade | Quem deve mexer |
|---|---|---|
| `dashboard-crm.html` | Dashboard visual — fonte única de verdade do frontend | Apenas substituição de dados/lógica; HTML/CSS estrutural intocável |
| `api/cron/app.py` | Flask: serve dashboard + auth + 6 endpoints de cron + admin backfill | Claude ao adicionar rota ou cron |
| `api/cron/email_structure.py` | Entry point do cron email_structure (maxDuration: 600s) | Claude ao ajustar throttle |
| `api/cron/email_flow.py` | Entry point do cron email_flow (maxDuration: 900s) | Claude ao ajustar janela ou throttle |
| `api/cron/email_campaign.py` | Entry point do cron email_campaign | Claude ao ajustar janela |
| `api/cron/revenue.py` | Entry point do cron de receita Shopify | — |
| `api/cron/sessions.py` | Entry point do cron de sessões | — |
| `api/cron/forms.py` | Entry point do cron de formulários | — |
| `ingestion/db/writers.py` | Todas as funções de upsert no Supabase | Claude com cuidado — afeta todas as fontes |
| `ingestion/flow_metrics_daily.py` | Runner do email_flow — lê estrutura do banco via `get_flow_message_structure` | Claude ao ajustar lookback ou throttle |
| `ingestion/flow_structure_daily.py` | Runner do email_structure — sincroniza dim_assets/dim_asset_items | Claude ao ajustar throttle |
| `ingestion/campaign_metrics_daily.py` | Runner do email_campaign | Claude ao ajustar lookback |
| `ingestion/main.py` | Entry points: shopify, sessions, forms | Claude ao ajustar janelas |
| `ingestion/sources/klaviyo_flow_metrics.py` | Lógica de busca de métricas via Klaviyo metric-aggregates API — lê estrutura do banco | Claude com cuidado — throttle sensível |
| `ingestion/sources/klaviyo_structure_sync.py` | Lógica de sincronização de estrutura de fluxos (dim_assets + dim_asset_items) | Claude ao ajustar throttle |
| `supabase/migrations/` | Schema do banco versionado | NUNCA editar migration já aplicada — sempre criar nova |
| `ingestion/backfill/load_order_history.py` | Backfill manual (não cron) de `fact_order_history_items` a partir de export CSV do Shopify | Claude ao rodar novo backfill; sempre `--dry-run` antes |
| `ingestion/backfill/load_order_history_legacy.py` | Backfill manual (não cron) de `fact_order_history_legacy` a partir da planilha de pedidos por e-mail (truncate + insert completo) | Claude ao recarregar; sempre `--dry-run` antes |
| `vercel.json` | Crons, routing, maxDuration | Claude ao adicionar cron ou ajustar timeout |
| `.env` | Credenciais reais | Apenas Daniel — Claude nunca lê nem commita |
| `PRODUCT.md` | Fonte de verdade do domínio | Claude + Daniel quando produto muda |
| `CLAUDE.md` | Regras de operação do agente | Claude + Daniel quando convenções mudam |
