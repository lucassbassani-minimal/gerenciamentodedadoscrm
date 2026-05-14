# ARCHITECTURE.md — Dashboard CRM · Minimal Club

> Mapa vivo do sistema. Lido em TODA sessão. Atualizado ao FIM de toda sessão.

---

## 1. Visão geral em 1 página

O sistema é composto por três partes que se encaixam como esteiras de uma fábrica.

**Parte 1 — Ingestão (esteira de entrada):** Um conjunto de scripts Python roda a cada 30 minutos num servidor Railway. Cada script é responsável por uma fonte de dados (Shopify, Klaviyo, Vekta, Sendflow, Google Sheets). Ele puxa os dados via API, valida com Pydantic e grava nas tabelas de fatos do Supabase. Os dados de sessão (GA4 via BigQuery) chegam por um caminho diferente: uma planilha Google Sheets atualizada de hora em hora recebe o export do BigQuery, e o script Python a lê via API.

**Parte 2 — Banco de dados (coração do sistema):** O Supabase (PostgreSQL) armazena tudo. Tabelas de dimensão guardam referências estáticas (canais, ativos, formulários). Tabelas de fatos acumulam os dados diários de cada fonte. Views calculadas combinam essas tabelas e entregam os KPIs prontos — receita por canal, funil, pace vs meta, saúde da base — sem que o frontend precise fazer nenhum cálculo.

**Parte 3 — Dashboard (esteira de saída):** O arquivo `dashboard-crm.html` existente — com layout e visual já aprovados — substitui seus dados mock por chamadas à API REST do Supabase via `supabase-js`. Cada seção do dashboard lê a view correspondente. Filtros de período, canal, tipo de cliente e ativo são passados como parâmetros na query.

O resultado: dados de Shopify, Klaviyo, Vekta, Sendflow e GA4 aparecem unificados num único painel, atualizados automaticamente, sem intervenção manual (exceto metas mensais, inseridas uma vez por mês).

---

## 2. Diagrama de módulos

### Lista de módulos

#### ingestion-shopify
- **Responsabilidade:** Buscar pedidos pagos do Shopify e gravá-los em `fact_orders`
- **Depende de:** Shopify Admin API, `ingestion/db/writers.py`, `ingestion/models/shopify_models.py`
- **Quem depende:** `scheduler`
- **Estado:** planejado

#### ingestion-klaviyo
- **Responsabilidade:** Buscar métricas de e-mail (fluxos, campanhas, formulários, saúde da base) do Klaviyo e gravá-las nas tabelas fact correspondentes
- **Depende de:** Klaviyo API, `ingestion/db/writers.py`, `ingestion/models/klaviyo_models.py`
- **Quem depende:** `scheduler`
- **Estado:** planejado

#### ingestion-vekta
- **Responsabilidade:** Buscar métricas de disparos e respostas de WhatsApp do Vekta e gravá-las em `fact_wpp_sends`
- **Depende de:** Vekta API (ou export CSV como fallback), `ingestion/db/writers.py`
- **Quem depende:** `scheduler`
- **Estado:** planejado

#### ingestion-sendflow
- **Responsabilidade:** Buscar dados de participantes e disparos da Comunidade WhatsApp do Sendflow
- **Depende de:** Sendflow API (ou export manual como fallback), `ingestion/db/writers.py`
- **Quem depende:** `scheduler`
- **Estado:** planejado

#### ingestion-sheets
- **Responsabilidade:** Ler dados de Sessões/ATC/BCO da planilha Google Sheets (export do BigQuery) e gravá-los em `fact_sessions`
- **Depende de:** Google Sheets API (gspread), `ingestion/db/writers.py`
- **Quem depende:** `scheduler`
- **Estado:** planejado

#### scheduler
- **Responsabilidade:** Orquestrar a execução de todos os módulos de ingestão a cada 30 minutos
- **Depende de:** todos os módulos `ingestion-*`
- **Quem depende:** Railway (hospeda e executa)
- **Estado:** planejado

