# Roteiro da apresentação: Help Desk AI First (CloudWalk × Inteli)

Base para montar os slides. Cada bloco traz **o que vai no slide**, **a fala** e **de onde vem o dado** (arquivo em `docs/` ou `resultados/`). Ordem pedida:

1. Problema → 2. Solução e por quê → 3. Arquitetura técnica → 4. Métricas e testes → 5. Decisões → 6. Fluxo da plataforma → 7. Por que assim + demonstração → 8. Desafios.

Tempo sugerido: 15 a 20 min. Para 10 min, use só os slides marcados com ★.

---

## Parte 1 · O problema que a CloudWalk trouxe

### Slide 1 ★ · Quem é a CloudWalk e o que ela já tem

**No slide**
- Fintech multi-marca: **InfinitePay** (Brasil) e **JIM** (EUA), serviços para milhões de microempreendedores
- Suporte em alto volume por **chat no app, WhatsApp e e-mail**
- Já opera um **agente de IA que atende de ponta a ponta**: interpreta, consulta sistemas, responde, executa ou escala
- Integração atual: help desk → **webhook** → **broker** → **Kafka** → agente

**Fala**
"A CloudWalk já resolveu a parte difícil da IA: o agente existe e atende. O que ela não controla é a plataforma onde esse atendimento acontece."

**Fonte:** TAP, seções 1 e 4.

### Slide 2 ★ · A dor

**No slide**
- O help desk atual é **de terceiros**: lento, com defeitos recorrentes, sem priorização das features pedidas
- Não foi feito para **várias marcas e várias equipes**
- Não deixa a operação **editar as filas** sem depender de desenvolvimento

**Fala**
"Uma operação desse porte precisa triar, priorizar e distribuir atendimentos entre marcas, equipes e temas. Uma fila única não serve, e a configuração precisa estar na mão da operação."

### Slide 3 · O que o case pediu

**No slide** (requisitos do TAP, seção 6)
- Recebimento por chat, WhatsApp e e-mail (simulados)
- Múltiplas filas, configuráveis e editáveis pela operação
- IA como atendente, por webhook e broker, como hoje
- Painel do analista com fila de escalas, contexto e histórico
- Triagem, priorização e distribuição entre IA e humanos
- Handoff com resumo e contexto; memória entre interações
- Rastreabilidade e auditoria de cada decisão
- Sustentar o volume de referência; experimento técnico; README com 8 itens

**Fala**
"Quebrei o TAP em 13 requisitos verificáveis. Cada um virou algo que eu teria de provar no final."

**Fonte:** `arquitetura.md`, seção 2; `validacao-pontos.md`.

---

## Parte 2 · A solução pensada e por quê

### Slide 4 ★ · O insight: o problema não é volume

**No slide**

| | Base | Estresse |
|---|---|---|
| Atendimentos por dia | 10.000 | 50.000 |
| Mensagens por dia (12 por atendimento) | 120.000 | 600.000 |
| Média | ~1,4 msg/s | ~7 msg/s |
| Pico concentrado | ~14 msg/s | ~70 msg/s |
| Meta do teste de carga | | **100 msg/s** |

- 10 mil/dia vem de dado público: a IA fez ~2,6 milhões de atendimentos em 2023 (75% do total)

**Fala**
"Antes de desenhar, medi. Dez mil atendimentos por dia é pouco para Postgres e Kafka. O desafio de verdade é **confiança e estado**: milhares de conversas abertas, cada uma com dono, fila e histórico certos, sem perder nem duplicar mensagem quando algo falha, quando o canal reenvia ou quando vem um pico. Num atendimento financeiro, uma mensagem perdida é um cliente sem resposta sobre o próprio dinheiro."

**Fonte:** `arquitetura.md`, seção 3; decisões 1 e 2.

### Slide 5 ★ · A solução em uma frase

**No slide**
> Um help desk próprio, multi-marca e multi-equipe, em que **a IA é um atendente dentro das filas** e o humano entra por escala, com a mesma integração que a CloudWalk já usa e **garantia de não perder nem duplicar mensagem**.

**Fala**
"A IA não é uma etapa antes do atendimento: ela é um atendente, como um humano, dentro das filas. Algumas filas vão direto para humanos, como fraude. Quando a IA escala, a conversa volta para o sistema de filas com prioridade maior, e o humano pode devolver para a IA."

### Slide 6 · Princípios que guiaram o desenho

