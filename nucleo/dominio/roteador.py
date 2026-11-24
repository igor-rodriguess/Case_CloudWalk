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


def filas_inalcancaveis(regras: dict) -> list[str]:
    """Filas ativas que nenhum atendimento alcança (ficam atrás de outra que casa antes).

    Exata: percorre todas as combinações dos campos. Os de domínio fechado usam o domínio
    inteiro; os abertos (categoria, segmento) usam os valores citados nas regras mais um
    valor que nenhuma regra cita. Com os campos de hoje, poucos milhares de combinações.
    """
    from itertools import product

    filas = [f for f in regras.get("filas") or [] if f.get("ativa", True) and f.get("id") != regras.get("fila_padrao")]
    dominios: dict[str, list] = {c: sorted(v, key=str) for c, v in VALORES.items()}
    for campo in CAMPOS - set(VALORES):
        citados = set()
        for f in filas:
            cond = f.get("condicoes") or {}
            for c in cond.get("todas", cond.get("qualquer", [])):
                if c.get("campo") == campo:
                    v = c.get("valor")
                    citados.update(v if isinstance(v, list) else [v])
        dominios[campo] = sorted(citados, key=str) + ["__outro__"]
    campos = sorted(dominios)
    alcancadas = set()
    for valores in product(*(dominios[c] for c in campos)):
        atendimento = dict(zip(campos, valores))
        for f in sorted(filas, key=lambda x: x.get("ordem", 0)):
            if condicoes_que_casam(f.get("condicoes") or {}, atendimento) is not None:
                alcancadas.add(f["id"])
                break
        if len(alcancadas) == len(filas):
            break
    return [f["id"] for f in filas if f["id"] not in alcancadas]


def _slas_sobrepostos(f: dict) -> list[str]:
    """`slas` de uma fila: [{"prioridade": 1|2|3|None, "limite_s": int}]; None vale para todas."""
    erros, vistas = [], []
    for s in f.get("slas") or []:
        p, limite = s.get("prioridade"), s.get("limite_s")
        if p not in (None, 1, 2, 3):
            erros.append(f"{f.get('id')}: SLA com prioridade inválida {p}")
        if not isinstance(limite, int) or limite <= 0:
            erros.append(f"{f.get('id')}: SLA precisa de limite_s inteiro positivo")
        cobre = {1, 2, 3} if p is None else {p}
        if any(cobre & v for v in vistas):
            erros.append(f"{f.get('id')}: SLAs sobrepostos para a prioridade {sorted(cobre)}")
        vistas.append(cobre)
    return erros


def validar(regras: dict, grupos_existentes: set[tuple[str, str]],
            grupos_elegiveis: set[tuple[str, str]] | None = None) -> ResultadoValidacao:
    """`grupos_elegiveis`: grupos com pelo menos um atendente com capacidade. Sem ele, só se
    confere que o grupo existe."""
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
        if (grupos_elegiveis is not None and f.get("ativa", True) and f.get("atendentes")
                and not any((g.get("tipo"), g.get("id")) in grupos_elegiveis for g in f["atendentes"])):
            r.erros.append(f"{nome}: nenhum grupo tem atendente elegível (com capacidade)")
        r.erros.extend(_slas_sobrepostos(f))
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
    if r.valida:  # só roda o roteador sobre regras bem formadas
        for fid in filas_inalcancaveis(regras):
            r.erros.append(f"{fid}: fila inalcançável (outra fila anterior casa todos os atendimentos dela)")
    return r
