# Modelo de Receita de Recompra — taxas de churn/reativação, bug de rollforward, 1ª projeção
**Data:** 13/07/2026 | **Status:** em andamento — Frentes 1 e 2 avançadas, Frente 3 (projeção completa) e Frente 4 (lógica de planilha) pendentes

---

## Contexto

Daniel está remodelando o modelo de receita de recompra da Minimal e trouxe `Análises - Base de Dados Extras/Modelo Receita.xlsx` — não é uma base de dados, é a especificação das fórmulas do modelo (linhas M1...Mx + linha "PROJEÇÃO"). Junto com isso já existiam na mesma pasta:

- `Instrução - Gerar Tabela de Coortes de Recompra.md` + `coortes_recompra_ate_2026-06-30.csv` — pipeline e matriz de coortes já validados por Daniel anteriormente (célula a célula)
- `Todos os negócios - Minimal - BQ. v2.csv` — base bruta de transações (510.915 linhas, e_mail/data/valor/tipo_de_venda/etapa_do_negocio), export do BigQuery (`silver_deals_minimal`)

**Escopo fechado com o Daniel:** só recompra (churn + reativação). **Não entra aquisição** (aROAS/Investimento/SQLs) neste modelo — o plano de investimento que ele vai passar entra só como insumo de quantos clientes novos esperar, não como análise de aquisição em si. Três frentes:
1. Identificar as taxas de churn e reativação históricas
2. Backtest: projetar 2026 como se estivéssemos em dez/2025, comparar com o realizado
3. Projeção real dos próximos meses
4. Entregável final: **não é uma planilha pronta** — é a lógica/fórmulas pro Daniel montar ele mesmo no Google Sheets

## Bug encontrado e corrigido

O cálculo inicial de "Clientes Totais" (rollforward `Totais(m-1) + Novos(m-1) - Churn(m-1)`, acumulado mês a mês) dava **98.623** em jun/2026. Validação direta na base (contagem manual de "última compra dentro dos últimos 12 meses") deu **120.364**. Causa: clientes que churnam, voltam a comprar, e churnam de novo (ex: `00jorgeluiz@gmail.com`) eram subtraídos duas vezes sem nunca ter sido somados de volta na reativação.

**Correção:** `contar_ativos_por_mes()` em `modelo_recompra_taxas.py` agora recalcula quem está "ativo" em cada mês direto da base (snapshot), em vez de acumular soma/subtração. Adicionada coluna `clientes_reentrantes` pra deixar visível a identidade completa:
```
Totais(m+1) = Totais(m) + Novos(m) + Reentrantes(m) - Churn(m)
```
Validado com `assert` no próprio script (ruído residual de 7 clientes em 275 mil, por um efeito de borda de cadastro já conhecido — mesma causa documentada na instrução de coortes).

## Definições fechadas com o Daniel

- **Churn** = 12 meses corridos sem nenhuma compra. Pode acontecer **mais de uma vez** por cliente (churna, reativa, pode churnar de novo).
- **Recente** = cliente cuja 1ª compra caiu nos últimos 6 meses.
- **Meses especiais** (sempre analisados separados do pool geral, nunca misturados na média/percentil dos "meses normais"): **março** (aniversário Minimal, 3ª maior campanha do ano), **novembro** (Black Friday), **dezembro** (Natal/pós-BF). Confirmado que só esses 3 têm sazonalidade própria reconhecida pelo Daniel (mesmo os picos que apareceram em julho/agosto em alguns anos foram descartados como ruído, não sazonalidade real).
- **Base ativa** (conceito simples, sem rollforward): clientes que compraram nos últimos 12 meses, olhando direto a última compra de cada um. Em jun/2026 = **129.594** de 275.761 totais históricos. Esse número foi confirmado como correto pelo Daniel.

### Pendência não resolvida: o que "Clientes Totais" significa no modelo final

Ao longo da sessão, "Clientes Totais" foi usado com dois sentidos diferentes e isso gerou bastante ida e volta:
- **(a)** Soma histórica de todo cliente que já comprou alguma vez — monotônico, só cresce. Em jun/2026 = 275.761.
- **(b)** Base líquida de churn via rollforward (`Totais anterior + Novos + Reentrantes - Churn`) — em jun/2026 = 120.364.

O Daniel confirmou explicitamente a fórmula (b) como "a fórmula de Clientes Totais" em determinado ponto, mas depois estranhou o resultado não bater com 275 mil (que só é possível com a definição (a)). As duas definições são matematicamente incompatíveis quando há churn > 0. **Não ficou fechado qual das duas vai pro modelo final** — retomar isso primeiro na próxima sessão, antes de fechar a Frente 3.

## Números de referência fechados (últimos 12 meses até jun/2026, sem meses especiais)

- Tx Reativação média: **5,13%**
- Tx Churn média: **6,33%**
- Curva de recompra por idade da coorte (toda a história, sem excluir meses especiais ainda):
  - M0: 5,94% | M1: 6,84% | M2: 5,03% | M3: 4,45% | M4: 4,05% | M5: 3,91%

## Plano de aquisição passado pelo Daniel (contagem de clientes novos, não R$)

jul/26=9.491 · ago/26=8.419 · set/26=10.035 · out/26=8.504 · nov/26=31.726 · dez/26=16.037

## Backtest feito (jul/2025, retroativo)

Projetando jul/2025 com a curva de recompra por offset (calculada com dado até jun/2025) × AOV: **+23,9% de erro** (projetado 4.284 recompras vs 3.457 reais). Hipótese não confirmada ainda: a taxa média por offset usada está contaminada por Black Friday/Natal de anos anteriores, inflando a curva. **Próximo passo natural:** refazer a curva de offset excluindo novembro/dezembro do cálculo (do jeito que já foi feito pra Tx Churn/Reativação) e re-testar.

## Projeção de exemplo pra julho/2026 (não fechada, é só o primeiro rascunho)

Usando as coortes de fev-jul/2026 (jul com o número do plano de aquisição, 9.491) × curva de offset:
- **Clientes Recentes em jul/2026: 46.230**
- **Recompras projetadas (bucket Recentes): 2.382**
- Falta somar o bucket "Ativos não recentes" pra fechar o total (depende de resolver a pendência de Clientes Totais acima primeiro).

## Arquivos gerados nesta sessão

Todos em `Análises - Base de Dados Extras/` — **pasta gitignorada, nada disso está versionado no git**:
- `modelo_recompra_taxas.py` — série mensal, taxas de churn/reativação, percentis de orçamento, meses especiais
- `modelo_recompra_backtest.py` — backtest jan-jun/2026 vs orçado (meses normais + março separado)
- `modelo_recompra_referencia.py` — tabela consolidada média/mediana/percentis por grupo de mês
- `modelo_recompra_planilha.py` — consolida tudo num único `.xlsx` com 8 abas (gerado uma vez; Daniel pediu depois pra parar de gerar arquivo e trazer os números só no chat)

## Próximos passos (retomar amanhã)

1. Fechar a definição de "Clientes Totais" (pendência acima) — decisão do Daniel, não é algo pra eu assumir.
2. Refazer a curva de recompra por offset (M0-M5) excluindo novembro/dezembro, re-rodar o backtest de jul/2025 pra ver se o erro cai.
3. Terminar a Frente 3: projeção completa jul-dez/2026 (Recentes + Ativos não recentes somados), usando o plano de aquisição que o Daniel já passou.
4. Frente 4 (ainda não iniciada): documento de lógica de fórmulas pro Daniel montar a projeção no Google Sheets — é o entregável final pedido, não uma planilha pronta.
