# Dashboard CRM · Minimal Club

> Documento de produto. Fonte de verdade do **domínio** e do **comportamento esperado**. Lido por todos os outros documentos. Atualizado quando o produto muda.

---

## 1. Visão e proposta de valor

**Em uma frase:** Dashboard unificado de CRM que consolida métricas de todos os canais de marketing da Minimal Club em um único lugar, com dados reais e atualizados a cada 30 minutos.

**Para quem, qual problema, como resolve:**
O time de CRM da Minimal Club opera cinco canais de marketing (e-mail fluxo, e-mail campanha, WhatsApp fluxo, WhatsApp campanha e comunidade WhatsApp) com dados espalhados em ferramentas diferentes — Klaviyo, Vekta, Sendflow, Shopify e GA4. Isso obriga o time a abrir vários sistemas toda manhã para tomar decisões operacionais simples, sem confiança de que os números estão certos. O dashboard resolve isso centralizando todas as métricas em uma tela única, com atribuição padronizada via UTM (last-click), atualização automática e faixas de alerta visuais para decisões rápidas.

**O que este produto NÃO é:**
- Não é uma ferramenta de disparo ou automação de marketing (não envia e-mails nem mensagens)
- Não é um CRM de relacionamento (não gerencia contatos individualmente)
- Não é um relatório de CAC, LTV ou ROAS (custos por canal fora do escopo V1)
- Não é um sistema de atribuição multi-touch (apenas last-click via UTM)
- Não substitui o Klaviyo, Vekta, Sendflow ou Shopify — lê dados deles, não os opera

---

## 2. Usuários e papéis

### Supervisor e time de CRM
- **Contexto:** Equipe operacional de CRM, usa em desktop no início do dia de trabalho
- **Objetivos no sistema:** Tomar decisões operacionais diárias — identificar canal ou ativo com performance abaixo do esperado e agir (ex: pausar campanha, ajustar copy de fluxo, otimizar formulário de captação)
- **Frustrações atuais:** Abre Klaviyo, Vekta, Sendflow e Shopify separadamente, sem confiança de que a soma dos números bate; gasta tempo reconciliando dados antes de poder agir
- **Frequência de uso:** Diária

### Diretores
- **Contexto:** Liderança da empresa, acessa em desktop em reuniões semanais de performance
- **Objetivos no sistema:** Responder se o canal CRM está dentro da meta orçada e se está evoluindo ao longo do tempo
- **Frustrações atuais:** Não existe visão consolidada de performance do CRM — dados chegam fragmentados ou via relatório manual
- **Frequência de uso:** Semanal

---

## 3. Glossário do domínio

### Disparo
- **Definição:** Ato de enviar uma mensagem de e-mail ou WhatsApp para um contato. Unidade de volume de todos os canais.
- **Exemplo:** O fluxo de carrinho abandonado fez 1.200 disparos ontem.
- **Relações:** Um fluxo ou campanha gera múltiplos disparos. Cada template ou e-mail individual tem seu próprio contador de disparos.
- **NÃO confundir com:** "Envio" — sinônimo proibido no projeto. Usar sempre "disparo".

### Fluxo
- **Definição:** Automação de marketing que roda continuamente 24 horas por dia, 7 dias por semana, disparada por um evento do cliente (ex: abandono de carrinho, cadastro, primeira compra).
- **Exemplo:** "Carrinho Abandonado E-mail" é um fluxo — roda sozinho o tempo todo para qualquer cliente que abandone o carrinho.
- **Relações:** Um fluxo é um ativo pai que contém múltiplos e-mails (canal e-mail) ou templates (canal WhatsApp).
- **NÃO confundir com:** "Automação", "sequência" — sinônimos proibidos.

### Campanha
- **Definição:** Disparo manual e pontual de uma mensagem para uma lista de contatos, decidido e executado pelo time em uma data específica.
- **Exemplo:** "Black Friday 2025 — E-mail" é uma campanha — foi enviada uma única vez para toda a base em novembro.
- **Relações:** Uma campanha é um ativo. No e-mail, a campanha já é o próprio e-mail. No WhatsApp, a campanha pode ter múltiplos templates.
- **NÃO confundir com:** "Blast", "envio em massa" — sinônimos proibidos.

