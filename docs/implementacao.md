# Guia de implementação

Como construir o que está em [`arquitetura.md`](arquitetura.md). A arquitetura diz o que e por quê; este arquivo diz como.

Valores marcados como **(inicial)** são pontos de partida, não medidos. Ajustar no experimento.

---

## 1. Estrutura do repositório

```
helpdesk-ai-first/
├── docker-compose.yml
├── .env.example
├── contrato/              # pacote compartilhado: envelope, eventos, JSON Schema
├── nucleo/
│   ├── api/               # mensagens, agente, painel
│   ├── dominio/           # estados, transicionar, roteador, distribuidor, triagem, disjuntor, memória
│   ├── infra/             # banco, modelos, relay da outbox, agendador
│   └── main.py
├── broker/                # webhook -> Kafka e Kafka -> núcleo
├── agente_mock/
├── canais/                # simulador dos canais de saída; grava entregas e transferências (juiz)
├── interface/             # Next.js (a partir da fatia 3)
├── reconciliador/         # banco próprio; lê o banco do núcleo
├── infra/postgres/        # scripts da primeira subida do Postgres
├── migrations/            # Alembic
├── carga/                 # k6, agenda, injeção de falhas (falhas.py), tabelas, analistas simulados
├── testes/
└── docs/
```

`contrato/` é instalado no núcleo, no broker e no mock.

## 2. Serviços

| Serviço | Porta | Papel |
|---|---|---|
| `postgres` | 5433 no host, 5432 na rede | Databases `helpdesk` (núcleo), `agente_mock`, `canais` e `reconciliador` |
| `redpanda` | 19092 no host, 9092 na rede | Kafka (modo de desenvolvimento, um nó) |
| `topicos`, `migracoes` | — | Criam os tópicos e aplicam as migrations, e terminam |
| `nucleo` | 8000 | API (uvicorn com 4 processos, sem laços) |
| `trabalhador` | — | Laços de fundo: relay (8 tarefas), agendador, distribuidor. Separado da API depois do primeiro lote (diário, dia 2) |
| `broker` | 8100 | `POST /webhook` e consumidor de `agente.para-helpdesk`; sem banco |
| `agente_mock` | 8200 | Consumidor de `helpdesk.para-agente`; `GET /saude` e `POST /modo` |
| `canais` | 8310 no host, 8300 na rede | Simulador dos canais de saída: recebe o que a plataforma envia ao cliente, inclusive a transferência; grava no database `canais`, onde o juiz lê as entregas; `POST /modo` com `fora` |
| `interface` | 3000 | Next.js: chat, acompanhamento, painel do analista, configuração |
| `reconciliador` | — | Job periódico e sob demanda no fim de cada execução do experimento. Na entrega, só o script SQL com I1 a I4 no fim de cada execução (9) |

Núcleo, broker, mock e canais usam a mesma imagem Python (`helpdesk-app`), com comando diferente por serviço. O mock, o simulador de canais e o reconciliador têm banco próprio: não escrevem nas tabelas do núcleo. O database `reconciliador` entra no script de `infra/postgres` na fatia 3. Portas do host fogem de 5432 e 9092 para não colidir com outros projetos.

Bibliotecas: FastAPI, SQLAlchemy 2.0, psycopg 3 (um driver, síncrono no Alembic e assíncrono na API), Alembic, Pydantic v2, aiokafka, httpx, pytest. Versões das imagens fixadas no compose.

## 3. Kafka

| Tópico | Chave | Partições (inicial) | Produz | Consome |
|---|---|---|---|---|
| `helpdesk.para-agente` | `id_conversa` | 12 | broker | agente mock |
| `agente.para-helpdesk` | `id_conversa` | 12 | agente mock | broker |
| `helpdesk.erros` | `id_conversa` | 3 | só o broker | operação |

- Produtor: `acks=all`, `enable_idempotence=True`. No modo de desenvolvimento o Redpanda confirma sem fsync: `acks=all` não garante durabilidade aqui (limitação).
- Consumidor: `enable_auto_commit=False`; commit depois do efeito. 12 partições = até 12 consumidores por grupo.
- O núcleo não publica no Kafka; a fila de erros dele é `outbox.status = 'erro'` (7.3).

## 4. Contrato

### 4.1 Envelope

| Campo | Tipo | Regra |
|---|---|---|
| `versao` | string | Casa com `^1\.\d+$`. Versão principal nova só para quebra |
| `id_evento` | UUID | v4 para evento original; v5 para evento derivado (4.3) |
| `tipo` | string | Um dos tipos de 4.2 |
| `id_conversa` | UUID | Chave de partição |
| `id_atribuicao` | UUID | Obrigatório nos eventos do agente |
| `causado_por` | UUID ou nulo | Obrigatório nos eventos do agente |
| `marca` | string | `infinitepay` ou `jim` |
| `timestamp` | ISO 8601 com fuso | |
| `dados` | objeto | Conteúdo por tipo |

- **Evolução:** dentro da versão principal só se acrescenta tipo ou campo, sempre opcional. O envelope continua recusando tipo desconhecido; quem tolera é o consumidor: trata esse erro de validação como "audita e confirma", sem mandar para a fila de erros. Outros erros de esquema vão para `helpdesk.erros` (pelo broker).
- `dados` é imutável só no envelope (`frozen` é raso): ninguém deve alterar o dicionário no caminho.
- Exemplos com ids legíveis (`evt_8f2a`, `conv_123`) são ilustrativos; o código exige UUID.
- **Fatia 1:** ao criar a conversa, o núcleo gera `id_atribuicao_atual` (sem tabela `atribuicoes`) e o manda em `conversa.atribuida` e `mensagem.recebida`. O mock devolve o `id_atribuicao` recebido e preenche `causado_por`; o núcleo grava em `mensagens.id_atribuicao`, sem fencing.
- Na entrega (arquitetura 19.1): envelope com `^1\.\d+$`; `agente.processando` é auditado e confirmado com 200, sem renovar prazo (7.7 é Evolução).

### 4.2 Tipos de evento

| Tipo | Direção | `dados` |
|---|---|---|
| `conversa.atribuida` | plataforma → agente | `cliente` (id, nome, segmento), `fila`, `persona` (opcional, D1), `historico` (últimas `HISTORICO_N` mensagens, lidas sob a trava), `perfil` (4.4) |
| `mensagem.recebida` | plataforma → agente | `id_mensagem`, `conteudo`, `canal` |
| `conversa.devolvida` | plataforma → agente | `motivo`, `nota_do_analista` e o mesmo contexto de `conversa.atribuida` |
| `conversa.encerrada` | plataforma → agente | `motivo` (`resolvida` ou `inatividade`) |
| `mensagem.enviada` | agente → plataforma | `conteudo`, `sequencia` (0, 1, 2... por mensagem recebida) |
| `acao.executada` | agente → plataforma | `acao`, `parametros`, `resultado` |
| `conversa.escalada` | agente → plataforma | `motivo`, `resumo`, `prioridade_sugerida`, `fontes` (opcional: ids das mensagens que sustentam o resumo) |
| `conversa.resolvida` | agente → plataforma | `resumo` |
| `agente.processando` | agente → plataforma | vazio; o `causado_por` aponta a mensagem em atendimento |

- O agente pode mandar várias `mensagem.enviada` por mensagem recebida, com `id_derivado(causado_por, "mensagem.enviada", sequencia)`.
- Evento do agente com `causado_por = X` cancela todos os `timeout_agente` pendentes da mesma atribuição criados até o de `referencia = X` (responder uma mensagem cobre as anteriores).
- Heartbeat: `id_derivado(causado_por, "agente.processando", n)`.
- Resumo no painel: com `fontes`, links para as mensagens citadas; sem, marcado "sem fontes". Resumo de reserva (escala por timeout ou falha) é extrativo: triagem + últimas N mensagens.
- JSON Schema de cada tipo exportado dos modelos Pydantic para `contrato/schemas/`.

### 4.3 Id determinístico

```python
NAMESPACE_HELPDESK = uuid.uuid5(uuid.NAMESPACE_URL, "helpdesk-ai-first")

def id_derivado(causado_por: UUID, tipo: str, sequencia: int = 0) -> UUID:
    return uuid.uuid5(NAMESPACE_HELPDESK, f"{causado_por}:{tipo}:{sequencia}")
```

Processar a mesma entrada duas vezes produz o mesmo id. É requisito do contrato: o mock cumpre; o agente real precisaria cumprir.

### 4.4 Perfil operacional

```json
"perfil": {
  "produtos": ["maquininha", "conta"],
  "contatos_30d": 3,
  "escalas_30d": 1,
  "canal_preferido": "whatsapp",
  "ultimo_assunto": {"categoria": "repasse", "data": "2026-11-10",
                     "resumo": "Repasse atrasado; resolvido após reprocessamento."}
}
```

