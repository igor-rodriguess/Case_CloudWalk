"""Escolha do atendente. Função pura: preferência do grupo na fila, depois menor ocupação.

Comparar só ocupação punha um analista com 1 conversa na frente da IA com 800 e invertia
o AI first; por isso o grupo vem antes.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class Candidato:
    id: UUID
    tipo: str
    grupo: int  # posição do grupo na lista de atendentes da fila
    disponivel: bool
    ativas: int
    capacidade: int


@dataclass(frozen=True)
class Escolha:
    id: UUID | None
    motivo: str


def escolher(candidatos: list[Candidato]) -> Escolha:
    livres = [c for c in candidatos if c.disponivel and c.ativas < c.capacidade]
    if not livres:
        return Escolha(None, "sem_candidato")
    grupo = min(c.grupo for c in livres)
    a = min((c for c in livres if c.grupo == grupo), key=lambda c: (c.ativas / c.capacidade, str(c.id)))
    return Escolha(a.id, "preferencia_e_menor_ocupacao")
