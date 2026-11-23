"""Roda as 6 execuções da entrega em sequência (E6 primeiro: é o piso do plano).

Uso: .venv\\Scripts\\python -m carga.lote [--aquecimento 420 --medicao 300 --conversas-por-s 4.15]

Padrão 4,15 conversas/s = 50 msg/s nas duas direções: o plano B do documento, porque esta
máquina sustentou cerca de 35 msg/s de cliente (70 no total) antes de recusar (diário, dia 2).
"""

import argparse
import asyncio
import json
import sys
import time

from carga.rodar import executar

ORDEM = [("E6", "ligada"), ("E6", "desligada"), ("E3b", "ligada"), ("E3b", "desligada"),
         ("E1", "ligada"), ("E1", "desligada")]


def main() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    p = argparse.ArgumentParser()
    p.add_argument("--aquecimento", type=float, default=420)
    p.add_argument("--medicao", type=float, default=300)
    p.add_argument("--conversas-por-s", type=float, default=4.15)
    p.add_argument("--so", nargs="*", default=None, help="ex.: E6 E3b, ou E3b:desligada")
    a = p.parse_args()
    for cenario, posicao in ORDEM:
        if a.so and cenario not in a.so and f"{cenario}:{posicao}" not in a.so:
            continue
        drenagem = 150 if cenario == "E6" else 90
        inicio = time.time()
        m = asyncio.run(executar(cenario, posicao, a.aquecimento, a.medicao, drenagem, 42, a.conversas_por_s))
        resumo = {k: m[k] for k in ("cenario", "posicao", "msg_por_s_total", "enviadas", "recusadas", "perdidas",
                                    "duplicadas", "escaladas", "espera_p95_s", "p95_interna_s", "recuperacao_s")}
        resumo["duracao_min"] = round((time.time() - inicio) / 60, 1)
        print(json.dumps(resumo, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