Só esses campos, por SQL sobre as conversas do cliente na marca (janela `PERFIL_JANELA_DIAS`). Nenhum texto inferido; o resumo do último assunto é o que foi escrito ao encerrar.

## 5. Banco de dados

### 5.1 O que entra em cada fatia

| Fatia | Tabelas e colunas |
|---|---|
| 1 | `clientes`, `conversas`, `mensagens` (migration 0001, não se edita) |
| 2 | Migration 0002: `mensagens.id_externo` com índice sem unicidade (a deduplicação é pela inbox, 7.2), `conversas.prioridade` para `smallint`, `mensagens.id_atribuicao_declarada`, `mensagens.seq`, `mensagens.sequencia`; `conversas.seq_mensagem`; `CHECK` dos seis estados. Tabelas `atendentes`, `atribuicoes`, `transicoes_permitidas`, `eventos` (com trigger), `eventos_processados`, `outbox`; índice de conversa aberta |
| 3 | `agendamentos`; `conversas.motivo_encerramento`; `violacoes` no banco `reconciliador` |
| 5 | `marcas`, `equipes`, `versoes_regras`, `escalas`, `disjuntores`; `conversas.idioma`, `conversas.origem`; `id_fila` como `text` em `conversas` e `atribuicoes` |
| 7 | `identidades`; `clientes.produtos` |

**Na entrega:** uma migration 0002 única com o que as fatias 2, 3, 5 e 7 listam. Tabelas e colunas de mecanismos que viraram Evolução (`disjuntores`, `conversas.na_fila_desde`, tipos de agendamento além de `timeout_agente`) podem existir sem uso. `identidades` em versão mínima: canal + identificador → cliente, sem fusão. `violacoes` não entra: o reconciliador é um script (9).

### 5.2 Tabelas

```sql
CREATE TABLE clientes (
    id            uuid PRIMARY KEY,
    marca         text NOT NULL,
    nome          text NOT NULL,          -- sintético
    segmento      text,
    produtos      text[] NOT NULL DEFAULT '{}',   -- fatia 7, sintético
    criado_em     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE conversas (
    id                   uuid PRIMARY KEY,
    id_cliente           uuid NOT NULL REFERENCES clientes(id),
    marca                text NOT NULL,
    canal                text NOT NULL,
    estado               text NOT NULL CHECK (estado IN
                         ('nova', 'na_fila', 'com_ia', 'escalada', 'com_humano', 'resolvida')),
    categoria            text,
    prioridade           smallint,                           -- 1 baixa, 2 média, 3 alta
    sentimento           text,
    idioma               text,
    origem               text NOT NULL DEFAULT 'cliente',   -- cliente, escalado
    id_fila              text,                               -- id estável da fila na versão de regras
    id_atendente         uuid,
    id_atribuicao_atual  uuid,
    versao_regras        int,
    versao               int    NOT NULL DEFAULT 0,
    seq_outbox           bigint NOT NULL DEFAULT 0,
    seq_mensagem         bigint NOT NULL DEFAULT 0,          -- sobe a cada mensagem, sob a trava
    motivo_encerramento  text,                               -- resolvida ou inatividade
    criada_em            timestamptz NOT NULL DEFAULT now(),
    atualizada_em        timestamptz NOT NULL DEFAULT now(),  -- gravado por transicionar
    resolvida_em         timestamptz
);
CREATE UNIQUE INDEX conversa_aberta_unica
    ON conversas (id_cliente, marca) WHERE estado <> 'resolvida';
CREATE INDEX ON conversas (id_fila, prioridade DESC, criada_em) WHERE estado IN ('na_fila', 'escalada');

CREATE TABLE mensagens (
    id                       uuid PRIMARY KEY,
    id_conversa              uuid NOT NULL REFERENCES conversas(id),
    autor_tipo               text NOT NULL CHECK (autor_tipo IN ('cliente', 'ia', 'humano', 'sistema')),
    id_autor                 uuid,
    conteudo                 text NOT NULL,
    canal                    text NOT NULL,
    id_externo               text,          -- id do canal (wamid, Message-ID); sempre gravado
    id_evento                uuid UNIQUE,
    causado_por              uuid,
    sequencia                int NOT NULL DEFAULT 0,
    id_atribuicao_declarada  uuid,          -- a que o evento dizia
    id_atribuicao            uuid,          -- a vigente ao gravar
    seq                      bigint,        -- conversas.seq_mensagem no momento
    criada_em                timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON mensagens (canal, id_externo);   -- sem unicidade: o juiz liga a resposta ao id_externo
CREATE INDEX ON mensagens (id_conversa, seq);
CREATE INDEX ON mensagens (causado_por) WHERE autor_tipo = 'ia';

CREATE TABLE atendentes (
    id           uuid PRIMARY KEY,
    tipo         text NOT NULL CHECK (tipo IN ('ia', 'humano')),
    nome         text NOT NULL,
    marca        text NOT NULL,
    id_equipe    uuid,
    habilidades  text[] NOT NULL DEFAULT '{}',
    capacidade   int  NOT NULL,           -- humano: conversas; IA: mensagens aguardando resposta
    ativas       int  NOT NULL DEFAULT 0, -- humano: conversas abertas, atualizado sob a trava
    status       text NOT NULL DEFAULT 'disponivel'
);

CREATE TABLE atribuicoes (
    id            uuid PRIMARY KEY,
    id_conversa   uuid NOT NULL REFERENCES conversas(id),
    id_fila       text,
    id_atendente  uuid NOT NULL REFERENCES atendentes(id),
    inicio        timestamptz NOT NULL DEFAULT now(),
    fim           timestamptz,
    motivo_fim    text
);
CREATE INDEX ON atribuicoes (id_atendente) WHERE fim IS NULL;

CREATE TABLE transicoes_permitidas (
    de text NOT NULL, para text NOT NULL, ator_tipo text NOT NULL,
    PRIMARY KEY (de, para, ator_tipo)
);

CREATE TABLE eventos (                 -- auditoria, só inserção
    id             bigserial PRIMARY KEY,
    id_evento      uuid,
    tipo           text NOT NULL,
    ator_tipo      text NOT NULL,
    id_ator        uuid,
    id_conversa    uuid,
    id_atribuicao  uuid,
    payload        jsonb NOT NULL DEFAULT '{}',
    criado_em      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON eventos (id_conversa, criado_em);
CREATE INDEX ON eventos (tipo, criado_em);
-- trigger BEFORE UPDATE OR DELETE ON eventos que levanta erro

CREATE TABLE eventos_processados (     -- inbox; na entrada, id_evento = chave_entrada(canal, id_externo)
    consumidor text NOT NULL, id_evento uuid NOT NULL,
    processado_em timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (consumidor, id_evento)
);

CREATE TABLE outbox (
    id                 bigserial PRIMARY KEY,
    id_evento          uuid NOT NULL UNIQUE,
    id_conversa        uuid,
    id_atribuicao      uuid,            -- do evento; capacidade da IA e timeout no envio
    sequencia          bigint,
    destino            text NOT NULL,   -- 'broker' ou 'canal'
    payload            jsonb NOT NULL,
    status             text NOT NULL DEFAULT 'pendente'
                       CHECK (status IN ('pendente', 'enviando', 'enviado', 'erro')),
    reservado_ate      timestamptz,
    tentativas         int  NOT NULL DEFAULT 0,
    proxima_tentativa  timestamptz NOT NULL DEFAULT now(),
    ultimo_erro        text,
    criado_em          timestamptz NOT NULL DEFAULT now(),
    enviado_em         timestamptz
);
CREATE INDEX ON outbox (status, proxima_tentativa);
CREATE INDEX ON outbox (id_conversa, destino, sequencia);

CREATE TABLE agendamentos (
    id             bigserial PRIMARY KEY,
    tipo           text NOT NULL,       -- timeout_agente, sla, inatividade_aviso,
                                        -- inatividade_encerra, espera_retida
    id_conversa    uuid NOT NULL,
    id_atribuicao  uuid,
    referencia     uuid,                -- ex.: id_evento da mensagem que aguarda resposta
    executar_em    timestamptz NOT NULL,
    renovacoes     int  NOT NULL DEFAULT 0,
    sonda          boolean NOT NULL DEFAULT false,
    status         text NOT NULL DEFAULT 'pendente'
                   CHECK (status IN ('pendente', 'executado', 'cancelado')),
    motivo_fim     text,                -- resposta, timeout, descartado, atribuicao_encerrada, nova_mensagem
    criado_em      timestamptz NOT NULL DEFAULT now(),
    finalizado_em  timestamptz
);
CREATE INDEX ON agendamentos (status, executar_em);
CREATE INDEX ON agendamentos (id_conversa) WHERE status = 'pendente';
CREATE INDEX ON agendamentos (id_atribuicao, tipo) WHERE status = 'pendente';
CREATE INDEX ON agendamentos (tipo, finalizado_em);

CREATE TABLE versoes_regras (
    numero serial PRIMARY KEY, filas jsonb NOT NULL,
    ativa boolean NOT NULL DEFAULT false, criada_por text NOT NULL,
    criada_em timestamptz NOT NULL DEFAULT now(), ativada_em timestamptz
);
CREATE UNIQUE INDEX uma_versao_ativa ON versoes_regras (ativa) WHERE ativa;

CREATE TABLE disjuntores (            -- uma linha por atendente IA
    id_atendente      uuid PRIMARY KEY REFERENCES atendentes(id),
    estado            text NOT NULL DEFAULT 'fechado'
                      CHECK (estado IN ('fechado', 'aberto', 'meio_aberto')),
    mudou_em          timestamptz NOT NULL DEFAULT now(),
    sondas_restantes  int NOT NULL DEFAULT 0
);

-- banco reconciliador
CREATE TABLE violacoes (
    id bigserial PRIMARY KEY, invariante text NOT NULL,
    referencia text NOT NULL, detectada_em timestamptz NOT NULL DEFAULT now()
);
```

