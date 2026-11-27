# Contexto completo do projeto: Help Desk AI First (CloudWalk × Inteli)

Documento único com tudo o que o projeto é, como foi feito e o que foi provado. Serve para quem chega agora (pessoa ou IA) e para montar apresentações. Estado em 27/11/2026. Detalhes e fontes ficam nos arquivos apontados em cada seção.

---

## 1. Identificação

| Item | Valor |
|---|---|
| Projeto | Help Desk Integrado a Agentes de IA ("Help Desk AI First") |
| Parceiro | CloudWalk (InfinitePay no Brasil, JIM nos EUA) |
| Instituição | Inteli, projeto individual, ~1 mês (início 17/11/2026, entrega 23/11/2026) |
| Autor | Igor Rodrigues |
| Repositório | `igor-rodriguess/Case_CloudWalk` (GitHub); pasta local `Documents/Case_ClaudWalk` |
| Documento de origem | TAP (Termo de Abertura do Projeto) `TAPI_Inteli_CloudWalk_HelpDesk_AgentesIA.pdf` |
| Divisão do trabalho | Backend escrito com agente de código e revisado pelo autor; front construído por agente e revisado pelo autor (declarado) |

---

## 2. O problema (TAP)

- A CloudWalk é uma fintech multi-marca com suporte em alto volume por **chat no app, WhatsApp e e-mail**, com pedidos sobre transações, repasses, taxas, crédito e maquininha.
- Já opera um **agente de IA que atende de ponta a ponta** (interpreta, consulta sistemas por ferramentas, responde, executa ou escala para humano), ligado ao help desk por **webhook → broker → tópico Kafka**.
- O help desk atual é **de terceiros**: lento, com defeitos recorrentes, sem priorização das features pedidas e sem estrutura multi-marca e multi-equipe.
- Pedido: uma plataforma **própria, AI first, multi-equipe, multi-marca, self-hosted**, escalável para milhares de atendimentos por dia com picos.

**Requisitos do TAP (seção 6):** canais simulados; múltiplas filas configuráveis e editáveis pela operação; interface de conversa; painel do analista com fila de escalas, contexto e histórico; integração por webhook e broker; triagem, priorização e distribuição entre IA e humanos; handoff com resumo e contexto; rastreabilidade e auditoria; memória entre interações; experimento técnico; README com 8 itens.

**Fora do escopo:** desenvolver o agente de IA, dados reais, integração com produção, apps móveis. A CloudWalk não fornece sistemas nem dados; o agente e os canais são simulados.

**Critérios de avaliação (TAP, seção 9):** aderência ao desenho; filas de fato configuráveis; robustez diante de falhas, reentregas e picos; handoff com resumo e contexto; evidência de escalabilidade; clareza e honestidade do experimento; reprodutibilidade e documentação; qualidade da demonstração.

---

## 3. A ideia central e a solução

**Premissas de volume** (`arquitetura.md`, seção 3):

| | Base | Estresse |
|---|---|---|
| Atendimentos por dia | 10.000 | 50.000 |
| Mensagens por dia (12 por atendimento) | 120.000 | 600.000 |
| Média | ~1,4 msg/s | ~7 msg/s |
| Pico (5x) | ~7 msg/s | ~35 msg/s |
| Pico concentrado em horário comercial | ~14 msg/s | ~70 msg/s |
| Meta do teste de carga | | 100 msg/s totais (duas direções) |

- 10 mil/dia: em 2023 a IA fez ~2,6 milhões de atendimentos (75% do total) → ~3,5 milhões/ano → ~9,5 mil/dia (dado público). 50 mil/dia e 12 mensagens por atendimento são premissas.

**Insight:** o volume é baixo para Postgres e Kafka. **O difícil é confiabilidade e estado**: não perder nem duplicar mensagem com falha, reentrega e pico, com milhares de conversas abertas, cada uma com dono, fila e histórico corretos.

**Solução:** help desk próprio em que **a IA é um atendente dentro das filas** (não uma etapa), o humano entra por escala, a integração com o agente é a mesma da CloudWalk e cada falha possível tem uma proteção que dá para desligar e medir.

