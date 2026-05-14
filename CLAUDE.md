# CLAUDE.md — Dashboard CRM · Minimal Club

> Manual de operação do agente neste projeto. Lido em TODA sessão. Atualizado quando convenções mudam.

---

## 1. Stack e versões

### Camadas do sistema

| Camada | Tecnologia | Versão | Papel |
|---|---|---|---|
| Banco de dados | **Supabase** (PostgreSQL) | última | Armazenamento central, views calculadas, API REST |
| Ingestão de dados | **Python** | 3.11+ | Scripts que puxam dados das fontes e gravam no Supabase |
| Validação de dados | **Pydantic** | 2.x | Schemas e validação dos dados vindos das APIs externas |
| Cliente HTTP | **httpx** | 0.27+ | Chamadas às APIs externas (Shopify, Klaviyo, Vekta, Sendflow) |
| Cliente Supabase | **supabase-py** | 2.x | Escrita e leitura no banco via Python |
| Google Sheets | **gspread** | 6.x | Leitura da planilha com dados de sessão (BigQuery → Sheets) |
| Configuração | **python-dotenv** | 1.x | Variáveis de ambiente |
| Agendamento | **schedule** | 1.x | Rodar ingestão a cada 30 minutos |
| Frontend | **HTML + Vanilla JS + supabase-js** | supabase-js 2.x | Dashboard existente — substituição de dados mock por API real |
| Deploy scripts | **Railway ou VPS simples** | — | Rodar o scheduler Python em produção |

### Bibliotecas permitidas por tipo de problema
- **HTTP externo:** `httpx` — nunca `requests` (httpx suporta async nativamente)
- **Validação de entrada de API:** `pydantic` — nunca validação manual com `if/else`
- **Datas:** `datetime` nativo + `python-dateutil` — nunca strings de data sem parse explícito
- **Variáveis de ambiente:** `python-dotenv` — nunca hardcode de credenciais
- **Banco (Python):** `supabase-py` — nunca SQL raw via psycopg2 no código de ingestão
- **Banco (SQL direto):** migrations em `supabase/migrations/` — único lugar de SQL explícito
- **Google Sheets:** `gspread` com service account — nunca OAuth interativo

### Bibliotecas proibidas
- `requests` — motivo: httpx é equivalente e suporta async; não misturar dois clientes HTTP
- `moment.js` ou `moment` (Python) — motivo: datetime nativo resolve; moment é peso desnecessário
- `pandas` — motivo: overhead desnecessário para ingestão linha a linha; se precisar de transformação em lote, justificar antes
- Qualquer ORM além de supabase-py — motivo: Supabase já é o cliente; dois ORMs criam divergência

---

## 2. Convenções de código

### Nomenclatura — Python (ingestão)
- **Arquivos:** snake_case com sufixo de responsabilidade — `shopify_ingestion.py`, `klaviyo_client.py`, `order_model.py`
- **Funções:** verbo + objeto específico e concreto
  - ✓ `fetch_paid_orders_since(date)`, `upsert_email_flow_metrics(metrics)`
  - ✗ `handle_data()`, `process()`, `manage_source()`
- **Variáveis:** sem abreviações — `channel_slug` ✓, `ch_sl` ✗
- **Booleans:** prefixo `is_`, `has_`, `can_` — `is_active`, `has_utm`
- **Constantes:** SCREAMING_SNAKE_CASE — `MAX_RETRY_ATTEMPTS = 3`
- **Modelos Pydantic:** PascalCase — `ShopifyOrder`, `KlaviyoFlowMetrics`

### Nomenclatura — SQL (Supabase)
- **Tabelas de fatos:** prefixo `fact_` — `fact_orders`, `fact_email_sends`
- **Tabelas de dimensão:** prefixo `dim_` — `dim_channels`, `dim_assets`
- **Views:** prefixo `vw_` — `vw_channel_kpis`, `vw_crm_daily_summary`
- **Colunas:** snake_case — `channel_id`, `sent_at`, `revenue_brl`
- **Chaves estrangeiras:** `[tabela_referenciada]_id` — `channel_id`, `asset_id`
- **Timestamps:** sempre em UTC; tipo `timestamptz`

### Nomenclatura — JavaScript (dashboard HTML)
- **Funções:** camelCase, verbo + objeto — `fetchChannelKpis()`, `renderFunnelChart()`
- **Variáveis:** camelCase — `channelRevenue`, `activeAssets`
- **Constantes de configuração:** SCREAMING_SNAKE_CASE — `SUPABASE_URL`

