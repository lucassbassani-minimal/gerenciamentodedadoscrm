# Spec — Integração Chatflux no WPP Fluxo

> Descreve o COMPORTAMENTO da feature antes de implementar. Densa o suficiente para servir de checkpoint sem ler código.

---

## 1. Resumo em 1 parágrafo

O Chatflux é uma segunda ferramenta de disparo de WhatsApp (além da Vekta) que hoje atua em dois fluxos: divide o **Welcome** com a Vekta (contabilizado hoje sob o flow_name `Welcome Site`, sem diferenciar Novos/Recorrentes) e roda sozinho o **Carrinho Abandonado** — fluxo que não existe hoje no WPP Fluxo. Esta feature adiciona a ingestão dos eventos de disparo/resposta do Chatflux (via API própria) e estende as views de WPP Fluxo para que os números de Disparos/Respostas/Receita apareçam somados aos da Vekta na mesma tabela, com um seletor no dashboard para filtrar por Vekta / Chatflux / Ambos.

---

## 2. Comportamento funcional

### 2.1 Caminho feliz (ingestão)
1. Cron `api/cron/chatflux.py` roda a cada 30 min.
2. Busca `GET /api/eventos` no Chatflux para a janela dos últimos 3 dias (cobre atraso de resposta).
3. Valida cada evento com Pydantic (`ChatfluxEvento`).
4. Faz upsert em `fact_chatflux_events`, deduplicando por `(telefone, segmento, etapa, event_timestamp)`.
5. Views `vw_wpp_flow_leads` e `vw_wpp_flow_revenue` já enxergam os novos dados no próximo carregamento do dashboard — nenhum redeploy do frontend necessário para esse ganho.

### 2.2 Caminho feliz (dashboard)
1. Usuário abre a aba "WhatsApp Fluxo".
2. Vê um seletor "Ferramenta: Ambos ▾" (Ambos / Vekta / Chatflux) no topo da página.
3. Ao trocar para "Chatflux", os KPIs, o gráfico e a tabela "Detalhamento por Fluxo" recalculam mostrando apenas os fluxos/linhas atribuíveis ao Chatflux (Welcome Site parcialmente, Carrinho Abandonado integralmente).
4. Ao voltar para "Ambos", os números batem com o total combinado (comportamento atual, preservado).

### 2.3 Casos de erro
| Quando | O que acontece | Como recupera |
|---|---|---|
| Token inválido/expirado | Chatflux responde 401 | Cron loga erro estruturado e re-raise (sem catch silencioso, R8); alerta via `ingestion/alert.py` como os outros crons |
| Período grande demais (>180 dias) | Chatflux responde 400 | Não deve ocorrer — a janela usada é de poucos dias; se ocorrer, mesmo tratamento acima |
| API fora do ar | httpx levanta erro de conexão | Mesmo tratamento — log + alerta + cron falha visivelmente no painel de crons |

---

## 3. Dados envolvidos

### 3.1 Entidades lidas
- `GET /api/eventos` (Chatflux) — log de disparo/resposta por telefone
- `fact_orders` — para a receita (via `vw_wpp_flow_revenue`, já existente)

### 3.2 Entidades criadas / atualizadas
- **Cria:** `fact_chatflux_events` — um registro por evento (disparo ou resposta)
- **Cria:** 1 linha em `dim_wpp_alia_campanha_mapping` (mapeamento sintético `abandoned_cart_ia` → flow_name `Carrinho Abandonado`, para a receita entrar em `vw_wpp_flow_revenue`)
- **Atualiza (CREATE OR REPLACE):** `vw_wpp_flow_leads`, `vw_wpp_flow_revenue`, `vw_wpp_flow_inscritos` — todas ganham coluna `ferramenta` (`'vekta'` ou `'chatflux'`)

### 3.3 Campos novos
| Tabela | Campo | Tipo | Default | Validação |
|---|---|---|---|---|
| `fact_chatflux_events` | `event_timestamp` | timestamptz | — | obrigatório |
| `fact_chatflux_events` | `segmento` | text | — | um de `Welcome Novos`, `Welcome Recorrentes`, `Carrinho Abandonado` |
| `fact_chatflux_events` | `etapa` | text | — | um de `disparo`, `resposta` |
| `fact_chatflux_events` | `telefone` | text | — | não vazio |
| `fact_chatflux_events` | `ingested_at` | timestamptz | `now()` | R12 |
| `vw_wpp_flow_leads`/`vw_wpp_flow_revenue`/`vw_wpp_flow_inscritos` | `ferramenta` | text | — | `'vekta'` ou `'chatflux'` |