**Princípios** (`arquitetura.md`, seção 5):
1. Conversa com estado, não esteira.
2. A IA é um atendente, não uma etapa; algumas filas vão direto a humanos.
3. Escalar é voltar ao sistema de filas (`origem = escalado`, prioridade maior); o humano pode devolver à IA.
4. Confiabilidade antes de escala.
5. Tudo vira evento registrado.
6. Regras são dados, não código (filas no banco, editadas pela interface; marcas são valor fixo no contrato).
7. Monólito modular: só sai do núcleo o que precisa escalar ou falhar sozinho.

**Engenharia reversa:** do Chatwoot, o bot como atendente e o handoff bot → humano → bot; do Zendesk, filas com condições, ordem, prioridade e fila padrão; do TAP, Kafka alimentado por webhook. Melhoria: o Chatwoot retenta o webhook do bot só em 429 e 500; aqui há outbox com retentativa para qualquer falha, deduplicação e fila de erros.

---

## 4. Arquitetura técnica

### 4.1 Componentes (Docker Compose)

| Serviço | Tecnologia | Papel | Porta |
|---|---|---|---|
| `nucleo` | Python 3.12, FastAPI, SQLAlchemy async, psycopg 3; 4 processos uvicorn | API: entrada dos canais, triagem, roteador, `transicionar`, painel, filas, supervisor | 8000 |
| `trabalhador` | mesma imagem; 4 réplicas | Laços de fundo: relay da outbox (4 por processo), distribuidor (2 por processo), agendador | — |
| `postgres` | PostgreSQL 16, `max_connections=400` | Bancos `helpdesk`, `agente_mock`, `canais` | 5433 |
| `redpanda` | Redpanda v24.2.7 (API Kafka), 1 nó | Tópicos `helpdesk.para-agente` e `agente.para-helpdesk` (12 partições, chave = conversa), `helpdesk.erros` (3) | 19092 |
| `broker` | FastAPI + aiokafka; 2 processos no mesmo grupo de consumo | Ponte webhook ↔ Kafka | 8100 |
| `agente_mock` | FastAPI + aiokafka, banco próprio | Faz o papel do agente da CloudWalk | 8200 |
| `canais` | FastAPI, banco próprio, pool de conexões | Onde o cliente recebe; deduplica por id do evento | 8310 |
| `front` (fora do Compose) | Next.js 16, React 19, TypeScript, Tailwind 4 | Telas | 3000 |

`migracoes` (Alembic) e `topicos` (rpk) rodam uma vez e terminam.

### 4.2 Garantias (uma por falha) — `arquitetura.md`, seção 11

| Falha | Proteção | Detalhe |
|---|---|---|
| Núcleo grava e o envio ao broker se perde | **Outbox transacional + relay** | Evento na mesma transação da mudança; relay reserva um item por vez (`FOR UPDATE SKIP LOCKED`, reserva de 30 s), envia fora da transação, grava o resultado; até 8 tentativas com recuo exponencial até 60 s; depois `erro` (fila de erros, reprocessável) |
| Ordem quebrada | **Ordem por conversa e destino** | Item só sai se nenhum anterior da mesma conversa e destino está pendente, enviando ou em erro; Kafka particionado por conversa |
| Mensagem envenenada trava tudo | **Estacionamento** | Item em `erro` segura só os seguintes da sua conversa; o reprocessamento restaura a ordem |
| Canal ou Kafka reentrega | **Inbox / idempotência** | Entrada com `chave_entrada` = uuid5(canal, `id_externo`); eventos do agente deduplicados pelo `id_evento`; mock com inbox própria; ids derivados determinísticos (uuid5 de `causado_por`, tipo, sequência) |
| Relay reenvia o que já tinha entregue | **Deduplicação no canal** | Adaptador do canal com índice único por `id_evento`; reenvio absorvido registrado (`GET /duplicatas`) |
| IA responde depois que o humano assumiu | **Fencing por `id_atribuicao`** | Evento com atribuição diferente da vigente é descartado e auditado |
| Corrida entre IA, humano e sistema | **Caminho único de escrita (`transicionar`)** | `SELECT ... FOR UPDATE` na conversa; transição validada em `transicoes_permitidas`; capacidade conferida (humano sob trava); grava estado, mensagem, auditoria e outbox na mesma transação |
| Atraso da plataforma contado contra o agente | **Prazo nasce no ack do broker** | `timeout_agente` (30 s) criado quando o relay recebe o ack; vencido → escala para humano |
| Broker perde mensagem | **Ack do Kafka antes do 200** | Webhook só responde depois do ack (`acks=all`, produtor idempotente); na volta, offset confirmado só depois do núcleo responder 2xx; núcleo fora = pausa da partição |
| Invariante quebrada sem ninguém ver | **Reconciliador** | I1 mensagem sem desfecho, I1b escala esperando humano além do prazo, I2 outbox parada, I3 resposta duplicada, I4 resposta fora do dono, I5 capacidade, I6 conversa aberta duplicada, I7 escala sem nota (`GET /supervisor/reconciliacao`) |
| Decisão sem explicação | **Auditoria só de inserção** | Tabela `eventos` com gatilho que bloqueia UPDATE; registra triagem, roteamento (regra e versão), distribuição (candidatos e motivo), transições, descartes, escalas |

