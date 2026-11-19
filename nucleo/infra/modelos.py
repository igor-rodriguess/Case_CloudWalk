"""Tabelas da fatia 1: clientes, conversas e mensagens.

As colunas de atribuição e causalidade já existem, nulas, para o contrato não mudar nas próximas fatias.
O índice único de conversa aberta fica para a fatia 2: esta é a versão ingênua do experimento.
"""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, MetaData, Text, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Nomes fixos para constraints: migrations ficam iguais em qualquer máquina.
CONVENCAO = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

UUID_PADRAO = text("gen_random_uuid()")


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=CONVENCAO)


class Cliente(Base):
    __tablename__ = "clientes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=UUID_PADRAO)
    marca: Mapped[str] = mapped_column(Text)
    nome: Mapped[str] = mapped_column(Text)  # sintético
    segmento: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Conversa(Base):
    __tablename__ = "conversas"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=UUID_PADRAO)
    id_cliente: Mapped[uuid.UUID] = mapped_column(ForeignKey("clientes.id"))
    marca: Mapped[str] = mapped_column(Text)
    canal: Mapped[str] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(Text)
    categoria: Mapped[str | None] = mapped_column(Text)
    prioridade: Mapped[str | None] = mapped_column(Text)
    sentimento: Mapped[str | None] = mapped_column(Text)
    id_fila: Mapped[uuid.UUID | None]
    id_atendente: Mapped[uuid.UUID | None]
    id_atribuicao_atual: Mapped[uuid.UUID | None]
    versao_regras: Mapped[int | None]
    versao: Mapped[int] = mapped_column(server_default=text("0"))
    seq_outbox: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolvida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Mensagem(Base):
    __tablename__ = "mensagens"
    __table_args__ = (
        CheckConstraint("autor_tipo IN ('cliente', 'ia', 'humano', 'sistema')", name="autor_tipo"),
        Index(None, "id_conversa", "criada_em"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=UUID_PADRAO)
    id_conversa: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversas.id"))
    autor_tipo: Mapped[str] = mapped_column(Text)
    id_autor: Mapped[uuid.UUID | None]
    conteudo: Mapped[str] = mapped_column(Text)
    canal: Mapped[str] = mapped_column(Text)
    id_evento: Mapped[uuid.UUID | None] = mapped_column(unique=True)  # evento que trouxe a mensagem
    causado_por: Mapped[uuid.UUID | None]
    id_atribuicao: Mapped[uuid.UUID | None]  # atribuição vigente ao gravar
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
