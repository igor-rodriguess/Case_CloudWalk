"""Envelope comum de todo evento entre a plataforma e o agente (arquitetura, seção 10)."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

TipoEvento = Literal[
    # plataforma -> agente
    "conversa.atribuida",
    "mensagem.recebida",
    "conversa.devolvida",
    "conversa.encerrada",
    # agente -> plataforma
    "mensagem.enviada",
    "acao.executada",
    "conversa.escalada",
    "conversa.resolvida",
    "agente.processando",
]

EVENTOS_DO_AGENTE: frozenset[str] = frozenset(
    {
        "mensagem.enviada",
        "acao.executada",
        "conversa.escalada",
        "conversa.resolvida",
        "agente.processando",
    }
)

Marca = Literal["infinitepay", "jim"]


class Envelope(BaseModel):
    # Campos desconhecidos são ignorados: campo novo numa versão 1.x não quebra quem está na 1.0.
    # Tipo desconhecido é recusado aqui; quem tolera é o consumidor (audita e confirma).
    model_config = ConfigDict(frozen=True)

    versao: str = Field(default="1.0", pattern=r"^1\.\d+$")
    id_evento: UUID
    tipo: TipoEvento
    id_conversa: UUID
    id_atribuicao: UUID | None = None
    causado_por: UUID | None = None
    marca: Marca
    timestamp: datetime
    dados: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def regras_do_contrato(self) -> "Envelope":
        # Regra 1: sem fuso, "13:30" é ambíguo entre Brasil (InfinitePay) e EUA (JIM).
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("timestamp precisa ter fuso horário")

        # Regra 2: sem atribuição e causa, o fencing e o id determinístico não funcionam.
        if self.tipo in EVENTOS_DO_AGENTE:
            faltando = [
                campo for campo in ("id_atribuicao", "causado_por") if getattr(self, campo) is None
            ]
            if faltando:
                raise ValueError(f"evento do agente sem {', '.join(faltando)}")
        return self
