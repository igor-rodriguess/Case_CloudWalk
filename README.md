# Help Desk AI First

Help desk próprio, multi-marca (InfinitePay, JIM) e multi-equipe, em que o agente de IA atende como um atendente dentro de filas configuráveis e o humano entra por escala. Projeto individual do Inteli com a CloudWalk.

## Problema

A CloudWalk já tem um agente de IA que atende de ponta a ponta, ligado ao help desk por webhook, broker e Kafka. O help desk é de terceiros: lento, com defeitos recorrentes e sem a estrutura multi-marca e multi-equipe da operação. A entrega é um help desk que recebe o agente como atendente, distribui os atendimentos em filas que a operação edita sem deploy e passa para humanos com contexto, sem perder nem duplicar mensagens.

O volume não é o desafio: 10 mil atendimentos por dia (estresse de 50 mil, meta de teste de 100 msg/s) cabem com folga em Postgres e Kafka. O desafio é confiabilidade e estado: milhares de conversas abertas ao mesmo tempo, com falhas, reentregas e picos (`docs/arquitetura.md`, seção 3).

## Arquitetura

```mermaid
flowchart LR
    C[Canais simulados] --> N[Núcleo]
    N -- outbox, webhook --> B[Broker]
    B -- Kafka --> A[Agente mock]
    A -- Kafka --> B
    B -- HTTP --> N
    N -- outbox --> S[Simulador de canais]
    U[Front-end] --> N
    N --- P[(Postgres)]
```

- **Núcleo** (`nucleo/`, FastAPI): entrada dos canais, triagem, roteador de filas (função pura), distribuidor com envelhecimento de prioridade, `transicionar` (toda escrita na conversa acontece sob a trava dela, nessa transação), outbox e relay, agendador de prazos, painel do analista, filas versionadas (re-roteamento de fila removida ao ativar), supervisor e reconciliador sob demanda.
- **Broker** (`broker/`): ponte da estrutura atual. Só responde ao webhook depois do ack do Kafka e só confirma o offset da volta depois do núcleo responder. O laço da volta tem supervisor: reinicia depois de exceção, e `/saude` responde 503 enquanto isso.
- **Agente mock** (`agente_mock/`): faz o papel do agente da CloudWalk, que está fora do escopo. Modos `normal`, `lento`, `duplicar`, `fora`.
- **Simulador de canais** (`canais/`): a ponta onde o cliente recebe; grava cada entrega para o juiz do experimento.

Garantias: entrega pelo menos uma vez com deduplicação na entrada, na API do agente e no mock (inbox), e saída por canal pelo menos uma vez, sem inbox; outbox transacional, fencing por `id_atribuicao` (resposta atrasada do agente não atropela o humano), prazo do agente contado do ack do broker, auditoria só de inserção com o porquê de cada decisão.

Documentos: [`docs/arquitetura.md`](docs/arquitetura.md) (o quê e por quê, com decisões e referências), [`docs/implementacao.md`](docs/implementacao.md) (como), [`docs/referencias.md`](docs/referencias.md), [`docs/api-front.md`](docs/api-front.md), [`docs/diario.md`](docs/diario.md), revisões em [`docs/revisoes/`](docs/revisoes/).

## Instalação

Requisitos: Docker com Compose, Python 3.12 (só para testes e experimento).

```bash
docker compose up -d --build
```

| Serviço | Endereço |
|---|---|
| API do núcleo e OpenAPI | http://localhost:8000/docs |
| Broker | http://localhost:8100 |
| Agente mock | http://localhost:8200 |
| Simulador de canais | http://localhost:8310 |
| Postgres | localhost:5433 (helpdesk / helpdesk) |
| Kafka (Redpanda) | localhost:19092 |

Testes:

```bash
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt -r requirements-dev.txt
.venv\Scripts\python -m pytest testes/test_contrato.py testes/test_dominio.py
.venv\Scripts\python -m pytest testes/test_integracao.py
.venv\Scripts\python testes\fumaca.py
```