#### supabase-schema
- **Responsabilidade:** Definir e versionar o schema do banco (tabelas, views, RLS, índices) via migrations SQL
- **Depende de:** nada
- **Quem depende:** todos os módulos de ingestão e o dashboard
- **Estado:** planejado

#### dashboard-frontend
- **Responsabilidade:** Renderizar os dados do Supabase no dashboard HTML existente, substituindo os dados mock
- **Depende de:** Supabase API REST (views `vw_*`), `supabase-js`
- **Quem depende:** nada (camada final)
- **Estado:** frontend pronto — integração com Supabase planejada

### Diagrama (ASCII)

```
[Shopify API]    → [ingestion-shopify]  →┐
[Klaviyo API]    → [ingestion-klaviyo]  →│
[Vekta API]      → [ingestion-vekta]   →├→ [writers.py] → [Supabase PostgreSQL]
[Sendflow API]   → [ingestion-sendflow] →│                       │
[Google Sheets]  → [ingestion-sheets]  →┘                  [views vw_*]
                                                                  │
[Input manual]   ──────────────────────────→ [fact_monthly_goals]│
                                                                  ↓
                               [scheduler.py no Railway]   [dashboard-crm.html]
                               (dispara tudo a cada 30min)  (supabase-js lê vw_*)
```

---

## 3. Entidades e modelo de dados

### dim_channels
Tabela de referência dos 5 canais. Criada uma vez, raramente alterada.

| Coluna | Tipo | Obrigatório | Default | Notas |
|---|---|---|---|---|
| id | uuid | sim | gen_random_uuid() | PK |
| name | text | sim | — | Ex: "E-mail Fluxo" — nome oficial exibido no dashboard |
| slug | text | sim | — | Ex: "email_flow" — usado no código e queries |
| utm_source | text | sim | — | Ex: "email" |
| utm_medium | text | não | null | Ex: "flow" — null para Comunidade |
| primary_kpi | text | sim | — | Ex: "receita_inscrito" ou "receita_disparo" |
| created_at | timestamptz | sim | now() | — |

- **Índices:** `slug` (UNIQUE)
- **RLS:** SELECT para anon; nenhuma escrita para anon ou service_role (inserido via migration)
- **Soft delete:** não — canal é referência imutável
- **Invariantes:** os 5 slugs canônicos nunca mudam sem ADR: `email_flow`, `email_campaign`, `wpp_flow`, `wpp_campaign`, `wpp_community`

---

### dim_assets
Ativos pai: fluxos e campanhas. Um por linha.

| Coluna | Tipo | Obrigatório | Default | Notas |
|---|---|---|---|---|
| id | uuid | sim | gen_random_uuid() | PK |
| external_id | text | sim | — | ID na ferramenta de origem (Klaviyo, Vekta, Sendflow) |
| channel_id | uuid | sim | — | FK → dim_channels |
| name | text | sim | — | Nome conforme aparece na ferramenta de origem |
| type | text | sim | — | "flow" ou "campaign" |
| is_active | boolean | sim | true | false quando desativado na ferramenta de origem |
| source_tool | text | sim | — | "klaviyo" | "vekta" | "sendflow" |
| created_at | timestamptz | sim | now() | — |
| updated_at | timestamptz | sim | now() | atualizado a cada sync |
| ingested_at | timestamptz | sim | now() | último sync bem-sucedido |

- **Chaves estrangeiras:** `channel_id` → `dim_channels.id`
- **Índices:** `(external_id, source_tool)` UNIQUE, `channel_id`, `is_active`
- **RLS:** SELECT para anon; INSERT/UPDATE apenas para service_role
- **Soft delete:** não — `is_active = false` é o estado de "desativado"; histórico de métricas preservado
- **Invariantes:** `type` só aceita "flow" ou "campaign"; `source_tool` só aceita os três valores listados

---

### dim_asset_items
Ativos filho: e-mails individuais (dentro de fluxos/campanhas de e-mail) e templates de WhatsApp.

