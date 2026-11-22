"""Roteiro de demonstração automatizado (reserva para a apresentação; docs/arquitetura.md 19.4).

Cada momento imprime o que está acontecendo e espera Enter para seguir, para acompanhar com
o front aberto. Use --sem-pausa para rodar direto. Precisa do ambiente no ar.
Uso: .venv\\Scripts\\python -m carga.demo
"""

import argparse
import subprocess
import time
import uuid
from pathlib import Path

import httpx

NUCLEO, MOCK, CANAIS = "http://localhost:8000", "http://localhost:8200", "http://localhost:8310"
RAIZ = Path(__file__).resolve().parent.parent
http = httpx.Client(timeout=15)
PAUSA = True


def titulo(texto: str) -> None:
    print(f"\n=== {texto} ===")
    if PAUSA:
        input("(Enter para seguir) ")


def enviar(canal, marca, ident, texto, id_externo=None):
    corpo = {"canal": canal, "marca": marca, "identificador": ident, "conteudo": texto,
             "id_externo": id_externo or str(uuid.uuid4())}
    return http.post(f"{NUCLEO}/mensagens", json=corpo).json()


def mostrar(id_conversa, espera=4):
    time.sleep(espera)
    d = http.get(f"{NUCLEO}/conversas/{id_conversa}").json()
    c = d["conversa"]
    print(f"  estado={c['estado']} fila={c['id_fila']} atendente={c.get('atendente')}")
    for m in d["mensagens"]:
        print(f"  [{m['autor_tipo']}] {m['conteudo']}")
    return d


def main() -> None:
    global PAUSA
    p = argparse.ArgumentParser()
    p.add_argument("--sem-pausa", action="store_true")
    PAUSA = not p.parse_args().sem_pausa
    s = uuid.uuid4().hex[:4]
    http.post(f"{MOCK}/modo", json={"modo": "normal"})

    titulo("1. Três canais, duas marcas: a triagem e o roteador escolhem a fila, a IA atende")
    a = enviar("chat", "infinitepay", f"demo-app-{s}", "meu repasse não caiu")
    b = enviar("whatsapp", "jim", f"+1555{s}", "my payout did not arrive")
    c = enviar("email", "infinitepay", f"loja{s}@exemplo.com", "acho que caí num golpe, não reconheço uma venda")
    for r in (a, b, c):
        mostrar(r["id_conversa"], 2)
    print("  (a terceira é fraude: a fila de fraude é só de humanos)")

    titulo("2. Reenvio do mesmo id_externo pelo canal: deduplicado pela inbox")
    ide = f"demo-dup-{s}"
    print("  primeira:", enviar("chat", "infinitepay", f"demo-app-{s}", "e agora?", ide)["duplicada"])
    print("  reenvio: ", enviar("chat", "infinitepay", f"demo-app-{s}", "e agora?", ide)["duplicada"])

    titulo("3. Cliente pede humano: escala com resumo e fontes, volta ao roteador, vai para a equipe")
    enviar("whatsapp", "jim", f"+1555{s}", "I want to talk to a human agent")
    d = mostrar(b["id_conversa"], 5)
    if d["escalas"]:
        e = d["escalas"][-1]
        print(f"  escala: motivo={e['motivo']} reserva={e['reserva']} fontes={len(e['fontes'])}")

    titulo("4. Broker fora por 30 s: a outbox segura, retenta e entrega depois (zero perda)")
    subprocess.run(["docker", "compose", "stop", "broker"], cwd=RAIZ, capture_output=True)
    r = enviar("chat", "infinitepay", f"demo-b-{s}", "quando cai o dinheiro da venda?")
    time.sleep(3)
    print("  outbox:", http.get(f"{NUCLEO}/supervisor/metricas").json()["outbox"])
    time.sleep(27)
    subprocess.run(["docker", "compose", "start", "broker"], cwd=RAIZ, capture_output=True)
    print("  broker de volta; aguardando a retentativa (pode levar até ~1 min pelo backoff)...")
    for _ in range(90):
        d = http.get(f"{NUCLEO}/conversas/{r['id_conversa']}").json()
        if any(m["autor_tipo"] == "ia" for m in d["mensagens"]):
            break
        time.sleep(1)
    mostrar(r["id_conversa"], 0)

    titulo("5. Agente lento: o prazo vence, escala por timeout e a resposta atrasada é descartada")
    http.post(f"{MOCK}/modo", json={"modo": "lento"})
    r = enviar("chat", "infinitepay", f"demo-l-{s}", "a maquininha não liga")
    print("  aguardando o prazo de 30 s contado do ack do broker...")
    mostrar(r["id_conversa"], 38)
    http.post(f"{MOCK}/modo", json={"modo": "normal"})
    time.sleep(8)
    d = http.get(f"{NUCLEO}/conversas/{r['id_conversa']}").json()
    descartes = [x for x in d["auditoria"] if x["tipo"] == "evento_descartado"]
    print(f"  respostas atrasadas descartadas pelo fencing: {len(descartes)}")

    titulo("6. Operação muda a fila sem deploy: nova versão, validação, ativação, rollback")
    ativa = http.get(f"{NUCLEO}/filas/ativa").json()
    regras = ativa["filas"]
    regras["filas"].insert(0, {"id": "jim-email", "nome": "JIM - E-mail", "ordem": 0, "prioridade": 2, "ativa": True,
                               "condicoes": {"todas": [{"campo": "marca", "operador": "igual", "valor": "jim"},
                                                       {"campo": "canal", "operador": "igual", "valor": "email"}]},
                               "atendentes": [{"tipo": "equipe", "id": "support-us"}]})
    nova = http.post(f"{NUCLEO}/filas/versoes", json={"regras": regras, "criada_por": "demo"}).json()
    print("  nova versão:", nova, "->", http.post(f"{NUCLEO}/filas/versoes/{nova['numero']}/ativar").json())
    print("  simulação:", http.post(f"{NUCLEO}/filas/simular",
                                    json={"atendimento": {"marca": "jim", "canal": "email", "origem": "cliente"}}).json())
    print("  rollback:", http.post(f"{NUCLEO}/filas/versoes/{ativa['numero']}/ativar").json())

    titulo("7. Reconciliação: invariantes conferidas")
    for nome, v in http.get(f"{NUCLEO}/supervisor/reconciliacao").json().items():
        print(f"  {nome}: {v['total']}")


if __name__ == "__main__":
    main()
