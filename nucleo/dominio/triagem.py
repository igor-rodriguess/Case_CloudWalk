"""Triagem por palavras-chave: categoria, prioridade (1 a 3), sentimento e idioma.

Função pura. Um classificador treinado fica como evolução (docs/arquitetura.md, seção 21).
"""

import re
from dataclasses import dataclass

CATEGORIAS = [
    ("fraude", r"golpe|fraude|clonad|n[aã]o reconhe[cç]o|fraud|scam|stolen"),
    ("credito", r"cr[eé]dito|empr[eé]stimo|parcela|limite|loan|credit"),
    ("repasse", r"repasse|recebimento|dep[oó]sito|liquida[cç][aã]o|payout|deposit|transfer"),
    ("maquininha", r"maquininha|m[aá]quina|leitor|card reader|terminal"),
    ("conta", r"conta|saldo|extrato|senha|account|balance|password"),
]
URGENCIA = r"urgente|bloquead|travad|parad[ao]|urgent|blocked|asap"
NEGATIVO = r"absurdo|p[eé]ssimo|horr[ií]vel|rid[ií]culo|raiva|vergonha|terrible|awful|angry|ridiculous|!!!"
PEDE_HUMANO = r"\bhumano\b|\batendente\b|falar com (uma )?pessoa|\bhuman\b|real person|\bagent\b"


@dataclass(frozen=True)
class Triagem:
    categoria: str
    prioridade: int
    sentimento: str
    idioma: str


def triar(texto: str, marca: str) -> Triagem:
    t = texto.lower()
    categoria = next((nome for nome, padrao in CATEGORIAS if re.search(padrao, t)), "geral")
    if categoria == "fraude" or re.search(URGENCIA, t):
        prioridade = 3
    elif categoria in ("repasse", "credito"):
        prioridade = 2
    else:
        prioridade = 1
    sentimento = "negativo" if re.search(NEGATIVO, t) else "neutro"
    idioma = "en" if marca == "jim" else "pt"
    return Triagem(categoria, prioridade, sentimento, idioma)


def pede_humano(texto: str) -> bool:
    return re.search(PEDE_HUMANO, texto.lower()) is not None