### Ativo
- **Definição:** Qualquer elemento do CRM que gera receita. Inclui fluxos, campanhas, e-mails individuais dentro de fluxos e templates individuais de WhatsApp. Organizado em hierarquia: ativo pai (fluxo ou campanha) e ativo filho (e-mail ou template).
- **Exemplo:** "Carrinho Abandonado E-mail" (ativo pai — fluxo) contém "E-mail 1 — Você esqueceu algo" (ativo filho — e-mail).
- **Relações:** Todo ativo pertence a um canal. Ativos filhos pertencem a um ativo pai.
- **NÃO confundir com:** Usar "ativo" para qualquer elemento CRM; "asset" em inglês não deve aparecer no código ou documentação.

### E-mail
- **Definição:** Mensagem individual dentro de um fluxo ou campanha de e-mail. Tem subject line próprio e métricas individuais.
- **Exemplo:** O fluxo de boas-vindas tem 3 e-mails: "E-mail 1 — Bem-vindo", "E-mail 2 — Nossa história", "E-mail 3 — Primeira oferta".
- **Relações:** Ativo filho do tipo e-mail. Pertence a um fluxo ou é a própria campanha.
- **NÃO confundir com:** "Mensagem" quando o contexto for e-mail.

### Template
- **Definição:** Mensagem individual de WhatsApp dentro de um fluxo ou campanha. Tem conteúdo próprio e métricas individuais de resposta.
- **Exemplo:** O fluxo de carrinho abandonado WhatsApp tem 2 templates: "Template 1 — Lembrete" e "Template 2 — Oferta".
- **Relações:** Ativo filho do tipo WhatsApp. Pertence a um fluxo ou campanha de WhatsApp.
- **NÃO confundir com:** "Mensagem", "copy" — usar sempre "template" para WhatsApp.

### Inscrito
- **Definição:** Contagem acumulada de pessoas que entraram em um fluxo. Contagens de e-mail e WhatsApp são separadas — a mesma pessoa pode ser inscrita em ambos com contagens independentes.
- **Exemplo:** O fluxo de boas-vindas tem 15.000 inscritos de e-mail e 8.000 inscritos de WhatsApp.
- **Relações:** Usado no denominador de KPIs como Receita/Inscrito. Não tem ciclo de vida rastreado — entradas são somadas; uma nova entrada de alguém já inscrito soma novamente.
- **NÃO confundir com:** "Assinante", "contato", "lead" — usar "inscrito" para quem está em fluxo.

### Base Ativa
- **Definição:** Segmento de inscritos de e-mail que abriram ou clicaram em algum e-mail nos últimos 90 dias. Definição oficial: segmento "Engaged 90d" do Klaviyo.
- **Exemplo:** A base total pode ter 40.000 e-mails, mas a base ativa tem 18.000 — os outros 22.000 não abriram nada em 90 dias.
- **Relações:** Denominador do KPI Receita/Inscrito para e-mail. Indicador de saúde da base.
- **NÃO confundir com:** Base total, lista de e-mails — base ativa é sempre o segmento Engaged 90d.

### Canal
- **Definição:** Uma das cinco divisões oficiais do CRM da Minimal Club, cada uma com sua fonte de dados, UTM e KPI principal.
- **Exemplo:** "WhatsApp Fluxo" é um canal. Tem UTM própria, fonte de dados própria (Vekta) e KPI principal próprio (Receita/Inscrito).
- **Relações:** Todo ativo pertence a um canal. Todo pedido atribuído ao CRM pertence a exatamente um canal (last-click).
- **NÃO confundir com:** "Plataforma", "ferramenta" — canal é a classificação de negócio, não a ferramenta técnica.

### Atribuição (Last-click via UTM)
- **Definição:** Regra que determina qual canal recebe o crédito de uma compra. O canal cujo link foi o último clicado antes da compra leva 100% do crédito. Um pedido pertence a exatamente um canal.
- **Exemplo:** Cliente clicou em e-mail de fluxo na segunda e em WhatsApp campanha na terça. Comprou na terça. → Crédito: WhatsApp Campanha.
- **Relações:** Toda receita do dashboard usa esta regra. Pedidos sem UTM de CRM ficam fora do dashboard V1.
- **NÃO confundir com:** Atribuição multi-touch, assistida, ou first-click — não usamos no V1.

---

## 4. Entidades do negócio