### 4.3 Estados da conversa

`nova → na_fila → com_ia → escalada → com_humano → resolvida`; o humano pode devolver (`com_humano → com_ia`); o cliente pode pedir humano com a IA ou ainda na fila (`na_fila → escalada`). Transições permitidas por ator numa tabela. Uma conversa aberta por cliente e marca (índice único).

### 4.4 Contrato com o agente

Envelope JSON versionado (`1.x`, campos novos opcionais, leitor tolerante): `versao`, `id_evento`, `tipo`, `id_conversa`, `id_atribuicao`, `causado_por`, `marca`, `timestamp`, `dados`.
- Plataforma → agente: `conversa.atribuida` (cliente, fila, triagem, histórico das últimas 20, perfil), `mensagem.recebida`, `conversa.devolvida`, `conversa.encerrada`.
- Agente → plataforma: `mensagem.enviada` (com `sequencia`), `conversa.escalada` (motivo, resumo, fontes, prioridade sugerida), `conversa.resolvida`, `acao.executada`, `agente.processando`.
- Esquema publicado: `contrato/esquema-envelope.json`; teste de contrato em `testes/test_contrato.py`.

### 4.5 Filas, triagem e distribuição

- **Triagem** por regras (`nucleo/dominio/triagem.py`): categoria (repasse, crédito, fraude, maquininha...), prioridade 1–3 (fraude e urgência = 3), sentimento, idioma; pedido de humano detectado por expressão regular (no código, não nas regras: nenhuma versão desliga).
- **Roteador** (função pura, `nucleo/dominio/roteador.py`): filas em ordem; a primeira cujas condições casam leva; senão, fila padrão. Campos: marca, canal, categoria, prioridade, idioma, segmento, sentimento, origem; operadores igual, diferente, em; condições "todas" ou "qualquer".
- **Regras versionadas** (`versoes_regras`): criar versão inativa, validar, simular, ativar atomicamente (re-roteia conversas de fila removida), rollback = reativar anterior.
- **Validador:** ids e ordens únicos, fila padrão obrigatória, grupos existentes, fila sem atendente elegível, **fila inalcançável** (busca exaustiva sobre os domínios), **SLAs sobrepostos**.
- **Distribuidor** (trabalhador): pega um lote de até 20 conversas da fila, ordenado por prioridade da fila, escaladas primeiro, prioridade com envelhecimento (`+1` a cada 600 s de espera) e chegada, travado com `SKIP LOCKED` (tarefas recebem lotes disjuntos); escolhe o grupo preferido da fila e, dentro dele, o atendente de menor ocupação; atribui pelo `transicionar`.
- **Seed:** 7 filas (escalas InfinitePay, escalas JIM, fraude só humanos, crédito, geral InfinitePay, geral JIM, padrão); 5 analistas (suporte-br, credito-br, support-us; capacidade 3) e 2 IAs (uma por marca, sem limite).

