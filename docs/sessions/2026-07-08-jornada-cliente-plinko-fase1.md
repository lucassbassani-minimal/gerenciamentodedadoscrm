# Jornada do Cliente — Efeito Plinko, Fase 1 entregue
**Data:** 08/07/2026 | **Status:** entregue — artifact publicado, aguardando decisão do Daniel sobre próximos passos

## Contexto

Blueprint em `Jornada do Cliente/Claude.md jornadas`, escrito para medir o efeito Plinko: quando um toque de
reativação (e-mail ou WhatsApp) acontece no meio do caminho de uma compra (não como último clique), quanto
tempo depois a venda sai e quem realmente fecha.

## Decisões de escopo tomadas com o Daniel

1. **Base usada:** `Jornada do Cliente/Base de Touchpoints.csv` — export da Shopify, last-click por sessão,
   128.912 linhas / 33.758 pedidos pagos, mai–jul/2026. Confirmado com o Daniel que é dado nativo do
   Shopify (não pixel/CDP de eventos brutos) — cada touchpoint é a sessão cujo último clique atribuído foi
   aquele canal, não um log de todo micro-evento.
2. **Sem gate de "cliente frio" nesta fase** — a base não tem histórico suficiente (só 30 dias antes de
   cada compra) para calcular inatividade de 90/180/365 dias. Fica para a Fase 2.
3. **Análise em 3 níveis de granularidade**, confirmado com o Daniel: (1) canal completo E-mail vs.
   WhatsApp, (2) os 5 canais oficiais, (3) fluxo individual dentro de E-mail Fluxo e WhatsApp Fluxo.
4. **Referências de nome de fluxo usadas:** `configurações de utm.xlsx` (raiz do projeto, 37 fluxos de
   e-mail) e as tabelas `dim_wpp_origem_mapping` / `dim_wpp_alia_campanha_mapping` no Supabase (projeto
   `gerenciamentodedadoscrm`) para WhatsApp.

## O que foi construído

- `Jornada do Cliente/analise_plinko.py` — script Python (sem pandas) que carrega a base, classifica cada
  touchpoint nos 5 canais oficiais, calcula tempo até compra / cascata / quem fecha nos 3 níveis, e reporta
  explicitamente qualquer `utm_campaign` que não bate com as referências como "não mapeado" em vez de
  descartar.
- `Jornada do Cliente/dados_dashboard.json` — saída consumida pelo artifact.
- Artifact publicado: dashboard com 5 abas (Visão Geral, Os 5 Canais, Fluxos de E-mail, Fluxos de WhatsApp,
  Não Mapeados).

## Achados principais

1. Entre os 33.758 pedidos pagos do período, 5.375 (15,9%) tiveram um toque de e-mail ou WhatsApp no meio
   do caminho, não como último clique — receita associada de R$ 3,3 milhões (17,5% do total).
2. **Efeito Plinko confirmado mesmo sem o gate de cliente frio:** só 30,8% dos pedidos tocados por e-mail
   no meio fecham pelo próprio e-mail (34,9% no WhatsApp) — a maior fatia fecha por "Outro" (ads/direto/
   orgânico): 49,1% no e-mail, 51,0% no WhatsApp.
3. Mediana de tempo até compra: 3,9 dias para e-mail, 1,3 dias para WhatsApp (P80: 17,7d e 13,6d
   respectivamente) — WhatsApp reativa mais rápido que e-mail.
4. Dentro dos 5 canais, WhatsApp Comunidade é o que mais fecha pelo próprio canal (44,4%) mas tem o maior
   tempo de resposta (mediana 8,6 dias) — sugere um público mais engajado mas menos impulsivo.
5. **Gaps de configuração encontrados:** dois fluxos de alto volume não existem em nenhuma referência —
   "abandoned_cart_ia" (~1.841 pedidos, recuperação de carrinho via IA) e "cartstack" (~742 pedidos,
   ferramenta de terceiro). Recomendação: cadastrar essas duas linhas na planilha/tabela de config antes da
   Fase 2.

## Ajustes pedidos pelo Daniel depois da primeira entrega (mesmo dia)

1. Gráficos de fluxo (abas 3/4) estavam confusos — corrigido: legenda explicando cores, limite de 12
   barras no gráfico (tabela completa continua com todos), nomes de fluxo quebrando em 2 linhas em vez de
   cortar.
2. Adicionado **% do total de vendas** em todo gráfico/tabela de canal e fluxo (não só contagem absoluta) —
   é a métrica que prova o tamanho do efeito Plinko em escala.
3. Adicionado **seletor Geral / Primeira Compra / Recompra** (topo do dashboard, afeta as abas 1-4), sem
   remover a visão combinada — Daniel pediu explicitamente para não perder o resumo geral.
4. Adicionado histograma de "dias até a compra" com P50/P80/P90 em destaque (chips grandes), no lugar de só
   um número na tabela — pedido explícito do Daniel pra deixar essa leitura mais clara.

**Achado novo do corte por segmento:** clientes de recompra são tocados pelo CRM no meio do caminho quase
2x mais que clientes de primeira compra — 20,9% dos pedidos de recompra tiveram toque de e-mail/WhatsApp no
meio, contra 11,4% na primeira compra. Faz sentido (o CRM tem mais histórico de quem já comprou), mas é
uma evidência a mais de que o efeito Plinko pesa mais na régua de recompra do que na de aquisição.

## Próximo passo

Combinado anteriormente (ver Seção 11 do blueprint): Fase 2 é um projeto novo de extração de eventos do
Klaviyo (Opened/Clicked Email por perfil, com timestamp — hoje só existe agregado por mensagem/dia), pra
habilitar o gate de "cliente frio" e o cálculo de taxa de conversão da régua. Ainda não iniciado — decisão
do Daniel sobre priorizar isso.