### Pedido
- **Atributos relevantes:** ID do pedido, data, valor, canal atribuído (via UTM source + medium), tipo de cliente (1ª compra ou recompra via orders_count), ID do cliente
- **Ciclo de vida:** Nasce como pedido pago no Shopify. Não tem estados intermediários relevantes — apenas pedidos pagos entram no sistema.
- **Quem cria:** Shopify (automático, via compra do cliente)
- **Quem edita:** Não editável no dashboard
- **Quem consulta:** Sistema de ingestão (leitura via API Shopify)

### Ativo (pai: Fluxo ou Campanha)
- **Atributos relevantes:** ID, nome, canal, tipo (fluxo/campanha), status (ativo/inativo), data de criação
- **Ciclo de vida:** Nasce quando criado na ferramenta de origem (Klaviyo, Vekta, Sendflow). Pode ser desativado — ao ser desativado, mantém histórico de métricas no dashboard com marcação visual de "inativo". Não é deletado do dashboard.
- **Quem cria:** Klaviyo (e-mail), Vekta (WhatsApp), Sendflow (comunidade)
- **Quem edita:** Status de ativo/inativo sincronizado da ferramenta de origem
- **Quem consulta:** Time de CRM e diretores via dashboard

### Ativo (filho: E-mail ou Template)
- **Atributos relevantes:** ID, nome/subject line (e-mail) ou conteúdo preview (template), ativo pai, posição no fluxo, métricas individuais
- **Ciclo de vida:** Existe enquanto o ativo pai existe. Métricas acumuladas preservadas mesmo se removido do fluxo.
- **Quem cria:** Klaviyo (e-mail), Vekta (template WA)
- **Quem consulta:** Time de CRM via drill-down nas tabelas de detalhamento

### Meta Mensal
- **Atributos relevantes:** Mês de referência, meta de receita 1ª compra, meta de receita recompra, meta de receita total CRM
- **Ciclo de vida:** Criada no início de cada mês via input manual. Não muda durante o mês.
- **Quem cria:** Daniel (input manual no Supabase)
- **Quem consulta:** Dashboard (pace do mês, projeção de fechamento)

---

## 5. Fluxos principais

### Ingestão diária de dados (automática, a cada 30 minutos)
- **Quem dispara:** Sistema de ingestão automática (scheduler)
- **Pré-condições:** Credenciais de API válidas configuradas no Supabase; projeto Supabase criado e tabelas existentes
- **Passos:**
  1. Scheduler dispara a cada 30 minutos
  2. Puxa pedidos pagos dos últimos 30 dias do Shopify via API (com UTM e orders_count)
  3. Puxa métricas de fluxos e campanhas de e-mail do Klaviyo via API
  4. Puxa dados de formulários e base ativa do Klaviyo Forms API
  5. Puxa disparos, respostas e leads do Vekta via API (WhatsApp Fluxo e Campanha)
  6. Puxa participantes e disparos do Sendflow via API (Comunidade)
  7. Lê planilha Google Sheets (atualizada de hora em hora via exportação BigQuery) para Sessões/ATC/BCO
  8. Grava dados brutos nas tabelas `fact_*` do Supabase (upsert por ID único)
  9. Views calculadas (`vw_*`) atualizam automaticamente na próxima consulta
- **Pós-condições:** Dados nas tabelas `fact_*` refletem estado das últimas 48 horas em todas as fontes
- **Divergências:** Se uma fonte falhar, as outras continuam. Dados da fonte com falha ficam com o último valor válido, com timestamp de última atualização exposto no dashboard.

### Ingestão de dados de sessão (BigQuery → Google Sheets → Supabase, horária)
- **Quem dispara:** Export agendado do BigQuery para Google Sheets (configurado uma vez, roda sozinho)
- **Pré-condições:** Planilha Google Sheets configurada como destino do export BigQuery; Supabase com acesso de leitura à planilha
- **Passos:**
  1. BigQuery exporta dados de Sessões/ATC/BCO por UTM e dia para Google Sheets (horário)
  2. Sistema de ingestão do Supabase lê a planilha a cada hora
  3. Atualiza tabela `fact_sessions` com os novos dados
- **Pós-condições:** Métricas de funil (Sessões/ATC/BCO) atualizadas com até 1 hora de defasagem

