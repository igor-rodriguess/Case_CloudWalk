"""Agenda determinística da carga (docs/implementacao.md, seção 14).

Modelo aberto por mensagem: conversas chegam a uma taxa fixa; cada uma manda 6 mensagens
com 84 s entre elas, sem esperar a resposta. Com a semente fixa, a mesma agenda se repete.
"""

import random
from dataclasses import dataclass

TEXTOS_PT = [
    "meu repasse não caiu", "quando cai o dinheiro da venda?", "a maquininha não liga",
    "quero saber meu saldo", "o pix do cliente não apareceu", "como faço para antecipar?",
]
TEXTOS_EN = [
    "my payout did not arrive", "when will the sale money land?", "the card reader is off",
    "what is my balance?", "the transfer did not show up", "how do I get paid earlier?",
]


@dataclass(frozen=True)
class Envio:
    t: float           # segundos desde o início da execução
    conversa: str      # chave da conversa na agenda (vira o identificador do lojista)
    k: int             # índice da mensagem na conversa (0 a 5)
    id_externo: str
    marca: str
    canal: str
    texto: str
    reenvio: bool = False


def gerar(execucao: str, duracao_s: float, semente: int = 42, conversas_por_s: float = 8.3,
          mensagens: int = 6, intervalo_s: float = 84.0, frac_reenvio: float = 0.0,
          atraso_reenvio_s: float = 2.0, frac_jim: float = 0.2) -> list[Envio]:
    rnd = random.Random(semente)
    agenda: list[Envio] = []
    n_conversas = int(duracao_s * conversas_por_s)
    for i in range(n_conversas):
        inicio = i / conversas_por_s
        marca = "jim" if rnd.random() < frac_jim else "infinitepay"
        textos = TEXTOS_EN if marca == "jim" else TEXTOS_PT
        conversa = f"{execucao}-c{i}"
        for k in range(mensagens):
            t = inicio + k * intervalo_s
            if t >= duracao_s:
                break
            envio = Envio(t, conversa, k, f"{conversa}-m{k}", marca, "chat", textos[k % len(textos)])
            agenda.append(envio)
            if frac_reenvio and rnd.random() < frac_reenvio:
                agenda.append(Envio(t + atraso_reenvio_s, conversa, k, envio.id_externo, marca, "chat",
                                    envio.texto, reenvio=True))
    agenda.sort(key=lambda e: e.t)
    return agenda
