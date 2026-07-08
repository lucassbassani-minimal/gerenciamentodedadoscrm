# Relatorio — Efeito Plinko na Atribuicao de Reativacao (Fase 1)

Gerado em 2026-07-08T14:21:50.668973 · Minimal Club · Dashboard CRM

## 1. Contexto e pergunta

Hoje, quando um e-mail ou WhatsApp de reativacao e disparado, ele costuma ser avaliado so pela receita que o Klaviyo/Vekta atribuem via **last-click direto** (o clique que efetivamente fechou a venda). Isso subestima o efeito real, porque esse toque raramente fecha a venda sozinho — ele "acorda" o cliente, que depois passa por outros canais (Meta, Google, direto, organico, outro e-mail, outro WhatsApp) antes de comprar.

Essa analise (Fase 1) mede, usando dados reais de pedidos pagos, o que acontece quando um toque de e-mail ou WhatsApp aparece **no meio do caminho** de uma compra — ou seja, quando nao e o ultimo clique antes dela:

1. Que % de todas as vendas esse canal/fluxo tocou (nao como ultimo clique)?
2. Quanto tempo depois desse toque a compra realmente aconteceu (distribuicao completa, nao so a media)?
3. Quantos outros toques aparecem no meio (evidencia de "cascata" entre canais)?
4. Quem efetivamente fecha a venda, quando nao e o proprio canal analisado?

## 2. Fonte de dados e limitacoes (importante para interpretar os numeros)

- **Fonte:** `Base de Touchpoints.csv`, export nativo do Shopify (nao e um pixel/CDP de eventos brutos). Cada linha e uma **sessao de entrada no site** cujo UTM foi o **last-click daquela sessao** — nao um log de todo micro-evento (abertura de e-mail, impressao de anuncio etc.).
- **Escopo:** somente pedidos com `financial_status = PAID`. 33.758 pedidos pagos no periodo (aprox. maio–julho/2026). Divididos em 17.740 de Primeira Compra e 16.018 de Recompra.
- **Janela de atribuicao:** cada pedido so carrega os touchpoints dos ~30 dias antes da compra — nao e um historico completo de interacao do cliente. Um toque de reativacao que aconteceu mais de 30 dias antes da compra nao aparece nesta base.
- **Sem gate de "cliente frio" ainda** (Fase 2, futura): nao ha verificacao de inatividade previa (90/180/365 dias sem comprar/clicar) antes de considerar um toque como "de reativacao" — todo toque de e-mail/WhatsApp que nao e o ultimo clique conta aqui, mesmo que o cliente ja estivesse "quente". Isso e um vies conservador: o efeito real de reativacao pura tende a ser tao forte ou mais forte que o mostrado aqui.
- **Classificacao de canal:** baseada no `utm_medium` real observado nos dados (nao na tabela idealizada do banco) — ver mapeamento na Secao 6.
- **10.673 eventos qualificados** (toques de CRM no meio do caminho) foram analisados no total, cobrindo os 3 recortes abaixo.

## 3.1. Segmento: Geral (Primeira Compra + Recompra)

**Total de pedidos pagos neste segmento:** 33.758
**Pedidos com QUALQUER toque de CRM (e-mail e/ou WhatsApp) no meio do caminho:** 5.375 (15,9% do total) — receita associada: R$ 3.305.656

### Nivel 1 — Canal completo (E-mail vs. WhatsApp)

#### E-mail

- Pedidos: **2.701** (8,0% do total de vendas do segmento)
- Receita associada: R$ 1.755.674
- Tempo até compra — mediana 3,9d | P50 3,9d | P80 17,7d | P90 23,9d
- % dos pedidos SEM nenhum outro toque no meio (venda direta): 24,7%
- % que fecha pelo MESMO canal do toque analisado: 30,8%
- Média de touchpoints de outros canais no meio: 3.8

Histograma de dias até a compra (contagem de pedidos por faixa):

| 0-1d | 1-3d | 3-7d | 7-14d | 14-21d | 21-30d | 30d+ |
|---|---|---|---|---|---|---|
| 966 | 288 | 345 | 369 | 344 | 389 | 0 |

Distribuição de quem fecha a venda:

| Canal que fecha | Pedidos | % |
|---|---:|---:|
| Outro (ads/direto/organico) | 1.325 | 49,1% |
| E-mail Campanha | 573 | 21,2% |
| E-mail Fluxo | 476 | 17,6% |
| WhatsApp Fluxo | 231 | 8,6% |
| WhatsApp Campanha | 56 | 2,1% |
| WhatsApp Comunidade | 40 | 1,5% |

#### WhatsApp

