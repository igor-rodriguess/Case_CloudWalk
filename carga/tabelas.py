"""Gera a tabela de resultados do README a partir de resultados/<cenario>/<posicao>/*.json."""

import json

from carga.falhas import RAIZ

COLUNAS = ["enviadas", "recusadas", "perdidas", "duplicadas", "escaladas", "esperando_humano",
           "espera_p95_s", "p95_interna_s", "recuperacao_s"]


def tabela() -> str:
    linhas = ["| Cenário | Chave | " + " | ".join(COLUNAS) + " |", "|" + "---|" * (len(COLUNAS) + 2)]
    for arquivo in sorted((RAIZ / "resultados").glob("*/*/*.json")):
        m = json.loads(arquivo.read_text(encoding="utf-8"))
        valores = ["—" if m.get(c) is None else str(m[c]) for c in COLUNAS]
        linhas.append(f"| {m['cenario']} | {m['posicao']} | " + " | ".join(valores) + " |")
    return "\n".join(linhas)


if __name__ == "__main__":
    print(tabela())