Limpeza diária: `outbox` com `status = 'enviado'` e `agendamentos` finalizados há mais de 7 dias **(inicial)**.

## 6. Máquina de estados

| De | Para | Ator | Disparo |
|---|---|---|---|
| `nova` | `na_fila` | sistema | triagem e roteamento |
| `na_fila` | `com_ia` | sistema | distribuidor escolheu a IA |
| `na_fila` | `com_humano` | sistema, humano | distribuidor ou analista puxou |
| `na_fila` | `escalada` | sistema | disjuntor aberto e `ESPERA_MAX_RETIDA_S` vencido (`agente_indisponivel`) |
| `com_ia` | `escalada` | ia, sistema, cliente | `conversa.escalada`; `timeout_agente`; `falha_integracao`; cliente pediu humano |
| `escalada` | `com_humano` | sistema, humano | distribuidor ou analista puxou |
| `com_humano` | `com_ia` | humano | analista devolveu |
| `com_ia` | `resolvida` | ia, sistema | `conversa.resolvida`; inatividade |
| `com_humano` | `resolvida` | humano, sistema | analista encerrou; inatividade |
| `resolvida` | `na_fila` | cliente | voltou dentro da janela |

Essas linhas viram a carga de `transicoes_permitidas` (uma linha por ator).

- **Escala:** ao entrar em `escalada`, a conversa recebe `origem = escalado` e passa por `rotear`, que escolhe a fila de escalas da marca e da equipe. Na mesma transação, grava na outbox (destino `canal`) uma mensagem de sistema de transferência ao cliente, com `causado_por` = evento que escalou: o `id_evento` do `conversa.escalada`; a `referencia` do `timeout_agente` (agendador); o `id_evento` do item da outbox que esgotou (relay); no pedido do cliente, a chave do evento de entrada, `chave_entrada(canal, id_externo)`. O `causado_por` diz o que escalou; o juiz liga a transferência às mensagens da conversa pela regra de 14.
- **Atribuição:** entrar em `com_ia` ou `com_humano` cria atribuição e atualiza `id_atribuicao_atual`; sair encerra a atribuição, cancela os agendamentos pendentes dela (`atribuicao_encerrada`) e zera `id_atribuicao_atual`.
- **Reabertura** (Evolução na entrega): `resolvida → na_fila` limpa `motivo_encerramento` e `resolvida_em` e passa de novo por `rotear`.
- **Devolução** (na entrega, só se couber; arquitetura 19.3): `com_humano → com_ia`; `conversa.devolvida` ganha `timeout_agente` no envio (7.3), como a atribuição.

## 7. Algoritmos

### 7.1 transicionar

Único caminho que escreve na conversa. Também grava mensagens sem mudar o estado (`para=None`). Não faz commit: quem chama abre a transação, e a inbox entra nela. Nunca levanta exceção por regra de negócio: devolve um resultado, e quem chama confirma a auditoria.

```python
async def transicionar(s, id_conversa, para, ator, id_atribuicao=None,
                       id_atendente=None, mensagem=None, saidas=(), motivo=None):
    c = await s.get(Conversa, id_conversa, with_for_update=True)

    if FENCING_ATIVO and id_atribuicao is not None and id_atribuicao != c.id_atribuicao_atual:
        await auditar(s, c, "evento_descartado", ator, motivo="atribuicao_vencida")
        return Resultado.DESCARTADO

    if para is not None:
        if not await permitida(s, c.estado, para, ator.tipo):
            await auditar(s, c, "transicao_invalida", ator, de=c.estado, para=para)
            return Resultado.REJEITADO
        atende = para in ("com_ia", "com_humano")
        if atende and not await tem_capacidade(s, id_atendente):  # humano: trava e lê ativas; IA: sem limite
            await auditar(s, c, "sem_capacidade", ator, atendente=id_atendente)
            return Resultado.SEM_CAPACIDADE                # nada mudou: segue com o dono atual
        if c.id_atribuicao_atual is not None:
            await encerrar_atribuicao(s, c, motivo)        # cancela agendamentos; ativas -= 1
        if atende:
            await criar_atribuicao(s, c, id_atendente)     # ativas += 1 (humano)
        if para == "escalada":
            c.origem = "escalado"
        if para == "resolvida":
            c.motivo_encerramento = "inatividade" if motivo == "inatividade" else "resolvida"
            c.resolvida_em = func.now()
        c.estado, c.versao = para, c.versao + 1

    if mensagem is not None:
        c.seq_mensagem += 1
        mensagem.seq = c.seq_mensagem
        mensagem.id_atribuicao_declarada = id_atribuicao
        mensagem.id_atribuicao = c.id_atribuicao_atual
        s.add(mensagem)
        await prazos_de_inatividade(s, c, mensagem)        # 7.8

    for evento in saidas:                                  # contexto (últimas N) lido aqui, sob a trava
        c.seq_outbox += 1
        s.add(Outbox(id_evento=evento.id_evento, id_conversa=c.id, sequencia=c.seq_outbox,
                     id_atribuicao=c.id_atribuicao_atual, destino=evento.destino,
                     payload=evento.model_dump(mode="json")))

    c.atualizada_em = func.now()
    await auditar(s, c, "transicao" if para else "mensagem", ator, para=para)
    return Resultado.APLICADO
```

- **Ordem de travas:** conversa → atendente novo (se humano) → agendamentos → atendente antigo (se humano) → disjuntor (Evolução na entrega). É a ordem do código: `tem_capacidade` trava o novo antes de `encerrar_atribuicao` cancelar agendamentos e liberar o antigo, para `SEM_CAPACIDADE` não deixar a conversa sem dono. Nunca dois humanos na mesma transação: não há `com_humano → com_humano`, e a IA não trava linha.
- **Capacidade:** humano conta conversas abertas (`ativas`, sob a trava da linha). Na entrega a IA não tem limite (decisão 39 é Evolução). Quando entrar (rodada 3, item 1): conta só `timeout_agente` pendentes das atribuições dela, enviados e sem resposta; evento parado na outbox é atraso da plataforma e não conta; sem travar a linha, porque é limite de custo; e só o distribuidor a confere, porque é ele que repesca `SEM_CAPACIDADE`.
- `acao.executada` descartada pelo fencing: auditada com o payload inteiro e `fora_da_atribuicao`. Resumo de `conversa.escalada` atrasado: anexado à escala vigente.
- Nenhuma chamada HTTP aqui dentro.

### 7.2 Consumidor com inbox

Vale para a API do agente no núcleo, para o mock, para a saída por canal e para a entrada dos canais.

```python
async def tratar(consumidor, envelope, efeito):
    async with sessao.begin() as s:
        novo = True
        if INBOX_ATIVA:
            novo = await s.scalar(text("""
                INSERT INTO eventos_processados (consumidor, id_evento)
                VALUES (:c, :e) ON CONFLICT DO NOTHING RETURNING 1
            """), {"c": consumidor, "e": envelope.id_evento})
        if novo:
            await efeito(s, envelope)
    # só depois do commit: confirmar offset ou responder 200
```

- A API do agente responde 200 para duplicata, descarte, transição inválida e tipo desconhecido (auditado); 503 quando o banco está fora. Nunca 500 por regra de negócio.
- Entrada dos canais: `POST /mensagens` recebe `id_externo` e chama `tratar("entrada", ...)` com `id_evento = uuid5(NAMESPACE_HELPDESK, f"entrada:{canal}:{id_externo}")`; repetido responde 200 sem efeito. A `mensagem.recebida` ganha id novo e grava `id_externo` sempre.
- Com `INBOX_ATIVA = false` (ablação), nenhum consumidor deduplica: o reenvio do canal vira mensagem e evento novos, com o mesmo `id_externo`, e o juiz liga as duas respostas a ele (E3b). Um `IntegrityError` em `mensagens.id_evento` (duplicata do agente, E3) é registrado em log e segue, sem travar.