### Consulta ao dashboard (tempo real, sob demanda)
- **Quem dispara:** Usuário abrindo o dashboard no navegador
- **Pré-condições:** Dashboard HTML carregado; Supabase online
- **Passos:**
  1. Dashboard carrega e faz requisição à API do Supabase com filtros padrão (MTD, todos os canais)
  2. Supabase executa as views `vw_*` e retorna os dados calculados
  3. Dashboard renderiza gráficos, KPIs e tabelas com os dados recebidos
  4. Usuário aplica filtros (período, canal, tipo de cliente, ativo) — cada mudança dispara nova requisição
- **Pós-condições:** Dados exibidos refletem estado atual do Supabase no momento da consulta
- **Divergências:** Se Supabase estiver fora, dashboard exibe mensagem de erro e último timestamp de dados válidos

### Input de metas mensais (manual, uma vez por mês)
- **Quem dispara:** Daniel, no início de cada mês
- **Passos:**
  1. Acessa interface de input de metas (formulário simples ou tabela no Supabase)
  2. Insere meta de receita 1ª compra, recompra e total para o mês vigente
  3. Dashboard passa a usar os novos valores no pace e na projeção de fechamento
- **Pós-condições:** Gauge de pace e projeção de fechamento atualizados para o mês corrente

---

## 6. KPIs e regras de cálculo

### Faturamento CRM
- **Mede:** Receita total gerada pelos 5 canais de CRM com atribuição last-click
- **Fórmula:** Soma do faturamento de pedidos atribuídos a cada canal via UTM
- **Unidade:** R$ (reais)
- **Frequência:** Diário e mensal (MTD)
- **Normal:** Definido por meta mensal
- **Alerta:** Projeção de fechamento abaixo de 90% da meta

### RPS (Revenue per Session)
- **Mede:** Eficiência do canal em gerar receita por visitante
- **Fórmula:** Faturamento ÷ Sessões
- **Unidade:** R$/sessão
- **Frequência:** Diário
- **Normal / Alerta:** Comparativo vs período anterior (sem faixa fixa — varia por canal e temporada)

### Conversão
- **Mede:** Percentual de visitantes que compram
- **Fórmula:** Compras ÷ Sessões
- **Unidade:** % 
- **Frequência:** Diário
- **Normal / Alerta:** Comparativo vs período anterior

### Ticket Médio
- **Mede:** Valor médio de cada pedido
- **Fórmula:** Faturamento ÷ Compras
- **Unidade:** R$
- **Frequência:** Diário
- **Normal / Alerta:** Comparativo vs período anterior

### Taxa de Abertura (E-mail)
- **Mede:** Percentual de e-mails abertos sobre os enviados
- **Fórmula:** E-mails Abertos ÷ Disparos
- **Unidade:** %
- **Frequência:** Por fluxo/campanha, acumulado
- **Normal:** ≥ 35%
- **Alerta:** < 35%

### CTOR (Click-to-Open Rate)
- **Mede:** Eficiência do conteúdo do e-mail entre quem já abriu
- **Fórmula:** Cliques ÷ Abertos
- **Unidade:** %
- **Frequência:** Por fluxo/campanha, acumulado
- **Normal:** ≥ 10%
- **Alerta:** < 10%

### Bounce Rate (E-mail)
- **Mede:** Percentual de e-mails que não chegaram ao destinatário
- **Fórmula:** Bounces ÷ Disparos
- **Unidade:** %
- **Frequência:** Por fluxo/campanha
- **Normal:** < 2%
- **Alerta:** ≥ 2%

### Spam Complaint Rate
- **Mede:** Percentual de destinatários que marcaram o e-mail como spam
- **Fórmula:** Reclamações ÷ Entregues
- **Unidade:** %
- **Frequência:** Por fluxo/campanha
- **Normal:** < 0,08%
- **Alerta:** ≥ 0,08% (crítico: > 0,1% — risco de blacklist)

### Taxa de Resposta (WhatsApp)
- **Mede:** Percentual de destinatários que responderam à mensagem
- **Fórmula:** Respostas ÷ Disparos
- **Unidade:** %
- **Frequência:** Por fluxo/campanha/template
- **Normal:** ≥ 9%
- **Alerta:** < 9%

### Receita/Inscrito
- **Mede:** Eficiência do canal em gerar receita por inscrito ativo
- **Fórmula:** Faturamento do canal ÷ Inscritos ativos
- **Unidade:** R$/inscrito
- **Frequência:** Diário e mensal
- **Normal / Alerta:** Comparativo vs período anterior (KPI principal de E-mail Fluxo e WhatsApp Fluxo)