- Pedidos: **3.323** (9,8% do total de vendas do segmento)
- Receita associada: R$ 1.970.647
- Tempo até compra — mediana 1,3d | P50 1,3d | P80 13,6d | P90 21,2d
- % dos pedidos SEM nenhum outro toque no meio (venda direta): 29,2%
- % que fecha pelo MESMO canal do toque analisado: 34,9%
- Média de touchpoints de outros canais no meio: 3.2

Histograma de dias até a compra (contagem de pedidos por faixa):

| 0-1d | 1-3d | 3-7d | 7-14d | 14-21d | 21-30d | 30d+ |
|---|---|---|---|---|---|---|
| 1.572 | 356 | 349 | 402 | 300 | 344 | 0 |

Distribuição de quem fecha a venda:

| Canal que fecha | Pedidos | % |
|---|---:|---:|
| Outro (ads/direto/organico) | 1.694 | 51,0% |
| WhatsApp Fluxo | 775 | 23,3% |
| WhatsApp Campanha | 406 | 12,2% |
| WhatsApp Comunidade | 166 | 5,0% |
| E-mail Fluxo | 156 | 4,7% |
| E-mail Campanha | 126 | 3,8% |

### Nivel 2 — Os 5 canais oficiais (resumo)

| Canal | Pedidos | % do total | Mediana | P80 | P90 | Sem toque no meio | Fecha mesmo canal | Receita |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| E-mail Fluxo | 1.507 | 4,5% | 1,8d | 13,5d | 21,6d | 26,1% | 25,8% | R$ 911.991 |
| E-mail Campanha | 1.626 | 4,8% | 6,6d | 19,3d | 24,5d | 22,6% | 32,5% | R$ 1.114.893 |
| WhatsApp Fluxo | 2.284 | 6,8% | 0,8d | 8,1d | 16,8d | 31,6% | 29,9% | R$ 1.343.180 |
| WhatsApp Campanha | 924 | 2,7% | 3,9d | 17,8d | 23,6d | 28,5% | 40,6% | R$ 525.714 |
| WhatsApp Comunidade | 365 | 1,1% | 8,6d | 22,7d | 27,2d | 16,2% | 44,4% | R$ 258.105 |

### Nivel 3 — Fluxos individuais (top 15 por volume)

**E-mail Fluxo:**

| Fluxo | Pedidos | % do total | Mediana | P80 | Sem toque no meio | Fecha mesmo canal | Receita |
|---|---:|---:|---:|---:|---:|---:|---:|
| [FLUXO] Welcome - Novo Modelo 2026 | 589 | 1,7% | 1,0d | 10,3d | 28,9% | 26,3% | R$ 364.090 |
| *(nao mapeado)* Nao mapeado: cartstack/carrinho | 510 | 1,5% | 1,1d | 11,8d | 25,9% | 27,6% | R$ 302.924 |
| [Fluxo] PageView - Perpetuo - Novo Modelo 2026 | 269 | 0,8% | 7,2d | 19,4d | 18,6% | 23,4% | R$ 175.965 |
| *(nao mapeado)* Nao mapeado: perpetuo/leads | 58 | 0,2% | 4,9d | 15,8d | 25,9% | 37,9% | R$ 27.398 |
| *(nao mapeado)* Ambiguo (campaign=abandoned_cart, term=leads) - possiveis: ['[Fluxo] Recuperação de Check-out Shopify - Envio ChatFlux - Novo Modelo 2026', '[Fluxo] Recuperação de Check-out [Chat Flux] - Novo Modelo 2026'] | 50 | 0,1% | 1,7d | 9,0d | 28,0% | 22,0% | R$ 24.336 |
| *(nao mapeado)* Ambiguo (campaign=abandoned_cart, term=clientes) - possiveis: ['[Fluxo] Recuperação de Check-out Shopify - Envio ChatFlux - Novo Modelo 2026', '[Fluxo] Recuperação de Check-out [Chat Flux] - Novo Modelo 2026'] | 44 | 0,1% | 4,7d | 12,8d | 31,8% | 27,3% | R$ 29.217 |
| [Fluxo] Fluxo MOF - Compre 3 e Leve 4 + Brinde - Novo Modelo 2026 | 38 | 0,1% | 0,4d | 4,5d | 36,8% | 31,6% | R$ 17.135 |
| [Fluxo] Fluxo MOF - Jeans Novos - Novo Modelo 2026 | 33 | 0,1% | 0,3d | 5,4d | 18,2% | 36,4% | R$ 21.478 |
| [FLUXO] [AQUISIÇÃO] - Pageview 30-60D - Novo Modelo 2026 | 31 | 0,1% | 2,8d | 12,1d | 19,4% | 41,9% | R$ 17.345 |
| [FLUXO] [AQUISIÇÃO] - Pageview 60-90D - Novo Modelo 2026 | 19 | 0,1% | 2,2d | 9,9d | 5,3% | 26,3% | R$ 10.889 |
| [Fluxo] Fluxo MOF - Camiseta T - Novo Modelo 2026 | 17 | 0,1% | 0,7d | 2,4d | 41,2% | 41,2% | R$ 8.154 |
| [Fluxo] Welcome Facebook | 14 | 0,0% | 1,2d | 9,5d | 42,9% | 14,3% | R$ 8.689 |
| [Fluxo] Fluxo MOF - Compre 3 e Leve 4 - Novo Modelo 2026 | 12 | 0,0% | 1,0d | 10,6d | 25,0% | 33,3% | R$ 6.300 |
| [Fluxo] [Retenção] - 21 - 60 DIAS | 11 | 0,0% | 3,1d | 7,8d | 27,3% | 36,4% | R$ 6.425 |
| [Fluxo] Fluxo MOF - Comfort - Novo Modelo 2026 | 11 | 0,0% | 6,2d | 16,0d | 27,3% | 45,5% | R$ 6.073 |