- `test_contrato.py` e `test_dominio.py`: 36 testes unitários (contrato, triagem, roteador, validação de regras, escolha do atendente).
- `test_integracao.py`: 9 testes contra o Postgres do compose, num banco descartável que o próprio arquivo cria e apaga; roda sozinho, num comando à parte. Cobre concorrência em `transicionar`, transição inválida, fencing, capacidade sob concorrência, `SEM_CAPACIDADE` sem deixar a conversa sem dono, auditoria só de inserção, conversa aberta única, deduplicação na entrada e na API do agente, tipo de evento desconhecido.
- `fumaca.py`: 18 verificações em 7 cenários contra o ambiente no ar: caminho feliz, reenvio deduplicado, escala para humano com resumo, resposta do analista e devolução para a IA, só o dono responde, timeout com a resposta atrasada descartada pelo fencing, reconciliação (confere I3 a I6).

O que o desenho previa e não tem teste automatizado está em `docs/implementacao.md`, seção 13, com o meio que cobre cada caso, quando há.

## Front-end

A interface (chat simulado, acompanhamento, painel do analista, editor de filas) é feita pelo autor, fora deste repositório, consumindo a API do núcleo; o contrato que ela usa está em [`docs/api-front.md`](docs/api-front.md) e no OpenAPI em `/docs`. Sem autenticação: o perfil é escolhido na tela.

A demonstração tem reserva sem o front: `carga/demo.py` percorre os 7 momentos do roteiro (`docs/arquitetura.md`, 19.4) contra o ambiente no ar, com pausa a cada momento:

```bash
.venv\Scripts\python -m carga.demo
```

## Configuração

Variáveis do núcleo (no `.env` ou no ambiente do compose): `OUTBOX_ATIVA`, `INBOX_ATIVA`, `FENCING_ATIVO`, `TIMEOUT_ATIVO` (chaves de ablação, `true` por padrão), `TIMEOUT_AGENTE_S` (30), `RETENTATIVAS_MAX` (8), `HISTORICO_N` (20), `CAPACIDADE_HUMANO` (3), `CAPACIDADE_IA` (1.000.000, na prática sem limite), `ENVELHECIMENTO_S` (600, hipótese). Lista completa em `docs/implementacao.md`, seção 10. As filas são configuradas pela API (`/filas`), sem deploy.

## Metodologia do experimento

Mede a robustez da plataforma, não a qualidade das respostas do agente.

- **Ablação:** uma versão só, com chaves que desligam cada proteção. Cada cenário roda com a chave que ele testa ligada e desligada.
- **Cenários:** E1 base (outbox e inbox juntas), E3b reenvio de 10% das mensagens pelo canal 2 s depois (inbox), E6 broker fora por 60 s (outbox).
- **Carga:** gerador Python (`carga/gerador.py`, no lugar do k6), 6 mensagens por conversa, 84 s entre elas, 7 min de aquecimento e 5 min medidos, agenda com semente fixa (`carga/agenda.py`; `--semente` de `carga/rodar.py`, padrão 42). A meta era 100 msg/s (8,3 conversas/s); num teste com o código anterior às correções de desempenho a máquina saturou perto de 70 msg/s no total (~35 de cliente), então as execuções rodam no plano B do documento: **50 msg/s nas duas direções (4,15 conversas/s)**, com o banco limpo e o código do commit atual. As previsões foram reescalonadas para 50 msg/s antes de ver a tabela (`docs/implementacao.md`, seção 14).
- **Juiz nas pontas:** conta o que o cliente enviou e o que o canal entregou; liga cada resposta à mensagem pelo banco do núcleo.
- **p95 interna:** da entrada da mensagem ao ack do broker, só para `mensagem.recebida` e só com a outbox ligada (desligada, não há linha de outbox: "—"). A 1ª mensagem de cada conversa fica fora da amostra.
- **Recuperação (E6):** da volta do broker até a última resposta entregue das mensagens enviadas durante a falha.
- O reconciliador (`GET /supervisor/reconciliacao`: I1, I1b, I2 a I6) é consulta sob demanda; não roda por execução do lote.