**No slide**
1. Conversa com estado, não esteira
2. A IA é um atendente, não uma etapa
3. Escalar é voltar para o sistema de filas
4. Confiabilidade antes de escala
5. Tudo vira evento registrado
6. Regras são dados, não código
7. Monólito modular: só sai do núcleo o que precisa escalar ou falhar sozinho

**Fonte:** `arquitetura.md`, seção 5.

### Slide 7 · De onde vieram as ideias (engenharia reversa)

**No slide**

| De onde | O que pegamos |
|---|---|
| Chatwoot | Bot como atendente; handoff bot → humano → bot |
| Zendesk | Fila = condições + ordem + prioridade; primeira que casa leva; fila padrão |
| CloudWalk (TAP) | Kafka entre plataforma e agente, alimentado por webhook |
| **Onde melhoramos** | O Chatwoot retenta o webhook do bot só em 429 e 500; nas outras falhas abre para humano. Aqui: outbox com retentativa para qualquer falha, deduplicação e fila de erros |

**Fonte:** `arquitetura.md`, seção 6.

---

## Parte 3 · A arquitetura técnica

### Slide 8 ★ · Visão geral dos componentes

**No slide** (diagrama)

```
Canais (chat, WhatsApp, e-mail) ──► NÚCLEO (FastAPI, 4 processos) ──► Postgres 16
                                       │   outbox
                                       ▼
                              TRABALHADOR (4 processos)
                              relay · distribuidor · agendador
                                       │ webhook
                                       ▼
                              BROKER (2 processos) ──► Redpanda/Kafka ──► AGENTE (mock)
                                       ▲                                     │
                                       └──── volta: agente.para-helpdesk ◄───┘
                              NÚCLEO ──outbox──► SIMULADOR DE CANAIS (o cliente recebe)
                              FRONT (Next.js) ──► API do núcleo
```

| Componente | Papel |
|---|---|
| Núcleo (`nucleo/`) | Entrada dos canais, triagem, roteador, `transicionar`, painel, filas versionadas, supervisor |
| Trabalhador | Relay da outbox, distribuidor de conversas, agendador de prazos |
| Broker (`broker/`) | A ponte atual: webhook ↔ Kafka |
| Redpanda | Tópicos `helpdesk.para-agente` e `agente.para-helpdesk` (12 partições, chave = conversa) e `helpdesk.erros` |
| Agente mock | Faz o papel do agente da CloudWalk (fora do escopo) |
| Simulador de canais | Onde o cliente recebe; ponta onde o juiz conta perdas e duplicatas |
| Front | Chat do lojista, painel do analista, editor de filas, auditoria, painel ao vivo |

**Fonte:** `README.md`, Arquitetura; `docker-compose.yml`.

### Slide 9 ★ · As garantias: uma proteção por falha

**No slide**

| Falha | Proteção | Como funciona |
|---|---|---|
| Núcleo grava, mas o envio se perde | **Outbox transacional** | Mensagem e evento na mesma transação; o relay envia depois, com retentativa (8 tentativas, recuo até 60 s) |
| Canal ou Kafka reentrega | **Inbox / idempotência** | Toda entrada tem id (`id_externo`, `id_evento`); repetida é descartada. O canal deduplica a saída |
| IA responde atrasada depois que o humano assumiu | **Fencing por `id_atribuicao`** | Resposta com atribuição vencida é descartada e auditada |
| Duas ações ao mesmo tempo na mesma conversa | **Caminho único de escrita** | `transicionar` trava a conversa, confere transição permitida e capacidade, grava estado, mensagem, auditoria e outbox numa transação |
| Atraso da plataforma contado contra o agente | **Prazo do ack do broker** | O `timeout_agente` (30 s) nasce no ack do Kafka; agente que não responde escala para humano |
| Mensagem envenenada trava tudo | **Estacionamento** | Item em erro segura só a sua conversa; o replay restaura a ordem |
| Decisão sem explicação | **Auditoria só de inserção** | Cada triagem, regra, escolha de atendente, escala e descarte gravados com o porquê |

**Fala**
"Desenhei a partir das falhas. Para cada ponto do caminho perguntei: e se isso falhar? Cada resposta virou uma proteção, e cada proteção virou uma chave que dá para desligar no experimento."

**Fonte:** `arquitetura.md`, seção 11.

### Slide 10 · A fronteira com o agente (broker e contrato)