| Coluna | Tipo | Obrigatório | Default | Notas |
|---|---|---|---|---|
| id | uuid | sim | gen_random_uuid() | PK |
| external_id | text | sim | — | ID na ferramenta de origem |
| asset_id | uuid | sim | — | FK → dim_assets (ativo pai) |
| name | text | sim | — | Subject line (e-mail) ou preview do template (WA) |
| type | text | sim | — | "email" ou "wpp_template" |
| position | integer | não | null | Posição no fluxo (1, 2, 3...) |
| created_at | timestamptz | sim | now() | — |
| updated_at | timestamptz | sim | now() | — |
| ingested_at | timestamptz | sim | now() | — |

- **Chaves estrangeiras:** `asset_id` → `dim_assets.id`
- **Índices:** `(external_id, type)` UNIQUE, `asset_id`
- **RLS:** SELECT para anon; INSERT/UPDATE apenas para service_role
- **Soft delete:** não — item removido do fluxo mantém histórico, apenas para de receber dados novos
- **Invariantes:** `type` só aceita "email" ou "wpp_template"; `type` deve ser consistente com o `source_tool` do ativo pai

---

### dim_forms
Formulários e popups de captação de leads do Klaviyo.

| Coluna | Tipo | Obrigatório | Default | Notas |
|---|---|---|---|---|
| id | uuid | sim | gen_random_uuid() | PK |
| external_id | text | sim | — | Klaviyo Form ID — UNIQUE |
| name | text | sim | — | Nome do formulário (deve incluir tipo e local) |
| type | text | sim | — | "popup" | "form" | "embed" |
| position | text | não | null | Ex: "Home", "Footer", "Landing SS25" |
| is_active | boolean | sim | true | — |
| created_at | timestamptz | sim | now() | — |
| ingested_at | timestamptz | sim | now() | — |

- **Índices:** `external_id` UNIQUE
- **RLS:** SELECT para anon; escrita apenas para service_role

---

### fact_orders
Pedidos pagos do Shopify com atribuição de canal por UTM.

| Coluna | Tipo | Obrigatório | Default | Notas |
|---|---|---|---|---|
| id | uuid | sim | gen_random_uuid() | PK |
| order_id | text | sim | — | Shopify Order ID — chave de upsert UNIQUE |
| order_date | date | sim | — | Data do pedido |
| revenue_brl | numeric(12,2) | sim | — | Valor do pedido em reais |
| attributed_channel_id | uuid | não | null | FK → dim_channels — null se sem UTM de CRM |
| utm_source | text | não | null | Valor bruto da UTM |
| utm_medium | text | não | null | Valor bruto da UTM |
| utm_campaign | text | não | null | Valor bruto da UTM |
| shopify_customer_id | text | sim | — | ID do cliente no Shopify |
| is_first_purchase | boolean | sim | — | true se orders_count = 1 |
| ingested_at | timestamptz | sim | now() | — |

- **Chaves estrangeiras:** `attributed_channel_id` → `dim_channels.id`
- **Índices:** `order_id` UNIQUE, `order_date`, `attributed_channel_id`, `is_first_purchase`
- **RLS:** SELECT para anon; INSERT/UPDATE apenas para service_role
- **Soft delete:** não — apenas pedidos pagos entram; cancelamentos ignorados na V1
- **Invariantes:** `revenue_brl` > 0; pedidos sem UTM de CRM têm `attributed_channel_id = null` e NÃO são distribuídos entre canais

---

### fact_sessions
Sessões, ATC e BCO por canal por dia — origem: Google Sheets (export BigQuery).

| Coluna | Tipo | Obrigatório | Default | Notas |
|---|---|---|---|---|
| id | uuid | sim | gen_random_uuid() | PK |
| date | date | sim | — | — |
| channel_id | uuid | sim | — | FK → dim_channels |
| sessions | integer | sim | 0 | — |
| add_to_cart | integer | sim | 0 | ATC |
| begin_checkout | integer | sim | 0 | BCO |
| ingested_at | timestamptz | sim | now() | — |

