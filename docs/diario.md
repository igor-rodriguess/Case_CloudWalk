# Diário de desenvolvimento

Uma entrada por parte construída. A última entrada diz onde paramos.

---

## Ponto de controle, fim do dia 1 (2026-11-21): backend no ar

**Commits:** `796bc35` contrato, `b768593` arquitetura, `f60bc0a` backend, `b52a667` testes.
**Estado:** `docker compose up -d --build` sobe tudo; `testes/fumaca.py` passa os 19 cenários; 36 testes unitários passam.
Mudou de ritmo: entrega em 23/11, o backend foi escrito pelo Claude e o front fica comigo (`docs/api-front.md`).

### Uma página por componente

**Contrato (`contrato/`).** Envelope Pydantic: versão casa com `^1.N`; evento do agente exige `id_atribuicao` e `causado_por`; `timestamp` exige fuso. `id_derivado` (uuid5) faz o agente gerar o mesmo id ao reprocessar.
Banca: *por que validar na fronteira?* Evento ruim é barrado na entrada, não vira erro três componentes depois.

**Banco (`migrations/0002`).** Atribuições, auditoria só de inserção (trigger recusa UPDATE/DELETE), inbox (`eventos_processados`), outbox, agendamentos, versões de regras, escalas. Índice único de conversa aberta por cliente e marca.
Banca: *como garante uma conversa só?* Índice único parcial; a entrada tenta de novo se dois pedidos colidirem.

**`transicionar` (`nucleo/dominio/transicionar.py`).** Único caminho que escreve na conversa. Trava a linha, aplica o fencing, confere a transição, confere a capacidade antes de encerrar a atribuição atual, grava estado, mensagem, auditoria e outbox na mesma transação.
Banca: *e se a IA responder depois do timeout?* A resposta leva o `id_atribuicao` antigo; o fencing descarta e audita (cenário 6 da fumaça).

**Outbox e relay (`nucleo/infra/relay.py`).** Reserva um item por vez (`SKIP LOCKED`, ordem por conversa e destino), envia fora da transação, grava o resultado. Retentativa com backoff e jitter; esgotou = `erro`, e destino broker escala por `falha_integracao`. O prazo do agente nasce no ack do broker.
Banca: *por que não publicar direto?* Salvar e publicar são duas operações; se cair no meio, perde. A outbox grava junto com o estado.

**Inbox.** Na entrada dos canais (chave `uuid5(canal, id_externo)`), na API do agente e no mock. Duplicata responde 200 sem efeito.
Banca: *exatamente uma vez?* Não existe na rede; é entrega pelo menos uma vez mais deduplicação nas pontas.

**Broker (`broker/main.py`).** 200 no webhook só depois do ack do Kafka; offset da volta só depois do 2xx do núcleo. 503 ou rede pausa a partição e tenta de novo sem limite (contrapressão); 500 repetido vai para `helpdesk.erros`.

**Agente mock (`agente_mock/main.py`).** Inbox e respostas no próprio banco, publicadas por um laço (a latência não trava a partição). Modos `normal`, `lento`, `duplicar`, `fora`. Escala se o cliente pede humano ou está irritado; resolve depois de 6 trocas.

**Filas (`nucleo/dominio/roteador.py`, `nucleo/api/filas.py`).** Roteador puro: primeira fila que casa leva, senão a padrão. Versões imutáveis, validação de campos, operadores e valores, ativação atômica, rollback e simulador. Ao ativar, conversas em fila removida são re-roteadas.

**Distribuidor (`nucleo/infra/distribuidor.py`, `nucleo/dominio/distribuicao.py`).** Laço de 1 s, uma conversa por transação. Escolha pura: grupo preferido da fila, depois menor ocupação (AI first). Registro de decisão com candidatos e motivo.

**Escala e handoff (`nucleo/dominio/acoes.py`, `nucleo/api/painel.py`).** Escala volta ao roteador com `origem = escalado`, grava resumo (do agente com fontes, ou de reserva, extrativo) e avisa o cliente. Analista assume, responde, devolve para a IA com nota ou encerra.

**Memória operacional.** `conversa.atribuida` leva as últimas 20 mensagens e o perfil de fatos (contatos e escalas em 30 dias, canal preferido, último assunto).

**Reconciliador (`nucleo/reconciliacao.py`).** I1 a I6 sob demanda em `/supervisor/reconciliacao`.

**Ablação.** `OUTBOX_ATIVA`, `INBOX_ATIVA`, `FENCING_ATIVO`, `TIMEOUT_ATIVO` no ambiente do núcleo (compose lê do `.env`).

### Problemas encontrados no dia
- Disco cheio travou o Docker; liberados ~100 GB (jogos e caches, com autorização).
- Porta 8300 ficou presa no Docker depois da falha; o simulador de canais usa 8310 no host (8300 dentro da rede).
- O mock reavaliava a escala na devolução e escalava de novo; corrigido.

### Próximo (dia 2)
Experimento E1, E3b e E6 nas duas posições das chaves, juiz nas pontas, README e roteiro da demonstração.

---

## Fatia 1, passo 1: infraestrutura, banco e tópicos

**Data:** 2026-11-17 a 2026-11-19 · **Commit:** `b5af437` · Feito antes do ritual; registrado depois.

**O que existe**

| Arquivo | Papel |
|---|---|
| `docker-compose.yml` | Sobe `postgres` (porta 5433 no host) e `redpanda` (19092). `topicos` e `migracoes` rodam uma vez e terminam |
| `infra/postgres/01-agente-mock.sql` | Cria o banco `agente_mock` na primeira subida do volume |
| `nucleo/infra/modelos.py` | Tabelas `clientes`, `conversas`, `mensagens` em SQLAlchemy 2.0 |
| `migrations/versions/0001_fatia1_tabelas.py` | Migration que cria as três tabelas |
| `alembic.ini`, `migrations/env.py` | Configuração do Alembic; a URL vem de `DATABASE_URL` |
| `nucleo/Dockerfile`, `nucleo/requirements.txt` | Imagem usada pelo serviço `migracoes` |

**Decisões**
- Portas do host 5433 e 19092 para não colidir com outros projetos.
- psycopg 3 como único driver (síncrono no Alembic, assíncrono na API).
- Colunas `id_atribuicao`, `causado_por` e `seq_outbox` já existem, nulas: o contrato não muda depois.
- Sem índice único de conversa aberta: esta é a versão ingênua do experimento. Entra na fatia 2.
- Convenção de nomes nas constraints, para a migration sair igual em qualquer máquina.

**Problema encontrado**
- O nome da check constraint saiu duplicado (`ck_mensagens_ck_mensagens_autor_tipo`), porque a convenção aplicou o prefixo sobre um nome que já tinha prefixo. Corrigido com `op.f()`, que marca o nome como final.

**Como verificar**

```bash
docker compose up -d --build
docker compose ps -a
docker compose exec postgres psql -U helpdesk -d helpdesk -c "\dt"
docker compose exec redpanda rpk topic list
```

Esperado: `postgres` e `redpanda` healthy; `topicos` e `migracoes` com `Exited (0)`; quatro tabelas (as três mais `alembic_version`); três tópicos.

**Perguntas de banca**
1. Por que a migration é escrita à parte dos modelos, se os dois descrevem as mesmas tabelas?
2. Por que `topicos` e `migracoes` são serviços que terminam, e não parte do núcleo?
3. Por que as colunas de atribuição já existem na fatia 1 se ninguém as usa?
