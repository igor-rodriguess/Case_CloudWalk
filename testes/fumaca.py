"""Teste de fumaça de ponta a ponta contra o ambiente rodando (docker compose up).

Uso: .venv\\Scripts\\python testes\\fumaca.py
Cada cenário imprime OK ou FALHOU com o motivo. Não apaga dados.
"""

import sys
import time
import uuid

import httpx

NUCLEO = "http://localhost:8000"
CANAIS = "http://localhost:8310"
MOCK = "http://localhost:8200"
http = httpx.Client(timeout=15)
falhas = []


def checar(nome: str, condicao: bool, detalhe: str = "") -> None:
    print(("OK      " if condicao else "FALHOU  ") + nome + (f"  ({detalhe})" if detalhe and not condicao else ""))
    if not condicao:
        falhas.append(nome)


def mensagem(canal, marca, ident, texto, id_externo=None):
    corpo = {"canal": canal, "marca": marca, "identificador": ident, "conteudo": texto,
             "id_externo": id_externo or str(uuid.uuid4())}
    return http.post(f"{NUCLEO}/mensagens", json=corpo).json()


def conversa(id_conversa):
    return http.get(f"{NUCLEO}/conversas/{id_conversa}").json()


def esperar(id_conversa, condicao, segundos=15):
    fim = time.time() + segundos
    while time.time() < fim:
        d = conversa(id_conversa)
        if condicao(d):
            return d
        time.sleep(0.5)
    return conversa(id_conversa)


def autores(d):
    return [m["autor_tipo"] for m in d["mensagens"]]


def atendente(nome):
    return next(a for a in http.get(f"{NUCLEO}/painel/atendentes").json() if a["nome"] == nome)


def modo_mock(modo):
    http.post(f"{MOCK}/modo", json={"modo": modo})


def main() -> None:
    sufixo = uuid.uuid4().hex[:6]
    modo_mock("normal")

    # 1. Caminho feliz: chat -> triagem -> fila -> IA -> resposta entregue no canal.
    r = mensagem("chat", "infinitepay", f"app-{sufixo}", "meu repasse não caiu", f"c1-{sufixo}")
    d = esperar(r["id_conversa"], lambda d: "ia" in autores(d))
    checar("1 caminho feliz: IA respondeu", "ia" in autores(d), str(autores(d)))
    checar("1 triagem e roteamento", d["conversa"]["categoria"] == "repasse"
           and d["conversa"]["id_fila"] == "infinitepay-geral", str(d["conversa"]["id_fila"]))
    time.sleep(1)
    entregas = http.get(f"{CANAIS}/entregas", params={"id_conversa": r["id_conversa"]}).json()
    checar("1 resposta chegou ao canal", any(e["autor"] == "ia" for e in entregas))
    tipos = [e["tipo"] for e in d["auditoria"]]
    checar("1 auditoria das decisões", {"triagem", "decisao_roteamento", "decisao_distribuicao"} <= set(tipos))

    # 2. Reenvio do mesmo id_externo pelo canal: sem efeito (inbox da entrada).
    dup = mensagem("chat", "infinitepay", f"app-{sufixo}", "meu repasse não caiu", f"c1-{sufixo}")
    checar("2 reenvio do canal deduplicado", dup["duplicada"] is True)

    # 3. Cliente pede humano: escala com resumo de reserva, volta ao roteador, vai para equipe.
    r3 = mensagem("whatsapp", "jim", f"+1555{sufixo}", "my payout did not arrive", f"w1-{sufixo}")
    esperar(r3["id_conversa"], lambda d: "ia" in autores(d))
    mensagem("whatsapp", "jim", f"+1555{sufixo}", "I want to talk to a human agent", f"w2-{sufixo}")
    d3 = esperar(r3["id_conversa"], lambda d: d["conversa"]["estado"] == "com_humano")
    checar("3 escala chegou a um humano", d3["conversa"]["estado"] == "com_humano", d3["conversa"]["estado"])
    checar("3 fila de escalas da marca", d3["conversa"]["id_fila"] == "escalas-jim", str(d3["conversa"]["id_fila"]))
    checar("3 resumo com fontes", bool(d3["escalas"]) and bool(d3["escalas"][-1]["fontes"]))

    # 4. Analista responde e devolve para a IA; a IA volta a atender com a nota.
    id_humano = d3["conversa"]["id_atendente"]
    r4 = http.post(f"{NUCLEO}/painel/conversas/{r3['id_conversa']}/responder",
                   json={"id_atendente": id_humano, "conteudo": "Hi, I'm checking it now."})
    checar("4 analista respondeu", r4.status_code == 200, r4.text)
    r4b = http.post(f"{NUCLEO}/painel/conversas/{r3['id_conversa']}/devolver",
                    json={"id_atendente": id_humano, "nota": "Payout reprocessed."})
    checar("4 devolveu para a IA", r4b.status_code == 200, r4b.text)
    d4 = esperar(r3["id_conversa"], lambda d: autores(d)[-1] == "ia")
    checar("4 IA respondeu depois da devolução", autores(d4)[-1] == "ia", str(autores(d4)))

    # 5. Fencing: analista que não é o dono não consegue responder.
    outro = atendente("Ana Souza")["id"]
    r5 = http.post(f"{NUCLEO}/painel/conversas/{r3['id_conversa']}/responder",
                   json={"id_atendente": outro, "conteudo": "intrusa"})
    checar("5 só o dono responde", r5.status_code == 409, str(r5.status_code))

    # 6. Agente lento: o prazo (contado do ack do broker) vence e a conversa escala por timeout.
    print("        (cenário 6 espera o timeout do agente, ~35 s)")
    modo_mock("lento")
    r6 = mensagem("chat", "infinitepay", f"app6-{sufixo}", "minha maquininha parou", f"c6-{sufixo}")
    d6 = esperar(r6["id_conversa"], lambda d: any(e["motivo"] == "timeout_agente" for e in d["escalas"]), 60)
    checar("6 timeout escalou", any(e["motivo"] == "timeout_agente" for e in d6["escalas"]),
           str([e["motivo"] for e in d6["escalas"]]))
    modo_mock("normal")
    time.sleep(8)  # a resposta atrasada chega depois da escala
    d6b = conversa(r6["id_conversa"])
    descartes = [e for e in d6b["auditoria"] if e["tipo"] == "evento_descartado"]
    checar("6 resposta atrasada descartada pelo fencing", bool(descartes)
           and "ia" not in autores(d6b), str(autores(d6b)))

    # 7. Reconciliação: nenhuma duplicata nem resposta fora de dono.
    rec = http.get(f"{NUCLEO}/supervisor/reconciliacao").json()
    checar("7 sem resposta duplicada (I3)", rec["I3_resposta_duplicada"]["total"] == 0)
    checar("7 sem resposta fora de dono (I4)", rec["I4_resposta_fora_de_dono"]["total"] == 0)
    checar("7 sem conversa aberta duplicada (I6)", rec["I6_conversa_aberta_duplicada"]["total"] == 0)
    checar("7 capacidade consistente (I5)", rec["I5_capacidade"]["total"] == 0)

    print()
    print("tudo certo" if not falhas else f"{len(falhas)} falha(s): {falhas}")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