- **Chaves estrangeiras:** `channel_id` → `dim_channels.id`
- **Índices:** `(date, channel_id)` UNIQUE, `date`
- **RLS:** SELECT para anon; escrita apenas para service_role
- **Invariantes:** `sessions >= add_to_cart >= begin_checkout >= 0`

---

### fact_email_sends
Métricas de e-mail por item de ativo (e-mail individual) por dia — origem: Klaviyo.

| Coluna | Tipo | Obrigatório | Default | Notas |
|---|---|---|---|---|
| id | uuid | sim | gen_random_uuid() | PK |
| date | date | sim | — | — |
| asset_item_id | uuid | sim | — | FK → dim_asset_items (type = "email") |
| sends | integer | sim | 0 | Disparos |
| opens | integer | sim | 0 | Aberturas |
| clicks | integer | sim | 0 | Cliques |
| bounces | integer | sim | 0 | — |
| spam_complaints | integer | sim | 0 | — |
| unsubscribes | integer | sim | 0 | — |
| ingested_at | timestamptz | sim | now() | — |

- **Chaves estrangeiras:** `asset_item_id` → `dim_asset_items.id`
- **Índices:** `(date, asset_item_id)` UNIQUE, `date`
- **RLS:** SELECT para anon; escrita apenas para service_role
- **Invariantes:** `sends >= opens >= clicks >= 0`; `bounces + spam_complaints + unsubscribes <= sends`

---

### fact_wpp_sends
Métricas de WhatsApp por template por dia — origem: Vekta.

| Coluna | Tipo | Obrigatório | Default | Notas |
|---|---|---|---|---|
| id | uuid | sim | gen_random_uuid() | PK |
| date | date | sim | — | — |
| asset_item_id | uuid | sim | — | FK → dim_asset_items (type = "wpp_template") |
| sends | integer | sim | 0 | Disparos |
| responses | integer | sim | 0 | Respostas (Acessar) |
| unlocks | integer | sim | 0 | Destravar Objeção |
| handoffs_to_sales | integer | sim | 0 | Leads ao Comercial |
| ingested_at | timestamptz | sim | now() | — |

- **Chaves estrangeiras:** `asset_item_id` → `dim_asset_items.id`
- **Índices:** `(date, asset_item_id)` UNIQUE, `date`
- **RLS:** SELECT para anon; escrita apenas para service_role
- **Invariantes:** `responses <= sends`; `handoffs_to_sales <= responses`

---

### fact_community_members
Snapshot diário de participantes da Comunidade WhatsApp — origem: Sendflow.

| Coluna | Tipo | Obrigatório | Default | Notas |
|---|---|---|---|---|
| id | uuid | sim | gen_random_uuid() | PK |
| date | date | sim | — | UNIQUE |
| total_members | integer | sim | — | Snapshot do dia |
| entries | integer | sim | 0 | Entradas no dia |
| exits | integer | sim | 0 | Saídas no dia |
| ingested_at | timestamptz | sim | now() | — |

- **Índices:** `date` UNIQUE
- **RLS:** SELECT para anon; escrita apenas para service_role
- **Invariantes:** `total_members > 0`

---

### fact_community_sends
Disparos de mensagens da Comunidade — origem: Sendflow.

| Coluna | Tipo | Obrigatório | Default | Notas |
|---|---|---|---|---|
| id | uuid | sim | gen_random_uuid() | PK |
| external_id | text | sim | — | ID da mensagem no Sendflow — UNIQUE |
| asset_id | uuid | sim | — | FK → dim_assets |
| sent_date | date | sim | — | Data do disparo |
| sends | integer | sim | 0 | Total de disparos |
| ingested_at | timestamptz | sim | now() | — |

- **Chaves estrangeiras:** `asset_id` → `dim_assets.id`
- **Índices:** `external_id` UNIQUE, `sent_date`
- **RLS:** SELECT para anon; escrita apenas para service_role

---

### fact_lead_captures
Performance de formulários e popups por dia — origem: Klaviyo Forms API.