### 4.6 Handoff, memória, SLA e dados

- **Escala**: três gatilhos (cliente pede, agente decide, prazo vence); grava resumo (do agente ou extrativo de reserva) com as mensagens-fonte; cliente recebe "vou te transferir" com **tempo estimado** (vagas livres, escalas na frente e tempo médio de atendimento humano das últimas 24 h; sem histórico, 600 s, hipótese).
- **Memória entre interações**: perfil operacional de 30 dias (contatos, escalas, canal preferido, último assunto) e últimas mensagens, enviados ao agente na atribuição. Memória semântica com embeddings ficou em Evolução.
- **SLA**: relógio que corre enquanto a operação deve resposta e pausa quando um atendente responde; limites por fila e prioridade (hipótese no seed: 300/900/1.800 s nas filas de escalas).
- **Retenção**: `POST /supervisor/expurgo` apaga o corpo de mensagens, payloads e notas de conversas resolvidas há mais de 90 dias (hipótese), preservando conversas marcadas como **ouvidoria**.
- **Isolamento por marca (RLS)**: leituras em nome de uma marca usam o papel `leitura_marca` com `app.marca`; sessão da JIM não lê linha da InfinitePay.
- **Trace ponta a ponta**: `GET /conversas/{id}/traco/{id_mensagem}` monta canal → núcleo → outbox → Kafka → agente → volta → entrega, com o tempo de cada salto.

### 4.7 Modelo de dados (principais tabelas)

`clientes`, `identidades`, `conversas` (estado, fila, dono, atribuição atual, SLA, ouvidoria), `mensagens` (autor, `id_externo`, `causado_por`, `sequencia`, atribuição declarada e vigente), `atribuicoes`, `atendentes`, `escalas`, `eventos` (auditoria), `outbox`, `eventos_processados` (inbox), `agendamentos`, `versoes_regras`, `transicoes_permitidas`. Migrations 0001 a 0007 em `migrations/versions/`.

### 4.8 API do núcleo (OpenAPI em `http://localhost:8000/docs`)

| Grupo | Rotas |
|---|---|
| Canais | `POST /mensagens` |
| Agente | `POST /agente/eventos` (chamado pelo broker) |
| Conversas | `GET /conversas`, `GET /conversas/{id}`, `GET /conversas/{id}/traco/{id_mensagem}` |
| Painel | `GET /painel/atendentes`, `GET /painel/fila`, `GET /painel/atendentes/{id}/conversas`, `POST /painel/conversas/{id}/assumir`, `.../responder`, `.../devolver`, `.../encerrar`, `.../ouvidoria` |
| Filas | `GET /filas/versoes`, `GET /filas/ativa`, `GET /filas/grupos`, `POST /filas/validar`, `POST /filas/versoes`, `POST /filas/versoes/{n}/ativar`, `POST /filas/simular` |
| Supervisor | `GET /supervisor/metricas`, `GET /supervisor/serie`, `GET /supervisor/reconciliacao`, `POST /supervisor/expurgo`, `GET /outbox/erros`, `POST /outbox/{id}/reprocessar`, `GET /config` |
| Demonstração | `POST /demo/trafego`, `GET /demo/trafego` (tráfego sintético) |

### 4.9 Front (`front/`)

| Tela | Para quem | O que faz |
|---|---|---|
| `/` Ao vivo | Operação | Chamadas por segundo (lojistas, IA, analistas), tempo de resposta da IA, conversas abertas; botões de tráfego sintético |
| `/cliente` | Lojista | Chat com marca e canal; reenvio com o mesmo id (mostra `duplicada`) |
| `/analista` | Analista | Fila de escalas, resumo com fontes, perfil, auditoria; assumir, responder, devolver, encerrar, ouvidoria |
| `/filas` | Supervisor | Editor de regras (formulário ou JSON), validar, simular, criar versão, ativar, rollback |
| `/conversas` | Supervisor | Lista e detalhe com linha do tempo da auditoria, relógio de SLA e trace |
| `/supervisor` | Supervisor | Métricas, ocupação, fila de erros com reprocessar, reconciliação |

