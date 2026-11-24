"""Testes das funções puras do domínio: triagem, roteador, validação e escolha do atendente."""

import uuid

from nucleo.dominio.distribuicao import Candidato, escolher
from nucleo.dominio.roteador import rotear, validar
from nucleo.dominio.triagem import pede_humano, triar
from nucleo.infra.seed import FILAS_V1

GRUPOS = {("ia", "ia-infinitepay"), ("ia", "ia-jim"), ("equipe", "suporte-br"),
          ("equipe", "credito-br"), ("equipe", "support-us")}


def atendimento(**kw):
    base = {"marca": "infinitepay", "canal": "chat", "categoria": "geral", "prioridade": 1,
            "idioma": "pt", "sentimento": "neutro", "origem": "cliente", "segmento_cliente": "pme"}
    base.update(kw)
    return base


class TestTriagem:
    def test_categorias(self):
        assert triar("meu repasse não caiu", "infinitepay").categoria == "repasse"
        assert triar("quero um empréstimo", "infinitepay").categoria == "credito"
        assert triar("my payout did not arrive", "jim").categoria == "repasse"

    def test_fraude_e_urgencia_sobem_prioridade(self):
        assert triar("acho que caí num golpe", "infinitepay").prioridade == 3
        assert triar("minha conta está bloqueada", "infinitepay").prioridade == 3

    def test_sentimento_e_idioma(self):
        t = triar("isso é um absurdo!!!", "jim")
        assert t.sentimento == "negativo" and t.idioma == "en"

    def test_pedido_de_humano(self):
        assert pede_humano("quero falar com um atendente")
        assert not pede_humano("obrigado, resolveu")


class TestRoteador:
    def test_primeira_fila_que_casa_leva(self):
        d = rotear(atendimento(categoria="credito"), FILAS_V1, 1)
        assert d.fila == "infinitepay-credito" and d.versao == 1

    def test_escalada_vai_para_fila_de_escalas(self):
        assert rotear(atendimento(origem="escalado"), FILAS_V1, 1).fila == "escalas-infinitepay"
        assert rotear(atendimento(marca="jim", origem="escalado"), FILAS_V1, 1).fila == "escalas-jim"

    def test_fraude_vai_direto_para_humanos(self):
        assert rotear(atendimento(categoria="fraude"), FILAS_V1, 1).fila == "infinitepay-fraude"

    def test_sem_casamento_vai_para_padrao(self):
        regras = {"fila_padrao": "padrao", "filas": [
            {"id": "jim", "ordem": 1, "condicoes": {"todas": [{"campo": "marca", "operador": "igual", "valor": "jim"}]}},
            {"id": "padrao", "ordem": 2, "condicoes": {}}]}
        d = rotear(atendimento(), regras, 7)
        assert d.fila == "padrao" and d.regra == "fila_padrao"

    def test_operador_em_e_qualquer(self):
        regras = {"fila_padrao": "p", "filas": [
            {"id": "x", "ordem": 1, "condicoes": {"qualquer": [
                {"campo": "canal", "operador": "em", "valor": ["whatsapp", "email"]},
                {"campo": "sentimento", "operador": "igual", "valor": "negativo"}]}},
            {"id": "p", "ordem": 2, "condicoes": {}}]}
        assert rotear(atendimento(canal="email"), regras, 1).fila == "x"
        assert rotear(atendimento(sentimento="negativo"), regras, 1).fila == "x"
        assert rotear(atendimento(), regras, 1).fila == "p"

    def test_reproduzir_decisao_e_deterministico(self):
        a = atendimento(categoria="credito", canal="whatsapp")
        assert rotear(a, FILAS_V1, 1) == rotear(a, FILAS_V1, 1)