| Coluna | Tipo | Obrigatório | Default | Notas |
|---|---|---|---|---|
| id | uuid | sim | gen_random_uuid() | PK |
| date | date | sim | — | — |
| form_id | uuid | sim | — | FK → dim_forms |
| views | integer | sim | 0 | Visualizações |
| subscribers | integer | sim | 0 | Inscrições |
| ingested_at | timestamptz | sim | now() | — |

- **Chaves estrangeiras:** `form_id` → `dim_forms.id`
- **Índices:** `(date, form_id)` UNIQUE, `date`
- **RLS:** SELECT para anon; escrita apenas para service_role
- **Invariantes:** `subscribers <= views`

---

### fact_email_health
Saúde da base de e-mail por canal por dia — origem: Klaviyo API.

| Coluna | Tipo | Obrigatório | Default | Notas |
|---|---|---|---|---|
| id | uuid | sim | gen_random_uuid() | PK |
| date | date | sim | — | — |
| channel_id | uuid | sim | — | FK → dim_channels (apenas canais de e-mail) |
| active_base_count | integer | sim | — | Engajados 90d — segmento Klaviyo |
| delivery_rate | numeric(5,4) | não | null | Entregues / Enviados |
| bounce_rate | numeric(5,4) | não | null | Bounces / Enviados |
| spam_complaint_rate | numeric(6,5) | não | null | Reclamações / Entregues |
| opt_out_rate | numeric(5,4) | não | null | Unsubscribes / Entregues |
| ingested_at | timestamptz | sim | now() | — |

- **Chaves estrangeiras:** `channel_id` → `dim_channels.id`
- **Índices:** `(date, channel_id)` UNIQUE
- **RLS:** SELECT para anon; escrita apenas para service_role
- **Invariantes:** `channel_id` deve ser de canal de e-mail (slug: "email_flow" ou "email_campaign")

---

### fact_monthly_goals
Metas mensais de receita — origem: input manual.

| Coluna | Tipo | Obrigatório | Default | Notas |
|---|---|---|---|---|
| id | uuid | sim | gen_random_uuid() | PK |
| month | date | sim | — | Sempre dia 1 do mês — UNIQUE |
| goal_first_purchase_brl | numeric(12,2) | sim | — | Meta receita 1ª compra |
| goal_repurchase_brl | numeric(12,2) | sim | — | Meta receita recompra |
| goal_total_brl | numeric(12,2) | sim | — | Meta receita total CRM |
| created_at | timestamptz | sim | now() | — |
| updated_at | timestamptz | sim | now() | — |

- **Índices:** `month` UNIQUE
- **RLS:** SELECT para anon; INSERT/UPDATE para service_role (inserção manual via Supabase Table Editor)
- **Invariantes:** `goal_total_brl = goal_first_purchase_brl + goal_repurchase_brl`

---

### Views calculadas

| View | O que entrega | Tabelas usadas |
|---|---|---|
| `vw_crm_daily_summary` | Receita, compras, sessões, conversão, TKM, RPS por canal e dia | `fact_orders`, `fact_sessions`, `dim_channels` |
| `vw_channel_kpis` | KPIs agregados por canal para qualquer período | `vw_crm_daily_summary`, `fact_email_sends`, `fact_wpp_sends` |
| `vw_asset_performance` | Performance completa por fluxo/campanha (ativo pai) | `fact_email_sends`, `fact_wpp_sends`, `fact_orders`, `dim_assets`, `dim_asset_items` |
| `vw_funnel_crm` | Sessões → ATC → BCO → Compras por canal | `fact_sessions`, `fact_orders`, `dim_channels` |
| `vw_leads_daily` | Leads por dia por formulário | `fact_lead_captures`, `dim_forms` |
| `vw_pace_vs_goals` | % atingido, projeção de fechamento, status | `fact_orders`, `fact_monthly_goals` |
| `vw_email_health` | Saúde da base de e-mail por canal | `fact_email_health`, `dim_channels` |

---

## 4. Fluxos de dados