### Tamanho
- Função Python: 4 a 25 linhas. Se passar, dividir por responsabilidade.
- Arquivo Python: até 300 linhas. Se passar, dividir por fonte ou responsabilidade.
- Query SQL em view: se passar de 50 linhas, adicionar comentário de seção.

### Tipos
- Python: type hints obrigatórios em todos os parâmetros e retornos de função
- Pydantic models para todos os dados vindos de APIs externas
- JavaScript: sem TypeScript (frontend é HTML puro) — comentar tipo esperado quando não óbvio

### Erros
- Mensagem inclui: (1) o valor recebido, (2) o formato esperado
- Exemplo Python: `raise ValueError(f"Canal inválido: recebido '{channel}', esperado um de {VALID_CHANNELS}")`
- Nunca capturar exceção e silenciar — sempre re-raise ou log estruturado

---

## 3. Estrutura de pastas obrigatória

```
gerenciamentodedadoscrm/
│
├── CLAUDE.md                  ← este arquivo
├── ARCHITECTURE.md            ← mapa vivo do sistema
├── PRODUCT.md                 ← fonte de verdade do domínio
├── README.md                  ← visão geral do projeto para humanos
│
├── dashboard-crm.html         ← FRONTEND EXISTENTE — não alterar estrutura HTML/CSS
│                                 Apenas substituir dados mock por chamadas à API Supabase
├── docs-crm.html              ← documentação executiva existente — não alterar
│
├── docs/
│   ├── specs/                 ← spec de cada feature antes de implementar
│   ├── decisions/             ← ADRs (decisões arquiteturais duradouras)
│   └── sessions/              ← log de cada sessão de desenvolvimento
│
├── ingestion/                 ← scripts Python de ingestão de dados
│   ├── sources/               ← um arquivo por fonte de dados externa
│   │   ├── shopify.py         ← pedidos e clientes
│   │   ├── klaviyo.py         ← e-mail fluxos, campanhas, formulários, base ativa
│   │   ├── vekta.py           ← WhatsApp fluxos e campanhas
│   │   ├── sendflow.py        ← comunidade WhatsApp
│   │   └── google_sheets.py   ← sessões/ATC/BCO do BigQuery via Sheets
│   ├── models/                ← Pydantic models para cada fonte
│   │   ├── shopify_models.py
│   │   ├── klaviyo_models.py
│   │   └── ...
│   ├── db/                    ← cliente Supabase e funções de escrita
│   │   ├── client.py          ← inicialização do supabase-py
│   │   └── writers.py         ← funções de upsert por tabela fact_*
│   ├── scheduler.py           ← orquestra o ciclo de 30 minutos
│   └── main.py                ← entry point para rodar manualmente
│
├── supabase/
│   └── migrations/            ← SQL versionado, um arquivo por mudança de schema
│                                 NUNCA alterar migration já aplicada — criar nova
│
├── .env.example               ← template de variáveis (sem valores reais)
├── .env                       ← valores reais — NUNCA commitar
├── requirements.txt           ← dependências Python
└── .gitignore
```

**O que NÃO vai em cada pasta:**
- `ingestion/sources/`: lógica de escrita no banco. Vai em `ingestion/db/writers.py`.
- `ingestion/models/`: lógica de negócio. Só estrutura de dados (Pydantic).
- `ingestion/db/`: regras de atribuição ou cálculo. Só operações de I/O com Supabase.
- `supabase/migrations/`: código Python. Só SQL puro.
- `dashboard-crm.html`: lógica de negócio. Só renderização e chamadas à API Supabase.

---

## 4. Regras invioláveis

### R1. Toda tabela do banco tem RLS habilitado.
- **Motivo:** sem RLS, qualquer cliente com a anon key lê todos os dados.
- **Violação:** exposição pública de dados de receita da empresa.

### R2. A `anon key` do Supabase só tem permissão de leitura (SELECT).
- **Motivo:** o dashboard HTML usa a anon key — nunca deve conseguir inserir ou deletar dados.
- **Violação:** qualquer usuário com DevTools poderia manipular dados de produção.

### R3. Escritas no banco (ingestão) usam exclusivamente a `service_role_key` via Python.
- **Motivo:** separação entre leitura pública (dashboard) e escrita confiável (ingestão).
- **Violação:** confundir as chaves expõe a service_role_key no frontend.

