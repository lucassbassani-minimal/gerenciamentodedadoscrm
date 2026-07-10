# Recompra, LTV e Redesenho de Fluxos do Zero
**Data:** 01/07/2026 | **Status:** análise em pausa — aguardando dados do Daniel

---

## Contexto

Os fluxos de CRM de recompra existentes foram cortados por onerar custo sem gerar receita. Hoje a Minimal Club **não tem fluxo de recompra ativo**. O objetivo é desenhar um modelo novo do zero, baseado em comportamento real de compra — **não** em receita atribuída aos fluxos antigos (decisão explícita do Daniel: essa fonte não é confiável para embasar a decisão nova).

## Fonte de dados usada

Planilha de pedidos por e-mail (Google Sheets, export manual, fora do Supabase): `data_de_fechamento`, `valor`, `e_mail`. 499.280 linhas válidas, 289.252 e-mails únicos, 25/10/2021 a 01/07/2026. Scripts e HTML do relatório ficaram em scratchpad de sessão (não versionados no repo, pois é análise ad-hoc, não pipeline de produção).

## O que já foi analisado

1. **Recompra e LTV por janela (base inteira, sem filtro de maturidade):** 30d 7,66% / 60d 11,32% / 90d 14,05% / 180d 19,71% / 12m 26,22% / total 32,51%.
2. **Correção por cohort (só clientes maduros por janela):** 12 meses sobe de 26,22% para **30,58%** — viés de ~4,4pp por incluir clientes recentes demais nas janelas longas.
3. **Mapa de calor mensal** (58 cohorts, out/2021–jul/2026) de recompra e LTV.
4. **Timing de recompra:** mediana de 120 dias até a 2ª compra, média 211 dias (cauda longa — parte relevante recompra só depois de 1-2 anos).
5. **Base fria:** 195.209 clientes (67,5%) só compraram 1x. Dessas, **151.763 (77,7%) já passaram de 6 meses sem voltar** — tamanho do público-alvo de um eventual fluxo de win-back.
6. **Recompra por ticket da 1ª compra (quartis):** não é linear — Q2 recompra mais (38,1%) mas mais devagar (165d); Q3 recompra menos (27,9%) e mais rápido (109d). Sinal de que o fluxo provavelmente não deveria ser único pra toda a base.

## Decisão pendente: dados que o Daniel vai buscar

Antes de fechar a conclusão de como os novos fluxos devem trabalhar, faltam (por prioridade):

**Alta prioridade**
1. **Produto/categoria por pedido** (line items do Shopify, não só valor total) — para explicar a diferença Q2 x Q3 e diferenciar fluxo de reposição vs. fluxo de novidade/cross-sell.
2. **Status atual de contato** (quem ainda tem e-mail inscrito/válido no Klaviyo e quem optou por WhatsApp no Vekta) — para saber o tamanho real do público endereçável entre os 151.763 "frios".
3. **Custo por disparo em cada canal** (Klaviyo por contato/mês, WhatsApp Business API por mensagem/template) — para não repetir o erro que motivou o corte dos fluxos antigos.

**Média prioridade**
4. Canal de origem da 1ª compra por cliente (UTM) — parcialmente disponível em `fact_orders` a partir de 23/04/2026; histórico mais antigo exigiria export do Shopify/GA com UTM.
5. Uso de cupom/desconto por pedido.
6. Fluxos/campanhas ativos hoje em Klaviyo/Vekta, para não duplicar disparo.

**Baixa prioridade**
7. Dados de pós-venda/reclamação.
8. Meta de negócio para recompra (referência de ambição, não um dado de comportamento).

## Próximo passo

Retomar quando o Daniel trouxer os dados de produto/categoria e status de contato (itens 1 e 2) — são os que mais mudam a conclusão. Vekta e Klaviyo não estão com MCP conectado nesta sessão, então não foi possível puxar isso diretamente; depende de export manual dele por enquanto.
