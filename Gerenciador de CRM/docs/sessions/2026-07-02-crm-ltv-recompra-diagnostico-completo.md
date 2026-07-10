# Diagnóstico Completo de LTV 30 Dias e Recompra (reset da análise anterior)
**Data:** 02/07/2026 | **Status:** entregue — artifact publicado, aguardando decisão do Daniel sobre quais iniciativas do roadmap priorizar

---

## Contexto

Continuação da análise de recompra/LTV de 01/07, mas o Daniel pediu para "zerar" e reconstruir a partir de um briefing muito mais amplo (33 perguntas de negócio, de funil de recompra a market basket a plano de ação de CRM). Ver `docs/sessions/2026-07-01-recompra-ltv-novos-fluxos.md` para o histórico anterior (ainda válido como registro, mas superado como entregável).

## Dados novos trazidos pelo Daniel

- **`Todos os pedidos Minimal/`** (pasta local, git-ignored): 36 zips de export do Shopify, item por pedido — 550.447 linhas, 223.542 pedidos pagos, cobertura **jan/2025 a jul/2026** (não é histórico completo, é o que o Daniel tinha disponível).
- Planilha antiga (`vendas_historico.csv`, 2021-2026, email+data+valor) já existia da sessão anterior, recuperada do scratchpad da sessão `02899bfe...`.

## Infraestrutura criada no Supabase (projeto `gerenciamentodedadoscrm`)

Tabelas novas e isoladas — nenhuma altera `fact_orders` ou qualquer coisa lida pelo dashboard:

- `fact_order_history_items` — item por pedido, jan/2025-jul/2026 (488.959 linhas carregadas)
- `fact_order_history_legacy` — email+data+valor, 2021-2026 (499.280 linhas, truncate+insert já que a fonte não tem order_id)
- 7 materialized views de apoio (ver ARCHITECTURE.md seção 3): `mv_order_history_category`, `mv_customer_purchase_sequence`, `mv_customer_ltv_windows`, `mv_order_dominant_product`, `mv_purchase_sequence_product`, `mv_first_purchase_category`, `mv_first_purchase_product`

Scripts de backfill (`ingestion/backfill/`, não são cron):
- `load_order_history.py` — carrega os zips do Shopify (filtra só `financial_status=paid`, R5)
- `load_order_history_legacy.py` — carrega a planilha antiga

## Decisões de escopo tomadas com o Daniel

1. **Granularidade de "produto":** 210 modelos (ex: "Camiseta Minimal"), sem quebrar por cor/tamanho — Daniel rejeitou explicitamente a opção por categoria ampla (9 grupos) E a opção de 5.506 variantes exatas de SKU.
2. **Cobertura de dados aceita como está:** export do Shopify só tem jan/2025 em diante; Daniel confirmou que é o que ele tinha, não vai atrás de mais histórico agora.
3. **Bug corrigido durante a sessão:** pedidos duplicados no mesmo dia (checkout dividido) estavam sendo contados como recompra instantânea — corrigido para exigir `order_date > first_purchase_date`. Sem essa correção, todas as taxas de recompra por janela vinham infladas (~15% de erro relativo).

## Achados principais (ver artifact para detalhe completo)

1. Maior salto de recompra natural é 90→180 dias (+6,5pp) — CRM hoje não antecipa isso.
2. Produto mais vendido (Camiseta Minimal) não é o que gera melhor cliente — Calça Comfort recompra quase o dobro (26,2% vs 13,8% em 90d).
3. Ticket da 1ª compra prevê LTV: Top 10% LTV começou com R$829 de ticket médio; Bottom 10% com R$106.
4. Elasticidade de mix é a maior alavanca: sair de 1 para 2 categorias quase triplica o LTV (R$819 → R$2.199).
5. 2ª compra em Kit (2x/3x) prevê LTV 2-4x maior do que peça avulsa.
6. Cluster de market basket real: "montagem de guarda-roupa de inverno" (Jaqueta+Calça+Suéter Essential/Westfield, lift 22-57x) e "comprador de presente" (Carteira+Perfume+Kit Cuidado Facial, lift 18-20x — provavelmente terceiros, não uso próprio).
7. Simulação: +10pp na recompra de 30 dias ≈ R$6,8 mi/ano de receita incremental (piso conservador, não conta efeito de mix).

## Entregável

Artifact publicado: relatório completo com os 7 módulos + rankings finais + roadmap de CRM priorizado em matriz Impacto × Esforço (5 iniciativas detalhadas com hipótese/evidência/campanha/KPI/receita incremental).

## Próximo passo

Nenhuma ação de banco pendente. Próximo passo é o Daniel decidir quais das 5 iniciativas do roadmap tocar primeiro (as 2 marcadas "Quick Win" — segmentação por categoria e reativação do Top 20% LTV — são as de menor esforço de implementação, já que usam fluxos que já existem no Klaviyo/Vekta, só resegmentados).