### R4. Atribuição de receita é sempre last-click via UTM. Nunca mudar sem ADR.
- **Motivo:** toda a lógica de faturamento por canal depende desta regra. Mudar silenciosamente invalida todo o histórico.
- **Violação:** números de receita inconsistentes entre períodos.

### R5. Somente pedidos com `financial_status = "paid"` do Shopify entram no sistema.
- **Motivo:** cancelamentos e reembolsos distorcem métricas de receita.
- **Violação:** receita inflada ou inconsistente.

### R6. Nunca alterar migration já aplicada. Sempre criar nova migration.
- **Motivo:** migrations aplicadas em produção são imutáveis; alterar o arquivo não refaz a mudança.
- **Violação:** ambiente local diverge de produção silenciosamente.

### R7. Dados de API externa sempre validados com Pydantic antes de gravar no banco.
- **Motivo:** APIs externas mudam sem avisar; dados inválidos corrompem métricas.
- **Violação:** valores nulos ou com tipo errado chegam ao dashboard sem erro visível.

### R8. Sem catch silencioso nos scripts de ingestão.
- **Motivo:** erro de ingestão silenciado = dashboard com dados desatualizados sem alerta.
- **Violação:** dados parados sem ninguém saber.

### R9. O arquivo `dashboard-crm.html` tem sua estrutura HTML e CSS preservada.
- **Motivo:** o visual foi aprovado pela gestão. Só os dados mudam.
- **Violação:** regressão visual que invalida a aprovação anterior.

### R10. Termos do glossário são obrigatórios no código. "Envio" é proibido — usar "disparo".
- **Motivo:** consistência entre documentos e código; facilita busca e debug.
- **Violação:** grep por "disparo" não encontra partes do código que usam "envio".

### R11. Views calculadas (`vw_*`) vivem no Supabase. Nunca no JavaScript do dashboard.
- **Motivo:** a única fonte de verdade para cálculo de KPIs é o banco. JavaScript renderiza, não calcula.
- **Violação:** KPI calculado diferente entre banco e frontend.

### R12. Cada registro de fato tem `ingested_at` (timestamptz). Nunca omitir.
- **Motivo:** rastrear frescor dos dados; o dashboard exibe "atualizado há X minutos".
- **Violação:** impossível saber se dado está desatualizado por falha de ingestão.

---

## 5. Glossário do domínio

> Use estes termos no código: variáveis, funções, tabelas, colunas.

| Termo | Definição (1 linha) | Como aparece no código |
|---|---|---|
| **Disparo** | Unidade de envio de e-mail ou WhatsApp. Termo canônico — nunca "envio". | `total_sends`, `sends_count`, `fact_email_sends` |
| **Fluxo** | Automação contínua 24/7 disparada por evento do cliente. | `flow`, `is_flow`, `dim_assets.type = 'flow'` |
| **Campanha** | Disparo manual pontual para lista específica. | `campaign`, `is_campaign`, `dim_assets.type = 'campaign'` |
| **Ativo** | Qualquer elemento CRM que gera receita (fluxo, campanha, e-mail, template). Hierarquia: pai → filho. | `asset`, `asset_id`, `parent_asset_id`, `dim_assets` |
| **E-mail** | Mensagem individual dentro de fluxo ou campanha de e-mail. Ativo filho. | `email_message`, `dim_email_messages` |
| **Template** | Mensagem individual de WhatsApp dentro de fluxo ou campanha. Ativo filho. | `wpp_template`, `dim_wpp_templates` |
| **Inscrito** | Contagem acumulada de entradas em fluxo. E-mail e WA contados separadamente. | `subscribers_count`, `total_subscribers` |
| **Base Ativa** | Inscritos de e-mail que engajaram nos últimos 90 dias (segmento Klaviyo). | `active_base_count`, `fact_email_health.active_base` |
| **Canal** | Uma das 5 divisões oficiais do CRM com UTM e KPI próprios. | `channel`, `channel_id`, `channel_slug`, `dim_channels` |
| **Atribuição** | Regra last-click UTM: canal do último clique antes da compra leva 100% da receita. | `attributed_channel_id`, `utm_source`, `utm_medium` |
| **Meta** | Valor alvo mensal de receita inserido manualmente. | `monthly_goal`, `fact_monthly_goals` |
| **CTOR** | Click-to-Open Rate = Cliques ÷ Abertos. Nunca "CTR" neste projeto. | `ctor`, `click_to_open_rate` |

