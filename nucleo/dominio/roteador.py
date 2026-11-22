"""Roteador de filas (modelo Zendesk): filas testadas em ordem, a primeira que casa leva,
sem casamento vai para a fila padrão. Função pura: não lê banco nem relógio, então uma
decisão gravada pode ser reproduzida e o simulador sai de graça.
"""

from dataclasses import dataclass, field
from typing import Any

CAMPOS = {"marca", "canal", "categoria", "prioridade", "idioma", "segmento_cliente", "sentimento", "origem"}
OPERADORES = {"igual", "diferente", "em"}
VALORES = {
    "marca": {"infinitepay", "jim"},
    "canal": {"chat", "whatsapp", "email"},
    "prioridade": {1, 2, 3},
    "idioma": {"pt", "en"},
    "sentimento": {"neutro", "negativo"},
    "origem": {"cliente", "escalado"},
}
POLITICAS_DISJUNTOR = {"reter", "transbordar"}


@dataclass(frozen=True)
class DecisaoRoteamento:
    fila: str
    regra: Any
    versao: int


@dataclass
class ResultadoValidacao:
    erros: list[str] = field(default_factory=list)

    @property
    def valida(self) -> bool:
        return not self.erros


def _casa(condicao: dict, atendimento: dict) -> bool:
    valor = atendimento.get(condicao["campo"])
    alvo = condicao["valor"]
    if condicao["operador"] == "igual":
        return valor == alvo
    if condicao["operador"] == "diferente":
        return valor != alvo
    return valor in alvo  # "em"


def condicoes_que_casam(condicoes: dict, atendimento: dict):
    """Devolve a lista de condições que casaram, ou None se a fila não casa."""
    if not condicoes:
        return []
    if "todas" in condicoes:
        lista = condicoes["todas"]
        return lista if all(_casa(c, atendimento) for c in lista) else None
    lista = condicoes.get("qualquer", [])
    casadas = [c for c in lista if _casa(c, atendimento)]
    return casadas or None


def rotear(atendimento: dict, regras: dict, versao: int) -> DecisaoRoteamento:
    for fila in sorted(regras["filas"], key=lambda f: f["ordem"]):
        if not fila.get("ativa", True) or fila["id"] == regras["fila_padrao"]:
            continue
        casadas = condicoes_que_casam(fila.get("condicoes") or {}, atendimento)
        if casadas is not None:
            return DecisaoRoteamento(fila=fila["id"], regra=casadas, versao=versao)
    return DecisaoRoteamento(fila=regras["fila_padrao"], regra="fila_padrao", versao=versao)


def validar(regras: dict, grupos_existentes: set[tuple[str, str]]) -> ResultadoValidacao:
    r = ResultadoValidacao()
    filas = regras.get("filas") or []
    ids = [f.get("id") for f in filas]
    if len(ids) != len(set(ids)):
        r.erros.append("ids de fila repetidos")
    ordens = [f.get("ordem") for f in filas]
    if len(ordens) != len(set(ordens)):
        r.erros.append("ordem repetida entre filas")
    if regras.get("fila_padrao") not in ids:
        r.erros.append("fila_padrao não existe entre as filas")
    for f in filas:
        nome = f.get("id", "?")
        if f.get("prioridade") not in (1, 2, 3):
            r.erros.append(f"{nome}: prioridade deve ser 1, 2 ou 3")
        if f.get("ao_abrir_disjuntor", "reter") not in POLITICAS_DISJUNTOR:
            r.erros.append(f"{nome}: ao_abrir_disjuntor deve ser reter ou transbordar")
        if not f.get("atendentes"):
            r.erros.append(f"{nome}: sem grupos de atendentes")
        for g in f.get("atendentes") or []:
            if (g.get("tipo"), g.get("id")) not in grupos_existentes:
                r.erros.append(f"{nome}: grupo {g.get('tipo')}:{g.get('id')} não existe")
        cond = f.get("condicoes") or {}
        lista = cond.get("todas", cond.get("qualquer", []))
        for c in lista:
            campo, op, valor = c.get("campo"), c.get("operador"), c.get("valor")
            if campo not in CAMPOS:
                r.erros.append(f"{nome}: campo desconhecido {campo}")
                continue
            if op not in OPERADORES:
                r.erros.append(f"{nome}: operador desconhecido {op}")
                continue
            if campo in VALORES:
                valores = valor if op == "em" else [valor]
                if op == "em" and not isinstance(valor, list):
                    r.erros.append(f"{nome}: operador 'em' exige lista")
                    continue
                invalidos = [v for v in valores if v not in VALORES[campo]]
                if invalidos:
                    r.erros.append(f"{nome}: valor inválido para {campo}: {invalidos}")
    return r