### 7.3 Relay da outbox

`RELAY_WORKERS` tarefas (11) reservam um item por vez, enviam fora da transação e gravam o resultado em outra. A ordem por conversa e destino vem da consulta de reserva, então tarefas diferentes só pegam conversas ou destinos diferentes. Cada tarefa drena até a fila esvaziar e só então dorme `RELAY_INTERVALO_MS`.

```sql
-- reserva (transação curta)
UPDATE outbox SET status = 'enviando', reservado_ate = now() + make_interval(secs => :reserva)
WHERE id = (
    SELECT o.id FROM outbox o
    WHERE (o.status = 'pendente' AND o.proxima_tentativa <= now()
           OR o.status = 'enviando' AND o.reservado_ate < now())
      AND NOT EXISTS (
          SELECT 1 FROM outbox p
          WHERE p.id_conversa = o.id_conversa AND p.destino = o.destino
            AND p.sequencia < o.sequencia AND p.status IN ('pendente', 'enviando'))
    ORDER BY o.criado_em
    LIMIT 1
    FOR UPDATE SKIP LOCKED)
RETURNING *;
```

Depois, fora da transação, `POST` ao broker ou ao simulador de canal, com timeout de requisição. Numa transação nova:
1. Sucesso: `status = 'enviado'`, `enviado_em = now()`. Se for `mensagem.recebida`, `conversa.atribuida` ou `conversa.devolvida`, trava a conversa e cria o `timeout_agente` (`referencia = id_evento`, `executar_em = enviado_em + TIMEOUT_AGENTE_S`) se a atribuição do evento ainda é a vigente e nenhum evento do agente já o cobriu (a resposta pode chegar antes deste passo).
2. Falha: `status = 'pendente'`, `tentativas += 1`, `proxima_tentativa = now() + atraso(tentativas)`, `ultimo_erro`.
3. Esgotou: `status = 'erro'` em transação própria; alerta. Destino `broker`: `transicionar(..., para="escalada", id_atribuicao=payload.id_atribuicao, motivo="falha_integracao")`; descartado ou rejeitado (já escalada) = nada a fazer, auditado. Destino `canal`: não escala. Linhas em `erro` voltam por `POST /outbox/{id}/reprocessar`.

```python
def atraso(tentativas):
    teto = min(BACKOFF_TETO_S, BACKOFF_BASE_S * 2 ** tentativas)
    return random.uniform(teto / 2, teto)   # gerador global, sem semente (na entrega)
```

Na entrega o jitter usa `random.uniform` do gerador global, sem semente; o relay ainda não lê `RELAY_SEMENTE`. A reprodução que vale aqui é em distribuição: com 8 tarefas, mesmo um `random.Random(RELAY_SEMENTE)` fixaria a sequência de sorteios, não qual item recebe cada um, porque a ordem em que as tarefas sorteiam não é determinística. O que o E6 depende do jitter (soma das 8 tentativas entre 61,5 s e 123 s) não muda com a semente.

Com os valores iniciais, as 8 tentativas levam de 61,5 s a 123 s. Como o prazo do agente só nasce no envio, para destino `broker` quem escala um evento que não saiu é o esgotamento, sem depender do jitter, e a mensagem que espera atrás dele na ordem não cobra o agente. Queda depois do envio e antes do resultado devolve a linha por `reservado_ate`; a reentrega é absorvida pela inbox do outro lado.

Com `OUTBOX_ATIVA = false` (ablação), `transicionar` grava, confirma e só então faz o `POST` direto, sem retentativa. No sucesso, o `timeout_agente` nasce como no passo 1; na falha não nasce prazo nem escala, e a perda chega ao juiz (E6, E7).

### 7.4 Agendador

```sql
SELECT id, id_conversa FROM agendamentos           -- sem travar
WHERE status = 'pendente' AND executar_em <= now()
ORDER BY executar_em LIMIT 50;
```

Para cada um, numa transação: `SELECT ... FROM conversas WHERE id = :c FOR UPDATE SKIP LOCKED` (ocupada = pula para o próximo ciclo); relê `agendamentos WHERE id = :a AND status = 'pendente' FOR UPDATE`; age; grava `status`, `motivo_fim`, `finalizado_em`.

`timeout_agente`:
- Nasce no ack do broker, na transação do relay que marca `enviado` (7.3, passo 1). Antes disso, o único caminho de escala é o esgotamento do relay.
- Renovado por `agente.processando` (7.7); cancelado (`resposta`) pelo evento do agente que o cobre (4.2).
- Ao vencer: atribuição mudada = `descartado`; senão `timeout` e escala (disjuntor: 7.9).
- Na subida do núcleo, `timeout_agente` já vencidos passam a `now() + TIMEOUT_AGENTE_S`.
- Com `TIMEOUT_ATIVO = false` (ablação), não é criado. A chave fica para o E4 e o E5, fora da entrega.

Na entrega, `timeout_agente` é o único tipo (arquitetura 19.1); SLA, inatividade e espera retida são Evolução.

Laços periódicos sem conversa (disjuntor, limpeza) usam `pg_try_advisory_xact_lock`, que solta no fim da transação e não fica preso a uma conexão do pool.

### 7.5 Broker

Sem banco e sem inbox; é o único produtor no Kafka.

Entrada (`POST /webhook`): valida (inválido: 422); publica com chave `id_conversa` e espera o ack; ack = 200; falha do Kafka = 503, e o relay tenta de novo.

Volta (consumidor de `agente.para-helpdesk`):
1. Esquema inválido: `helpdesk.erros`, confirma.
2. `POST /agente/eventos`. 2xx: confirma.
3. 4xx: `helpdesk.erros`, confirma.
4. 503 ou falha de rede (conexão recusada, timeout): `consumer.pause(tp)`, espera com backoff, `resume(tp)`. Sem limite, sempre chamando `getmany()` (senão passa de `max_poll_interval_ms` e o grupo rebalanceia).
5. 500 repetido: `RETENTATIVAS_MAX`, depois `helpdesk.erros` com alerta; o reprocessamento escala pela `id_atribuicao`. Enquanto o 500 se repete, a partição fica parada (até ~2 min com os valores iniciais) e os timeouts das conversas dela contam contra o agente; aceito porque 500 é defeito do núcleo. **Na entrega:** entre as tentativas a partição pausa como no passo 4; o 500 repetido vai a `helpdesk.erros` depois de `RETENTATIVAS_MAX` e o offset é confirmado, sem o reprocessamento que escala pela `id_atribuicao` (Evolução); a conversa escala pelo `timeout_agente` pendente, então nada some sem aviso.

Desde a fatia 1 o broker já faz a ida e a volta (passos 2 e 4 simplificados); o núcleo nunca publica direto no Kafka.

### 7.6 Agente mock

- Consome `helpdesk.para-agente`. Numa transação do banco `agente_mock`: inbox + resposta com `publicar_em = now() + LATENCIA_MS`. Confirma o offset. Um laço publica as respostas vencidas com produtor idempotente. Assim a latência simulada não serializa a partição.
- Devolve o `id_atribuicao` recebido; `causado_por` = evento de origem; ids por `id_derivado`.
- Escala se a mensagem pede humano ou tem palavra de irritação, com `fontes`; resolve (`conversa.resolvida`) depois de `MOCK_TROCAS` respostas (6, o modelo de carga da seção 14).
- Todo sorteio do mock usa `random.Random(MOCK_SEMENTE)`.
- Na entrega, modos `normal`, `duplicar` e `fora`; `lento` e `trabalhando` ficam com o E4 e o E4b.

| Modo (`POST /modo`) | Comportamento |
|---|---|
| `normal` | Responde com `LATENCIA_MS` |
| `lento` | Responde depois do timeout, sem heartbeat |
| `trabalhando` | Heartbeat a cada `TIMEOUT_AGENTE_S / 3`; responde depois do timeout, antes do teto |
| `duplicar` | Publica cada resposta duas vezes |
| `fora` | Para de consumir |

### 7.7 Prazo renovável (heartbeat)

Evolução na entrega (arquitetura 19.1).

```sql
UPDATE agendamentos
SET executar_em = now() + make_interval(secs => :timeout), renovacoes = renovacoes + 1
WHERE tipo = 'timeout_agente' AND status = 'pendente'
  AND referencia = :causado_por AND id_atribuicao = :id_atribuicao
  AND renovacoes < :renovacoes_max
RETURNING id;
```

