"""Roda as 6 execuções da entrega em sequência (E6 primeiro: é o piso do plano).

Uso: .venv\\Scripts\\python -m carga.lote [--aquecimento 420 --medicao 300]
"""

import argparse
import asyncio
import json
import time

from carga.rodar import executar

ORDEM = [("E6", "ligada"), ("E6", "desligada"), ("E3b", "ligada"), ("E3b", "desligada"),
         ("E1", "ligada"), ("E1", "desligada")]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--aquecimento", type=float, default=420)
    p.add_argument("--medicao", type=float, default=300)
    a = p.parse_args()
    for cenario, posicao in ORDEM:
        drenagem = 150 if cenario == "E6" else 90
        inicio = time.time()
        m = asyncio.run(executar(cenario, posicao, a.aquecimento, a.medicao, drenagem, 42))
        resumo = {k: m[k] for k in ("cenario", "posicao", "enviadas", "recusadas", "perdidas", "duplicadas",
                                    "escaladas", "espera_p95_s", "p95_interna_s", "recuperacao_s")}
        resumo["duracao_min"] = round((time.time() - inicio) / 60, 1)
        print(json.dumps(resumo, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