class TestValidacao:
    def test_regras_do_seed_sao_validas(self):
        assert validar(FILAS_V1, GRUPOS).valida

    def test_erros_detectados(self):
        ruim = {"fila_padrao": "nao-existe", "filas": [
            {"id": "a", "ordem": 1, "prioridade": 5, "atendentes": [{"tipo": "equipe", "id": "fantasma"}],
             "condicoes": {"todas": [{"campo": "marca", "operador": "igual", "valor": "JIM"},
                                     {"campo": "cor", "operador": "igual", "valor": "azul"}]}},
            {"id": "a", "ordem": 1, "prioridade": 1, "atendentes": [{"tipo": "equipe", "id": "suporte-br"}]}]}
        erros = " ".join(validar(ruim, GRUPOS).erros)
        for trecho in ("repetidos", "ordem repetida", "fila_padrao", "prioridade", "fantasma", "JIM", "cor"):
            assert trecho in erros

    def _regras(self, *filas):
        base = {"prioridade": 1, "atendentes": [{"tipo": "equipe", "id": "suporte-br"}]}
        return {"fila_padrao": "p", "filas": [*({**base, **f} for f in filas), {**base, "id": "p", "ordem": 99}]}

    def test_fila_inalcancavel_atras_de_outra_mais_ampla(self):
        marca_ip = {"todas": [{"campo": "marca", "operador": "igual", "valor": "infinitepay"}]}
        credito_ip = {"todas": [{"campo": "marca", "operador": "igual", "valor": "infinitepay"},
                                {"campo": "categoria", "operador": "igual", "valor": "credito"}]}
        ruim = self._regras({"id": "ip", "ordem": 1, "condicoes": marca_ip},
                            {"id": "ip-credito", "ordem": 2, "condicoes": credito_ip})
        assert any("ip-credito: fila inalcançável" in e for e in validar(ruim, GRUPOS).erros)
        boa = self._regras({"id": "ip-credito", "ordem": 1, "condicoes": credito_ip},
                           {"id": "ip", "ordem": 2, "condicoes": marca_ip})
        assert validar(boa, GRUPOS).valida

    def test_qualquer_vazio_nunca_casa(self):
        ruim = self._regras({"id": "x", "ordem": 1, "condicoes": {"qualquer": []}})
        assert any("x: fila inalcançável" in e for e in validar(ruim, GRUPOS).erros)

    def test_fila_sem_atendente_elegivel(self):
        regras = self._regras({"id": "x", "ordem": 1, "atendentes": [{"tipo": "equipe", "id": "credito-br"}],
                               "condicoes": {"todas": [{"campo": "categoria", "operador": "igual", "valor": "credito"}]}})
        elegiveis = GRUPOS - {("equipe", "credito-br")}
        assert any("x: nenhum grupo tem atendente elegível" in e for e in validar(regras, GRUPOS, elegiveis).erros)
        assert validar(regras, GRUPOS, GRUPOS).valida

    def test_slas_sobrepostos(self):
        cond = {"todas": [{"campo": "canal", "operador": "igual", "valor": "email"}]}
        ruim = self._regras({"id": "x", "ordem": 1, "condicoes": cond,
                             "slas": [{"prioridade": None, "limite_s": 600}, {"prioridade": 3, "limite_s": 60}]})
        assert any("SLAs sobrepostos" in e for e in validar(ruim, GRUPOS).erros)
        boa = self._regras({"id": "x", "ordem": 1, "condicoes": cond,
                            "slas": [{"prioridade": 3, "limite_s": 60}, {"prioridade": 1, "limite_s": 600}]})
        assert validar(boa, GRUPOS).valida

    def test_catch_all_e_obrigatoria(self):
        sem_padrao = self._regras({"id": "x", "ordem": 1, "condicoes": {}})
        sem_padrao["fila_padrao"] = "nenhuma"
        assert any("fila_padrao não existe" in e for e in validar(sem_padrao, GRUPOS).erros)


class TestEscolha:
    def c(self, grupo, ativas, capacidade=3, tipo="humano", disponivel=True):
        return Candidato(uuid.uuid4(), tipo, grupo, disponivel, ativas, capacidade)

    def test_preferencia_do_grupo_vem_antes_da_ocupacao(self):
        ia = self.c(0, 800, 2000, "ia")
        humano = self.c(1, 0)
        assert escolher([ia, humano]).id == ia.id  # AI first

    def test_menor_ocupacao_dentro_do_grupo(self):
        a, b = self.c(0, 2), self.c(0, 1)
        assert escolher([a, b]).id == b.id

    def test_lotado_ou_indisponivel_fica_de_fora(self):
        assert escolher([self.c(0, 3), self.c(0, 0, disponivel=False)]).id is None
        cheio, livre = self.c(0, 3), self.c(1, 0)
        assert escolher([cheio, livre]).id == livre.id


class TestSla:
    def test_pausar_e_retomar_nao_alteram_o_acumulado(self):
        from datetime import datetime, timedelta, timezone

        from nucleo.dominio import sla

        t0 = datetime(2026, 11, 24, 12, 0, tzinfo=timezone.utc)
        acc, desde = sla.retomar(0, None, t0)                      # cliente escreve: corre
        acc, desde = sla.pausar(acc, desde, t0 + timedelta(seconds=30))  # atendente responde
        assert (acc, desde) == (30_000, None)
        assert sla.pausar(acc, desde, t0 + timedelta(minutes=10)) == (30_000, None)  # pausar de novo
        assert sla.decorrido_ms(acc, desde, t0 + timedelta(hours=1)) == 30_000      # pausado não corre
        acc, desde = sla.retomar(acc, desde, t0 + timedelta(minutes=20))
        assert sla.retomar(acc, desde, t0 + timedelta(minutes=21)) == (acc, desde)  # retomar de novo
        acc, desde = sla.pausar(acc, desde, t0 + timedelta(minutes=20, seconds=5))
        assert acc == 35_000

    def test_limite_por_prioridade_e_geral(self):
        from nucleo.dominio.sla import limite_da_fila

        fila = {"slas": [{"prioridade": 3, "limite_s": 300}, {"prioridade": None, "limite_s": 1800}]}
        assert limite_da_fila(fila, 3) == 300 and limite_da_fila(fila, 1) == 1800
        assert limite_da_fila({}, 2) is None
