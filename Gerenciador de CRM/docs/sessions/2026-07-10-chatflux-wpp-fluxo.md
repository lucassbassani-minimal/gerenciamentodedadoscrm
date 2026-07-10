# Sessão — 2026-07-10 — Integração Chatflux no WPP Fluxo

## Contexto

Chatflux é uma 2ª ferramenta de disparo de WhatsApp, ao lado da Vekta. Ela atua em:
- **Welcome** — dividido 50/50 com a Vekta em disparos (Novos+Recorrentes somados, sem diferenciar entre si, contabilizados sob o flow_name já existente `Welcome Site`).
- **Carrinho Abandonado** — fluxo 100% novo, não existia antes no WPP Fluxo.

Objetivo: ingerir os eventos de disparo/resposta do Chatflux e mostrar os mesmos números (Disparos/Respostas/Receita) já vistos para a Vekta, com um seletor Vekta/Chatflux/Ambos nos painéis "Métricas Específicas" e "Detalhamento por Fluxo" da página WPP Fluxo. Spec completa em `Gerenciador de CRM/docs/specs/chatflux-wpp-fluxo.md`.

## O que foi feito

1. **Migration aplicada em produção** (`supabase/migrations/20260710000042_chatflux_wpp_fluxo.sql`):
   - Tabela nova `fact_chatflux_events` (RLS + índices).
   - Mapeamento `abandoned_cart_ia` → flow_name `Carrinho Abandonado` em `dim_wpp_alia_campanha_mapping`.
   - `vw_wpp_flow_leads`, `vw_wpp_flow_revenue`, `vw_wpp_flow_inscritos` recriadas com coluna `ferramenta` (`vekta`/`chatflux`).
   - **Já validado**: a receita do Chatflux aparece corretamente (98 pedidos com `ferramenta='chatflux'` em `vw_wpp_flow_revenue`), confirmando a regra de UTM (`utm_campaign='abandoned_cart_ia'` OU `utm_campaign ILIKE '%welcome%' AND utm_content='chatflux'`).
2. **Ingestão implementada e testada de ponta a ponta:**
   - `ingestion/models/chatflux_models.py` — Pydantic `ChatfluxEvento`.
   - `ingestion/sources/chatflux.py` — `fetch_chatflux_eventos_since` (GET `/api/eventos`, paginado) + `run_chatflux_ingestion` (janela de 3 dias).
   - `ingestion/db/writers.py` — `upsert_chatflux_events`.
   - `api/cron/chatflux.py` — entry point, mesmo padrão do `wpp_flow.py`.
   - `vercel.json` — cron registrado (`5,35 * * * *`).
   - `.env` (local) e `.env.example` — `CHATFLUX_API_BASE_URL` / `CHATFLUX_API_TOKEN`.
   - **Rodado localmente contra a API real: 2.633 eventos upsertados** em `fact_chatflux_events` (janela de 3 dias). Views conferidas no banco: `vw_wpp_flow_leads` (chatflux: 2.068 disparos / 565 respostas) e `vw_wpp_flow_revenue` (chatflux: R$588.979 vs vekta: R$717.682).
3. **Seletor Vekta/Chatflux/Ambos no dashboard** (`dashboard-crm.html`, exceção pontual autorizada à R9):
   - Estado global `wppToolFilter` + `onWppToolFilterChange()` + `_filterByTool()`.
   - `fetchWppFlowLeads`/`fetchWppFlowRevenue` passaram a trazer a coluna `ferramenta`; linhas filtradas logo após o fetch.
   - Corrigido: dentro do bloco "Métricas Específicas" do wf, as métricas "Receita/Disparo" e "Conversão Resposta→Venda" usavam `s.rev`/`s.purchases` (total do canal, sem filtro) — trocado por `wppRevRows`/`wppRevRowsComp` (já filtrados por ferramenta), senão ficariam inconsistentes com "Disparos"/"Respostas" ao filtrar.
   - Seletor `<select id="wf-tool-filter">` posicionado ao lado do título "Métricas específicas" (afeta esse painel + a tabela "Detalhamento por Fluxo" logo abaixo, escopo pedido pelo Daniel). O grid de KPIs genérico do topo ("Faturamento/Compras/Sessões/..." comum a todos os canais) foi mantido fora do escopo do filtro, por não ter sido pedido.
4. **Testado localmente:** sintaxe do JS validada (`node --check`), smoke test com Playwright headless (page carrega, zero erros de console) — a verificação visual autenticada (login por magic-link @minimalclub.com.br) fica para o Daniel, pois exige credenciais reais.
5. **Documentação atualizada:** `PRODUCT.md` (seção 5, glossário de Canal/Ativo) e `Controle Geral/ARCHITECTURE.md` (seção "ingestion-vekta" corrigida de "não iniciado" para o estado real + nova seção "ingestion-chatflux").

## Encerramento

- [x] `CHATFLUX_API_TOKEN`/`CHATFLUX_API_BASE_URL` registradas na Vercel (Production, via CLI).
- [x] Commit + push para `origin` e `empresa` (inclui também `fact_order_history_items`, feature separada já pendente de sessões anteriores — decisão do Daniel foi subir tudo junto).
- [ ] Verificação visual autenticada do seletor no navegador (Daniel) — pendente, não automatizável (login por magic-link).
- [ ] Acompanhar o primeiro disparo do cron `/api/cron/chatflux` em produção (roda aos minutos `5,35` de cada hora) para confirmar que não há erro de ambiente na Vercel.

## Decisões de produto confirmadas nesta sessão

- Welcome Novos + Recorrentes do Chatflux somam juntos em `Welcome Site` (não diferenciar).
- Carrinho Abandonado é fluxo novo, UTM `abandoned_cart_ia`.
- Receita dentro de Welcome se separa por `utm_content`: `chatflux` vs `vekta`.
- Seletor de ferramenta: autorizado tocar estrutura do dashboard (exceção pontual à R9) — mas testar localmente antes de subir é valorizado.