Uma linha: audita `prazo_renovado`. Nenhuma: `renovacao_recusada` (atribuição vencida, teto ou prazo finalizado). Responde 200. `RENOVACOES_MAX = 0` desliga a renovação (E4b).

### 7.8 Inatividade

Evolução na entrega (arquitetura 19.1).

```python
async def prazos_de_inatividade(s, c, mensagem):    # chamado por transicionar
    if mensagem.autor_tipo == "sistema":
        return
    await cancelar(s, c.id, tipos=("inatividade_aviso", "inatividade_encerra"),
                   motivo_fim="nova_mensagem")
    if mensagem.autor_tipo in ("ia", "humano") and c.estado in ("com_ia", "com_humano"):
        await agendar(s, "inatividade_aviso", c, referencia=mensagem.id,
                      executar_em=agora() + prazo_aviso(c.canal))
```

- Aviso: se a conversa saiu de `com_ia`/`com_humano` ou o cliente escreveu depois da `referencia`, `descartado`. Senão, mensagem do sistema pelo canal e agenda `inatividade_encerra`.
- Encerramento: mesma checagem; `transicionar(..., para="resolvida", motivo="inatividade")`, com `conversa.encerrada` se estava com a IA.
- A checagem sob a trava da conversa evita corrida; a ordem de travas (7.1) evita deadlock.

### 7.9 Disjuntor

Versão simplificada (decisão 24). Evolução na entrega (arquitetura 19.1). Correções anotadas da rodada 3, para quando entrar: passo de retenção no distribuidor (8) que executa o `reter`, com índice único parcial `agendamentos (id_conversa) WHERE tipo = 'espera_retida' AND status = 'pendente'`, e sair de `na_fila` para atribuição cancela o `espera_retida` (`motivo_fim = atribuida`); `atribuicoes.sonda` gravado pelo distribuidor e copiado pelo relay para o `timeout_agente`, e `timeout` ou `falha_integracao` em `sondas` reabre.

```python
def avaliar(estado, desfechos, segundos_no_estado, sondas, cfg):
    if estado == "fechado":
        falhas = len(desfechos) - desfechos.count("resposta")      # timeout ou falha_integracao
        if len(desfechos) >= cfg.min_amostras and falhas / len(desfechos) >= cfg.taxa:
            return "aberto"
    elif estado == "aberto" and segundos_no_estado >= cfg.espera_s:
        return "meio_aberto"
    elif estado == "meio_aberto":
        if "timeout" in sondas:
            return "aberto"
        if sondas.count("resposta") >= cfg.sondas:
            return "fechado"
    return estado
```

- `desfechos`: os últimos `DISJUNTOR_MIN_AMOSTRAS` da IA, entre `motivo_fim` dos `timeout_agente` (`resposta` ou `timeout`) e esgotamentos do relay para ela (`falha_integracao`), que não geram timeout (7.4). Reavaliado sob `FOR UPDATE` na linha do disjuntor a cada desfecho: com 20 de amostra e 50%, abre na 10ª falha seguida.
- `sondas`: desfechos dos agendamentos com `sonda = true` desde `mudou_em`. Sonda cancelada devolve a vaga (`sondas_restantes + 1`).
- Um laço a cada `DISJUNTOR_AVALIACAO_S` cuida de aberto → meio-aberto.
- Distribuidor: fechado, IA candidata; meio-aberto, só se conseguir sonda (`UPDATE disjuntores SET sondas_restantes = sondas_restantes - 1 WHERE ... AND sondas_restantes > 0`), e o agendamento nasce com `sonda = true`; aberto, IA fora e vale `ao_abrir_disjuntor` da fila. `reter` (padrão): a conversa nova não vai a outro grupo; fica em `na_fila`, recebe uma mensagem de espera e um `espera_retida` para `agora + ESPERA_MAX_RETIDA_S`, que escala se ela ainda estiver em `na_fila`. `transbordar`: segue para o próximo grupo; sem outro grupo, retém do mesmo jeito.
- Conversas que já estavam com a IA seguem a regra normal de timeout.
- `DISJUNTOR_ATIVO = false` desliga (E8).

### 7.10 Interface

As telas releem o estado pela API a cada `INTERFACE_LEITURA_S` (`GET /painel/fila`, `GET /conversas/{id}`), filtrando por marca e filas do usuário no servidor. Sem canal ao vivo nesta entrega.

API REST do front, congelada nas primeiras 2 h do dia 1: o FastAPI gera o OpenAPI, publicado em `/docs`, com payloads de exemplo. Cobre conversas e mensagens (chat simulado e acompanhamento), painel do analista e fila de escalas (assumir, responder, encerrar e, se couber, devolver), configuração de filas (versões, validar, ativar, rollback) e contadores do supervisor (`GET /metricas`). Depois do congelamento, só campos opcionais novos.

## 8. Roteador e distribuidor

O atendimento junta os campos da conversa (`marca`, `canal`, `categoria`, `prioridade`, `idioma`, `sentimento`, `origem`) e do cliente (`segmento` → `segmento_cliente`).

```python
def rotear(atendimento: Atendimento, regras: VersaoRegras) -> DecisaoRoteamento:
    for fila in sorted(regras.filas, key=lambda f: f.ordem):
        if fila.ativa:
            casadas = condicoes_que_casam(fila.condicoes, atendimento)   # None se não casa
            if casadas is not None:
                return DecisaoRoteamento(fila=fila.id, regra=casadas, versao=regras.numero)
    return DecisaoRoteamento(fila=regras.fila_padrao.id, regra="fila_padrao", versao=regras.numero)
```

- Função pura; teste em tabela. Reproduzir uma decisão gravada é teste unitário.
- Cada roteamento lê a versão ativa (`versoes_regras WHERE ativa`, índice único).
- Validação antes de ativar: campos, operadores **e valores** conhecidos (`marca` em `marcas`, `canal`, `prioridade`); `ordem` sem repetição; fila padrão; ids de fila únicos; todo grupo de `atendentes` existe; `prioridade` inteira de 1 a 3; `ao_abrir_disjuntor` em `reter` ou `transbordar` (ausente = `reter`). Ao ativar, conversas em `na_fila` de fila removida voltam a `rotear` (Evolução na entrega; até lá, remover fila com conversas esperando as deixa sem atendimento).
- `atendentes` da fila: lista ordenada de grupos `{"tipo": "ia"|"equipe", "id": ...}`.

Distribuidor: laço a cada `DISTRIBUIDOR_INTERVALO_S` e logo depois de cada transição que libera capacidade.

A cada ciclo, sem travar, monta `:filas` e `:prio_fila`: as filas com algum grupo elegível (disjuntor e `ao_abrir_disjuntor` incluídos, quando entrarem) que tem atendente livre, e a prioridade de cada uma. Na entrega a IA não tem limite, então fila com a IA está sempre em `:filas`. Depois repete, uma transação por conversa:

```sql
SELECT c.id FROM conversas c
JOIN unnest(:filas::text[], :prio_fila::int[]) AS f(id_fila, prioridade) ON f.id_fila = c.id_fila
WHERE c.estado IN ('na_fila', 'escalada')
ORDER BY f.prioridade DESC,
         (c.origem = 'escalado') DESC,
         coalesce(c.prioridade, 1) DESC,
         c.criada_em
LIMIT 1
FOR UPDATE SKIP LOCKED;
```

Envelhecimento (decisão 10) é Evolução: quando entrar, soma `floor(extract(epoch FROM now() - c.na_fila_desde) / :envelhecimento_s)` à prioridade da conversa e desempata por `na_fila_desde`, gravado por `transicionar` ao entrar em `na_fila` ou `escalada` (rodada 3, N3: a idade da conversa punia quem passou tempo com a IA).

Monta os candidatos dos grupos da fila, chama `escolher` (pura) e `transicionar`, e confirma. `SEM_CAPACIDADE` (outra instância ocupou a vaga) tira a fila de `:filas` neste ciclo; sem linha, o ciclo acaba. Fila lotada não segura as outras, e com uma conversa por transação nenhuma instância trava dois atendentes ao mesmo tempo. O analista também puxa da fila de escalas com `SKIP LOCKED`.

```python
def escolher(candidatos: list[Candidato]) -> Escolha:   # na ordem de preferência da fila
    livres = [c for c in candidatos if c.disponivel and c.ativas < c.capacidade]
    if not livres:
        return Escolha(None, "sem_candidato")
    grupo = min(c.grupo for c in livres)
    a = min((c for c in livres if c.grupo == grupo),
            key=lambda c: (c.ativas / c.capacidade, str(c.id)))
    return Escolha(a.id, "preferencia_e_menor_ocupacao")
```

A migration semeia um atendente IA e as equipes de exemplo.

Registro de decisão: eventos `decisao_roteamento` (oito campos, versão, fila, regra) e `decisao_distribuicao` (fila, disjuntor, candidatos com grupo, status, carga e capacidade, escolhido, motivo), na transação da atribuição.