### 3.4 Migrations necessárias
- **Migração:** cria `fact_chatflux_events` (+ RLS + índices + unique constraint), insere mapeamento `abandoned_cart_ia`, recria as 3 views com a coluna `ferramenta`.
- **Reversível?** Sim — `DROP TABLE`/`DROP VIEW` + recriar views antigas.
- **Impacto em dados existentes:** nenhum dado é alterado; `fact_wpp_flow_subscribers`, `leads_webhook` e as tabelas de mapeamento existentes permanecem intactas. As views recriadas mantêm 100% de compatibilidade com as consultas atuais do dashboard quando `ferramenta` não é filtrada (SELECT explícito de colunas, sem `SELECT *`).

---

## 4. Regras de negócio explícitas

- **R1 (mapeamento de fluxo).** Eventos com `segmento` = `Welcome Novos` ou `Welcome Recorrentes` são contabilizados no flow_name `Welcome Site` (mesma linha da Vekta), sem diferenciar Novos/Recorrentes entre si.
- **R2 (fluxo novo).** Eventos com `segmento` = `Carrinho Abandonado` criam/alimentam o flow_name `Carrinho Abandonado`, inexistente até hoje no WPP Fluxo.
- **R3 (atribuição de receita, deriva de R4 do CLAUDE.md).** A receita continua sendo atribuída por last-click UTM (`fact_orders.utm_campaign`), sem mudança na regra de atribuição — apenas uma subclassificação (`ferramenta`) por cima da receita já atribuída ao canal `wpp_flow`:
  - `utm_campaign = 'abandoned_cart_ia'` → `ferramenta = 'chatflux'`
  - `utm_campaign ILIKE '%welcome%' AND utm_content = 'chatflux'` → `ferramenta = 'chatflux'`
  - Qualquer outro caso dentro de `wpp_flow` → `ferramenta = 'vekta'` (default histórico/legado)
- **R4 (disparos/respostas do Chatflux).** "Disparos" = contagem de telefones distintos com `etapa='disparo'` por dia/fluxo; "Respostas" = contagem de eventos com `etapa='resposta'`. Chatflux não tem conceito de "Destravar Objeção"/"Necessita Atenção" nem de "Inscritos" — essas colunas ficam zeradas/vazias para linhas `ferramenta='chatflux'`.

---

## 5. UI/UX

### 5.1 Telas afetadas
- Página "WhatsApp Fluxo" (`page-wf`) — adiciona seletor de ferramenta; tabela "Detalhamento por Fluxo" e cards de "Métricas Específicas" passam a refletir o filtro selecionado.

### 5.2 Componentes novos necessários
- Seletor `<select id="wf-tool-filter">` (Ambos/Vekta/Chatflux) — filtra client-side as linhas já trazidas das views (R11: cálculo continua no banco, JS só filtra/re-agrupa).

### 5.3 Estados visuais
| Tela | Vazio | Erro |
|---|---|---|
| WPP Fluxo com filtro Chatflux, fora do período de dados | "Sem dados no período" (já existente) | Erro de fetch já tratado por `showDataError` existente |

---

## 6. Casos de borda específicos desta feature

| Caso | Comportamento esperado |
|---|---|
| Evento do Chatflux chega duplicado (retry) | Upsert por `(telefone, segmento, etapa, event_timestamp)` evita duplicata |
| Pedido com `utm_campaign='welcome'` e `utm_content` antigo (ex.: `em001`, `temp1196`) | Cai no default `ferramenta='vekta'` (comportamento histórico, pré-Chatflux) |
| Usuário filtra "Chatflux" em fluxo que só a Vekta roda (ex.: Retenção) | Linha não aparece ou aparece com "—" (sem dados para essa ferramenta) |
| Cron do Chatflux falha (API fora do ar) | Falha visível no painel de crons + alerta, sem corromper dados já ingeridos |

---

## 7. Critérios de aceite testáveis

- [ ] **CA1.** Rodando o cron manualmente, `fact_chatflux_events` recebe as linhas do período pedido.
- [ ] **CA2.** Com filtro "Ambos", os totais de Disparos/Respostas do flow `Welcome Site` incluem tanto leads da Vekta quanto eventos do Chatflux.
- [ ] **CA3.** Com filtro "Chatflux", aparece uma linha `Carrinho Abandonado` com Disparos/Respostas/Receita reais.
- [ ] **CA4.** Com filtro "Vekta", os números batem exatamente com o que a tabela mostrava antes desta feature existir.
- [ ] **CA5.** Receita de `Welcome Site` com filtro "Chatflux" reflete só pedidos com `utm_content='chatflux'`.

---

## 8. Riscos e impactos

### Módulos existentes que podem quebrar
- `vw_wpp_flow_leads`/`vw_wpp_flow_revenue`/`vw_wpp_flow_inscritos` são recriadas (CREATE OR REPLACE) — qualquer consumidor que dependa da ordem/lista de colunas via `SELECT *` quebraria; o dashboard usa `SELECT` explícito, então está protegido.

### Reversibilidade
- Sim — migration nova reversível (dropar tabela/mapeamento e recriar views na versão anterior).

### Dado em produção afetado
- Nenhum dado existente é alterado ou removido; a feature é estritamente aditiva.