*+ 19 outros fluxos menores, somando 73 pedidos (omitidos aqui por volume baixo).*

**WhatsApp Fluxo:**

| Fluxo | Pedidos | % do total | Mediana | P80 | Sem toque no meio | Fecha mesmo canal | Receita |
|---|---:|---:|---:|---:|---:|---:|---:|
| Welcome Site | 1.066 | 3,2% | 0,7d | 8,9d | 32,6% | 30,2% | R$ 625.390 |
| *(nao mapeado)* Nao mapeado: abandoned_cart_ia/recuperacaodecheck_out_ia | 824 | 2,4% | 0,5d | 4,4d | 33,6% | 25,7% | R$ 490.017 |
| Welcome TOF | 298 | 0,9% | 0,3d | 5,5d | 31,2% | 44,6% | R$ 154.178 |
| Pageview | 217 | 0,6% | 4,2d | 19,1d | 23,5% | 29,5% | R$ 131.647 |
| Up-Sell Perpetuo | 53 | 0,2% | 1,0d | 6,6d | 34,0% | 34,0% | R$ 34.943 |
| *(nao mapeado)* Nao mapeado: upsell_sorteiocopa/entre700e1400 | 24 | 0,1% | 9,4d | 24,0d | 16,7% | 16,7% | R$ 16.359 |
| *(nao mapeado)* Nao mapeado: upsell_sorteiocopa/menos700 | 14 | 0,0% | 12,1d | 25,0d | 7,1% | 7,1% | R$ 5.797 |
| *(nao mapeado)* Nao mapeado: (utm_campaign vazio) | 5 | 0,0% | 0,8d | 0,8d | 0,0% | 40,0% | R$ 3.028 |
| *(nao mapeado)* Nao mapeado: welcomefacebook/welcomefacebook | 5 | 0,0% | 0,1d | 2,0d | 20,0% | 20,0% | R$ 4.264 |
| *(nao mapeado)* Nao mapeado: pageview-30-60d/compre3eleve4maiscarteira | 2 | 0,0% | 7,7d | 10,9d | 0,0% | 0,0% | R$ 1.081 |
| *(nao mapeado)* Nao mapeado: upsell_sorteiocopa/entre1400e2100 | 2 | 0,0% | 19,9d | 20,6d | 0,0% | 0,0% | R$ 1.385 |
| *(nao mapeado)* Nao mapeado: abandoned_cart/primeiracompra | 2 | 0,0% | 5,2d | 5,7d | 0,0% | 50,0% | R$ 1.154 |
| *(nao mapeado)* Nao mapeado: abandoned_cart/recuperacaodecheck_out_comercial | 1 | 0,0% | 16,0d | 16,0d | 0,0% | 0,0% | R$ 924 |
| *(nao mapeado)* Nao mapeado: blackfriday2025/welcome | 1 | 0,0% | 14,7d | 14,7d | 100,0% | 100,0% | R$ 538 |

## 3.2. Segmento: Primeira Compra

**Total de pedidos pagos neste segmento:** 17.740
**Pedidos com QUALQUER toque de CRM (e-mail e/ou WhatsApp) no meio do caminho:** 2.025 (11,4% do total) — receita associada: R$ 1.076.083

### Nivel 1 — Canal completo (E-mail vs. WhatsApp)

#### E-mail

- Pedidos: **805** (4,5% do total de vendas do segmento)
- Receita associada: R$ 443.403
- Tempo até compra — mediana 1,1d | P50 1,1d | P80 10,8d | P90 20,3d
- % dos pedidos SEM nenhum outro toque no meio (venda direta): 27,8%
- % que fecha pelo MESMO canal do toque analisado: 28,9%
- Média de touchpoints de outros canais no meio: 3.4

Histograma de dias até a compra (contagem de pedidos por faixa):

