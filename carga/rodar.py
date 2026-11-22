"""Roda um cenário do experimento numa posição da chave e grava o resultado.

Uso (com o ambiente no ar):
  .venv\\Scripts\\python -m carga.rodar E1 ligada --aquecimento 120 --medicao 180
Cenários: E1 (base; OUTBOX_ATIVA e INBOX_ATIVA juntas), E3b (reenvio do canal; INBOX_ATIVA),
E6 (broker fora 60 s; OUTBOX_ATIVA). Posição: ligada ou desligada.
"""

import argparse
import asyncio
import csv
import json
import os
import subprocess
import time
from pathlib import Path

import httpx
import psycopg

from carga.agenda import gerar
from carga.falhas import RAIZ, parar_por
from carga.gerador import reproduzir
from carga.juiz import NUCLEO_DB, julgar

NUCLEO = "http://localhost:8000"
MOCK = "http://localhost:8200"
CHAVES = {"E1": ["OUTBOX_ATIVA", "INBOX_ATIVA"], "E3b": ["INBOX_ATIVA"], "E6": ["OUTBOX_ATIVA"]}
RESULTADOS = RAIZ / "resultados"


def preparar(cenario: str, posicao: str) -> dict:
    valor = "true" if posicao == "ligada" else "false"
    env = {**os.environ, "OUTBOX_ATIVA": "true", "INBOX_ATIVA": "true"}
    for chave in CHAVES[cenario]:
        env[chave] = valor
    subprocess.run(["docker", "compose", "up", "-d", "broker", "agente_mock", "canais", "nucleo"],
                   cwd=RAIZ, env=env, check=True, capture_output=True)
    esperado = {k: env[k] == "true" for k in ("OUTBOX_ATIVA", "INBOX_ATIVA")}
    for _ in range(120):
        try:
            cfg = httpx.get(f"{NUCLEO}/config", timeout=2).json()
            if all(cfg[k] == v for k, v in esperado.items()):
                break
        except httpx.HTTPError:
            pass
        time.sleep(1)
    else:
        raise RuntimeError("núcleo não subiu com as chaves pedidas")
    httpx.post(f"{MOCK}/modo", json={"modo": "normal"}, timeout=5)
    # Configuração do experimento: a capacidade da IA como limite de custo está em Evolução;
    # aqui ela não limita, para medir só a integração.
    with psycopg.connect(NUCLEO_DB, autocommit=True) as c:
        c.execute("UPDATE atendentes SET capacidade = 1000000 WHERE tipo = 'ia'")
    return esperado


async def executar(cenario: str, posicao: str, aquecimento: float, medicao: float, drenagem: float,
                   semente: int) -> dict:
    chaves = preparar(cenario, posicao)
    execucao = f"{cenario}-{posicao}-{int(time.time())}"
    duracao = aquecimento + medicao
    agenda = gerar(execucao, duracao, semente=semente, frac_reenvio=0.1 if cenario == "E3b" else 0.0)
    inicio = time.time() + 2
    tarefas = [reproduzir(agenda, NUCLEO, inicio)]
    if cenario == "E6":
        tarefas.append(parar_por("broker", aquecimento + min(60, medicao / 4), 60, inicio))
    resultados = await asyncio.gather(*tarefas)
    registros, falha = resultados[0], (resultados[1] if cenario == "E6" else None)
    await asyncio.sleep(drenagem)
    metricas, linhas = julgar(registros, aquecimento, duracao, falha)
    metricas.update(cenario=cenario, posicao=posicao, chaves=chaves, aquecimento_s=aquecimento,
                    medicao_s=medicao, semente=semente, envios_agenda=len(agenda), falha=falha,
                    execucao=execucao)
    pasta = RESULTADOS / cenario / posicao
    pasta.mkdir(parents=True, exist_ok=True)
    with open(pasta / f"{execucao}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()) if linhas else ["vazio"])
        w.writeheader()
        w.writerows(linhas)
    (pasta / f"{execucao}.json").write_text(json.dumps(metricas, indent=2, ensure_ascii=False), encoding="utf-8")
    return metricas


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("cenario", choices=list(CHAVES))
    p.add_argument("posicao", choices=["ligada", "desligada"])
    p.add_argument("--aquecimento", type=float, default=420)
    p.add_argument("--medicao", type=float, default=300)
    p.add_argument("--drenagem", type=float, default=90)
    p.add_argument("--semente", type=int, default=42)
    a = p.parse_args()
    m = asyncio.run(executar(a.cenario, a.posicao, a.aquecimento, a.medicao, a.drenagem, a.semente))
    print(json.dumps({k: v for k, v in m.items() if k not in ("falha",)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