## 9. Reconciliador

Roda a cada `RECONCILIADOR_INTERVALO_S` sobre a janela recente (`RECONCILIADOR_JANELA_MIN`) e, no fim de cada execução do experimento, sobre tudo. Lê o banco do núcleo e grava `violacoes` no banco `reconciliador`. Complementa o juiz das pontas (seção 14).

**Na entrega:** um script SQL com I1 a I4, rodado no fim de cada execução do experimento, gravando o resultado no CSV da execução. O serviço periódico, o banco `reconciliador` e I5 a I7 são Evolução.

| Invariante | Consulta |
|---|---|
| I1 mensagem sem desfecho | mensagem de cliente com `seq` maior que a última coberta por evento enviado ao atendente, mais velha que `PRAZO_RESPOSTA_S`, sem prazo pendente no futuro. Conversa em `escalada` ou `na_fila` só humana conta à parte, como "esperando humano" |
| I2 outbox parada | `pendente` ou `enviando` mais velho que `OUTBOX_LIMITE_S` |
| I3 resposta duplicada | mais de uma mensagem de IA com o mesmo `(causado_por, sequencia)`, ou o mesmo conteúdo com ids diferentes para o mesmo `causado_por` |
| I4 resposta fora de dono | mensagem de IA com `id_atribuicao_declarada` diferente de `id_atribuicao` |
| I5 capacidade estourada | humano com `ativas` maior que a capacidade ou diferente da contagem de atribuições abertas |
| I6 conversa aberta duplicada | mais de uma não resolvida para o mesmo cliente e marca |
| I7 conversa esquecida | em `com_ia` ou `com_humano`, última mensagem (fora as do sistema) do atendente, sem agendamento de inatividade pendente |

```sql
-- I3
SELECT causado_por, sequencia FROM mensagens
WHERE autor_tipo = 'ia' AND causado_por IS NOT NULL AND criada_em > now() - make_interval(mins => :janela)
GROUP BY causado_por, sequencia HAVING count(*) > 1;

-- I4
SELECT id FROM mensagens
WHERE autor_tipo = 'ia' AND id_atribuicao_declarada IS DISTINCT FROM id_atribuicao
  AND criada_em > now() - make_interval(mins => :janela);

-- I6
SELECT id_cliente, marca FROM conversas
WHERE estado <> 'resolvida' GROUP BY id_cliente, marca HAVING count(*) > 1;
```

A ordem das mensagens é por `seq` (gravado sob a trava), não por `criada_em`, que é a hora de início da transação.

## 10. Configuração

| Variável | Valor (inicial) | Uso |
|---|---|---|
| `OUTBOX_ATIVA`, `INBOX_ATIVA`, `FENCING_ATIVO`, `TIMEOUT_ATIVO` | true | Chaves de ablação do experimento (seção 14) |
| `TIMEOUT_AGENTE_S` | 30 | Prazo do agente, contado a partir do ack do broker |
| `RENOVACOES_MAX` | 3 | Heartbeats aceitos por mensagem; espera máxima 30 × 4 = 120 s |
| `RETENTATIVAS_MAX` | 8 | Tentativas antes da fila de erros |
| `BACKOFF_BASE_S` / `BACKOFF_TETO_S` | 0,5 / 60 | Atraso das retentativas |
| `RELAY_INTERVALO_MS` | 100 | Pausa do relay quando a fila esvazia (entra no p95) |
| `RELAY_WORKERS` | 8 | Tarefas do relay (11) |
| `RELAY_SEMENTE` / `MOCK_SEMENTE` | fixa por execução | Jitter do relay e sorteios do mock; também no `.env.example`. A do relay reproduz o jitter em distribuição, não item a item (8 tarefas); na entrega o relay ainda sorteia sem ela (7.3) |
| `RELAY_RESERVA_S` | 30 | Prazo de `enviando` |
| `DISTRIBUIDOR_INTERVALO_S` | 1 | Laço do distribuidor |
| `ENVELHECIMENTO_S` | 600 (hipótese) | Espera na fila que sobe a prioridade da conversa em um degrau. Evolução (decisão 10) |
| `JANELA_REABERTURA_H` | 24 | Reabrir em vez de criar conversa |
| `INATIVIDADE_AVISO_MIN` / `INATIVIDADE_ENCERRA_MIN` | 10 / 20 | Chat e WhatsApp |
| `INATIVIDADE_EMAIL_AVISO_H` / `INATIVIDADE_EMAIL_ENCERRA_H` | 24 / 72 | E-mail |
| `DISJUNTOR_ATIVO` | true | Desligado na linha de base do E8 |
| `DISJUNTOR_MIN_AMOSTRAS` / `DISJUNTOR_TAXA` | 20 / 0,5 | Janela por contagem |
| `DISJUNTOR_ESPERA_S` / `DISJUNTOR_SONDAS` / `DISJUNTOR_AVALIACAO_S` | 30 / 5 / 5 | Meio-aberto |
| `ESPERA_MAX_RETIDA_S` | 300 | Espera máxima de conversa retida |
| `HISTORICO_N` / `PERFIL_JANELA_DIAS` | 20 / 30 | Contexto da IA |
| `PRAZO_RESPOSTA_S` / `OUTBOX_LIMITE_S` | 120 / 60 | Reconciliador (I1, I2) |
| `RECONCILIADOR_INTERVALO_S` / `RECONCILIADOR_JANELA_MIN` | 30 / 10 | Reconciliador |
| `INTERFACE_LEITURA_S` | 2 | Leitura periódica das telas |
| `CAPACIDADE_HUMANO` | 3 | Conversas abertas por analista. Sem inatividade na entrega, conversa à espera do cliente ocupa vaga até o analista encerrar (limitação) |
| `CAPACIDADE_IA` | 2000 | Mensagens aguardando resposta (custo). Evolução: na entrega a IA não tem limite |
| `LATENCIA_MS` | 800 | Latência simulada do mock |
| `MOCK_TROCAS` / `K6_SEMENTE` | 6 / fixa por execução | Fim da conversa pelo mock; semente do k6 (seção 14) |
| `ANALISTAS_SIMULADOS` / `ANALISTA_RESPOSTA_S` | 10 / 30 (hipótese) | `carga/analistas.py`, só com o E8 (fora da entrega) |

## 11. Observabilidade

Log em JSON com `servico`, `id_conversa`, `id_evento`, `id_atribuicao`, `causado_por`, `consumidor`, `resultado`. Na entrega, as métricas abaixo são contadores em `GET /metricas`; Prometheus e Grafana são Evolução.

| Métrica | Tipo |
|---|---|
| `mensagens_recebidas_total{canal,marca}`, `reenvios_descartados_total{canal}` | contador |
| `latencia_interna_segundos` (entrada da mensagem até o ack do broker; a única latência interna) | histograma |
| `latencia_ponta_a_ponta_segundos` | histograma |
| `outbox_pendentes`, `outbox_idade_max_segundos`, `outbox_erro_total{destino}` | gauge, contador |
| `eventos_duplicados_ignorados_total{consumidor}`, `eventos_descartados_fencing_total` | contador |
| `escalas_total{motivo}`, `fila_escalas_tamanho` | contador, gauge |
| `prazo_renovado_total`, `renovacao_recusada_total{motivo}`, `encerradas_inatividade_total{canal}` | contador |
| `disjuntor_estado{atendente}`, `conversas_retidas` | gauge |
| `reconciliador_violacoes_total{invariante}` | contador |

Atraso do consumidor: Redpanda. No E9, espera por trava e conexões: `pg_stat_activity` durante a carga.

**Dimensionamento do relay (Lei de Little, concorrência = chegada × tempo de serviço).** Valores iniciais, a conferir no E1.

| Salto | Chegada no E1 | Chegada no E2 | Serviço (inicial) | Concorrência necessária | Configuração |
|---|---|---|---|---|---|
| Relay da outbox | ~108 itens/s (~58 para o broker: 50 `mensagem.recebida` + 8,3 `conversa.atribuida`; ~50 respostas para o canal) | ~216 | ~15 ms por item (duas transações e o `POST`) | ~1,6 (E1) e ~3,2 (E2) | `RELAY_WORKERS = 8`; drena antes de dormir |
| Pool de conexões do núcleo | — | — | — | ≥ `RELAY_WORKERS` + API + agendador + distribuidor | pool do SQLAlchemy |

O consumidor de volta do broker (uma tarefa por partição) fica sem dimensionamento medido na entrega (rodada 3, item 9).

## 12. Entrega de 23/11: o que fazer e quando está pronto

Escopo, Evolução, plano e pisos: arquitetura 19.1 a 19.3. A ordem de fatias (decisão 32) fica só como ordem de dependência.