| 0-1d | 1-3d | 3-7d | 7-14d | 14-21d | 21-30d | 30d+ |
|---|---|---|---|---|---|---|
| 382 | 99 | 108 | 89 | 52 | 75 | 0 |

Distribuição de quem fecha a venda:

| Canal que fecha | Pedidos | % |
|---|---:|---:|
| Outro (ads/direto/organico) | 407 | 50,6% |
| E-mail Fluxo | 198 | 24,6% |
| WhatsApp Fluxo | 91 | 11,3% |
| E-mail Campanha | 89 | 11,1% |
| WhatsApp Campanha | 20 | 2,5% |

#### WhatsApp

- Pedidos: **1.427** (8,0% do total de vendas do segmento)
- Receita associada: R$ 740.721
- Tempo até compra — mediana 0,6d | P50 0,6d | P80 7,6d | P90 17,0d
- % dos pedidos SEM nenhum outro toque no meio (venda direta): 33,5%
- % que fecha pelo MESMO canal do toque analisado: 37,1%
- Média de touchpoints de outros canais no meio: 2.6

Histograma de dias até a compra (contagem de pedidos por faixa):

| 0-1d | 1-3d | 3-7d | 7-14d | 14-21d | 21-30d | 30d+ |
|---|---|---|---|---|---|---|
| 829 | 159 | 131 | 121 | 93 | 94 | 0 |

Distribuição de quem fecha a venda:

| Canal que fecha | Pedidos | % |
|---|---:|---:|
| Outro (ads/direto/organico) | 753 | 52,8% |
| WhatsApp Fluxo | 421 | 29,5% |
| WhatsApp Campanha | 151 | 10,6% |
| E-mail Fluxo | 64 | 4,5% |
| E-mail Campanha | 26 | 1,8% |
| WhatsApp Comunidade | 12 | 0,8% |

### Nivel 2 — Os 5 canais oficiais (resumo)

| Canal | Pedidos | % do total | Mediana | P80 | P90 | Sem toque no meio | Fecha mesmo canal | Receita |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| E-mail Fluxo | 596 | 3,4% | 0,9d | 8,1d | 18,2d | 29,5% | 29,9% | R$ 315.443 |
| E-mail Campanha | 302 | 1,7% | 3,0d | 14,5d | 21,3d | 23,5% | 23,2% | R$ 174.736 |
| WhatsApp Fluxo | 1.149 | 6,5% | 0,4d | 5,2d | 14,4d | 34,4% | 33,9% | R$ 593.005 |
| WhatsApp Campanha | 317 | 1,8% | 1,5d | 14,3d | 21,9d | 32,2% | 44,8% | R$ 166.033 |
| WhatsApp Comunidade | 23 | 0,1% | 2,9d | 14,6d | 16,7d | 13,0% | 52,2% | R$ 13.692 |

### Nivel 3 — Fluxos individuais (top 15 por volume)

**E-mail Fluxo:**

| Fluxo | Pedidos | % do total | Mediana | P80 | Sem toque no meio | Fecha mesmo canal | Receita |
|---|---:|---:|---:|---:|---:|---:|---:|
| [FLUXO] Welcome - Novo Modelo 2026 | 275 | 1,6% | 0,7d | 6,6d | 31,6% | 28,7% | R$ 144.894 |
| *(nao mapeado)* Nao mapeado: cartstack/carrinho | 161 | 0,9% | 0,2d | 6,0d | 31,1% | 33,5% | R$ 85.260 |
| [Fluxo] PageView - Perpetuo - Novo Modelo 2026 | 45 | 0,2% | 1,7d | 10,1d | 24,4% | 40,0% | R$ 23.850 |
| *(nao mapeado)* Nao mapeado: perpetuo/leads | 41 | 0,2% | 4,7d | 18,0d | 24,4% | 36,6% | R$ 17.980 |
| *(nao mapeado)* Ambiguo (campaign=abandoned_cart, term=leads) - possiveis: ['[Fluxo] Recuperação de Check-out Shopify - Envio ChatFlux - Novo Modelo 2026', '[Fluxo] Recuperação de Check-out [Chat Flux] - Novo Modelo 2026'] | 40 | 0,2% | 2,3d | 12,5d | 30,0% | 20,0% | R$ 19.344 |
| [FLUXO] [AQUISIÇÃO] - Pageview 30-60D - Novo Modelo 2026 | 28 | 0,2% | 2,5d | 13,1d | 17,9% | 46,4% | R$ 15.557 |
| [Fluxo] Fluxo MOF - Compre 3 e Leve 4 + Brinde - Novo Modelo 2026 | 25 | 0,1% | 0,1d | 4,1d | 44,0% | 36,0% | R$ 10.311 |
| [FLUXO] [AQUISIÇÃO] - Pageview 60-90D - Novo Modelo 2026 | 17 | 0,1% | 2,2d | 10,2d | 5,9% | 29,4% | R$ 9.870 |
| [Fluxo] Fluxo MOF - Jeans Novos - Novo Modelo 2026 | 17 | 0,1% | 0,3d | 3,1d | 11,8% | 29,4% | R$ 9.511 |
| [Fluxo] Fluxo MOF - Camiseta T - Novo Modelo 2026 | 14 | 0,1% | 0,4d | 1,7d | 42,9% | 50,0% | R$ 6.361 |
| [Fluxo] Welcome Facebook | 10 | 0,1% | 2,2d | 7,7d | 30,0% | 20,0% | R$ 7.030 |
| [Fluxo] Fluxo MOF - Compre 3 e Leve 4 - Novo Modelo 2026 | 8 | 0,1% | 1,0d | 10,2d | 25,0% | 37,5% | R$ 4.003 |
| *(nao mapeado)* Nao mapeado: perpetuo/thejourney | 6 | 0,0% | 0,2d | 6,1d | 16,7% | 33,3% | R$ 2.673 |
| [Fluxo] Fluxo MOF - Comfort - Novo Modelo 2026 | 4 | 0,0% | 3,9d | 6,8d | 25,0% | 75,0% | R$ 1.671 |
| [Fluxo] [Retenção] - 21 - 60 DIAS | 2 | 0,0% | 11,0d | 17,6d | 0,0% | 50,0% | R$ 918 |