**No slide**
- Broker responde 200 ao webhook **só depois do ack do Kafka** (`acks=all`, produtor idempotente)
- Na volta, confirma o offset **só depois do núcleo responder 2xx**; núcleo fora = pausa a partição (contrapressão, não perda)
- Conversas diferentes em paralelo, ordem garantida dentro da conversa
- Contrato: envelope JSON versionado (`1.x`) com `id_evento`, `tipo`, `id_conversa`, `id_atribuicao`, `causado_por`, `marca`, `timestamp`, `dados`; esquema publicado em `contrato/esquema-envelope.json`
- Ids determinísticos: reprocessar dá o mesmo id

**Fonte:** `arquitetura.md`, seções 10 e 11.4; `broker/main.py`.

### Slide 11 · Estados da conversa

**No slide**

```
nova → na_fila → com_ia ──escala──► escalada → com_humano → resolvida
                   ▲                                │
                   └────────── devolve ─────────────┘
```

- Transições permitidas por ator numa tabela; fora dela, rejeitada e auditada
- Uma conversa aberta por cliente e marca (índice único)

**Fonte:** `arquitetura.md`, seção 8.

### Slide 12 · Camadas de segurança de dados e operação

**No slide**
- **Isolamento por marca no banco (RLS):** sessão da JIM não lê linha da InfinitePay
- **SLA** que corre enquanto a operação deve resposta e pausa quando o atendente responde
- **Expurgo por retenção** que preserva casos de ouvidoria
- **Reconciliador** de invariantes (I1 a I7): sem mensagem sem desfecho, sem duplicata, sem resposta fora do dono, capacidade consistente, toda escala com nota
- **Trace ponta a ponta** de cada mensagem: canal → núcleo → Kafka → agente → volta → entregue

**Fonte:** migrations 0005 e 0006; `nucleo/reconciliacao.py`; `validacao-pontos.md`.

---

## Parte 4 · Métricas, avaliações e testes de requisições

### Slide 13 ★ · Experimento por ablação (a prova das proteções)

**No slide** — 50 msg/s, 5 min medidos, 7.469 mensagens do cliente por execução

| Cenário | Proteção | Perdidas | Duplicadas |
|---|---|---|---|
| E1 base | ligada | 0 | 0 |
| E3b canal reenviando | inbox desligada | 0 | **637** |
| E3b canal reenviando | inbox ligada | 0 | **0** |
| E6 broker fora 60 s | outbox desligada | **1.455** | 0 |
| E6 broker fora 60 s | outbox ligada | **0** | 0 |

- p95 interna sem falha: **0,10 s** (meta 500 ms)
- Recuperação do E6 ligado: 109 s (previsto ~70 s: declarado)

**Fala**
"Não bastava dizer que funciona. Desliguei cada proteção e medi nas pontas, onde o cliente recebe. Sem a deduplicação, 637 respostas duplicadas; com ela, zero. Sem a outbox e com o broker fora por um minuto, 1.455 mensagens perdidas, 19%; com ela, zero."

**Fonte:** `README.md`, Resultados; `resultados/`.

### Slide 14 ★ · 100 mil requisições

**No slide**

| Medida | Resultado |
|---|---|
| Mensagens | **100.000** de **20.000** lojistas (5 cada), todas HTTP 200 |
| Taxa | ~46 msg/s do cliente, **~92 msg/s no total** (meta do case: 100) |
| Respondidas, uma a uma | **100.000 de 100.000** |
| Duplicatas / escalas | **0 / 0** |
| Espera p95 da resposta | **8,7 s** |
| p95 interna | **0,45 s** (critério < 0,5 s) |
| Duração | 37 min |
| Reconciliação I1 a I7 | zerada |

**Fala**
"Testei com 100 mil mensagens: todas respondidas, nenhuma duplicada, 1,7 vez o volume de um dia inteiro da operação de referência em 37 minutos."

**Fonte:** `testes-de-carga.md`, "Rodada de desempenho".

### Slide 15 · A evolução da capacidade (antes e depois da rodada de desempenho)

**No slide**

| Rodada | Entrada (msg/s do cliente) | Respondidas | Espera p95 | p95 interna |
|---|---|---|---|---|
| Rajada, agente agrupando respostas | 52,9 | 98,4% próprias (100% das conversas) | 12 min | 6 min |
| Cadenciada, código anterior | 25,0 | 100% | 91 s | 33 s |
| Cadenciada, código novo (15 mil) | 25,0 | 100% | **2,3 s** | **0,19 s** |
| **100 mil, código novo** | **45,8** | **100%** | **8,7 s** | **0,45 s** |

**Fonte:** `testes-de-carga.md`.

