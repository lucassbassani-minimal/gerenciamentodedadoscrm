# Sessão 2026-06-11 — Correção de inscritos e gráfico E-mail Fluxo

## Problema relatado

1. Painel "Métricas específicas" mostrava R$11,52 de receita/inscrito
2. Gráfico mostrava ~R$0,41 de média — inconsistente com o KPI
3. Coluna "Inscritos" no Detalhamento por Fluxo mostrava 4.691 para o Welcome (esperado: ~26.765)

## Diagnóstico

### Bug 1 — Inscritos truncados (root cause: limite de linhas da API Supabase)

`fetchEmailFlowItems` consultava `vw_flow_email_items` que retorna **1 linha por (message_id, data)**.
Com ~350 mensagens × 30 dias = ~10.500 linhas por consulta, o limite de `max_rows` do Supabase
cortava a resposta. O JS agregava dados parciais e exibia inscritos incorretos.

Confirmado via requisição direta à Klaviyo API (script `debug_welcome_sends.py`):
- `[EM001][LEADS] - Welcome`: 19.288 disparos (30 dias) — correto no banco
- `[EM001][CLIENTES] - Welcome`: 7.317 disparos — correto no banco
- Total esperado: ~26.605 | Dashboard exibia: 4.691

### Bug 2 — Gráfico com valores minúsculos

O gráfico calculava: `receita_do_dia / total_inscritos_do_período`
Resultado: (R$10.000/dia) / 26.000 inscritos = R$0,38 ≈ R$0,04 após a correção do bug 1.
Um gráfico diário com denominador acumulado do período não tem sentido.

## Correções aplicadas

### Fix 1 — Função SQL `get_flow_item_metrics`

Migration: `20260611000033_fn_get_flow_item_metrics.sql`

Substitui a query à view por uma função RPC que agrega no banco:
- **Antes:** `vw_flow_email_items` → ~10.500 linhas → truncadas pelo max_rows
- **Depois:** `get_flow_item_metrics(start_date, end_date)` → ~350 linhas (1 por mensagem)

`fetchEmailFlowItems` passa a chamar `_sb.rpc('get_flow_item_metrics', ...)`.

### Fix 2 — Função SQL `get_daily_em001_sends`

Migration: `20260611000034_fn_get_daily_em001_sends.sql`

Retorna disparos diários de e-mails EM001 (aceita `p_flow_id` opcional para filtro de fluxo).
Usado pelo gráfico como denominador diário.

### Fix 3 — Gráfico Receita/Inscrito por dia

Cálculo correto: `receita_do_dia / disparos_EM001_do_dia`

- Canal (todos os fluxos): usa `get_daily_em001_sends(start, end)` sem filtro
- Fluxo selecionado: usa `get_daily_em001_sends(start, end, flow_id)` com filtro

O KPI card "Receita / Inscrito" continua correto: total_receita_período / total_EM001_período.

## Arquivos alterados

| Arquivo | Mudança |
|---|---|
| `dashboard-crm.html` | `fetchEmailFlowItems` usa RPC; gráfico usa `em001ByDay`; override no filtro de fluxo |
| `supabase/migrations/20260611000033_fn_get_flow_item_metrics.sql` | Nova função SQL |
| `supabase/migrations/20260611000034_fn_get_daily_em001_sends.sql` | Nova função SQL |

## Commits

- `f711a51` fix: corrige contagem de inscritos no Detalhamento por Fluxo
- `ea57e60` fix: grafico E-mail Fluxo usa Receita/Disparo diario em vez de Receita/Inscrito
- `e377110` fix: grafico Receita/Inscrito usa EM001 diario como denominador

## Observações

- O botão "↻ Atualizar D-1" chama `renderChannel('ef')` após o backfill — compatível com todas as correções, sem alteração necessária.
- O fluxo Welcome tem duas branches (LEADS e CLIENTES), cada uma com EM001. Ambas são somadas corretamente pela regex `/EM001/i` no JS.
- `vw_flow_email_items` permanece no banco mas não é mais consumida pelo dashboard — pode ser removida numa migration futura se não tiver outro uso.