Identidade visual baseada em cloudwalk.io: fundo quase preto, off-white `#ecebe9`, laranja `#e25813`, verde-terminal `#24d332`, azul `#467afc`; Gabarito e IBM Plex Mono. Séries do gráfico validadas para daltonismo (azul, verde-água `#24a8a8`, laranja). Sem autenticação: o perfil é escolhido na tela. Leitura periódica de 2 s.

### 4.10 Agente mock

Determinístico, sem LLM (`agente_mock/main.py`; versão = commit): uma frase fixa por troca (6 por idioma), escala por expressão regular, resolve na 6ª resposta; latência simulada de 800 ms; modos `normal`, `lento`, `duplicar`, `fora`. Na atribuição, responde cada mensagem que esperou na fila (`sequencia` 0, 1, 2). Grava respostas com `publicar_em` e publica em lote.

---

## 5. O caminho de uma mensagem

1. Lojista → `POST /mensagens` (canal, marca, identificador, conteúdo, `id_externo`).
2. Inbox: repetida → responde `duplicada = true` e para.
3. Triagem; conversa aberta do cliente travada (ou criada); `transicionar` grava mensagem, auditoria e, se a conversa está com a IA, o evento `mensagem.recebida` na outbox.
4. Conversa nova: roteador escolhe a fila; distribuidor atribui (IA ou humano) e grava `conversa.atribuida` na outbox.
5. Relay → broker `/webhook` → Kafka (ack) → nasce o prazo de 30 s.
6. Agente consome, responde `mensagem.enviada` com `causado_por` e `id_atribuicao`.
7. Kafka → broker → `POST /agente/eventos` → inbox → fencing → `transicionar` grava a resposta, cancela o prazo, grava a saída na outbox.
8. Relay → canal (deduplica) → cliente recebe.
9. Escala: resumo, aviso com tempo estimado, volta ao roteador com `origem = escalado` → fila de escalas → analista.

---

## 6. Experimento técnico (ablação) — `README.md`, Resultados

50 msg/s, 5 min medidos, 7.469 mensagens do cliente por execução; juiz nas pontas (gerador e simulador de canal), ligação exata resposta → mensagem pela outbox.

| Cenário | Proteção | Perdidas | Duplicadas | Escaladas | p95 interna |
|---|---|---|---|---|---|
| E1 base | desligada | 0 | 0 | 0 | — |
| E1 base | ligada | 0 | 0 | 0 | 0,10 s |
| E3b canal reenviando | inbox desligada | 0 | **637** | 0 | 0,12 s |
| E3b canal reenviando | inbox ligada | 0 | **0** | 0 | 0,10 s |
| E6 broker fora 60 s | outbox desligada | **1.455** | 0 | 25 | — |
| E6 broker fora 60 s | outbox ligada | **0** | 0 | 0 | 18,0 s (recuperação 109 s) |

Hipótese e previsão escritas antes de rodar; uma repetição por cenário (vale zero contra não zero e ordem de grandeza).

---

## 7. Testes de carga e hipóteses — `testes-de-carga.md`

**Achado de método:** do Windows, o encaminhamento de porta do Docker limita a ~20 req/s; de dentro da rede do Compose, 92 msg/s na mesma bancada. Os testes rodam dentro do Docker.

| Teste | Resultado |
|---|---|
| T1 rampa 40–200 msg/s (código inicial) | Joelho entre 60 e 80 msg/s totais |
| T3 telas do front, 100 clientes + 50 msg/s | p95 de 3,6 a 4,2 s (meta < 1 s, não passou; sem carga < 120 ms) |
| T4 rajada 100 mil, agente agrupando respostas | 100% das conversas respondidas, 0 duplicatas, 1,6% das mensagens respondidas junto com a seguinte |
| T4 rajada 100 mil, agente respondendo uma a uma | Colapso: prazo do agente vencendo e escalando (metaestável) |
| T4 cadenciado 25 msg/s, código anterior | 100% respondidas, espera p95 91 s |
| **100 mil, código novo, oferta 50 msg/s (efetivo 45,8; ~92 totais)** | **100.000 respondidas, 0 duplicatas, 0 escalas, espera p95 8,7 s, p95 interna 0,45 s, 37 min, reconciliação zerada** |
| H2: 2.000 msgs, 19% reenvios, relay fora 38 s, 1% envenenadas | Passa: 0 duplicatas, 0 violações de ordem, envenenadas estacionaram só a sua conversa |
| H3: 1.000 pedidos de atendente | Passa: 100% com nota e tempo estimado entregue ao cliente |
| H1: 200 msg/s totais | Não passa numa máquina: ingestão p95 75 s, 3.090 escaladas, 0 perdas, 0 duplicatas; reserva do relay 0,5–4 ms |
| Da clonagem à demo | 3,3 min (imagens no cache) |