*+ 8 outros fluxos menores, somando 10 pedidos (omitidos aqui por volume baixo).*

**WhatsApp Fluxo:**

| Fluxo | Pedidos | % do total | Mediana | P80 | Sem toque no meio | Fecha mesmo canal | Receita |
|---|---:|---:|---:|---:|---:|---:|---:|
| Welcome Site | 512 | 2,9% | 0,5d | 5,0d | 35,2% | 32,2% | R$ 269.154 |
| *(nao mapeado)* Nao mapeado: abandoned_cart_ia/recuperacaodecheck_out_ia | 398 | 2,2% | 0,4d | 3,4d | 35,4% | 30,2% | R$ 203.897 |
| Welcome TOF | 251 | 1,4% | 0,2d | 5,1d | 32,3% | 45,4% | R$ 124.634 |
| Pageview | 98 | 0,6% | 1,9d | 16,0d | 25,5% | 31,6% | R$ 50.295 |
| *(nao mapeado)* Nao mapeado: welcomefacebook/welcomefacebook | 4 | 0,0% | 0,0d | 1,2d | 25,0% | 25,0% | R$ 3.866 |
| Up-Sell Perpetuo | 3 | 0,0% | 0,9d | 2,8d | 33,3% | 66,7% | R$ 1.802 |
| *(nao mapeado)* Nao mapeado: (utm_campaign vazio) | 2 | 0,0% | 0,5d | 0,7d | 0,0% | 50,0% | R$ 1.386 |
| *(nao mapeado)* Nao mapeado: upsell_sorteiocopa/entre700e1400 | 1 | 0,0% | 29,4d | 29,4d | 100,0% | 0,0% | R$ 716 |
| *(nao mapeado)* Nao mapeado: upsell_sorteiocopa/menos700 | 1 | 0,0% | 10,4d | 10,4d | 0,0% | 0,0% | R$ 267 |
| *(nao mapeado)* Nao mapeado: abandoned_cart/primeiracompra | 1 | 0,0% | 4,3d | 4,3d | 0,0% | 0,0% | R$ 417 |

## 3.3. Segmento: Recompra

**Total de pedidos pagos neste segmento:** 16.018
**Pedidos com QUALQUER toque de CRM (e-mail e/ou WhatsApp) no meio do caminho:** 3.350 (20,9% do total) — receita associada: R$ 2.229.572

### Nivel 1 — Canal completo (E-mail vs. WhatsApp)

#### E-mail

- Pedidos: **1.896** (11,8% do total de vendas do segmento)
- Receita associada: R$ 1.312.271
- Tempo até compra — mediana 6,0d | P50 6,0d | P80 19,3d | P90 25,0d
- % dos pedidos SEM nenhum outro toque no meio (venda direta): 23,4%
- % que fecha pelo MESMO canal do toque analisado: 31,6%
- Média de touchpoints de outros canais no meio: 4.0

Histograma de dias até a compra (contagem de pedidos por faixa):

| 0-1d | 1-3d | 3-7d | 7-14d | 14-21d | 21-30d | 30d+ |
|---|---|---|---|---|---|---|
| 584 | 189 | 237 | 280 | 292 | 314 | 0 |

Distribuição de quem fecha a venda:

| Canal que fecha | Pedidos | % |
|---|---:|---:|
| Outro (ads/direto/organico) | 918 | 48,4% |
| E-mail Campanha | 484 | 25,5% |
| E-mail Fluxo | 278 | 14,7% |
| WhatsApp Fluxo | 140 | 7,4% |
| WhatsApp Comunidade | 40 | 2,1% |
| WhatsApp Campanha | 36 | 1,9% |

#### WhatsApp

- Pedidos: **1.896** (11,8% do total de vendas do segmento)
- Receita associada: R$ 1.229.927
- Tempo até compra — mediana 3,1d | P50 3,1d | P80 16,5d | P90 23,0d
- % dos pedidos SEM nenhum outro toque no meio (venda direta): 25,9%
- % que fecha pelo MESMO canal do toque analisado: 33,3%
- Média de touchpoints de outros canais no meio: 3.7

Histograma de dias até a compra (contagem de pedidos por faixa):

| 0-1d | 1-3d | 3-7d | 7-14d | 14-21d | 21-30d | 30d+ |
|---|---|---|---|---|---|---|
| 743 | 197 | 218 | 281 | 207 | 250 | 0 |

Distribuição de quem fecha a venda:

| Canal que fecha | Pedidos | % |
|---|---:|---:|
| Outro (ads/direto/organico) | 941 | 49,6% |
| WhatsApp Fluxo | 354 | 18,7% |
| WhatsApp Campanha | 255 | 13,4% |
| WhatsApp Comunidade | 154 | 8,1% |
| E-mail Campanha | 100 | 5,3% |
| E-mail Fluxo | 92 | 4,9% |

### Nivel 2 — Os 5 canais oficiais (resumo)

| Canal | Pedidos | % do total | Mediana | P80 | P90 | Sem toque no meio | Fecha mesmo canal | Receita |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| E-mail Fluxo | 911 | 5,7% | 3,1d | 16,9d | 23,0d | 23,9% | 23,2% | R$ 596.548 |
| E-mail Campanha | 1.324 | 8,3% | 7,4d | 20,1d | 25,1d | 22,4% | 34,7% | R$ 940.157 |
| WhatsApp Fluxo | 1.135 | 7,1% | 1,1d | 11,2d | 18,8d | 28,8% | 25,9% | R$ 750.175 |
| WhatsApp Campanha | 607 | 3,8% | 5,0d | 18,6d | 25,2d | 26,5% | 38,4% | R$ 359.682 |
| WhatsApp Comunidade | 342 | 2,1% | 9,0d | 23,1d | 27,4d | 16,4% | 43,9% | R$ 244.412 |

### Nivel 3 — Fluxos individuais (top 15 por volume)

**E-mail Fluxo:**

| Fluxo | Pedidos | % do total | Mediana | P80 | Sem toque no meio | Fecha mesmo canal | Receita |
|---|---:|---:|---:|---:|---:|---:|---:|
| *(nao mapeado)* Nao mapeado: cartstack/carrinho | 349 | 2,2% | 2,1d | 14,2d | 23,5% | 24,9% | R$ 217.663 |
| [FLUXO] Welcome - Novo Modelo 2026 | 314 | 2,0% | 1,1d | 14,3d | 26,4% | 24,2% | R$ 219.196 |
| [Fluxo] PageView - Perpetuo - Novo Modelo 2026 | 224 | 1,4% | 8,8d | 20,2d | 17,4% | 20,1% | R$ 152.115 |
| *(nao mapeado)* Ambiguo (campaign=abandoned_cart, term=clientes) - possiveis: ['[Fluxo] Recuperação de Check-out Shopify - Envio ChatFlux - Novo Modelo 2026', '[Fluxo] Recuperação de Check-out [Chat Flux] - Novo Modelo 2026'] | 44 | 0,3% | 4,7d | 12,8d | 31,8% | 27,3% | R$ 29.217 |
| *(nao mapeado)* Nao mapeado: perpetuo/leads | 17 | 0,1% | 5,8d | 12,5d | 29,4% | 41,2% | R$ 9.418 |
| [Fluxo] Fluxo MOF - Jeans Novos - Novo Modelo 2026 | 16 | 0,1% | 0,9d | 7,9d | 25,0% | 43,8% | R$ 11.967 |
| [Fluxo] Fluxo MOF - Compre 3 e Leve 4 + Brinde - Novo Modelo 2026 | 13 | 0,1% | 1,5d | 4,7d | 23,1% | 23,1% | R$ 6.825 |
| *(nao mapeado)* Ambiguo (campaign=abandoned_cart, term=leads) - possiveis: ['[Fluxo] Recuperação de Check-out Shopify - Envio ChatFlux - Novo Modelo 2026', '[Fluxo] Recuperação de Check-out [Chat Flux] - Novo Modelo 2026'] | 10 | 0,1% | 0,0d | 3,8d | 20,0% | 30,0% | R$ 4.993 |
| *(nao mapeado)* Nao mapeado: clientes60D/clientes | 9 | 0,1% | 7,0d | 24,1d | 44,4% | 33,3% | R$ 6.982 |
| *(nao mapeado)* Ambiguo (campaign=retencao, term=0-30_dias) - possiveis: ['[Fluxo] [Retenção] - 21 - 60 DIAS', '[Fluxo] [Retenção] - 60 - 90 DIAS', '[Fluxo] [Retenção] - 90 - 120 DIAS', '[Fluxo] [Retenção] 120-150D', '[Fluxo] [Retenção] 150-180D', '[Fluxo] [Retenção] 180-210D'] | 9 | 0,1% | 7,0d | 19,2d | 33,3% | 22,2% | R$ 4.117 |
| [Fluxo] [Retenção] - 21 - 60 DIAS | 9 | 0,1% | 3,1d | 6,8d | 33,3% | 33,3% | R$ 5.507 |
| [Fluxo] Fluxo MOF - Comfort - Novo Modelo 2026 | 7 | 0,0% | 8,3d | 20,3d | 28,6% | 28,6% | R$ 4.401 |
| *(nao mapeado)* Nao mapeado: upsell_sorteiocopa/menos700 | 6 | 0,0% | 7,8d | 21,4d | 0,0% | 0,0% | R$ 3.824 |
| [Fluxo] [Retenção] 120-150D | 6 | 0,0% | 2,2d | 14,9d | 50,0% | 50,0% | R$ 3.606 |
| [Fluxo] [Retenção] 180-210D | 5 | 0,0% | 0,8d | 12,1d | 40,0% | 40,0% | R$ 3.568 |