| Marco | Entrega | Pronto quando |
|---|---|---|
| Dia 1, primeiras 2 h | OpenAPI gerado pelo FastAPI e publicado em `/docs`, com payloads de exemplo de todas as rotas do front (7.10) | O front monta as telas com os exemplos; a partir daqui as rotas só ganham campos opcionais |
| Dia 1, 12h | Migration 0002 única; `transicionar` com fencing; outbox e relay; inbox; broker (11.4 da arquitetura; 500 repetido para `helpdesk.erros` sem reprocessamento, 7.5); mock com `normal`, `duplicar` e `fora` | Mensagem vai e volta pelo broker. O broker existe desde a fatia 1: `POST /webhook` publica com ack e o consumidor de `agente.para-helpdesk` faz `POST /agente/eventos` e confirma o offset depois do 2xx. O núcleo nunca publica direto no Kafka |
| Dia 1, fim | Agendador do `timeout_agente`; roteador, versões e validação; distribuidor; escala com resumo e mensagem de transferência; auditoria e registro de decisão; identidades mínimas e memória (perfil e últimas N); devolução se couber; testes de 13.1 nesse escopo | Escala por timeout chega ao painel; uma página por componente no `diario.md` (ponto de controle 1). **Piso:** se não chegar, devolução e memória saem |
| Dia 2, 13h | Chaves `OUTBOX_ATIVA` e `INBOX_ATIVA`; juiz; `carga/agenda.py`; script do reconciliador (I1 a I4); E1, E3b e E6 | Tabela da seção 14 com uma repetição; página por componente no diário (ponto de controle 2). **Piso:** só o E6, nas duas posições |
| Dia 2, fim | README com subida em um comando e limitações (arquitetura 17 e 19.1); `carga/tabelas.py`; gravação de reserva | Outra pessoa sobe tudo com um comando |

## 13. Testes obrigatórios

Na entrega (arquitetura 19.3): 13.1 sem as chaves de fencing e timeout; de 13.2, os de timeout, broker fora, deadlock, reinício e as violações plantadas de I1 a I4; de 13.3, roteador, versões sem o re-roteamento de fila removida, `escolher` sem o caso de capacidade da IA, distribuidor, isolamento por marca e escala. Devolução com a IA no limite, I5 a I7, disjuntor, heartbeat, inatividade, reabertura e fusão ficam com os mecanismos, em Evolução.

### 13.1 Fatia 2

- Duas tarefas chamam `transicionar` na mesma conversa: uma aplica, a outra vê o estado novo.
- Transição fora da tabela devolve `REJEITADO` e a auditoria fica gravada.
- Evento com `id_atribuicao` antigo é descartado e auditado.
- Mesmo evento duas vezes na API do agente: um efeito, duas respostas 200.
- Mesmo `id_externo` duas vezes no `POST /mensagens`: uma mensagem, pela inbox da entrada. Com `INBOX_ATIVA = false`: duas mensagens com o mesmo `id_externo` gravado.
- Relay morto entre a reserva e o resultado: o evento sai quando a reserva vence.
- Uma linha que sempre falha não impede o envio das outras conversas.
- Falha no destino `canal` não segura a mensagem seguinte para o `broker` da mesma conversa.
- Kafka fora: o broker responde 503 e o relay tenta de novo.
- Duas mensagens simultâneas de cliente novo criam uma conversa só.
- Duas atribuições simultâneas ao mesmo analista no limite: uma passa, a outra devolve `SEM_CAPACIDADE`.
- `UPDATE` em `eventos` falha.
- Cada chave de ablação desligada produz o comportamento de 7.2, 7.3, 7.1 e 7.4.

### 13.2 Fatia 3

- `timeout_agente` só existe depois do ack do broker; evento parado na outbox, ou atrás de outro em retentativa, não escala por timeout.
- Resposta que chega antes do passo 1 do relay: o timeout não nasce.
- Resposta antes do prazo cancela o timeout; resposta à segunda mensagem cancela também o da primeira.
- `agente.processando` empurra o prazo; depois de `RENOVACOES_MAX`, dispara; com atribuição vencida, não renova.
- Broker fora por 3 min, começando sem mensagem em voo: nenhum laço; cada conversa escalada uma vez, pelo esgotamento do relay (`falha_integracao`), nenhuma por timeout; linhas em `erro` reprocessáveis.
- Broker fora com mensagens em voo (respostas no Kafka quando o broker cai): essas conversas escalam por `timeout`, com o motivo gravado, e a transferência chega ao cliente.
- Devolução com a IA no limite: `SEM_CAPACIDADE`; a conversa segue `com_humano` com a mesma atribuição, `ativas` do analista e agendamentos intactos.
- Resposta e vencimento do prazo no mesmo instante, 100 repetições: nenhum erro de deadlock.
- Inatividade: aviso, encerramento, capacidade liberada; mensagem do cliente no instante do disparo cancela; `escalada` não é encerrada.
- Reinício do núcleo com prazos vencidos: reagendados, sem escala em massa.
- Violação plantada de cada invariante (I1 a I7) é encontrada.

### 13.3 Fatia 5

- Roteador em tabela; decisão gravada refeita dá a mesma fila.
- Versão com valor fora do domínio (`"JIM"`) não ativa; rollback; conversa guarda a versão; fila removida re-roteia.
- Consulta de uma marca não devolve dados de outra.
- `escolher` em tabela: preferência, ocupação, empate, sem candidato; IA com 800 de 2000 vence analista com 1 de 3 quando vem primeiro.
- Distribuidor: conversa sem capacidade fica em `na_fila` e é atribuída quando libera; duas instâncias não pegam a mesma; fila lotada com a conversa mais antiga não impede a atribuição em outra fila com atendente livre; prioridade 3 sai antes de 2 e 1.
- Disjuntor aberto: fila `reter` mantém a conversa nova em `na_fila` com mensagem de espera; fila `transbordar` a entrega à equipe.
- Escala passa por `rotear` com `origem = escalado`.
- `avaliar` em tabela; abre na 10ª falha; sonda cancelada devolve a vaga; três instâncias mudam o estado uma vez só.

### 13.4 Fatia 7

- Perfil só com os campos previstos.
- Mesmo cliente em dois canais cai no mesmo histórico só com evidência forte.
- Reabertura re-roteia e limpa `motivo_encerramento` e `resolvida_em`.

## 14. Experimento

Mede a robustez da plataforma, não a qualidade das respostas do agente. Na entrega rodam E1, E3b e E6 (arquitetura 19.2); os outros cenários ficam com desenho e previsão no fim desta seção.

**Ablação (decisão 12).** Uma versão só, a robusta. Na entrega, as chaves `OUTBOX_ATIVA` e `INBOX_ATIVA`; `FENCING_ATIVO` e `TIMEOUT_ATIVO` ficam para o E4 e o E5. Cada cenário roda com a proteção que ele testa ligada e desligada; o resto fica igual (mesmo broker, mesmo mock, mesmas tabelas). A tag `ingenua` é só o marco da fatia 1.

**Na entrega, o k6 foi substituído por `carga/gerador.py`** (asyncio + httpx): reproduz a mesma agenda de `carga/agenda.py`, cada envio no seu instante, sem esperar os anteriores, com um reenvio em erro. Evita uma ferramenta a mais e roda no mesmo `.venv`. Onde esta seção diz k6, leia o gerador. Orquestração: `carga/rodar.py` (um cenário e posição), `carga/lote.py` (as 6 execuções), `carga/juiz.py`, `carga/falhas.py`, `carga/tabelas.py`.

**Juiz nas pontas** (arquitetura 17):
- O k6 grava `(id_externo, conversa, enviado_em, status HTTP)`; o simulador de canal (database `canais`) grava cada resposta entregue e cada mensagem de transferência, com `id_conversa` e `causado_por`.
- Correspondência resposta → `id_externo`, a mesma nas duas posições de `OUTBOX_ATIVA`: a resposta entregue tem `causado_por` = evento enviado ao agente; a linha de `mensagens` com `autor_tipo = 'ia'` e esse `causado_por` dá a conversa e o `seq`; a mensagem do cliente da mesma conversa com o maior `seq` abaixo dele dá o `id_externo`. Com `OUTBOX_ATIVA = false` não há outro caminho: o id do evento só existiria na linha da outbox. A transferência cobre as mensagens do cliente da conversa dela ainda sem resposta; as enviadas depois são "esperando humano".
- Limitação do juiz: a contagem vem das pontas, mas a correspondência vem do banco do núcleo; a regra supõe uma resposta por mensagem antes da mensagem seguinte da conversa, o que vale na carga da entrega (84 s entre mensagens, mock com 0,8 s). Resposta atrasada além disso seria atribuída à mensagem seguinte.
- Escala só conta pela mensagem de transferência (6), vista na ponta, não pelo banco.
- Perdida = enviada com 2xx, sem resposta entregue nem transferência. Duplicada = mais de uma resposta entregue para a mesma mensagem e sequência. Esperando humano = enviada a conversa já escalada; nem perdida nem respondida. Recusada = sem 2xx depois do reenvio; fica fora de "perdidas".
- Cobertura por `seq` (mensagem anterior coberta pela resposta a uma posterior) fica para quando entrar outro cenário (rodada 3, item 6b): no E1, no E3b e no E6 o mock responde cada mensagem.
- O script do reconciliador (I1 a I4, seção 9) explica a causa.

