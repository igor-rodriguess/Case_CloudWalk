"""Testes de carga completos (docs/testes-de-carga.md): T1 rampa, T2 rajada, T3 leitura do front.

Uso (ambiente no ar, de preferência com banco limpo):
  .venv\\Scripts\\python -m carga.completo [--so T1 T2 T3]
Grava resultados/carga/<teste>-<instante>.json e imprime um resumo por teste.
"""

import argparse
import asyncio
import json
import random
import subprocess
import sys
import threading
import time
from collections import defaultdict
from statistics import quantiles

import httpx
import psycopg

from carga.agenda import Envio, gerar
from carga.falhas import RAIZ
from carga.gerador import reproduzir
from carga.juiz import NUCLEO_DB, julgar
from carga.rodar import NUCLEO, preparar

SAIDA = RAIZ / "resultados" / "carga"


def pct(valores, p):
    valores = sorted(valores)
    if not valores:
        return None
    if len(valores) < 20:
        return round(valores[-1], 3)
    return round(quantiles(valores, n=100)[p - 1], 3)


class AmostradorDocker:
    """Lê `docker stats` a cada 10 s para apontar o gargalo por contêiner."""

    def __init__(self):
        self.amostras: list[tuple[float, str, float]] = []
        self._parar = threading.Event()
        self._fio = threading.Thread(target=self._laco, daemon=True)

    def _laco(self):
        while not self._parar.is_set():
            try:
                r = subprocess.run(["docker", "stats", "--no-stream", "--format", "{{.Name}};{{.CPUPerc}}"],
                                   capture_output=True, text=True)
            except FileNotFoundError:
                return  # dentro do contêiner não há docker; a CPU é amostrada pelo host (testes-de-carga.md)
            agora = time.time()
            for linha in r.stdout.splitlines():
                nome, _, cpu = linha.partition(";")
                if nome.startswith("helpdesk-"):
                    try:
                        self.amostras.append((agora, nome.removeprefix("helpdesk-").rsplit("-", 1)[0],
                                              float(cpu.strip("%"))))
                    except ValueError:
                        pass
            self._parar.wait(10)

    def __enter__(self):
        self._fio.start()
        return self

    def __exit__(self, *exc):
        self._parar.set()
        self._fio.join(timeout=30)

    def media(self, ini: float, fim: float) -> dict:
        por = defaultdict(list)
        for t, nome, cpu in self.amostras:
            if ini <= t <= fim:
                por[nome].append(cpu)
        return {n: round(sum(v) / len(v), 1) for n, v in sorted(por.items())}


def esperar_drenar(maximo_s: float) -> float:
    """Espera a outbox esvaziar e o número de mensagens parar de crescer por 20 s."""
    inicio, ultimo, parado_desde = time.time(), -1, time.time()
    with psycopg.connect(NUCLEO_DB, autocommit=True) as c:
        while time.time() - inicio < maximo_s:
            pend = c.execute("SELECT count(*) FROM outbox WHERE status IN ('pendente','enviando')").fetchone()[0]
            total = c.execute("SELECT count(*) FROM mensagens").fetchone()[0]
            if total != ultimo:
                ultimo, parado_desde = total, time.time()
            if pend == 0 and time.time() - parado_desde >= 20:
                break
            time.sleep(2)
    return round(time.time() - inicio, 1)


def salvar(nome: str, dados: dict) -> None:
    SAIDA.mkdir(parents=True, exist_ok=True)
    (SAIDA / f"{nome}-{int(time.time())}.json").write_text(json.dumps(dados, indent=2, ensure_ascii=False),
                                                           encoding="utf-8")


