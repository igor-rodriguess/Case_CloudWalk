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
│   ├── dominio/           # estados, transicionar, roteador, distribuidor, triagem
│   ├── infra/             # banco, modelos, relay da outbox, agendador
│   └── main.py
├── broker/                # webhook -> Kafka e Kafka -> núcleo
├── agente_mock/
├── reconciliador/         # roda contra qualquer versão (ingênua ou robusta)
├── migrations/            # Alembic
├── carga/                 # scripts k6 e injeção de falhas
├── testes/
└── docs/
```

`contrato/` é instalado no núcleo, no broker e no mock. Uma fonte só para o envelope evita que os três divirjam.

## 2. Serviços

| Serviço | Porta | Papel |
|---|---|---|
| `postgres` | 5433 no host, 5432 na rede do compose | Banco do núcleo (database `helpdesk`) e do mock (database `agente_mock`) |
| `redpanda` | 19092 no host, 9092 na rede do compose | Kafka |
| `topicos` | — | Cria os tópicos e termina |
| `migracoes` | — | Roda `alembic upgrade head` e termina |
| `nucleo` | 8000 | API e workers (relay da outbox, agendador) |
| `broker` | 8100 | `POST /webhook` e consumidor de `agente.para-helpdesk` |
| `agente_mock` | 8200 | Consumidor de `helpdesk.para-agente`; `GET /saude` e `POST /modo` para o experimento |
| `reconciliador` | — | Job periódico; também roda sob demanda no fim de cada execução do experimento |

O mock tem banco próprio para não ler nem escrever nas tabelas do núcleo, como o agente real.

As portas do host fogem de 5432 e 9092 para não colidir com outros projetos na mesma máquina.

Bibliotecas: FastAPI, SQLAlchemy 2.0, psycopg 3 (um driver só, síncrono para o Alembic e assíncrono para a API), Alembic, Pydantic v2, aiokafka, httpx, pytest. Fixar as versões das imagens no compose.

## 3. Kafka

| Tópico | Chave | Partições (inicial) | Quem produz | Quem consome |
|---|---|---|---|---|
| `helpdesk.para-agente` | `id_conversa` | 12 | broker | agente mock |
| `agente.para-helpdesk` | `id_conversa` | 12 | agente mock | broker |
| `helpdesk.erros` | `id_conversa` | 3 | núcleo, broker | operação (reprocessamento) |

- Produtor: `acks=all`, `enable_idempotence=True`.
- Consumidor: `enable_auto_commit=False`. Commit manual depois do efeito.
- 12 partições permitem até 12 consumidores em paralelo, folga ampla para 100 msg/s.

## 4. Contrato

### 4.1 Envelope

| Campo | Tipo | Regra |
|---|---|---|
| `versao` | string | `"1.0"`. Mudança que quebra compatibilidade sobe a versão principal |
| `id_evento` | UUID | v4 para evento original; v5 para evento derivado (4.3) |
| `tipo` | string | Um dos tipos de 4.2 |
| `id_conversa` | UUID | Chave de partição |
| `id_atribuicao` | UUID ou nulo | Atribuição a que o evento se refere. Obrigatório nos eventos do agente |
| `causado_por` | UUID ou nulo | `id_evento` que originou este. Obrigatório nos eventos do agente |
| `marca` | string | `infinitepay` ou `jim` |
| `timestamp` | ISO 8601 com fuso | Hora de criação do evento |
| `dados` | objeto | Conteúdo por tipo |

Validar com Pydantic em toda entrada. Evento inválido vai para `helpdesk.erros` com o motivo.

### 4.2 Tipos de evento

| Tipo | Direção | `dados` |
|---|---|---|
| `conversa.atribuida` | plataforma → agente | `cliente` (id, nome, segmento), `fila`, `historico` (últimas N mensagens), `resumo_anterior`, `persona` |
| `mensagem.recebida` | plataforma → agente | `id_mensagem`, `conteudo`, `canal` |
| `conversa.devolvida` | plataforma → agente | `motivo`, `nota_do_analista` |
| `conversa.encerrada` | plataforma → agente | `motivo` |
| `mensagem.enviada` | agente → plataforma | `conteudo` |
| `acao.executada` | agente → plataforma | `acao`, `parametros`, `resultado` |
| `conversa.escalada` | agente → plataforma | `motivo`, `resumo`, `prioridade_sugerida` |
| `conversa.resolvida` | agente → plataforma | `resumo` |

Regra da versão 1.0: cada `mensagem.recebida` gera no máximo uma `mensagem.enviada`. O reconciliador depende disso (seção 9).

Exportar o JSON Schema de cada tipo a partir dos modelos Pydantic para `contrato/schemas/`.

### 4.3 Id determinístico

```python
NAMESPACE_HELPDESK = uuid.uuid5(uuid.NAMESPACE_URL, "helpdesk-ai-first")