**Rodada de desempenho** (causas medidas com amostras a cada 30 s e `py-spy`): ordenação da fila inteira por conversa no distribuidor; a linha `atendentes` da IA como fila única da marca; pools de conexão menores que a concorrência; volta do broker e mock em série; broker num processo; log por requisição. Uma tentativa intermediária com mais processos piorou (contenção). Resultado: espera p95 de 91 s para 8,7 s com quase o dobro da taxa.

---

## 8. Testes automatizados e qualidade

- `testes/test_dominio.py` e `test_contrato.py`: 48 unitários e 29 de contrato (triagem, roteador, validadores, escolha do atendente, SLA, mock, esquema publicado).
- `testes/test_integracao.py`: 17 testes em banco descartável (concorrência em `transicionar`, fencing, capacidade, auditoria só de inserção, conversa aberta única, deduplicação, estacionamento e replay, webhook 5x, fila nova sem deploy, rollback < 5 s, escala que regra nenhuma desliga, expurgo, tempo estimado, RLS).
- `testes/fumaca.py`: verificações em 7 cenários contra o ambiente no ar.
- Arquitetura revisada em 5 rodadas (`docs/revisoes/`): de 6,0 / 4,5 (desenho / viabilidade) para 8,5 / 8,5.

---

## 9. Decisões principais (42 registradas em `arquitetura.md`, seção 20)

Volume base 10 mil/dia e meta de 100 msg/s; gargalo é confiabilidade; supervisor como quarta persona; conversa como máquina de estados; IA como atendente; filas no modelo Zendesk; contrato JSON versionado e Kafka por conversa; monólito modular; outbox, idempotência e fila de erros; Python/FastAPI, Postgres, Redpanda, Next.js; experimento por ablação; inbox por consumidor e ids determinísticos; caminho único de escrita com fencing; broker responde só depois do ack; agendador único; reconciliador; regras versionadas; roteador função pura; interface por leitura de 2 s; memória operacional (semântica em Evolução); plano de 2 dias com corte por requisito; roteiro de demonstração. Decisões forçadas pela carga: canal deduplica, IA sem contador, distribuidor por lote, pools, broker em 2 e trabalhador em 4 processos.

---

## 10. Desafios enfrentados

Escopo × prazo (corte por requisito); instrumento que enganava (porta do Docker no Windows); gargalos escondidos (distribuidor, linha da IA, pools); mais processos piorando antes de melhorar; colapso metaestável em rajada; juiz do experimento atribuindo resposta atrasada à mensagem seguinte (corrigido, execução refeita, resultado antigo guardado); 1 duplicata por reserva vencida do relay (deduplicação no canal); RLS ignorado pelo superusuário (papel próprio); ambiente instável (disco cheio, Docker caindo, máquina dormindo no meio da carga).

---

## 11. Limitações (declaradas no README)

Uma máquina só; 200 msg/s não passa; escala horizontal não testada; sem controle de admissão; agente mock sem LLM; triagem por regras; Redpanda de um nó sem fsync; Postgres sem réplica; sem autenticação; contrato é proposta (formato real não público); canais simulados (sem janela de 24 h do WhatsApp nem encadeamento de e-mail); uma repetição por cenário; telas do front lentas com 100 clientes simultâneos sob carga; valores de SLA, retenção e tempo de atendimento são hipóteses.

## 12. Evolução e plano de corte