### Slide 16 · Hipóteses de robustez, handoff e escala

**No slide**

| Hipótese | Montagem | Resultado |
|---|---|---|
| H2 robustez | 2.000 mensagens, 19% de reenvios, relay derrubado 38 s, 1% de mensagens envenenadas | **Passa:** 0 duplicatas ao cliente, **0 violações de ordem**, envenenadas estacionaram só a sua conversa |
| H3 handoff | 1.000 pedidos de atendente | **Passa:** 1.000 com nota de handoff e tempo estimado informado ao cliente |
| H1 escala | 200 msg/s no total | **Não passa numa máquina:** fila cresce (ingestão p95 75 s); 0 perdas, 0 duplicatas; reserva do relay 0,5 a 4 ms |

**Fonte:** `testes-de-carga.md`; `resultados/hipoteses/`.

### Slide 17 · Qualidade e reprodutibilidade

**No slide**
- Testes automatizados: **48 unitários**, **29 de contrato**, **17 de integração** (banco descartável), **fumaça** com 7 cenários
- Teste de contrato no lugar do Pact: o que o agente lê existe no que a plataforma envia
- Da clonagem à demo: **3,3 min** (imagens no cache)
- Arquitetura revisada em **5 rodadas**: notas de desenho e viabilidade de **6,0 / 4,5** para **8,5 / 8,5**

**Fonte:** `README.md`; `testes-de-carga.md`, Reprodutibilidade; `docs/revisoes/`.

---

## Parte 5 · Escolhas e decisões tomadas

### Slide 18 ★ · As decisões que definem o projeto (42 registradas)

**No slide**

| Decisão | Por quê |
|---|---|
| Gargalo é confiabilidade, não throughput (2) | O volume calculado é baixo; o risco é perder ou duplicar |
| IA como atendente dentro das filas (5) | Mesma regra para IA e humano; escala volta ao roteamento |
| Filas no modelo Zendesk, versionadas, com validação e rollback (6, 20) | Operação edita sem deploy e volta atrás em segundos |
| Kafka particionado por conversa; contrato JSON versionado (7, 34) | Ordem por conversa; agente real entra sem perceber |
| Monólito modular; broker e agente fora do núcleo (8) | Menos peças; separa só o que falha sozinho |
| Outbox + idempotência + fila de erros (9, 14) | Pelo menos uma vez com deduplicação = efeito de exatamente uma vez |
| Caminho único de escrita com trava e fencing (15) | Nenhuma corrida entre IA, humano e sistema |
| Broker responde só depois do ack do Kafka (17) | Webhook confirmado = mensagem durável |
| Experimento por ablação (12) | Prova cada proteção pelo efeito de tirá-la |
| Plano de 2 dias com corte por requisito (41) | O desenho completo não cabia; manteve o que a avaliação pesa |

**Fonte:** `arquitetura.md`, seção 20.

### Slide 19 · Stack e por quê

**No slide**

| Camada | Escolha | Por quê |
|---|---|---|
| Núcleo e workers | Python + FastAPI | Velocidade de entrega; async |
| Banco | PostgreSQL 16 | Transação para a outbox; JSONB para as filas; RLS |
| Mensageria | Redpanda (API Kafka) | Mesma interface do Kafka da CloudWalk; um binário |
| Interface | Next.js + React | Sugerido no TAP |
| Testes e carga | pytest; gerador próprio em Python | Uma ferramenta a menos |
| Empacotamento | Docker Compose | Um comando para subir tudo |

- **Python ou Ruby:** a CloudWalk usa Ruby; as partes só conversam por HTTP, Kafka e JSON Schema, então dá para migrar uma por vez.

**Fonte:** `arquitetura.md`, seção 15.

### Slide 20 · Decisões que o teste de carga forçou

**No slide**
- Gerador de carga dentro da rede do Docker (do Windows, o encaminhamento de porta limitava a ~20 req/s)
- Canal deduplica pelo id do evento (1 duplicata em 20 mil, por reserva vencida do relay)
- IA sem contador de ocupação (a linha da IA virava fila única da marca)
- Distribuidor por lote travado com `SKIP LOCKED`
- Pools de conexão do tamanho da concorrência; broker em 2 processos; trabalhador em 4
- Agente respondendo cada mensagem que esperou na fila

**Fonte:** `testes-de-carga.md`; `diario.md`, dia 3.

### Slide 21 · O que ficou para Evolução (e por quê)