---

## 6. Padrões de implementação canônicos

### Como criar um novo script de ingestão para uma fonte

1. Criar `ingestion/sources/[fonte].py` com:
   - Função `fetch_[entidade]_since(date: datetime) -> list[RawModel]`
   - Cliente HTTP com retry em caso de 429/500
   - Log de início, fim e quantidade de registros
2. Criar `ingestion/models/[fonte]_models.py` com Pydantic models dos dados brutos
3. Criar ou atualizar função em `ingestion/db/writers.py`:
   - `upsert_[tabela](records: list[Model]) -> int` (retorna quantidade gravada)
   - Upsert por chave única (nunca insert simples — risco de duplicata)
4. Adicionar chamada em `ingestion/scheduler.py`
5. Atualizar `ARCHITECTURE.md` (seção de fontes e fluxo de dados)

### Como adicionar uma migration no Supabase

1. Criar arquivo em `supabase/migrations/YYYYMMDDHHMMSS_[descricao].sql`
2. Cabeçalho obrigatório:
   ```sql
   -- Migration: [descrição em 1 linha]
   -- Reversível: sim/não (se não, justificar)
   ```
3. Sempre incluir:
   - `ALTER TABLE ... ENABLE ROW LEVEL SECURITY;` para novas tabelas
   - Políticas RLS de leitura para anon role
   - Políticas RLS de escrita apenas para service_role
   - Índices nas colunas de filtro frequente (`channel_id`, `date`, `asset_id`)
4. Testar localmente com `supabase db reset` antes de aplicar em produção
5. Atualizar `ARCHITECTURE.md` (seção de modelo de dados)

### Como conectar uma nova métrica do dashboard ao Supabase

1. Identificar a view `vw_*` correspondente no banco (ou criar nova view em migration)
2. Em `dashboard-crm.html`, localizar a seção de dados mock que será substituída
3. Adicionar função JS:
   ```js
   async function fetch[NomeDaMetrica](filters) {
     const { data, error } = await supabase
       .from('vw_[nome_da_view]')
       .select('...')
       .eq('channel_slug', filters.channel)
       .gte('date', filters.startDate)
     if (error) showDataError('[nome da métrica]', error)
     return data
   }
   ```
4. Substituir o bloco de mock data pela chamada à função
5. Testar com filtros de período e canal

### Como criar uma nova view calculada no Supabase

1. Criar migration com `CREATE OR REPLACE VIEW vw_[nome] AS ...`
2. A view deve:
   - Expor `ingested_at` da tabela fact mais recente usada
   - Nomear colunas com termos do glossário (seção 5)
   - Incluir `channel_slug` para filtro no frontend
3. Adicionar política RLS de SELECT para anon role na view
4. Documentar a view em `ARCHITECTURE.md` (seção de views)

---

## 7. Anti-patterns explícitos

### Anti-pattern 1: Catch silencioso na ingestão
```python
# Ruim — erro engolido, dashboard fica desatualizado sem aviso
try:
    records = fetch_shopify_orders(since)
    upsert_orders(records)
except Exception:
    pass

# Bom — erro logado com contexto, re-raised para o scheduler tratar
try:
    records = fetch_shopify_orders(since)
    upsert_orders(records)
except httpx.HTTPError as e:
    logger.error({"source": "shopify", "error": str(e), "since": since.isoformat()})
    raise
```

### Anti-pattern 2: Validação manual em vez de Pydantic
```python
# Ruim — valida manualmente, fácil de esquecer campo
def parse_order(raw: dict) -> dict:
    if raw.get("financial_status") != "paid":
        return None
    return {"id": raw["id"], "total": raw["total_price"]}

# Bom — Pydantic valida e converte tipos automaticamente
class ShopifyOrder(BaseModel):
    id: str
    total_price: Decimal
    financial_status: Literal["paid"]
    utm_source: str | None = None
    utm_medium: str | None = None

order = ShopifyOrder.model_validate(raw)  # lança ValidationError se inválido
```

### Anti-pattern 3: Cálculo de KPI no JavaScript do dashboard
```js
// Ruim — receita calculada no frontend, diverge do banco
const revenue = orders.reduce((sum, o) => sum + o.total, 0)

// Bom — view no Supabase calcula, JS só renderiza
const { data } = await supabase.from('vw_channel_kpis').select('revenue_brl')
renderKpiCard(data[0].revenue_brl)
```

