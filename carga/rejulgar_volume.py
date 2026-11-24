"""Rejulga uma execução do T2/T4 a partir do banco, sem os registros do gerador.

O T4c gravou o resultado com a janela do juiz de -1 a 1 s (só as 25 primeiras mensagens): a janela
servia para a rajada, em que tudo sai no instante 0. Aqui o envio de cada mensagem é o `criada_em`
dela no núcleo; toda mensagem gravada foi aceita (HTTP 200).

Uso: python -m carga.rejulgar_volume T2-1795523127 T4c-volume-cadenciado
"""

import asyncio
import json
import sys
from collections import defaultdict

import psycopg

from carga.agenda import Envio
from carga.completo import pct, salvar
from carga.gerador import Registro
from carga.juiz import NUCLEO_DB, julgar


def main(execucao: str, nome: str) -> None:
    with psycopg.connect(NUCLEO_DB) as c:
        linhas = c.execute(
            """
            SELECT m.id_externo, m.id_conversa::text, c.marca, m.canal, extract(epoch FROM m.criada_em)
            FROM mensagens m JOIN conversas c ON c.id = m.id_conversa
            WHERE m.autor_tipo = 'cliente' AND m.id_externo LIKE %s
            """,
            (f"{execucao}-%",),
        ).fetchall()
    t0 = min(float(x[4]) for x in linhas)
    registros = []
    for id_ext, conv, marca, canal, criada in linhas:
        chave, k = id_ext.rsplit("-m", 1)
        envio = Envio(float(criada) - t0, chave, int(k), id_ext, marca, canal or "chat", "")
        registros.append(Registro(envio, float(criada), 200, conv))
    m, julgadas = julgar(registros, -1, float("inf"))
    ultima = {}
    for linha in julgadas:
        chave, k = linha["id_externo"].rsplit("-m", 1)
        if chave not in ultima or int(k) > ultima[chave][0]:
            ultima[chave] = (int(k), linha["desfecho"])
    esperas = [linha["espera_s"] for linha in julgadas if linha["espera_s"] != ""]
    desfechos = defaultdict(int)
    for linha in julgadas:
        desfechos[linha["desfecho"]] += 1
    resultado = {
        "teste": f"{nome} (rejulgado do banco)", "execucao": execucao, "mensagens": len(registros),
        "conversas": len(ultima),
        "conversas_sem_resposta": sum(1 for _k, d in ultima.values() if d in ("perdida", "recusada")),
        "mensagens_sem_resposta_propria": m["perdidas"],
        **{k: m[k] for k in ("enviadas", "recusadas", "perdidas", "duplicadas", "escaladas", "respondidas",
                             "espera_p95_s", "p95_interna_s", "respostas_ligadas_exata",
                             "respostas_ligadas_por_ordem")},
        "espera_p50_s": pct(esperas, 50), "espera_p99_s": pct(esperas, 99),
        "desfechos": dict(desfechos),
    }
    salvar(f"{nome}-rejulgado", resultado)
    print(json.dumps(resultado, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    main(sys.argv[1], sys.argv[2])