### Fluxo 1 — Ingestão automática a cada 30 minutos (Shopify, Klaviyo, Vekta, Sendflow)

1. **Trigger:** `scheduler.py` via `schedule.every(30).minutes` rodando no Railway
2. **Função que executa:** `ingestion/scheduler.py` → chama cada módulo `ingestion/sources/*.py`
3. **Validações:**
   - Dados brutos de API validados via Pydantic antes de qualquer escrita (R7)
   - Shopify: apenas `financial_status = "paid"` processado (R5)
   - UTM: `utm_source` + `utm_medium` mapeados para `channel_id` via `dim_channels`; sem match → `attributed_channel_id = null`
4. **Operações de banco (em ordem):**
   - Upsert em `dim_assets` (sincroniza ativos ativos/inativos)
   - Upsert em `dim_asset_items` (sincroniza e-mails e templates)
   - Upsert em `fact_orders` por `order_id`
   - Upsert em `fact_email_sends` por `(date, asset_item_id)`
   - Upsert em `fact_wpp_sends` por `(date, asset_item_id)`
   - Upsert em `fact_community_members` por `date`
   - Upsert em `fact_community_sends` por `external_id`
   - Upsert em `fact_lead_captures` por `(date, form_id)`
   - Upsert em `fact_email_health` por `(date, channel_id)`
5. **Resposta:** Log estruturado com contagem de registros por tabela e timestamp
6. **Side effects:** Se qualquer fonte falhar, log de erro com contexto; ingestão das outras fontes continua (R8)

---

### Fluxo 2 — Ingestão de dados de sessão (BigQuery → Sheets → Supabase, horária)

1. **Trigger:** `scheduler.py` via `schedule.every(1).hours`
2. **Função que executa:** `ingestion/sources/google_sheets.py`
3. **Validações:**
   - Verifica que colunas esperadas existem na planilha (date, channel_slug, sessions, add_to_cart, begin_checkout)
   - Valida tipos via Pydantic
   - `sessions >= add_to_cart >= begin_checkout` (invariante)
4. **Operações de banco:**
   - Upsert em `fact_sessions` por `(date, channel_id)`
5. **Side effects:** Log com data mais recente processada e contagem de linhas

---

### Fluxo 3 — Consulta ao dashboard (tempo real, sob demanda)

1. **Trigger:** Usuário abre `dashboard-crm.html` ou aplica filtro
2. **Função que executa:** JavaScript no `dashboard-crm.html` via `supabase-js`
3. **Validações:** Filtros de período e canal validados no frontend antes de enviar query
4. **Operações de banco:**
   - SELECT nas views `vw_*` com filtros de data e channel_slug
   - Cada seção do dashboard faz sua própria query à view correspondente
5. **Resposta:** JSON retornado pelo Supabase; dashboard renderiza sem cálculo
6. **Side effects:** Se Supabase retornar erro, exibir mensagem de dados indisponíveis com último timestamp conhecido

---

### Fluxo 4 — Input de metas mensais (manual, mensal)

1. **Trigger:** Daniel acessa o Supabase Table Editor no início de cada mês
2. **Operação de banco:** INSERT ou UPDATE em `fact_monthly_goals` para o mês vigente
3. **Pós-condição:** `vw_pace_vs_goals` automaticamente passa a usar os novos valores

---

## 5. Decisões arquiteturais já tomadas

