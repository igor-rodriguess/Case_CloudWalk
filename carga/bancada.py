"""Bancada de vazão por concorrência: GET /saude e POST /mensagens.

Roda no Windows (contra localhost) ou dentro da rede do compose (contra http://nucleo:8000),
para separar o custo do encaminhamento de porta do Docker Desktop do custo do sistema.
Uso: python -m carga.bancada [url_base]
"""

import asyncio
import sys
import time
import uuid

import httpx


async def bater(n, conc, metodo, url, corpo=None):
    sem = asyncio.Semaphore(conc)
    lat, erros = [], 0
    limites = httpx.Limits(max_connections=conc, max_keepalive_connections=conc)
    async with httpx.AsyncClient(timeout=30, limits=limites) as c:
        async def um(i):
            nonlocal erros
            async with sem:
                t = time.time()
                try:
                    r = await (c.get(url) if metodo == "get" else c.post(url, json=corpo(i)))
                    if r.status_code >= 400:
                        erros += 1
                except httpx.HTTPError:
                    erros += 1
                lat.append(time.time() - t)

        t0 = time.time()
        await asyncio.gather(*(um(i) for i in range(n)))
        dt = time.time() - t0
    lat.sort()
    return {"req_s": round(n / dt, 1), "p50_s": round(lat[len(lat) // 2], 3),
            "p95_s": round(lat[int(0.95 * len(lat))], 3), "erros": erros}


def main() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    base = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    s = uuid.uuid4().hex[:6]

    def corpo(i):
        return {"canal": "chat", "marca": "infinitepay", "identificador": f"b{s}-{i}-{time.time_ns()}",
                "conteudo": "meu repasse nao caiu", "id_externo": str(uuid.uuid4())}

    for conc in (1, 10, 50, 150):
        print("saude", conc, asyncio.run(bater(1000 if conc > 1 else 100, conc, "get", f"{base}/saude")), flush=True)
    for conc in (1, 10, 50, 150):
        print("mensagens", conc, asyncio.run(bater(600 if conc > 1 else 50, conc, "post", f"{base}/mensagens", corpo)),
              flush=True)


if __name__ == "__main__":
    main()
