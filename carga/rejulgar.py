"""Rejulga execuções já feitas, a partir do CSV, com o juiz atual.

Precisa do banco da execução ainda no ar (o lote não apaga o banco entre execuções).
Reescreve o JSON da execução mantendo os campos de configuração e falha.
Uso: .venv\\Scripts\\python -m carga.rejulgar resultados/E1/ligada/E1-ligada-123.csv [...]
"""

import csv
import json
import sys
from pathlib import Path

from carga.agenda import Envio
from carga.gerador import Registro
from carga.juiz import julgar


def rejulgar(caminho_csv: Path) -> dict:
    caminho_json = caminho_csv.with_suffix(".json")
    antigo = json.loads(caminho_json.read_text(encoding="utf-8"))
    registros = []
    with open(caminho_csv, encoding="utf-8") as f:
        for linha in csv.DictReader(f):
            envio = Envio(float(linha["t"]), "", 0, linha["id_externo"], "", "chat", "")
            reg = Registro(envio, enviado_em=float(linha["enviado_em"]), status=int(linha["status"]),
                           id_conversa=linha["conversa"] or None)
            registros.append(reg)
    ini = antigo["aquecimento_s"]
    fim = ini + antigo["medicao_s"]
    metricas, linhas = julgar(registros, ini, fim, antigo.get("falha"))
    novo = {**antigo, **metricas, "rejulgado": True}
    caminho_json.write_text(json.dumps(novo, indent=2, ensure_ascii=False), encoding="utf-8")
    with open(caminho_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
        w.writeheader()
        w.writerows(linhas)
    return novo


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        m = rejulgar(Path(arg))
        print(json.dumps({k: m.get(k) for k in ("cenario", "posicao", "enviadas", "perdidas", "duplicadas",
                                                 "escaladas", "respostas_ligadas_exata",
                                                 "respostas_ligadas_por_ordem")}, ensure_ascii=False))
