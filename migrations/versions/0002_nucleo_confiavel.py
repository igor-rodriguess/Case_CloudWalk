"""núcleo confiável: atribuições, auditoria, outbox, inbox, agendador, filas, disjuntor

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-21

Junta as tabelas das fatias 2, 3, 5 e 7 do guia (docs/implementacao.md, 5.2) por causa do prazo.
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

TRANSICOES = [
    ("nova", "na_fila", "sistema"),
    ("na_fila", "com_ia", "sistema"),
    ("na_fila", "com_humano", "sistema"),
    ("na_fila", "com_humano", "humano"),
    ("na_fila", "escalada", "sistema"),
    ("com_ia", "escalada", "ia"),
    ("com_ia", "escalada", "sistema"),
    ("com_ia", "escalada", "cliente"),
    ("escalada", "com_humano", "sistema"),
    ("escalada", "com_humano", "humano"),
    ("com_humano", "com_ia", "humano"),
    ("com_ia", "resolvida", "ia"),
    ("com_ia", "resolvida", "sistema"),
    ("com_humano", "resolvida", "humano"),
    ("com_humano", "resolvida", "sistema"),
    ("resolvida", "na_fila", "cliente"),
]

SQL = """
ALTER TABLE clientes ADD COLUMN produtos text[] NOT NULL DEFAULT '{}';

ALTER TABLE conversas ALTER COLUMN prioridade TYPE smallint USING NULL;
ALTER TABLE conversas ALTER COLUMN id_fila TYPE text USING id_fila::text;
ALTER TABLE conversas ADD COLUMN idioma text;
ALTER TABLE conversas ADD COLUMN origem text NOT NULL DEFAULT 'cliente';
ALTER TABLE conversas ADD COLUMN seq_mensagem bigint NOT NULL DEFAULT 0;
ALTER TABLE conversas ADD COLUMN motivo_encerramento text;
ALTER TABLE conversas ADD COLUMN na_fila_desde timestamptz;
ALTER TABLE conversas ADD CONSTRAINT ck_conversas_estado CHECK (estado IN
    ('nova', 'na_fila', 'com_ia', 'escalada', 'com_humano', 'resolvida'));
CREATE UNIQUE INDEX conversa_aberta_unica ON conversas (id_cliente, marca) WHERE estado <> 'resolvida';
CREATE INDEX ix_conversas_fila ON conversas (id_fila, prioridade DESC, criada_em)
    WHERE estado IN ('na_fila', 'escalada');

ALTER TABLE mensagens ADD COLUMN id_externo text;
ALTER TABLE mensagens ADD COLUMN sequencia int NOT NULL DEFAULT 0;
ALTER TABLE mensagens ADD COLUMN id_atribuicao_declarada uuid;
ALTER TABLE mensagens ADD COLUMN seq bigint;
CREATE INDEX ix_mensagens_canal_externo ON mensagens (canal, id_externo);
CREATE INDEX ix_mensagens_conversa_seq ON mensagens (id_conversa, seq);
CREATE INDEX ix_mensagens_causado_por ON mensagens (causado_por) WHERE autor_tipo = 'ia';

CREATE TABLE identidades (
    canal          text NOT NULL,
    identificador  text NOT NULL,
    marca          text NOT NULL,
    id_cliente     uuid NOT NULL REFERENCES clientes(id),
    PRIMARY KEY (canal, identificador, marca)
);

CREATE TABLE atendentes (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tipo         text NOT NULL CHECK (tipo IN ('ia', 'humano')),
    nome         text NOT NULL,
    marca        text NOT NULL,
    id_equipe    text,
    capacidade   int  NOT NULL,
    ativas       int  NOT NULL DEFAULT 0,
    status       text NOT NULL DEFAULT 'disponivel'
);

CREATE TABLE atribuicoes (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    id_conversa   uuid NOT NULL REFERENCES conversas(id),
    id_fila       text,
    id_atendente  uuid NOT NULL REFERENCES atendentes(id),
    sonda         boolean NOT NULL DEFAULT false,
    inicio        timestamptz NOT NULL DEFAULT now(),
    fim           timestamptz,
    motivo_fim    text
);
CREATE INDEX ix_atribuicoes_abertas ON atribuicoes (id_atendente) WHERE fim IS NULL;

CREATE TABLE transicoes_permitidas (
    de text NOT NULL, para text NOT NULL, ator_tipo text NOT NULL,
    PRIMARY KEY (de, para, ator_tipo)
);