# ---------------------------------------------------------------- T1 rampa
async def t1_rampa(degraus=(40, 60, 80, 100, 120, 140, 160, 200), duracao=150.0, medir_ultimos=100.0) -> dict:
    preparar("E1", "ligada")
    execucao = f"T1-{int(time.time())}"
    agenda: list[Envio] = []
    for i, total in enumerate(degraus):
        conversas_por_s = total / 2 / 6  # metade do total é do cliente; 6 mensagens por conversa
        parte = gerar(f"{execucao}-s{i}", duracao, semente=42 + i, conversas_por_s=conversas_por_s, intervalo_s=10)
        agenda += [Envio(e.t + i * duracao, e.conversa, e.k, e.id_externo, e.marca, e.canal, e.texto) for e in parte]
    agenda.sort(key=lambda e: e.t)
    inicio = time.time() + 2
    with AmostradorDocker() as docker:
        registros = await reproduzir(agenda, NUCLEO, inicio)
        drenagem = esperar_drenar(600)
    resultado = {"teste": "T1 rampa", "execucao": execucao, "inicio_epoch": inicio, "duracao_degrau_s": duracao,
                 "drenagem_s": drenagem, "degraus": []}
    for i, total in enumerate(degraus):
        ini, fim = i * duracao + (duracao - medir_ultimos), (i + 1) * duracao
        prefixo = f"{execucao}-s{i}-"
        regs = [r for r in registros if r.envio.conversa.startswith(prefixo)]
        janela = [r for r in regs if ini <= r.envio.t < fim]
        m, _ = julgar(regs, ini, fim)
        resultado["degraus"].append({
            "msg_s_total_alvo": total,
            "msg_s_cliente_oferecida": round(len(janela) / medir_ultimos, 1),
            "msg_s_cliente_aceita": round(sum(1 for r in janela if 200 <= r.status < 300) / medir_ultimos, 1),
            "post_p95_s": pct([r.latencia_req_s for r in janela if r.status], 95),
            **{k: m[k] for k in ("enviadas", "recusadas", "perdidas", "duplicadas", "escaladas",
                                 "espera_p95_s", "p95_interna_s")},
            "cpu_medio_pct": docker.media(inicio + ini, inicio + fim),
        })
    salvar("T1-rampa", resultado)
    return resultado


# ---------------------------------------------------------------- T2 rajada
async def t2_rajada(n=20_000, clientes=5_000, nome="T2-rajada", taxa: float | None = None) -> dict:
    """Sem `taxa`, envia o mais rápido possível. Com `taxa` (msg/s do cliente), a mensagem i sai
    no instante i / taxa; as de um mesmo cliente ficam `clientes / taxa` segundos uma da outra."""
    preparar("E1", "ligada")
    execucao = f"T2-{int(time.time())}"
    rnd = random.Random(7)
    from carga.agenda import TEXTOS_EN, TEXTOS_PT

    agenda = []
    for i in range(n):
        cliente, k = i % clientes, i // clientes
        marca = "jim" if cliente % 5 == 0 else "infinitepay"
        texto = rnd.choice(TEXTOS_EN if marca == "jim" else TEXTOS_PT)
        agenda.append(Envio(i / taxa if taxa else 0.0, f"{execucao}-c{cliente}", k, f"{execucao}-c{cliente}-m{k}", marca, "chat", texto))
    with AmostradorDocker() as docker:
        t0 = time.time()
        registros = await reproduzir(agenda, NUCLEO, t0)
        t_envio = time.time() - t0
        drenagem = esperar_drenar(1200)
        t_fim = time.time()
    m, linhas = julgar(registros, -1, float("inf"))  # todas; o envio cadenciado vai até n / taxa
    # Mensagens quase simultâneas do mesmo cliente podem ser respondidas juntas (o agente recebe o
    # histórico). A perda que importa é a da conversa: a última mensagem de cada cliente sem resposta.
    ultima = {}
    for linha in linhas:
        k = int(linha["id_externo"].rsplit("-m", 1)[1])
        chave = linha["id_externo"].rsplit("-m", 1)[0]
        if chave not in ultima or k > ultima[chave][0]:
            ultima[chave] = (k, linha["desfecho"])
    conversas_sem_resposta = sum(1 for _k, d in ultima.values() if d in ("perdida", "recusada"))
    status = defaultdict(int)
    for r in registros:
        status[str(r.status)] += 1
    resultado = {
        "teste": nome, "execucao": execucao, "inicio_epoch": t0, "fim_epoch": t_fim,
        "mensagens": n, "clientes": clientes, "taxa_oferecida_msg_s": taxa,
        "envio_s": round(t_envio, 1), "vazao_entrada_msg_s": round(n / t_envio, 1),
        "post_p50_s": pct([r.latencia_req_s for r in registros if r.status], 50),
        "post_p95_s": pct([r.latencia_req_s for r in registros if r.status], 95),
        "post_p99_s": pct([r.latencia_req_s for r in registros if r.status], 99),
        "status_http": dict(status), "drenagem_s": drenagem,
        "ate_ultima_resposta_s": round(t_fim - t0, 1),
        "conversas": len(ultima), "conversas_sem_resposta": conversas_sem_resposta,
        "mensagens_sem_resposta_propria": m["perdidas"],
        **{k: m[k] for k in ("enviadas", "recusadas", "perdidas", "duplicadas", "escaladas", "respondidas",
                             "espera_p95_s", "p95_interna_s")},
        "cpu_medio_pct": docker.media(t0, t_fim),
    }
    salvar(nome, resultado)
    return resultado