def id_derivado(causado_por: UUID, tipo: str, sequencia: int = 0) -> UUID:
    return uuid.uuid5(NAMESPACE_HELPDESK, f"{causado_por}:{tipo}:{sequencia}")
```

O mock usa essa função para todo evento que gera. Processar a mesma entrada duas vezes produz o mesmo id, e a inbox do núcleo ignora o segundo.

## 5. Banco de dados

### 5.1 O que entra em cada fatia

| Fatia | Tabelas |
|---|---|
| 1 | `clientes`, `conversas`, `mensagens` (já com as colunas de atribuição e causalidade, nulas) |
| 2 | `atendentes`, `atribuicoes`, `transicoes_permitidas`, `eventos`, `eventos_processados`, `outbox`; índice único de conversa aberta |
| 3 | `agendamentos`, `violacoes` |
| 4 | `marcas`, `equipes`, `versoes_regras`, `escalas` |
| 6 | `identidades` |
| 8 | `personas` (D1) |

O índice único de conversa aberta entra só na fatia 2 para a versão ingênua continuar ingênua.

### 5.2 Tabelas centrais

```sql
CREATE TABLE clientes (
    id            uuid PRIMARY KEY,
    marca         text NOT NULL,
    nome          text NOT NULL,          -- sintético
    segmento      text,
    criado_em     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE conversas (
    id                   uuid PRIMARY KEY,
    id_cliente           uuid NOT NULL REFERENCES clientes(id),
    marca                text NOT NULL,
    canal                text NOT NULL,
    estado               text NOT NULL,
    categoria            text,
    prioridade           text,
    sentimento           text,
    id_fila              uuid,
    id_atendente         uuid,
    id_atribuicao_atual  uuid,
    versao_regras        int,
    versao               int    NOT NULL DEFAULT 0,  -- sobe a cada transição
    seq_outbox           bigint NOT NULL DEFAULT 0,  -- ordem dos eventos de saída
    criada_em            timestamptz NOT NULL DEFAULT now(),
    atualizada_em        timestamptz NOT NULL DEFAULT now(),
    resolvida_em         timestamptz
);

-- fatia 2
CREATE UNIQUE INDEX conversa_aberta_unica
    ON conversas (id_cliente, marca) WHERE estado <> 'resolvida';

CREATE TABLE mensagens (
    id             uuid PRIMARY KEY,
    id_conversa    uuid NOT NULL REFERENCES conversas(id),
    autor_tipo     text NOT NULL CHECK (autor_tipo IN ('cliente', 'ia', 'humano', 'sistema')),
    id_autor       uuid,
    conteudo       text NOT NULL,
    canal          text NOT NULL,
    id_evento      uuid UNIQUE,     -- evento que trouxe a mensagem, quando houver
    causado_por    uuid,
    id_atribuicao  uuid,            -- atribuição vigente quando a mensagem foi gravada
    criada_em      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON mensagens (id_conversa, criada_em);

CREATE TABLE atendentes (
    id           uuid PRIMARY KEY,
    tipo         text NOT NULL CHECK (tipo IN ('ia', 'humano')),
    nome         text NOT NULL,
    marca        text NOT NULL,
    id_equipe    uuid,
    habilidades  text[] NOT NULL DEFAULT '{}',
    capacidade   int  NOT NULL,
    status       text NOT NULL DEFAULT 'disponivel'
);

CREATE TABLE atribuicoes (
    id            uuid PRIMARY KEY,
    id_conversa   uuid NOT NULL REFERENCES conversas(id),
    id_fila       uuid,
    id_atendente  uuid NOT NULL REFERENCES atendentes(id),
    inicio        timestamptz NOT NULL DEFAULT now(),
    fim           timestamptz,
    motivo_fim    text
);

CREATE TABLE transicoes_permitidas (
    de          text NOT NULL,
    para        text NOT NULL,
    ator_tipo   text NOT NULL,
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

CREATE TABLE eventos_processados (     -- inbox
    consumidor     text NOT NULL,
    id_evento      uuid NOT NULL,
    processado_em  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (consumidor, id_evento)
);

CREATE TABLE outbox (
    id                 bigserial PRIMARY KEY,
    id_evento          uuid NOT NULL UNIQUE,
    id_conversa        uuid,
    sequencia          bigint,
    destino            text NOT NULL,   -- 'broker' ou 'canal'
    payload            jsonb NOT NULL,
    status             text NOT NULL DEFAULT 'pendente'
                       CHECK (status IN ('pendente', 'enviado', 'erro')),
    tentativas         int  NOT NULL DEFAULT 0,
    proxima_tentativa  timestamptz NOT NULL DEFAULT now(),
    ultimo_erro        text,
    criado_em          timestamptz NOT NULL DEFAULT now(),
    enviado_em         timestamptz
);
CREATE INDEX ON outbox (status, proxima_tentativa);
CREATE INDEX ON outbox (id_conversa, sequencia);

CREATE TABLE agendamentos (
    id             bigserial PRIMARY KEY,
    tipo           text NOT NULL,       -- 'timeout_agente', 'sla'
    id_conversa    uuid NOT NULL,
    id_atribuicao  uuid,
    referencia     uuid,                -- ex.: id_evento da mensagem que aguarda resposta
    executar_em    timestamptz NOT NULL,
    status         text NOT NULL DEFAULT 'pendente'
                   CHECK (status IN ('pendente', 'executado', 'cancelado')),
    criado_em      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON agendamentos (status, executar_em);

CREATE TABLE versoes_regras (
    numero       serial PRIMARY KEY,
    filas        jsonb NOT NULL,
    ativa        boolean NOT NULL DEFAULT false,
    criada_por   text NOT NULL,
    criada_em    timestamptz NOT NULL DEFAULT now(),
    ativada_em   timestamptz
);
CREATE UNIQUE INDEX uma_versao_ativa ON versoes_regras (ativa) WHERE ativa;

CREATE TABLE violacoes (
    id           bigserial PRIMARY KEY,
    invariante   text NOT NULL,
    referencia   text NOT NULL,
    detectada_em timestamptz NOT NULL DEFAULT now()
);
```

## 6. Máquina de estados

Estados: `nova`, `na_fila`, `com_ia`, `escalada`, `com_humano`, `resolvida`.

| De | Para | Ator | Disparo |
|---|---|---|---|
| `nova` | `na_fila` | sistema | triagem e roteamento |
| `na_fila` | `com_ia` | sistema | distribuidor escolheu a IA |
| `na_fila` | `com_humano` | sistema, humano | fila só humana ou analista puxou |
| `com_ia` | `escalada` | ia | `conversa.escalada` |
| `com_ia` | `escalada` | sistema | `timeout_agente` ou `falha_integracao` |
| `com_ia` | `escalada` | cliente | pediu humano |
| `escalada` | `com_humano` | humano | analista assumiu |
| `com_humano` | `com_ia` | humano | analista devolveu |
| `com_ia` | `resolvida` | ia | `conversa.resolvida` |
| `com_humano` | `resolvida` | humano | analista encerrou |
| `resolvida` | `na_fila` | cliente | voltou dentro da janela de reabertura |

Essas linhas viram a carga inicial de `transicoes_permitidas` numa migration.

Atribuição: entrar em `com_ia` ou `com_humano` cria uma atribuição nova e atualiza `id_atribuicao_atual`. Sair desses estados encerra a atribuição (`fim`, `motivo_fim`) e zera `id_atribuicao_atual`.

## 7. Algoritmos

### 7.1 transicionar

Único caminho que escreve na conversa. Também é usado para gravar mensagens da IA sem mudar o estado (`para=None`), porque elas precisam do fencing.

`transicionar` não faz commit. Quem chama abre a transação, e a inbox entra nela.

```python
async def transicionar(s, id_conversa, para, ator, id_atribuicao=None,
                       id_atendente=None, mensagem=None, saidas=(), motivo=None):
    c = await s.get(Conversa, id_conversa, with_for_update=True)

    # fencing
    if id_atribuicao is not None and id_atribuicao != c.id_atribuicao_atual:
        await auditar(s, c, "evento_descartado", ator, motivo="atribuicao_vencida")
        return Resultado.DESCARTADO

    if para is not None:
        if not await permitida(s, c.estado, para, ator.tipo):
            await auditar(s, c, "transicao_invalida", ator, de=c.estado, para=para)
            raise TransicaoInvalida(c.estado, para)

        if c.id_atribuicao_atual is not None:
            await encerrar_atribuicao(s, c.id_atribuicao_atual, motivo)
            c.id_atribuicao_atual = None
            c.id_atendente = None

        if para in ("com_ia", "com_humano"):
            a = await s.get(Atendente, id_atendente, with_for_update=True)
            if await conversas_ativas(s, a.id) >= a.capacidade:
                raise SemCapacidade(a.id)
            nova = await criar_atribuicao(s, c, a)
            c.id_atribuicao_atual = nova.id
            c.id_atendente = a.id

        c.estado = para
        c.versao += 1

    if mensagem is not None:
        mensagem.id_atribuicao = c.id_atribuicao_atual
        s.add(mensagem)

    for evento in saidas:
        c.seq_outbox += 1
        s.add(Outbox(id_evento=evento.id_evento, id_conversa=c.id,
                     sequencia=c.seq_outbox, destino=evento.destino,
                     payload=evento.model_dump(mode="json")))

    await auditar(s, c, "transicao" if para else "mensagem", ator, para=para)
    return Resultado.APLICADO
```

Ordem das travas: sempre conversa primeiro, atendente depois. Ordem fixa evita deadlock.

### 7.2 Consumidor com inbox

Vale para a API do agente no núcleo, para o mock e para a saída por canal.

```python
async def tratar(consumidor, envelope, efeito):
    async with sessao.begin() as s:
        novo = await s.scalar(text("""
            INSERT INTO eventos_processados (consumidor, id_evento)
            VALUES (:c, :e) ON CONFLICT DO NOTHING RETURNING 1
        """), {"c": consumidor, "e": envelope.id_evento})
        if novo:
            await efeito(s, envelope)   # chama transicionar
    # commit da transação acima; só depois confirmar offset ou responder 200
```

A API do agente responde 200 também para evento duplicado. Responder erro faria o broker reenviar para sempre.

### 7.3 Relay da outbox

Loop no núcleo. Pode haver mais de um relay; `SKIP LOCKED` evita que dois peguem a mesma linha, e o `NOT EXISTS` mantém a ordem por conversa.

```sql
SELECT o.*
FROM outbox o
WHERE o.status = 'pendente'
  AND o.proxima_tentativa <= now()
  AND NOT EXISTS (
      SELECT 1 FROM outbox p
      WHERE p.id_conversa = o.id_conversa
        AND p.sequencia < o.sequencia
        AND p.status = 'pendente')
ORDER BY o.criado_em
LIMIT 50
FOR UPDATE SKIP LOCKED;
```

Para cada linha:
1. Envia (`POST` ao broker ou ao simulador de canal), com timeout de requisição.
2. Sucesso: `status = 'enviado'`, `enviado_em = now()`.
3. Falha: `tentativas += 1`, `proxima_tentativa = now() + atraso(tentativas)`, `ultimo_erro`.
4. `tentativas` chegou ao máximo: `status = 'erro'`, publica em `helpdesk.erros` e chama `transicionar(..., para="escalada", ator=sistema, motivo="falha_integracao")`.

```python
def atraso(tentativas):
    teto = min(BACKOFF_TETO_S, BACKOFF_BASE_S * 2 ** tentativas)
    return random.uniform(teto / 2, teto)   # jitter
```

Travar, enviar e atualizar acontecem na mesma transação, com timeout curto na requisição. Se o processo cair depois de enviar e antes do commit, a linha continua pendente e é reenviada. Essa reentrega é absorvida pela inbox do outro lado.

### 7.4 Agendador

```sql
SELECT * FROM agendamentos
WHERE status = 'pendente' AND executar_em <= now()
ORDER BY executar_em
LIMIT 50
FOR UPDATE SKIP LOCKED;
```

`timeout_agente`:
- Criado na mesma transação em que `mensagem.recebida` ou `conversa.atribuida` vai para a outbox, com `id_atribuicao` e `referencia` = `id_evento` enviado.
- Cancelado (`status = 'cancelado'`) quando chega evento do agente com `causado_por` igual à `referencia`.
- Ao executar: `transicionar(..., para="escalada", ator=sistema, id_atribuicao=ag.id_atribuicao, motivo="timeout_agente")`. Se a atribuição já mudou, o fencing descarta. Marcar `executado` em qualquer caso.

### 7.5 Broker

Entrada (`POST /webhook`):
1. Valida o envelope. Inválido: 422.
2. Publica em `helpdesk.para-agente` com chave `id_conversa` e espera o ack.
3. Ack: 200. Falha ou timeout do Kafka: 503. O relay da outbox tenta de novo.

Volta (consumidor de `agente.para-helpdesk`):
1. Valida. Inválido: publica em `helpdesk.erros`, confirma o offset.
2. `POST` ao núcleo em `/agente/eventos`.
3. 2xx: confirma o offset.
4. 4xx: publica em `helpdesk.erros`, confirma o offset.
5. 5xx repetido para o mesmo evento: retentativa com backoff; depois de `RETENTATIVAS_MAX`, `helpdesk.erros` e confirma.
6. Núcleo inalcançável (conexão recusada, timeout): não confirma, espera e tenta de novo, sem limite. É contrapressão: a partição para até o núcleo voltar.

### 7.6 Agente mock

- Consome `helpdesk.para-agente`, com inbox no banco `agente_mock`.
- Para `conversa.atribuida` e `mensagem.recebida`, gera uma resposta com `id_derivado(id_evento, "mensagem.enviada")`, mesmo `id_conversa` e mesmo `id_atribuicao`.
- Escala (`conversa.escalada`) se a mensagem pede humano ou tem palavra de irritação; resolve depois de N trocas.
- Publica em `agente.para-helpdesk` com produtor idempotente.

Modos para o experimento (`POST /modo`):

| Modo | Comportamento |
|---|---|
| `normal` | Responde com `LATENCIA_MS` |
| `lento` | Responde depois do timeout do núcleo |
| `duplicar` | Publica cada resposta duas vezes |
| `fora` | Para de consumir |

## 8. Roteador e distribuidor

```python
def rotear(atendimento: Atendimento, regras: VersaoRegras) -> Fila:
    for fila in sorted(regras.filas, key=lambda f: f.ordem):
        if fila.ativa and casa(fila.condicoes, atendimento):
            return fila
    return regras.fila_padrao
```

- `casa`: `todas` exige todas as condições; `qualquer`, pelo menos uma.
- Operadores: `igual`, `diferente`, `em` (valor é lista).
- Função pura: não lê banco, não grava, não usa hora atual. Teste em tabela (atendimento, regras, fila esperada).

Validação antes de ativar uma versão: campos e operadores conhecidos, `ordem` sem repetição, fila padrão existe, todo atendente citado existe.

Distribuidor: entre os atendentes da fila com status `disponivel` e capacidade livre, escolher o com menos conversas ativas. Atendente em várias filas atende primeiro a de maior prioridade. A atribuição em si passa por `transicionar`, que confere a capacidade sob trava.

## 9. Reconciliador

Roda a cada `RECONCILIADOR_INTERVALO_S` e no fim de cada execução do experimento. Cada linha encontrada vira registro em `violacoes`, métrica e log.

| Invariante | Consulta |
|---|---|
| I1 mensagem sem desfecho | mensagem de cliente mais velha que `PRAZO_RESPOSTA_S`, conversa em `na_fila` ou `com_ia`, sem mensagem de IA ou humano depois dela |
| I2 outbox parada | `status = 'pendente'` e `criado_em` mais velho que `OUTBOX_LIMITE_S` |
| I3 resposta duplicada | mais de uma mensagem de IA com o mesmo `causado_por` |
| I4 resposta fora de dono | mensagem de IA gravada fora do intervalo da atribuição dela |
| I5 capacidade estourada | atendente com mais conversas ativas que a capacidade |
| I6 conversa aberta duplicada | mais de uma conversa não resolvida para o mesmo cliente e marca |

```sql
-- I1
SELECT m.id FROM mensagens m JOIN conversas c ON c.id = m.id_conversa
WHERE m.autor_tipo = 'cliente'
  AND m.criada_em < now() - make_interval(secs => :prazo)
  AND c.estado IN ('na_fila', 'com_ia')
  AND NOT EXISTS (
      SELECT 1 FROM mensagens r
      WHERE r.id_conversa = m.id_conversa
        AND r.autor_tipo IN ('ia', 'humano')
        AND r.criada_em > m.criada_em);

-- I3
SELECT causado_por FROM mensagens
WHERE autor_tipo = 'ia' AND causado_por IS NOT NULL
GROUP BY causado_por HAVING count(*) > 1;

-- I4
SELECT m.id FROM mensagens m
LEFT JOIN atribuicoes a ON a.id = m.id_atribuicao
WHERE m.autor_tipo = 'ia'
  AND (a.id IS NULL OR m.criada_em NOT BETWEEN a.inicio AND coalesce(a.fim, now()));

-- I6
SELECT id_cliente, marca FROM conversas
WHERE estado <> 'resolvida'
GROUP BY id_cliente, marca HAVING count(*) > 1;
```

Na versão ingênua não há atribuições; ali I4 compara com o estado da conversa no momento da mensagem, reconstruído pelos eventos de auditoria.

## 10. Configuração

| Variável | Valor (inicial) | Uso |
|---|---|---|
| `TIMEOUT_AGENTE_S` | 30 | Prazo para o agente responder |
| `RETENTATIVAS_MAX` | 8 | Tentativas antes da fila de erros |
| `BACKOFF_BASE_S` | 0,5 | Primeiro atraso |
| `BACKOFF_TETO_S` | 60 | Atraso máximo |
| `JANELA_REABERTURA_H` | 24 | Reabrir em vez de criar conversa nova |
| `PRAZO_RESPOSTA_S` | 120 | I1 do reconciliador |
| `OUTBOX_LIMITE_S` | 60 | I2 do reconciliador |
| `RECONCILIADOR_INTERVALO_S` | 30 | Frequência do reconciliador |
| `CAPACIDADE_HUMANO` | 3 | Conversas simultâneas por analista |
| `CAPACIDADE_IA` | 2000 | Limite da IA (custo) |
| `LATENCIA_MS` | 800 | Latência simulada do mock |

## 11. Observabilidade

Log em JSON, um por linha, sempre com: `servico`, `id_conversa`, `id_evento`, `id_atribuicao`, `causado_por`, `consumidor`, `resultado`.

Métricas Prometheus:

| Métrica | Tipo |
|---|---|
| `mensagens_recebidas_total{canal,marca}` | contador |
| `latencia_interna_segundos` (entrada até o ack do broker) | histograma |
| `latencia_ponta_a_ponta_segundos` | histograma |
| `outbox_pendentes` e `outbox_idade_max_segundos` | gauge |
| `eventos_duplicados_ignorados_total{consumidor}` | contador |
| `eventos_descartados_fencing_total` | contador |
| `fila_erros_total{origem}` | contador |
| `escalas_total{motivo}` | contador |
| `reconciliador_violacoes_total{invariante}` | contador |

O atraso do consumidor vem do próprio Redpanda.

## 12. Fatias: o que fazer e quando está pronto

| Fatia | Entrega | Pronto quando |
|---|---|---|
| 1 Esqueleto | Compose, 3 tabelas, `POST /mensagens`, publicação direta no Kafka, mock com texto fixo, volta pelo consumidor | Mensagem vai e volta em teste de ponta a ponta; tag git `ingenua` criada |
| 2 Confiabilidade A | `transicionar`, transições permitidas, atribuições, outbox e relay, inbox, broker com as duas regras, índice de conversa aberta | Testes de 13.1 passam |
| 3 Confiabilidade B | Agendador, ordem na outbox, fila de erros com escala, reconciliador | Testes de 13.2 passam; reconciliador zerado após carga curta |
| 4 Filas | Roteador, distribuidor, versões de regras, validação e rollback, tela de configuração | Testes de 13.3 passam; supervisor troca regra sem deploy |
| 5 Humano | Fila de escalas, painel do analista, resumo de reserva, devolução para a IA | Analista assume, responde e devolve; histórico completo visível |
| 6 Canais e memória | WhatsApp e e-mail simulados, identidades, reabertura, resumo anterior para o agente | Mesmo cliente em dois canais cai no mesmo histórico só com evidência forte |
| 7 Experimento | Seção 14 | Tabela de resultados preenchida nas duas versões |
| 8 Diferenciais | A escolher | — |
| 9 README e demo | — | Outra pessoa sobe tudo com um comando seguindo o README |

## 13. Testes obrigatórios

### 13.1 Fatia 2

- Duas tarefas chamam `transicionar` na mesma conversa ao mesmo tempo: uma aplica, a outra vê o estado novo e falha ou é rejeitada.
- Transição fora da tabela é rejeitada e auditada.
- Evento com `id_atribuicao` antigo é descartado e auditado.
- Mesmo evento entregue duas vezes na API do agente: um efeito, duas respostas 200.
- Processo do relay morto entre o commit da transação e o envio: o evento sai quando o relay volta.
- Kafka fora: o broker responde 503 e o relay tenta de novo.
- Duas mensagens simultâneas de cliente novo criam uma conversa só.
- Duas atribuições simultâneas ao mesmo analista no limite de capacidade: só uma passa.

### 13.2 Fatia 3

- Agente sem resposta: conversa vai para `escalada` com `timeout_agente` depois do prazo.
- Resposta do agente antes do prazo cancela o timeout.
- Evento em retentativa segura os eventos seguintes da mesma conversa, e não os de outras.
- Evento que sempre falha vai para `helpdesk.erros` e a conversa é escalada com `falha_integracao`.
- Violação plantada de cada invariante é encontrada pelo reconciliador.

### 13.3 Fatia 4

- Roteador em tabela: cada combinação de condições, `todas` e `qualquer`, fallback.
- Versão inválida não ativa.
- Rollback reativa a versão anterior e novas conversas usam a regra antiga.
- Conversa guarda a versão de regras com que foi roteada.
- Consulta de uma marca não devolve dados de outra.

## 14. Experimento

Rodar cada cenário na versão ingênua (tag `ingenua`) e na robusta, com a mesma carga.

| Cenário | Como provocar |
|---|---|
| E1 Base | k6 a 100 msg/s por 10 minutos |
| E2 Pico | k6 com rampa até 5x por 3 minutos |
| E3 Duplicatas | mock em modo `duplicar` |
| E4 Agente lento | mock em modo `lento` |
| E5 Agente fora | `docker compose stop agente_mock` por 60 s durante a carga |
| E6 Broker fora | `docker compose stop broker` por 60 s durante a carga |
| E7 Núcleo morto | `docker compose kill -s SIGKILL nucleo` durante a carga, depois `start` |

Ao fim de cada execução: esperar a fila esvaziar, rodar o reconciliador e coletar as métricas.

| Cenário | Versão | Enviadas | Perdidas (I1) | Duplicadas (I3) | Fora de dono (I4) | p95 interna | Recuperação |
|---|---|---|---|---|---|---|---|
| E1 | ingênua | | | | | | |
| E1 | robusta | | | | | | |

Repetir cada cenário pelo menos 3 vezes e reportar média e variação.

## 15. Em aberto

| Ponto | Proposta atual |
|---|---|
| Cliente Kafka em Python | aiokafka (assíncrono, combina com FastAPI) |
| Partições | 12 |
| Autenticação do painel | Usuário fixo por perfil; autenticação real fora do escopo |
| Interface | Next.js mínimo: chat, painel do analista, configuração de filas |
| Triagem | Regras na fatia 4; classificador próprio em discussão (seção 20 da arquitetura) |