**Recuperação** = do retorno da dependência até I1 e I2 zerarem e `outbox_pendentes` voltar ao nível de antes da falha.

**Carga.** "100 msg/s" = total das duas direções. Modelo aberto, por mensagem: `carga/agenda.py`, com `K6_SEMENTE`, gera a agenda `(instante, id_conversa, k, id_externo, marca, canal, texto)`, e o k6 a reproduz com `constant-arrival-rate` de mensagens (50/s do cliente no E1). VUs ≈ chegada × latência da requisição, ordem de dezenas, em vez de um VU dormindo por conversa. Valores sem fonte são hipótese.

| Parâmetro | Valor | Origem |
|---|---|---|
| Chegada de conversas | 8,3/s na agenda (25 a cada 3 s) | arq 3 |
| Mensagens do cliente | 6 por conversa | arq 3 (premissa) |
| Intervalo | 84 s fixo (5 intervalos em 420 s), sem esperar a resposta | derivado dos 420 s da arq 3 |
| Fim | o mock manda `conversa.resolvida` depois da 6ª resposta (`MOCK_TROCAS`) | 7.6 |
| Marca | 80% InfinitePay (PT), 20% JIM (EN) | hipótese |
| Canal | só chat, para isolar a integração | — |
| Texto | sem pedido de humano nem palavra de irritação | evita escala por regra |
| Reenvio | uma vez, com o mesmo `id_externo`, em erro ou timeout da requisição | arq 17 |

Conta: 8,3 × 6 = 50 msg/s do cliente, mais 50 do mock (1:1) = 100. Cada conversa fica ~420 s, então L ≈ 8,3 × 420 ≈ 3.500 conversas no sistema, o da arq 3. O regime só chega depois de 420 s: 7 min de aquecimento fora da medição e 5 min medidos, ~12 min por execução. Se a máquina não sustentar, a carga cai para 50 msg/s e isso vai para as limitações.

**Registros.** CSV bruto por execução em `resultados/<cenario>/<chave>/<repeticao>.csv` (registros do juiz e métricas); `carga/tabelas.py` gera as tabelas do README a partir deles. Sementes em 10: `K6_SEMENTE`, `MOCK_SEMENTE`, `RELAY_SEMENTE` (esta reproduz o jitter só em distribuição, e na entrega o relay ainda não a lê; 7.3).

**Repetição.** Uma por cenário e posição: 6 execuções, ~1,2 h de máquina, em lote por script (arquitetura 19.2). Segunda e terceira só se sobrar tempo. Sem elas não há variância: a leitura fica em zero × não zero e ordem de grandeza (limitação).

**Na entrega**, com previsão escrita antes de rodar:

| Cenário | Como provocar | Chave | Previsto desligada | Previsto ligada |
|---|---|---|---|---|
| E1 Base | 100 msg/s, 5 min medidos | `OUTBOX_ATIVA` e `INBOX_ATIVA` juntas | Zero perda e duplicata; p95 menor (sem o laço do relay nem as transações de reserva) | Zero; p95 interna < 500 ms. A diferença de p95 é o custo da proteção |
| E3b Reenvio do canal | 10% das mensagens (inicial), sorteadas com `K6_SEMENTE`, reenviadas 2 s depois com o mesmo `id_externo`; os reenvios entram na agenda (`carga/agenda.py`) e o k6 os envia | `INBOX_ATIVA` | Duplicatas: duas mensagens com o mesmo `id_externo`, duas respostas ligadas a ele | Zero |
| E6 Broker fora | `stop broker` no minuto 8 (1 min dentro da janela medida), `start` 60 s depois, por `carga/falhas.py` | `OUTBOX_ATIVA` | Perdas (POST sem retentativa; sem envio não nasce prazo, então não escala). Escaladas por timeout das respostas que estavam no caminho de volta quando o broker caiu (ordem de 40 a 60, hipótese: ~50 msg/s × ~1 s em voo) | Zero perda, com atraso. Escaladas pelo esgotamento do relay (poucas ou nenhuma: 60 s fica abaixo dos 61,5 s mínimos das 8 tentativas) e pelo mesmo timeout das respostas no caminho de volta (ordem de 40 a 60, hipótese). Recuperação prevista: até ~70 s depois da volta, dominada pelo teto do backoff (60 s); a drenagem dos ~3.500 eventos acumulados (~58/s × 60 s) leva segundos com 8 tarefas (hipótese) |

| Cenário | Chave | Enviadas | Recusadas | Perdidas | Duplicadas | Escaladas | Esperando humano | Espera p95 até a 1ª resposta | p95 interna | Recuperação |
|---|---|---|---|---|---|---|---|---|---|---|
| E1 | desligada | | | | | | | | | |
| E1 | ligada | | | | | | | | | |
| E3b | desligada | | | | | | | | | |
| E3b | ligada | | | | | | | | | |
| E6 | desligada | | | | | | | | | |
| E6 | ligada | | | | | | | | | |

**Fora da entrega** (arquitetura 19.1), com a previsão corrigida na rodada 3 para quando entrarem:

| Cenário | Como provocar | Chave | Previsto desligada | Previsto ligada |
|---|---|---|---|---|
| E2 Pico | Rampa até 200 msg/s por 3 min | todas | Zero; p95 menor | Zero; p95 maior, abaixo de 500 ms (custo da proteção) |
| E3 Duplicatas do agente | Mock `duplicar` | `INBOX_ATIVA` | Zero: o `UNIQUE (id_evento)` da 0001 e o id determinístico já barram | Zero |
| E7 Núcleo morto | 10 mortes por execução, uma a cada 60 s (`SIGKILL` e `start`) | `OUTBOX_ATIVA` | Perdas: a janela entre commit e `POST` é de milissegundos, então ≈ eventos em voo por morte × 10, ordem de unidades a dezenas (hipótese). Recusadas: o núcleo fica fora mais que o reenvio único | Zero perda; recusadas como na desligada |
| E4 Agente lento | Mock `lento`, três células | `TIMEOUT_ATIVO`, `FENCING_ATIVO` | Timeout ligado e fencing desligado: respostas fora de dono gravadas (I4). Timeout desligado: sem troca de dono, o fencing não se aplica; mede a espera | Timeout e fencing ligados: zero I4 |
| E4b Agente trabalhando | Mock `trabalhando` | `RENOVACOES_MAX` 0 × 3 | Escalas à toa | Zero escalas à toa até o teto |
| E5 Agente fora | `stop agente_mock` por 60 s | `TIMEOUT_ATIVO` | Sem escala; espera até o agente voltar (pode responder mais rápido na volta) | Escaladas por timeout |
| E8 Agente fora longo | Queda de 2 min (10 min só como bônus); `carga/analistas.py`; fila AI first com `reter` e com `transbordar` | `DISJUNTOR_ATIVO` | ~3.500 escalas das conversas já com a IA, que o disjuntor não evita | `reter`: carga humana ~20% menor; `transbordar`: ~0%, com espera p95 menor (ordem de grandeza, rodada 2) |
| E9 Escalabilidade | `--scale nucleo=N --scale broker=N`, N = 1 e 3; degraus de 50 msg/s até p95 > 500 ms | — | — | Zero perda e duplicata nas duas; primeiro gargalo identificado |

No E8, carga humana total = conversas distintas que entram em `escalada` ou em atribuição humana entre o início da queda e 10 min depois da volta; o pico do estoque vai em coluna à parte. O analista simulado assume a primeira da fila dele, responde em `ANALISTA_RESPOSTA_S` (30, hipótese), encerra depois de responder à 6ª mensagem do cliente e não devolve.

## 15. Em aberto

| Ponto | Proposta atual |
|---|---|
| Cliente Kafka | aiokafka |
| Partições | 12 |
| Autenticação do painel | Usuário fixo por perfil |
| Triagem | Regras na fatia 5; classificador em discussão (arquitetura, seção 21) |
| Código do contrato (versão `^1\.\d+$`, `agente.processando`, consumidor tolerante) | No backend, dia 1 (4.1) |
| Limiares do disjuntor | Valores iniciais; calibrar no E8 (Evolução) |
| Marca como valor fixo no contrato | Terceira marca exige deploy; declarado nas limitações |
