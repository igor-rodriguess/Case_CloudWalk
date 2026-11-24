# Validação dos pontos do roteiro de 24/11

Conferência, item por item, de um roteiro de validação recebido em 24/11/2026 (página externa, tratada como lista de critérios). Cada linha diz o estado e onde está a evidência. "Fora do alcance" é o que depende de material ou ambiente da CloudWalk; o plano para esses itens está em [`plano-de-corte.md`](plano-de-corte.md).

## Requisitos R1 a R13

| Item | Estado | Evidência |
|---|---|---|
| R1 canais chat, WhatsApp, e-mail simulados | Atende | `POST /mensagens` (`canal`), `canais/`, tela `/cliente` |
| R2 filas por marca, equipe, categoria ou prioridade, editáveis sem desenvolvimento | Atende | `/filas` (versões, validar, simular, ativar, rollback), tela `/filas`; teste de fila nova recebendo o próximo atendimento |
| R3 IA como atendente via webhook e broker | Atende | `broker/`, `agente_mock/`, `nucleo/api/agente.py` |
| R4 painel do analista com fila, contexto e histórico | Atende | `/painel/*`, tela `/analista` |
| R5 rastreabilidade e auditoria | Atende | tabela `eventos` (só inserção), linha do tempo em `/conversas/{id}`, trace por mensagem |
| R6 milhares de atendimentos por dia, com picos | Atende, numa máquina | `docs/testes-de-carga.md` (100 mil mensagens) |
| R7 handoff com resumo, histórico e memória | Atende | escala com resumo e fontes, perfil de 30 dias, invariante I7 |
| R8 IA primeiro nível, humano por escala | Atende | roteamento e distribuição do seed |
| R9 experimento com hipótese, método e limitações | Atende | README (E1, E3b, E6), testes de carga, H2 e H3 |
| R10 LGPD, dados sintéticos, agente e canais mockados | Atende | dados sintéticos; RLS por marca; expurgo com retenção |
| R11 resistente a falhas, reentregas e picos | Atende | outbox, inbox, fencing, relay com estacionamento, E3b, E6, H2 |
| R12 README com oito itens | Atende | problema, arquitetura, instalação, modelos e configurações, metodologia, resultados, limitações, evolução |
| R13 interface de conversa | Atende | tela `/cliente` e `/analista` |

## Critérios de aceite

| Critério | Estado | Evidência |
|---|---|---|
| Mensagem percorre o circuito e a resposta volta à tela do cliente | Atende | teste no navegador (README, Front-end); `testes/fumaca.py` |
| Suíte Pact com o mock como consumidor | Atende com substituto | esquema publicado `contrato/esquema-envelope.json` e `testes/test_contrato.py` (o que o mock lê existe no que a plataforma envia; o que ele devolve valida). Sem Pact: um só produtor e um só consumidor no repositório |
| Webhook entregue cinco vezes gera uma mensagem | Atende | `test_webhook_entregue_cinco_vezes_gera_uma_mensagem` |
| Sessão da `jim` não lê linhas da `infinitepay` (RLS) | Atende | migration 0006, `test_sessao_da_jim_nao_le_linhas_da_infinitepay` |
| Operador cria fila pela interface e o próximo atendimento cai nela | Atende | `test_operacao_cria_fila_sem_deploy_...`; tela `/filas` testada no navegador |
| Rollback de regras em menos de 5 s | Atende | mesmo teste, com o tempo medido |
| Pausar e retomar o SLA não altera o acumulado | Atende | `nucleo/dominio/sla.py`, `TestSla` |
| Regra de escala a pedido do cliente não pode ser editada nem desligada | Atende | a escala a pedido está no código, não nas regras; `test_pedido_de_atendente_escala_mesmo_sem_fila_de_escalas_nas_regras` |
| Pedido de atendente escala em qualquer turno e informa tempo estimado | Atende | `estimar_espera`, transição `na_fila -> escalada`; `test_pedido_de_atendente_na_fila_...`; H3 |
| Resposta tardia da IA depois que o humano assume não chega ao cliente | Atende | fencing; `test_fencing_descarta_evento_de_atribuicao_vencida`; visto no navegador |
| 100% das escalas com nota de handoff | Atende | invariante I7; H3 |
| Expurgo remove corpos vencidos e preserva ouvidoria | Atende | `POST /supervisor/expurgo`, `POST /painel/conversas/{id}/ouvidoria`; `test_expurgo_...` |
| Mensagem envenenada estaciona só a sua conversa; o replay restaura a ordem | Atende | relay; `test_item_envenenado_...`; H2 |
| Um único trace cobre canal, núcleo, broker, agente e retorno | Atende | `GET /conversas/{id}/traco/{id_mensagem}`, cartão na tela da conversa. Trace montado pelos ids do contrato, sem OpenTelemetry |
| Da clonagem à demo em menos de 30 minutos | Ver `testes-de-carga.md`, "Reprodutibilidade" | |

## Hipóteses

| Hipótese | Resultado |
|---|---|
| H1: ~200 msg/s, ingestão ao agente p95 < 500 ms, claim p95 < 50 ms | **Não passa nesta máquina.** Claim de 0,5 a 4 ms (passa); ingestão p95 de 75 s a ~156 msg/s totais (não passa). O sistema sustenta ~92 msg/s totais com p95 interna de 0,45 s (100 mil mensagens). Detalhe em `testes-de-carga.md` |
| H2: 20% de reenvios, relay fora, 1% envenenadas; zero violações de ordem e zero duplicatas ao cliente | **Passa.** 19% de reenvios absorvidos, relay fora 38 s, 20 envenenadas estacionaram só a sua conversa; 2.000 entregas, 0 duplicatas, 0 violações de ordem |
| H3: 100% de 1.000 pedidos de humano com nota completa e tempo estimado | **Passa.** 1.000 de 1.000 com nota, tempo estimado gravado e aviso com o tempo entregue ao cliente |

## Validadores de regras

| Validador | Estado |
|---|---|
| Bloquear regra inalcançável | Atende: busca exaustiva sobre os domínios dos campos (`filas_inalcancaveis`) |
| Exigir catch-all | Atende: `fila_padrao` obrigatória e o roteador sempre cai nela |
| Bloquear fila sem atendente elegível | Atende: grupo precisa ter atendente com capacidade |
| Bloquear SLAs sobrepostos | Atende: duas entradas de SLA da mesma fila não podem cobrir a mesma prioridade |

## Fora do alcance do case

| Item | Por quê | Plano |
|---|---|---|
| Amostra anonimizada do legado, nomes de tópicos, chave, assinatura, chamadas HTTP do agente | Material da CloudWalk, fechado pelo TAP | `plano-de-corte.md`, seção 1 |
| Teste diferencial contra fixtures do legado | Depende da amostra | `plano-de-corte.md`, seção 2 |
| Shadow, canário e corte por marca | Produção | `plano-de-corte.md`, seção 2 |
