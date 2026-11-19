"""fatia 1: clientes, conversas e mensagens

Revision ID: 0001
Revises:
Create Date: 2026-11-17
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

UUID_PADRAO = sa.text("gen_random_uuid()")
AGORA = sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "clientes",
        sa.Column("id", sa.Uuid(), server_default=UUID_PADRAO, nullable=False),
        sa.Column("marca", sa.Text(), nullable=False),
        sa.Column("nome", sa.Text(), nullable=False),
        sa.Column("segmento", sa.Text(), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=AGORA, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_clientes"),
    )

    op.create_table(
        "conversas",
        sa.Column("id", sa.Uuid(), server_default=UUID_PADRAO, nullable=False),
        sa.Column("id_cliente", sa.Uuid(), nullable=False),
        sa.Column("marca", sa.Text(), nullable=False),
        sa.Column("canal", sa.Text(), nullable=False),
        sa.Column("estado", sa.Text(), nullable=False),
        sa.Column("categoria", sa.Text(), nullable=True),
        sa.Column("prioridade", sa.Text(), nullable=True),
        sa.Column("sentimento", sa.Text(), nullable=True),
        sa.Column("id_fila", sa.Uuid(), nullable=True),
        sa.Column("id_atendente", sa.Uuid(), nullable=True),
        sa.Column("id_atribuicao_atual", sa.Uuid(), nullable=True),
        sa.Column("versao_regras", sa.Integer(), nullable=True),
        sa.Column("versao", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("seq_outbox", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("criada_em", sa.DateTime(timezone=True), server_default=AGORA, nullable=False),
        sa.Column("atualizada_em", sa.DateTime(timezone=True), server_default=AGORA, nullable=False),
        sa.Column("resolvida_em", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["id_cliente"], ["clientes.id"], name="fk_conversas_id_cliente_clientes"),
        sa.PrimaryKeyConstraint("id", name="pk_conversas"),
    )

    op.create_table(
        "mensagens",
        sa.Column("id", sa.Uuid(), server_default=UUID_PADRAO, nullable=False),
        sa.Column("id_conversa", sa.Uuid(), nullable=False),
        sa.Column("autor_tipo", sa.Text(), nullable=False),
        sa.Column("id_autor", sa.Uuid(), nullable=True),
        sa.Column("conteudo", sa.Text(), nullable=False),
        sa.Column("canal", sa.Text(), nullable=False),
        sa.Column("id_evento", sa.Uuid(), nullable=True),
        sa.Column("causado_por", sa.Uuid(), nullable=True),
        sa.Column("id_atribuicao", sa.Uuid(), nullable=True),
        sa.Column("criada_em", sa.DateTime(timezone=True), server_default=AGORA, nullable=False),
        sa.CheckConstraint(
            "autor_tipo IN ('cliente', 'ia', 'humano', 'sistema')", name=op.f("ck_mensagens_autor_tipo")
        ),
        sa.ForeignKeyConstraint(["id_conversa"], ["conversas.id"], name="fk_mensagens_id_conversa_conversas"),
        sa.PrimaryKeyConstraint("id", name="pk_mensagens"),
        sa.UniqueConstraint("id_evento", name="uq_mensagens_id_evento"),
    )
    op.create_index("ix_mensagens_id_conversa_criada_em", "mensagens", ["id_conversa", "criada_em"])


def downgrade() -> None:
    op.drop_index("ix_mensagens_id_conversa_criada_em", table_name="mensagens")
    op.drop_table("mensagens")
    op.drop_table("conversas")
    op.drop_table("clientes")