Memória semântica com embeddings; disjuntor por saúde do agente; encerramento por inatividade; prazo renovável; capacidade da IA por trabalho em voo; escala em várias máquinas; autenticação. Entrada em produção (`plano-de-corte.md`): validar premissas com amostra real da CloudWalk → modo shadow (7 dias) → canário (5%, 25%) → corte por marca com rollback por flag.

---

## 13. Como rodar

```bash
docker compose up -d --build                     # tudo no ar (API em :8000/docs)
cd front && npm install && npm run dev           # telas em http://localhost:3000
py -3.12 -m venv .venv && .venv\Scripts\pip install -r requirements.txt -r requirements-dev.txt
.venv\Scripts\python -m pytest testes/test_contrato.py testes/test_dominio.py
.venv\Scripts\python -m pytest testes/test_integracao.py
.venv\Scripts\python testes\fumaca.py
.venv\Scripts\python -m carga.demo               # demonstração pela API, sem front
.venv\Scripts\python -m carga.hipoteses H2       # hipóteses H2 e H3
```

Configuração principal (ambiente do núcleo): `OUTBOX_ATIVA`, `INBOX_ATIVA`, `FENCING_ATIVO`, `TIMEOUT_ATIVO` (chaves de ablação), `TIMEOUT_AGENTE_S` (30), `RETENTATIVAS_MAX` (8), `HISTORICO_N` (20), `CAPACIDADE_HUMANO` (3), `ENVELHECIMENTO_S` (600), `DB_POOL` (20), `RELAY_WORKERS` (4), `DISTRIBUIDOR_TAREFAS` (2), `DISTRIBUIDOR_LOTE` (20), `RETENCAO_DIAS` (90), `ATENDIMENTO_HUMANO_S` (600).

---

## 14. Mapa do repositório

| Caminho | Conteúdo |
|---|---|
| `nucleo/` | API e domínio (`api/`, `dominio/`, `infra/`, `reconciliacao.py`, `trabalhador.py`) |
| `broker/`, `agente_mock/`, `canais/` | Ponte Kafka, agente simulado, simulador de canais |
| `contrato/` | Envelope, ids, regra do histórico, esquema JSON publicado |
| `migrations/` | Alembic, 0001 a 0007 |
| `carga/` | Gerador, agenda, juiz, lote do experimento, testes completos, hipóteses, demo |
| `testes/` | Unitários, contrato, integração, fumaça |
| `front/` | Next.js |
| `resultados/` | Dados brutos do experimento, da carga e das hipóteses |
| `docs/arquitetura.md` | Fonte da verdade: requisitos, premissas, princípios, decisões |
| `docs/implementacao.md` | Como construir: SQL, contrato campo a campo, algoritmos, configuração |
| `docs/testes-de-carga.md` | Carga, desempenho, hipóteses, reprodutibilidade |
| `docs/validacao-pontos.md` | Conferência item a item do roteiro de validação |
| `docs/plano-de-corte.md` | Premissas com a CloudWalk, shadow, canário, corte |
| `docs/defesa.md` | Guia para a banca |
| `docs/roteiro-apresentacao.md`, `roteiro-arquitetura.md`, `roteiro-demo.md` | Roteiros |
| `docs/diario.md` | Registro do desenvolvimento por dia |

---

## 15. Glossário rápido

- **Outbox**: tabela onde o evento é gravado junto com a mudança, para ser enviado depois com retentativa.
- **Inbox / idempotência**: registro do que já foi processado, para descartar repetidas.
- **Fencing**: descartar resposta de quem já não é o dono da conversa.
- **Relay**: laço que lê a outbox e envia.
- **SKIP LOCKED**: vários processos pegam itens diferentes sem esperar uns pelos outros.
- **Ablação**: desligar uma proteção para medir o efeito de não tê-la.
- **p95**: valor abaixo do qual ficam 95% das medidas.
- **Juiz**: contador nas pontas (o que o cliente mandou e o que recebeu) usado no experimento.
- **Metaestável**: sistema que, passada a capacidade, entra num ciclo em que a própria reação à sobrecarga a piora.