*+ 15 outros fluxos menores, somando 38 pedidos (omitidos aqui por volume baixo).*

**WhatsApp Fluxo:**

| Fluxo | Pedidos | % do total | Mediana | P80 | Sem toque no meio | Fecha mesmo canal | Receita |
|---|---:|---:|---:|---:|---:|---:|---:|
| Welcome Site | 554 | 3,5% | 1,0d | 11,0d | 30,3% | 28,3% | R$ 356.236 |
| *(nao mapeado)* Nao mapeado: abandoned_cart_ia/recuperacaodecheck_out_ia | 426 | 2,7% | 0,7d | 5,3d | 31,9% | 21,6% | R$ 286.120 |
| Pageview | 119 | 0,7% | 6,5d | 19,3d | 21,8% | 27,7% | R$ 81.352 |
| Up-Sell Perpetuo | 50 | 0,3% | 1,0d | 7,0d | 34,0% | 32,0% | R$ 33.141 |
| Welcome TOF | 47 | 0,3% | 1,1d | 11,1d | 25,5% | 40,4% | R$ 29.543 |
| *(nao mapeado)* Nao mapeado: upsell_sorteiocopa/entre700e1400 | 23 | 0,1% | 8,8d | 20,2d | 13,0% | 17,4% | R$ 15.643 |
| *(nao mapeado)* Nao mapeado: upsell_sorteiocopa/menos700 | 13 | 0,1% | 13,8d | 25,4d | 7,7% | 7,7% | R$ 5.530 |
| *(nao mapeado)* Nao mapeado: (utm_campaign vazio) | 3 | 0,0% | 0,8d | 0,8d | 0,0% | 33,3% | R$ 1.642 |
| *(nao mapeado)* Nao mapeado: pageview-30-60d/compre3eleve4maiscarteira | 2 | 0,0% | 7,7d | 10,9d | 0,0% | 0,0% | R$ 1.081 |
| *(nao mapeado)* Nao mapeado: upsell_sorteiocopa/entre1400e2100 | 2 | 0,0% | 19,9d | 20,6d | 0,0% | 0,0% | R$ 1.385 |
| *(nao mapeado)* Nao mapeado: abandoned_cart/recuperacaodecheck_out_comercial | 1 | 0,0% | 16,0d | 16,0d | 0,0% | 0,0% | R$ 924 |
| *(nao mapeado)* Nao mapeado: abandoned_cart/primeiracompra | 1 | 0,0% | 6,0d | 6,0d | 0,0% | 100,0% | R$ 737 |
| *(nao mapeado)* Nao mapeado: blackfriday2025/welcome | 1 | 0,0% | 14,7d | 14,7d | 100,0% | 100,0% | R$ 538 |
| *(nao mapeado)* Nao mapeado: welcomefacebook/welcomefacebook | 1 | 0,0% | 1,7d | 1,7d | 0,0% | 0,0% | R$ 398 |

## 4. Campanhas/fluxos nao mapeados (gap de configuracao)