**No slide**
- Memória semântica com embeddings (custo de serviço, pgvector, conjunto rotulado)
- Disjuntor por saúde do agente; encerramento por inatividade; prazo renovável
- Agente real com LLM (fora do escopo do TAP)
- Escala em várias máquinas; autenticação de usuários

**Fonte:** `arquitetura.md`, seções 19.1 e 21.

---

## Parte 6 · O fluxo da plataforma

### Slide 22 ★ · O caminho de uma mensagem

**No slide** (sequência numerada)
1. Lojista manda mensagem → `POST /mensagens` (canal, marca, `id_externo`)
2. **Inbox:** repetida? descarta e responde "duplicada"
3. **Triagem:** categoria, prioridade, sentimento, idioma
4. **`transicionar`** com a conversa travada: grava mensagem, auditoria e outbox
5. **Roteador:** regras versionadas → fila (ex.: InfinitePay Crédito)
6. **Distribuidor:** grupo preferido da fila e menor ocupação → IA ou humano
7. Com a IA: evento `conversa.atribuida` na outbox → **relay** → **broker** → **Kafka** (ack) → nasce o prazo de 30 s
8. **Agente** lê, responde com `mensagem.enviada` (`causado_por`, `id_atribuicao`)
9. Volta pelo Kafka → broker → `POST /agente/eventos` → inbox → **fencing** → `transicionar`
10. Saída na outbox → relay → **canal** (deduplica) → **cliente recebe**

**Fala**
"Cada salto tem um id que viaja junto, e é por isso que dá para montar o trace de qualquer mensagem e dizer onde ela está."

**Fonte:** `arquitetura.md`, seção 7.

### Slide 23 · O fluxo do handoff

**No slide**
- Três gatilhos de escala: **o cliente pede**, **o agente decide**, **o prazo do agente vence**
- A escala leva **resumo com as mensagens-fonte**; o cliente recebe **"vou te transferir"** com o **tempo estimado** de espera
- A conversa volta ao roteador com `origem = escalado` → fila de escalas → analista
- O analista **assume, responde, devolve para a IA com nota ou encerra**
- Resposta atrasada da IA nesse meio tempo é **descartada pelo fencing**

**Fonte:** `arquitetura.md`, seção 12; `nucleo/dominio/acoes.py`.

### Slide 24 · Como a operação organiza o atendimento

**No slide**
- **Filas como dado:** condições (marca, canal, categoria, prioridade, idioma, segmento, sentimento, origem), ordem, prioridade, grupos de atendentes, SLAs
- Validador bloqueia: fila inalcançável, fila sem atendente elegível, SLAs sobrepostos, falta de fila padrão
- Simular antes de ativar; ativar é atômico; rollback = reativar versão anterior
- Distribuição com envelhecimento de prioridade (quem espera sobe)
- Quatro perfis: lojista, agente de IA, analista, supervisor

**Fonte:** `arquitetura.md`, seções 4 e 12; tela `/filas`.

---

## Parte 7 · Por que foi construída assim + demonstração

### Slide 25 ★ · Cada escolha ligada ao que a avaliação pesa

**No slide**

| Critério do TAP (seção 9) | Onde a arquitetura responde |
|---|---|
| Aderência ao desenho fornecido | Mesma estrutura webhook → broker → Kafka → agente |
| Filas de fato configuráveis | Regras versionadas, validação, simulação, rollback, tela de edição |
| Robustez diante de falhas, reentregas e picos | Outbox, inbox, fencing, estacionamento; provado no E3b, E6 e H2 |
| Handoff com resumo e contexto | Escala com fontes, tempo estimado, invariante I7; provado na H3 |
| Evidência de escalabilidade | 100 mil mensagens a ~92 msg/s; limite medido e declarado (H1) |
| Clareza e honestidade do experimento | Hipótese e previsão escritas antes de rodar; limitações no README |
| Reprodutibilidade e documentação | Docker Compose, 3,3 min da clonagem à demo, 8 itens do README |
| Qualidade da demonstração | Painel ao vivo, chat, painel do analista, editor de filas, trace |

### Slide 26 ★ · Demonstração ao vivo (5 min)

Preparação: `docker compose up -d`, depois `npm run dev` em `front/`, e abrir http://localhost:3000. Clicar em **Simular tráfego** 20 s antes.