### Anti-pattern 4: Insert sem upsert (gera duplicatas na ingestão)
```python
# Ruim — toda execução do scheduler duplica os registros
supabase.table("fact_orders").insert(records).execute()

# Bom — upsert por chave única (order_id)
supabase.table("fact_orders").upsert(records, on_conflict="order_id").execute()
```

### Anti-pattern 5: "Envio" no lugar de "disparo"
```python
# Ruim — viola glossário, quebra consistência de busca no código
total_envios = klaviyo_flow["sends_count"]

# Bom — usar termo canônico do glossário
total_disparos = klaviyo_flow["sends_count"]
```

### Anti-pattern 6: Credencial hardcoded
```python
# Ruim — credential exposta no código
client = supabase.create_client("https://xyz.supabase.co", "eyJhbGci...")

# Bom — sempre via variável de ambiente
client = supabase.create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SERVICE_ROLE_KEY"]
)
```

### Anti-pattern 7: Migration alterada em vez de nova migration criada
```sql
-- Ruim — editar arquivo de migration existente
-- supabase/migrations/20260101_initial.sql  ← NUNCA editar depois de aplicado

-- Bom — criar novo arquivo
-- supabase/migrations/20260515_add_ingested_at_to_fact_orders.sql
ALTER TABLE fact_orders ADD COLUMN IF NOT EXISTS ingested_at TIMESTAMPTZ DEFAULT NOW();
```

---

## 8. Como rodar e testar localmente

```bash
# 1. Instalar dependências Python
pip install -r requirements.txt

# 2. Configurar variáveis de ambiente
cp .env.example .env
# editar .env com as chaves reais

# 3. Subir Supabase local
supabase start

# 4. Aplicar todas as migrations
supabase db reset

# 5. Rodar ingestão manualmente (uma vez)
python ingestion/main.py

# 6. Rodar scheduler (loop de 30 min)
python ingestion/scheduler.py

# 7. Abrir dashboard
# Abrir dashboard-crm.html no navegador
# OU servir com: python -m http.server 8080
```

### Variáveis de ambiente obrigatórias (`.env.example`)
```env
# Supabase
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=

# Shopify
SHOPIFY_STORE_URL=
SHOPIFY_ACCESS_TOKEN=

# Klaviyo
KLAVIYO_API_KEY=

# Vekta
VEKTA_API_URL=
VEKTA_API_KEY=

# Sendflow
SENDFLOW_API_KEY=

# Google Sheets (BigQuery export)
GOOGLE_SHEETS_SPREADSHEET_ID=
GOOGLE_SERVICE_ACCOUNT_JSON_PATH=
```

### Como verificar se a ingestão está funcionando
```bash
# Ver logs do último run
python ingestion/main.py --verbose

# Consultar tabela no Supabase local
supabase db --execute "SELECT COUNT(*), MAX(ingested_at) FROM fact_orders;"
```

---

## 9. Comportamento esperado do Claude

1. **Antes de qualquer código:** ler `ARCHITECTURE.md` inteiro.
2. **Antes de implementar feature nova:** confirmar em voz alta — (a) quais tabelas serão tocadas, (b) qual fonte de dados envolvida, (c) qual o risco de corromper dados existentes.
3. **Quando em dúvida sobre fonte de dados:** consultar `PRODUCT.md` seção 5 (Fluxos) e seção 8 (Restrições). Não inventar.
4. **Ao terminar sessão:** atualizar `ARCHITECTURE.md` + criar `docs/sessions/YYYY-MM-DD-[tema].md`.
5. **Se encontrar inconsistência entre `ARCHITECTURE.md` e código real:** parar, reportar, não silenciar nem consertar sem alinhamento.
6. **Nunca tocar `dashboard-crm.html` além da substituição de dados mock** — layout, CSS e estrutura HTML são intocáveis.
7. **Nunca adicionar dependência Python** sem perguntar e justificar contra as alternativas já no stack.
8. **Nunca criar migration sem nome descritivo** e cabeçalho de reversibilidade.
9. **Nunca usar "envio"** — sempre "disparo" (R10).
10. **Antes de conectar nova fonte de dados:** verificar se `PRODUCT.md` seção 5 já descreve o fluxo esperado. Se não descreve, atualizar `PRODUCT.md` primeiro.
