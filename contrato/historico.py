"""Regra comum ao agente e ao juiz para ler o histórico de `conversa.atribuida`."""


def pendentes_do_cliente(historico: list[dict]) -> list[dict]:
    """Mensagens do cliente depois da última resposta (da IA ou de humano), em ordem.

    Enquanto a conversa espera na fila, as mensagens do cliente só entram no histórico; quando a
    IA recebe a conversa, estas são as que ainda não tiveram resposta. O agente responde cada uma
    com `sequencia` = posição nesta lista, e o juiz usa a mesma posição para ligar a resposta.
    """
    pendentes = []
    for m in historico or []:
        if m.get("autor") == "cliente":
            pendentes.append(m)
        elif m.get("autor") in ("ia", "humano"):
            pendentes = []
    return pendentes