1. **Ao vivo:** linhas de lojistas e IA andando juntas; números do topo; botão **Pico · 30/s**
2. **Chat:** "meu repasse não caiu" → IA responde em ~1 s; **reenviar com o mesmo id** → `duplicada = true`; "quero falar com um atendente" → transferência com tempo estimado
3. **Painel do analista:** resumo com fontes destacadas, auditoria com o **descarte por fencing**, responder, **devolver para a IA** com nota
4. **Filas:** editar, validar, simular, criar versão, ativar, **rollback**
5. **Conversa:** linha do tempo da auditoria, **trace** da mensagem, relógio de **SLA**
6. **Operação:** reconciliação com todas as invariantes em zero

Plano B se o front falhar: `.venv\Scripts\python -m carga.demo` percorre os mesmos momentos pela API.

**Fonte:** `roteiro-demo.md`.

---

## Parte 8 · Principais desafios

### Slide 27 ★ · Desafios e como foram resolvidos

**No slide**

| Desafio | O que aconteceu | Como resolvemos |
|---|---|---|
| **Escopo × prazo** | A primeira revisão deu viabilidade 4,5: o desenho não cabia | Corte por requisito (decisão 41); resto em Evolução |
| **O instrumento enganava** | O sistema "saturava" em ~70 msg/s, mas era o Docker no Windows limitando a ~20 req/s | Gerador dentro da rede do Docker (92 msg/s na mesma bancada) |
| **Gargalos escondidos** | Distribuidor ordenava a fila inteira por conversa; a linha da IA virava fila única da marca; pools pequenos | Diagnóstico com amostras a cada 30 s e perfil `py-spy`; espera p95 de 91 s para 8,7 s |
| **Mais processos pioraram** | 4 processos antes de tirar a contenção aumentaram a disputa | Primeiro tirar a contenção, depois escalar |
| **Colapso metaestável** | Em rajada acima da capacidade, o prazo do agente vencia e cada escala aumentava a fila | Medido e documentado; capacidade sustentável medida; controle de admissão em Evolução |
| **O juiz do experimento errou** | 7 "perdidas" e 7 "duplicadas" eram a mesma resposta atrasada atribuída à mensagem seguinte | Ligação exata pela outbox; execução refeita; resultado antigo guardado |
| **Reentrega rara do relay** | Reserva vencida sob pausa de CPU gerou 1 duplicata em 20 mil | Deduplicação no adaptador do canal |
| **RLS que não valia** | O usuário do banco no Docker é superusuário e passa por cima das políticas | Papel próprio `leitura_marca` usado nas leituras por marca |
| **Ambiente** | Disco cheio, Docker caindo de madrugada, computador dormindo no meio do teste | Rodadas refeitas do zero; suspensão bloqueada durante a carga |

**Fala de fechamento**
"O maior aprendizado foi que os gargalos nunca estavam onde eu imaginava. A disciplina de medir, achar a causa e só então mudar foi o que levou o tempo de resposta de 91 para 9 segundos sem perder nem duplicar uma mensagem."

### Slide 28 ★ · Limites e próximos passos

**No slide**
- Uma máquina só: 200 msg/s não passa (H1); escala horizontal não testada
- Agente simulado, sem LLM; triagem por regras; memória semântica em Evolução
- Contrato é proposta nossa: validar com uma amostra real da CloudWalk
- Caminho de entrada em produção: **modo shadow** (7 dias comparando) → **canário** (5%, depois 25%) → **corte por marca**, com rollback por flag

**Fonte:** `README.md`, Limitações; `plano-de-corte.md`.

### Slide 29 · Encerramento

**No slide**
> Uma plataforma própria, multi-marca, com a IA como primeiro atendente, desenhada a partir das falhas, revisada antes de ser construída e provada com 100 mil mensagens sem perder nem duplicar.

---

## Apoio: perguntas prováveis

| Pergunta | Resposta |
|---|---|
| Aguenta 100 mil? | Sim, 100 mil mensagens respondidas a ~92 msg/s totais. Em rajada acima da capacidade, a fila cresce e escala para humano, sem perder nem duplicar |
| Por que não 200 msg/s? | A máquina inteira chega perto do limite de CPU; o próximo passo é escalar em várias máquinas |
| Usa rede neural? | Não; a IA é a da CloudWalk, simulada, como o TAP permite. Embeddings estão desenhados em Evolução |
| E se o broker cair? | A outbox segura e reenvia; no E6, zero perdas com o broker fora 60 s |
| E se a IA responder depois do humano? | O fencing descarta; aparece na auditoria |
| Como a operação muda uma fila? | Editor na tela: validar, simular, ativar; rollback em segundos |
| Por que Python? | Prazo; contratos abertos permitem migrar para Ruby por componente |