CREATE TABLE eventos (
    id             bigserial PRIMARY KEY,
    id_evento      uuid,
    tipo           text NOT NULL,
    ator_tipo      text NOT NULL,
    id_ator        uuid,
    id_conversa    uuid,
    id_atribuicao  uuid,
    payload        jsonb NOT NULL DEFAULT '{}',
    criado_em      timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX ix_eventos_conversa ON eventos (id_conversa, criado_em);
CREATE INDEX ix_eventos_tipo ON eventos (tipo, criado_em);

CREATE FUNCTION eventos_imutaveis() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'eventos é só inserção';
END $$;
CREATE TRIGGER tg_eventos_imutaveis BEFORE UPDATE OR DELETE ON eventos
    FOR EACH ROW EXECUTE FUNCTION eventos_imutaveis();

CREATE TABLE eventos_processados (
    consumidor text NOT NULL, id_evento uuid NOT NULL,
    processado_em timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (consumidor, id_evento)
);

CREATE TABLE outbox (
    id                 bigserial PRIMARY KEY,
    id_evento          uuid NOT NULL UNIQUE,
    id_conversa        uuid,
    id_atribuicao      uuid,
    sequencia          bigint,
    destino            text NOT NULL CHECK (destino IN ('broker', 'canal')),
    payload            jsonb NOT NULL,
    status             text NOT NULL DEFAULT 'pendente'
                       CHECK (status IN ('pendente', 'enviando', 'enviado', 'erro')),
    reservado_ate      timestamptz,
    tentativas         int  NOT NULL DEFAULT 0,
    proxima_tentativa  timestamptz NOT NULL DEFAULT now(),
    ultimo_erro        text,
    criado_em          timestamptz NOT NULL DEFAULT clock_timestamp(),
    enviado_em         timestamptz
);
CREATE INDEX ix_outbox_status ON outbox (status, proxima_tentativa);
CREATE INDEX ix_outbox_ordem ON outbox (id_conversa, destino, sequencia);

CREATE TABLE agendamentos (
    id             bigserial PRIMARY KEY,
    tipo           text NOT NULL,
    id_conversa    uuid NOT NULL,
    id_atribuicao  uuid,
    referencia     uuid,
    executar_em    timestamptz NOT NULL,
    renovacoes     int  NOT NULL DEFAULT 0,
    sonda          boolean NOT NULL DEFAULT false,
    status         text NOT NULL DEFAULT 'pendente'
                   CHECK (status IN ('pendente', 'executado', 'cancelado')),
    motivo_fim     text,
    criado_em      timestamptz NOT NULL DEFAULT clock_timestamp(),
    finalizado_em  timestamptz
);
CREATE INDEX ix_agendamentos_vencidos ON agendamentos (status, executar_em);
CREATE INDEX ix_agendamentos_conversa ON agendamentos (id_conversa) WHERE status = 'pendente';
CREATE INDEX ix_agendamentos_atribuicao ON agendamentos (id_atribuicao, tipo) WHERE status = 'pendente';
CREATE UNIQUE INDEX uq_espera_retida ON agendamentos (id_conversa)
    WHERE tipo = 'espera_retida' AND status = 'pendente';

CREATE TABLE versoes_regras (
    numero serial PRIMARY KEY, filas jsonb NOT NULL,
    ativa boolean NOT NULL DEFAULT false, criada_por text NOT NULL,
    criada_em timestamptz NOT NULL DEFAULT now(), ativada_em timestamptz
);
CREATE UNIQUE INDEX uma_versao_ativa ON versoes_regras (ativa) WHERE ativa;

CREATE TABLE escalas (
    id           bigserial PRIMARY KEY,
    id_conversa  uuid NOT NULL REFERENCES conversas(id),
    motivo       text NOT NULL,
    resumo       text,
    fontes       jsonb NOT NULL DEFAULT '[]',
    reserva      boolean NOT NULL DEFAULT false,
    prioridade   smallint,
    criada_em    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_escalas_conversa ON escalas (id_conversa, criada_em);

CREATE TABLE disjuntores (
    id_atendente      uuid PRIMARY KEY REFERENCES atendentes(id),
    estado            text NOT NULL DEFAULT 'fechado'
                      CHECK (estado IN ('fechado', 'aberto', 'meio_aberto')),
    mudou_em          timestamptz NOT NULL DEFAULT now(),
    sondas_restantes  int NOT NULL DEFAULT 0
);

CREATE TABLE desfechos_ia (
    id            bigserial PRIMARY KEY,
    id_atendente  uuid NOT NULL REFERENCES atendentes(id),
    desfecho      text NOT NULL CHECK (desfecho IN ('resposta', 'timeout', 'falha_integracao')),
    sonda         boolean NOT NULL DEFAULT false,
    criado_em     timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX ix_desfechos_ia ON desfechos_ia (id_atendente, id DESC);
"""


def upgrade() -> None:
    op.execute(SQL)
    for de, para, ator in TRANSICOES:
        op.execute(
            f"INSERT INTO transicoes_permitidas VALUES ('{de}', '{para}', '{ator}')"
        )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS desfechos_ia, disjuntores, escalas, versoes_regras, agendamentos,
            outbox, eventos_processados, eventos, transicoes_permitidas, atribuicoes,
            atendentes, identidades CASCADE;
        DROP FUNCTION IF EXISTS eventos_imutaveis();
        DROP INDEX IF EXISTS conversa_aberta_unica, ix_conversas_fila, ix_mensagens_canal_externo,
            ix_mensagens_conversa_seq, ix_mensagens_causado_por;
        ALTER TABLE conversas DROP CONSTRAINT IF EXISTS ck_conversas_estado;
        ALTER TABLE conversas DROP COLUMN idioma, DROP COLUMN origem, DROP COLUMN seq_mensagem,
            DROP COLUMN motivo_encerramento, DROP COLUMN na_fila_desde;
        ALTER TABLE mensagens DROP COLUMN id_externo, DROP COLUMN sequencia,
            DROP COLUMN id_atribuicao_declarada, DROP COLUMN seq;
        ALTER TABLE clientes DROP COLUMN produtos;
        """
    )