```bash
.venv\Scripts\python -m carga.lote
.venv\Scripts\python -m carga.tabelas
```

## Resultados

RESULTADOS_AQUI

## Limitações

- Ambiente local, agente mock com texto fixo, dados sintéticos, premissas de volume (12 mensagens por atendimento, pico de 5x).
- Entrega pelo menos uma vez onde não controlamos o receptor; o id determinístico é requisito imposto ao agente. A saída por canal não tem inbox: uma entrega repetida pelo relay (reenvio depois de um envio que deu certo sem o resultado gravado) conta como duplicata no juiz, também com as chaves ligadas.
- Ordem por conversa e destino deixa de valer depois de um item em `erro` na outbox: reprocessado, ele sai depois dos seguintes.
- Redpanda de um nó em modo de desenvolvimento, que confirma sem fsync.
- Fila no caminho de volta conta contra o agente: resposta presa no broker escala por timeout.
- O formato do contrato é proposta nossa (o da CloudWalk não é público); marca fixa no contrato.
- Canais simulados: janela de 24 h do WhatsApp e encadeamento de e-mail ficam de fora.
- A ablação desliga uma chave por vez e não mede interações entre proteções.
- Postgres sem réplica: falha de disco ou de banco não é testada.
- Sem autenticação (perfil escolhido na tela); isolamento por marca só por filtro.
- O gerador de carga (Python, no lugar do k6) roda na mesma máquina e disputa CPU com o sistema.
- A qualidade do resumo de handoff não é medida.
- Sem inatividade: conversa com humano esperando o cliente ocupa vaga até o analista encerrar.
- O juiz depende do banco do núcleo para ligar resposta a mensagem e supõe uma resposta antes da mensagem seguinte da conversa.
- Uma repetição por cenário e posição: sem variância; vale zero contra não zero e a ordem de grandeza.
- Carga medida a 50 msg/s, não a 100: numa máquina só, com gerador, broker, Kafka, Postgres e mock juntos, o sistema começou a recusar perto de 70 msg/s no total, num teste com o código anterior às correções de desempenho. A meta de 100 msg/s fica sem evidência.
- A IA não tem limite na prática (`CAPACIDADE_IA` = 1.000.000, contada em conversas abertas; o limite por custo é Evolução), mas `transicionar` trava a linha da IA a cada atribuição e a atualiza a cada escala e resolução. Isso serializa essas transações por marca e é possível fonte de contenção na saturação (hipótese, não medida).
- p95 interna só na posição ligada e sem a 1ª mensagem de cada conversa (subestima a latência de quem abre a conversa); a comparação de custo entre as posições fica com a espera até a 1ª resposta.
- Reconciliador simplificado e sob demanda: I3 não compara conteúdo (não vê a duplicata do E3b) e I1 só olha conversas com a IA; quem mede perda e duplicata é o juiz.
- Re-roteamento de fila removida pula a conversa travada no instante da ativação (`SKIP LOCKED`); ela só é re-roteada na ativação seguinte. Envelhecimento (`ENVELHECIMENTO_S` = 600 s) é hipótese, sem medida; nenhum dos dois tem teste próprio.
- Parte dos testes previstos não está automatizada (relay morto, linha que sempre falha, Kafka fora, deadlock, reinício, invariantes plantadas, distribuidor, isolamento por marca): lista e cobertura alternativa em `docs/implementacao.md`, seção 13.
- Cenários fora da entrega: rampa até 200 msg/s, duplicatas do agente, agente lento e fora como cenário medido, núcleo morto, disjuntor, escalabilidade horizontal. Desenho e previsão em `docs/implementacao.md`, seção 14.

## Evolução

Disjuntor por saúde do agente com política por fila, renovação de prazo (heartbeat), inatividade e SLA, reabertura e fusão de identidades, capacidade da IA por custo (sem travar a linha da IA), reconciliador periódico com I3 por conteúdo, canal ao vivo (SSE), memória semântica com embeddings, várias instâncias medidas, migração gradual para Ruby. Detalhes em `docs/arquitetura.md`, seção 21, e `docs/diferenciais.md`.