### Receita/Disparo
- **Mede:** Eficiência de cada disparo em gerar receita
- **Fórmula:** Faturamento do canal ÷ Disparos
- **Unidade:** R$/disparo
- **Frequência:** Diário e mensal
- **Normal / Alerta:** Comparativo vs período anterior (KPI principal de E-mail Campanha, WhatsApp Campanha e Comunidade)

### CTOR não é CTR
> Regra inviolável: CTOR = Cliques ÷ **Abertos** (não ÷ Enviados). O termo "CTR" foi aposentado neste projeto. Qualquer referência a "CTR de e-mail" no código deve ser lida como CTOR.

---

## 7. Escopo

### 7.1 Entra na V1
- 6 páginas do dashboard (Resumo CRM + 5 canais)
- Dados reais de todos os 5 canais com atribuição last-click via UTM
- Atualização automática a cada 30 minutos (dados de sessão: horária via Google Sheets)
- Filtros globais: período, comparativo, canal, tipo de cliente, fluxo/campanha
- Semáforos de alerta para métricas com faixa definida (abertura, CTOR, bounce, spam, resposta WA)
- Input manual de metas mensais
- Drill-down em tabelas de fluxos (pai → e-mails/templates filhos)
- Rankings top 5 melhores e piores por receita e por KPI principal do canal
- Saúde da base de e-mail (entregabilidade)

### 7.2 Fica para depois
- Saúde da base WhatsApp (Quality Rating, bloqueios) — *depende de acesso ao Meta Business Manager*
- CAC, LTV, ROAS por canal — *custos por canal ainda não estruturados*
- Aba "Sem Atribuição" para UTMs não reconhecidas — *complexidade de classificação manual para V2*
- Migração Hubspot → Klaviyo para inscritos WhatsApp — *em andamento fora do escopo do dashboard*
- Integração direta com BigQuery (sem passar por Google Sheets) — *simplificado para V1*

### 7.3 Nunca vai entrar
- Envio ou agendamento de campanhas — *o dashboard é de leitura, nunca de operação*
- Gestão individual de contatos — *não é um CRM de relacionamento*
- Atribuição multi-touch — *decisão arquitetural definitiva: last-click via UTM*
- Análise de cohort ou retenção detalhada — *fora do problema atual*

---

## 8. Restrições e premissas

### Operacionais
- Dashboard de leitura apenas — nenhuma ação sobre as ferramentas de origem é feita pelo sistema
- Apenas pedidos **pagos** do Shopify entram no sistema — cancelamentos e estornos ignorados na V1
- Pedidos sem UTM de CRM não são atribuídos a nenhum canal e ficam fora do dashboard V1
- Todos os links de CRM precisam ter UTMs no padrão definido (source + medium) para que a atribuição funcione — pré-requisito operacional
- Interface desktop-first — sem otimização para mobile na V1

### Legais / regulatórias
- Nenhuma PII (informação pessoal identificável) de clientes é exposta no dashboard — apenas métricas agregadas
- Chaves de API das ferramentas configuradas com permissão **somente leitura**

### Orçamento / prazo
- Sem deadline externo fixo — confiabilidade dos dados tem prioridade sobre velocidade de entrega
- Stack deve usar plano gratuito ou de baixo custo enquanto possível (Supabase Free Tier para início)

### Integrações futuras esperadas
- Klaviyo como fonte oficial de inscritos WhatsApp (após migração do Hubspot — arquitetura deve prever troca de fonte sem refatoração)
- Acesso direto ao BigQuery via service account (substituir Google Sheets como intermediário na V2)
- Meta Business Manager para saúde da base WhatsApp (quando acesso estiver disponível)

---

### Padrão de UTMs obrigatório

| Canal | utm_source | utm_medium |
|---|---|---|
| E-mail Fluxo | `email` | `flow` |
| E-mail Campanha | `email` | `campaign` |
| WhatsApp Fluxo | `whatsapp` | `flow` |
| WhatsApp Campanha | `whatsapp` | `campaign` |
| WhatsApp Comunidade | `community` | (qualquer) |

> Pré-requisito crítico: auditar todos os links ativos antes de ligar o sistema de ingestão.