# ---------------------------------------------------------------- T3 leitura do front
TELAS = ["/painel/fila?marca=infinitepay", "/conversas?estado=com_ia&limite=50",
         "/supervisor/metricas", "/filas/ativa"]


async def t3_leitura(clientes=100, duracao=60.0, fundo_msg_s=50) -> dict:
    preparar("E1", "ligada")
    execucao = f"T3-{int(time.time())}"
    agenda = gerar(execucao, duracao + 60, semente=3, conversas_por_s=fundo_msg_s / 2 / 6, intervalo_s=10)
    lat = defaultdict(list)
    erros = defaultdict(int)
    inicio = time.time() + 2
    fim_leitura = inicio + 60 + duracao  # 60 s de aquecimento do fundo

    async def leitor(cliente: httpx.AsyncClient, atraso: float):
        await asyncio.sleep(max(0.0, inicio + 60 - time.time()) + atraso)
        while time.time() < fim_leitura:
            ciclo = time.time()
            for tela in TELAS:
                t0 = time.time()
                try:
                    r = await cliente.get(f"{NUCLEO}{tela}")
                    if r.status_code >= 400:
                        erros[tela] += 1
                except httpx.HTTPError:
                    erros[tela] += 1
                lat[tela].append(time.time() - t0)
            await asyncio.sleep(max(0.0, 2 - (time.time() - ciclo)))

    limites = httpx.Limits(max_connections=clientes, max_keepalive_connections=clientes)
    async with httpx.AsyncClient(timeout=15, limits=limites) as cliente:
        fundo = asyncio.create_task(reproduzir(agenda, NUCLEO, inicio))
        await asyncio.gather(*(leitor(cliente, i * 2 / clientes) for i in range(clientes)))
        await fundo
    resultado = {
        "teste": "T3 leitura do front", "execucao": execucao, "clientes": clientes, "duracao_s": duracao,
        "fundo_msg_s_total": fundo_msg_s,
        "telas": {t: {"requisicoes": len(lat[t]), "erros": erros[t], "p50_s": pct(lat[t], 50),
                      "p95_s": pct(lat[t], 95), "p99_s": pct(lat[t], 99)} for t in TELAS},
    }
    salvar("T3-leitura", resultado)
    return resultado


def reconciliacao() -> dict:
    r = httpx.get(f"{NUCLEO}/supervisor/reconciliacao", timeout=300).json()
    resultado = {"teste": "reconciliacao", "invariantes": {k: v["total"] for k, v in r.items()}}
    salvar("reconciliacao", resultado)
    return resultado


def main() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    p = argparse.ArgumentParser()
    p.add_argument("--so", nargs="*", default=["T1", "T2", "T3", "R"])
    p.add_argument("--taxa", type=float, default=25.0, help="msg/s do cliente no T4c")
    a = p.parse_args()
    if "T1" in a.so:
        print(json.dumps(asyncio.run(t1_rampa()), ensure_ascii=False), flush=True)
    if "T2" in a.so:
        print(json.dumps(asyncio.run(t2_rajada()), ensure_ascii=False), flush=True)
    if "T3" in a.so:
        print(json.dumps(asyncio.run(t3_leitura()), ensure_ascii=False), flush=True)
    if "T4" in a.so:  # volume: 100 mil mensagens de 20 mil clientes
        print(json.dumps(asyncio.run(t2_rajada(n=100_000, clientes=20_000, nome="T4-volume")),
                         ensure_ascii=False), flush=True)
    if "T4c" in a.so:  # o mesmo volume em cadência sustentável (a carga do experimento, 50 msg/s totais)
        print(json.dumps(asyncio.run(t2_rajada(n=100_000, clientes=20_000, nome="T4c-volume-cadenciado",
                                               taxa=a.taxa)), ensure_ascii=False), flush=True)
    if "R" in a.so:
        print(json.dumps(reconciliacao(), ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