| Data | Decisão | Por quê | Impede no futuro | ADR |
|---|---|---|---|---|
| 2026-05-14 | Atribuição last-click via UTM | Única regra de atribuição implementável com os dados disponíveis | Atribuição multi-touch exige refatoração completa de `fact_orders` e views | — |
| 2026-05-14 | Python + Railway para scheduler | Simples de implementar, menor curva de aprendizado, custo baixo | Migração para n8n ou pg_cron exige reescrever scripts de ingestão | — |
| 2026-05-14 | Duas tabelas separadas para hierarquia de ativos (`dim_assets` + `dim_asset_items`) | Mais fácil de auditar, tipos bem separados, sem campo nullable confuso | Hierarquia com 3+ níveis exige nova tabela; self-join é mais simples para isso | — |
| 2026-05-14 | BigQuery → Google Sheets → Supabase para dados de sessão | Acesso direto ao BigQuery não disponível na V1 | Migração para BigQuery direto exige service account e refatoração do módulo `ingestion-sheets` | — |
| 2026-05-14 | Frontend em HTML puro (sem Next.js ou framework) | Dashboard já construído e aprovado; não há motivo para reescrever | Funcionalidades interativas avançadas (real-time, formulários complexos) exigirão framework | — |
| 2026-05-14 | Apenas pedidos pagos no sistema (sem cancelamentos/reembolsos) | Bases da Minimal Club só expõem pedidos pagos; simplifica V1 | Incluir reembolsos na V2 exige campo `status` em `fact_orders` e ajuste nas views | — |

---

## 6. Pontos frágeis conhecidos

### Google Sheets como intermediário de dados de sessão
- **Onde:** `ingestion/sources/google_sheets.py` + planilha externa
- **Por que é frágil:** Se o nome de uma coluna mudar na planilha, ou o export do BigQuery for interrompido, a ingestão de sessões para silenciosamente
- **O que vai estourar primeiro:** Dashboard sem dados de RPS e Conversão após mudança não comunicada na planilha
- **Plano:** Aceitar e monitorar na V1; migrar para BigQuery API direto na V2 com service account

### Vekta como fonte de WhatsApp
- **Onde:** `ingestion/sources/vekta.py`
- **Por que é frágil:** Não confirmado se Vekta tem API — pode precisar de fallback para export CSV manual
- **O que vai estourar primeiro:** Ingestão de WhatsApp não funciona se não houver API
- **Plano:** Confirmar antes de implementar. Se não tiver API, implementar ingestion via CSV com upload manual e criar processo documentado

### Hubspot como fonte de inscritos WhatsApp
- **Onde:** `ingestion/sources/klaviyo.py` (após migração) ou `ingestion/sources/hubspot.py` (temporário)
- **Por que é frágil:** Fonte temporária; migração para Klaviyo está planejada mas sem data
- **O que vai estourar primeiro:** Métrica de Receita/Inscrito do WhatsApp Fluxo incorreta se migração acontecer sem aviso
- **Plano:** Implementar com flag de fonte (`SUBSCRIBERS_SOURCE=hubspot|klaviyo`) em `.env` para troca sem reescrita

### Consistência de UTMs nos links de CRM
- **Onde:** Links de e-mail e WhatsApp nas ferramentas de envio
- **Por que é frágil:** Se UTMs não seguirem o padrão, pedidos ficam sem atribuição — receita some do dashboard
- **O que vai estourar primeiro:** Receita CRM total menor que real; canais com zero receita sem motivo técnico
- **Plano:** Auditar UTMs antes do primeiro go-live (ver `PRODUCT.md` seção 8)

---

## 7. Inventário de arquivos críticos

| Caminho | Responsabilidade | Quem deve mexer | Quem NÃO deve mexer |
|---|---|---|---|
| `dashboard-crm.html` | Dashboard visual existente — integração com Supabase | Claude (apenas substituição de dados mock) | Ninguém mexe no HTML/CSS estrutural |
| `ingestion/db/writers.py` | Todas as funções de upsert no Supabase | Claude com cuidado — mudança aqui afeta todas as fontes | — |
| `ingestion/scheduler.py` | Orquestração do ciclo de 30 min | Claude ao adicionar nova fonte | — |
| `supabase/migrations/` | Schema do banco versionado | Claude ao criar nova tabela/view (sempre nova migration) | Nunca editar migration já aplicada |
| `.env` | Credenciais reais de todas as APIs | Apenas Daniel | Claude nunca lê ou commita |
| `PRODUCT.md` | Fonte de verdade do domínio | Claude + Daniel quando produto muda | Claude nunca muda sem alinhamento explícito |
| `CLAUDE.md` | Regras de operação do agente | Claude + Daniel quando convenções mudam | — |
