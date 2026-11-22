"""Id determinístico para eventos derivados (arquitetura, seção 11.1).

Quem processa o mesmo evento duas vezes gera o mesmo id para a resposta,
e a inbox do outro lado descarta a repetição.
"""

import uuid

NAMESPACE_HELPDESK = uuid.uuid5(uuid.NAMESPACE_URL, "helpdesk-ai-first")


def id_derivado(causado_por: uuid.UUID, tipo: str, sequencia: int = 0) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE_HELPDESK, f"{causado_por}:{tipo}:{sequencia}")