Toda campanha/termo de UTM que apareceu nos dados mas nao bate com a planilha `configuracoes de utm.xlsx` (e-mail) nem com as tabelas `dim_wpp_origem_mapping`/`dim_wpp_alia_campanha_mapping` do Supabase (WhatsApp). Reportado em vez de descartado.

| Campanha/termo (raw) | Ocorrencias |
|---|---:|
| Nao mapeado: abandoned_cart_ia/recuperacaodecheck_out_ia | 1.017 |
| Nao mapeado: cartstack/carrinho | 742 |
| Nao mapeado: perpetuo/leads | 67 |
| Ambiguo (campaign=abandoned_cart, term=leads) - possiveis: ['[Fluxo] Recuperação de Check-out Shopify - Envio ChatFlux - Novo Modelo 2026', '[Fluxo] Recuperação de Check-out [Chat Flux] - Novo Modelo 2026'] | 60 |
| Ambiguo (campaign=abandoned_cart, term=clientes) - possiveis: ['[Fluxo] Recuperação de Check-out Shopify - Envio ChatFlux - Novo Modelo 2026', '[Fluxo] Recuperação de Check-out [Chat Flux] - Novo Modelo 2026'] | 48 |
| Nao mapeado: upsell_sorteiocopa/entre700e1400 | 36 |
| Nao mapeado: upsell_sorteiocopa/menos700 | 23 |
| Nao mapeado: perpetuo/thejourney | 12 |
| Nao mapeado: clientes60D/clientes | 10 |
| Ambiguo (campaign=retencao, term=0-30_dias) - possiveis: ['[Fluxo] [Retenção] - 21 - 60 DIAS', '[Fluxo] [Retenção] - 60 - 90 DIAS', '[Fluxo] [Retenção] - 90 - 120 DIAS', '[Fluxo] [Retenção] 120-150D', '[Fluxo] [Retenção] 150-180D', '[Fluxo] [Retenção] 180-210D'] | 10 |
| Nao mapeado: (utm_campaign vazio) | 6 |
| Nao mapeado: welcomefacebook/welcomefacebook | 6 |
| Nao mapeado: blackfriday2025/welcome | 5 |
| Nao mapeado: pageview-30-60d/compre3eleve4maiscarteira | 3 |
| Nao mapeado: upsell_sorteiocopa/entre1400e2100 | 3 |
| Nao mapeado: fluxo_desengajamento/clientes | 2 |
| Nao mapeado: abandoned_cart/primeiracompra | 2 |
| Nao mapeado: fluxo_desengajamento/leads | 1 |
| Nao mapeado: abandoned_cart/recuperacaodecheck_out_comercial | 1 |
| Nao mapeado: perpetuo/entregadosvouchers | 1 |
| Nao mapeado: welcome_geral/primeira-compra | 1 |
| Nao mapeado: fluxo_desengajamento/ | 1 |

**Maiores gaps:** `abandoned_cart_ia` (fluxo de recuperacao de carrinho via IA, ~1.841 pedidos somando e-mail e WhatsApp) e `cartstack` (ferramenta de terceiro, ~742 pedidos) nao existem em nenhuma referencia cadastrada — vale adicionar antes da Fase 2.

## 5. Achados principais (sintese)

1. **Efeito Plinko confirmado mesmo sem gate de cliente frio:** so ~31% dos pedidos tocados por e-mail no meio do caminho fecham pelo proprio e-mail (~35% no WhatsApp) — a maior fatia fecha por "Outro" (Meta/Google/direto/organico).
2. **Recompra e tocada quase 2x mais que Primeira Compra:** 20,9% dos pedidos de recompra tiveram toque de CRM no meio, contra 11,4% na primeira compra — o efeito Plinko pesa mais na regua de recompra.
3. **WhatsApp reativa mais rapido que e-mail:** mediana de 1,3 dia vs. 3,9 dias ate a compra (visao geral).
4. **Gaps de configuracao de UTM** (Secao 4) escondem parte do volume real de dois fluxos de alto volume.

## 6. Regras de classificacao usadas (para auditoria)

| Canal oficial | utm_medium considerado (case-insensitive) |
|---|---|
| E-mail Fluxo | `email_fluxo`, `fluxos_crm` |
| E-mail Campanha | `email_campanha` |
| WhatsApp Fluxo | `whatsapp_fluxo`, `whatsapp_fluxo_ia` |
| WhatsApp Campanha | `whatsapp_campanha` |
| WhatsApp Comunidade | `comunidade` |

Um "toque de reativacao" = touchpoint com um desses `utm_medium`, que NAO e o ultimo clique antes da compra (`is_last_before_purchase = false`). "Dias ate a compra" = `processed_at` (data/hora da compra) menos `touchpoint_at` (data/hora desse toque especifico). Quando um pedido tem mais de um toque qualificado do mesmo tipo, usa-se o primeiro cronologicamente (e o que "soltou a ficha").