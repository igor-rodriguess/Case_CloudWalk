import uuid

import pytest
from pydantic import ValidationError

from contrato import Envelope, id_derivado


def evento(**mudancas):
    """Evento válido da plataforma para o agente; cada teste muda só o que interessa."""
    base = {
        "versao": "1.0",
        "id_evento": str(uuid.uuid4()),
        "tipo": "mensagem.recebida",
        "id_conversa": str(uuid.uuid4()),
        "marca": "infinitepay",
        "timestamp": "2026-11-17T13:30:00-03:00",
        "dados": {"conteudo": "meu repasse não caiu", "canal": "chat"},
    }
    base.update(mudancas)
    return base


def evento_do_agente(**mudancas):
    base = {
        "tipo": "mensagem.enviada",
        "id_atribuicao": str(uuid.uuid4()),
        "causado_por": str(uuid.uuid4()),
        "dados": {"conteudo": "Vou verificar seu repasse."},
    }
    base.update(mudancas)
    return evento(**base)


class TestEstrutura:
    def test_evento_valido_e_aceito(self):
        env = Envelope.model_validate(evento())
        assert env.tipo == "mensagem.recebida"
        assert isinstance(env.id_conversa, uuid.UUID)

    def test_aceita_json_cru(self):
        env = Envelope.model_validate_json(Envelope.model_validate(evento()).model_dump_json())
        assert env.marca == "infinitepay"

    def test_tipo_desconhecido_e_recusado(self):
        with pytest.raises(ValidationError):
            Envelope.model_validate(evento(tipo="mensagem.apagada"))

    def test_marca_desconhecida_e_recusada(self):
        with pytest.raises(ValidationError):
            Envelope.model_validate(evento(marca="outra"))

    def test_versao_principal_nova_e_recusada(self):
        with pytest.raises(ValidationError):
            Envelope.model_validate(evento(versao="2.0"))

    def test_versao_menor_nova_e_aceita(self):
        assert Envelope.model_validate(evento(versao="1.3")).versao == "1.3"

    def test_heartbeat_do_agente_existe(self):
        Envelope.model_validate(
            evento(
                tipo="agente.processando",
                id_atribuicao=str(uuid.uuid4()),
                causado_por=str(uuid.uuid4()),
                dados={},
            )
        )

    def test_id_que_nao_e_uuid_e_recusado(self):
        with pytest.raises(ValidationError):
            Envelope.model_validate(evento(id_evento="evt_123"))

    def test_campo_extra_e_ignorado(self):
        env = Envelope.model_validate(evento(campo_futuro="x"))
        assert not hasattr(env, "campo_futuro")

    def test_envelope_e_imutavel(self):
        env = Envelope.model_validate(evento())
        with pytest.raises(ValidationError):
            env.tipo = "conversa.encerrada"


class TestRegrasDoContrato:
    """As duas regras do model_validator (parte do Igor)."""

    def test_timestamp_sem_fuso_e_recusado(self):
        with pytest.raises(ValidationError, match="fuso"):
            Envelope.model_validate(evento(timestamp="2026-11-17T13:30:00"))

    def test_timestamp_em_utc_e_aceito(self):
        Envelope.model_validate(evento(timestamp="2026-11-17T16:30:00Z"))

    def test_evento_do_agente_completo_e_aceito(self):
        Envelope.model_validate(evento_do_agente())

    @pytest.mark.parametrize("campo", ["id_atribuicao", "causado_por"])
    def test_evento_do_agente_sem_campo_obrigatorio_e_recusado(self, campo):
        dados = evento_do_agente()
        del dados[campo]
        with pytest.raises(ValidationError, match=campo):
            Envelope.model_validate(dados)

    @pytest.mark.parametrize(
        "tipo", ["acao.executada", "conversa.escalada", "conversa.resolvida"]
    )
    def test_todos_os_eventos_do_agente_exigem_atribuicao(self, tipo):
        dados = evento_do_agente(tipo=tipo)
        del dados["id_atribuicao"]
        with pytest.raises(ValidationError):
            Envelope.model_validate(dados)

    def test_evento_da_plataforma_sem_esses_campos_e_aceito(self):
        Envelope.model_validate(evento(tipo="conversa.atribuida"))


class TestIdDerivado:
    def test_mesma_entrada_gera_mesmo_id(self):
        origem = uuid.uuid4()
        assert id_derivado(origem, "mensagem.enviada") == id_derivado(origem, "mensagem.enviada")

    def test_entradas_diferentes_geram_ids_diferentes(self):
        origem = uuid.uuid4()
        ids = {
            id_derivado(origem, "mensagem.enviada"),
            id_derivado(origem, "conversa.escalada"),
            id_derivado(origem, "mensagem.enviada", sequencia=1),
            id_derivado(uuid.uuid4(), "mensagem.enviada"),
        }
        assert len(ids) == 4


class TestPendentesDoCliente:
    def test_mensagens_depois_da_ultima_resposta(self):
        from contrato import pendentes_do_cliente
        h = [{"id": "1", "autor": "cliente"}, {"id": "2", "autor": "ia"},
             {"id": "3", "autor": "cliente"}, {"id": "4", "autor": "cliente"}]
        assert [m["id"] for m in pendentes_do_cliente(h)] == ["3", "4"]

    def test_resposta_humana_tambem_fecha(self):
        from contrato import pendentes_do_cliente
        h = [{"id": "1", "autor": "cliente"}, {"id": "2", "autor": "humano"}]
        assert pendentes_do_cliente(h) == []

    def test_mensagem_de_sistema_nao_fecha(self):
        from contrato import pendentes_do_cliente
        h = [{"id": "1", "autor": "cliente"}, {"id": "2", "autor": "sistema"}, {"id": "3", "autor": "cliente"}]
        assert [m["id"] for m in pendentes_do_cliente(h)] == ["1", "3"]


class TestAgenteMockRespondeCadaMensagem:
    def test_atribuicao_com_tres_pendentes_gera_tres_respostas_com_ids_proprios(self):
        mock = pytest.importorskip("agente_mock.main")
        historico = [{"id": str(i), "autor": "cliente", "conteudo": "oi"} for i in range(3)]
        env = Envelope.model_validate(evento(tipo="conversa.atribuida", id_atribuicao=str(uuid.uuid4()),
                                             dados={"historico": historico}))
        saida = mock.decidir(env, trocas=mock.respostas_devidas(env))
        enviadas = [e for e in saida if e["tipo"] == "mensagem.enviada"]
        assert [e["dados"]["sequencia"] for e in enviadas] == [0, 1, 2]
        assert len({e["id_evento"] for e in enviadas}) == 3
        assert enviadas[0]["id_evento"] == str(id_derivado(env.id_evento, "mensagem.enviada", 0))

    def test_mensagem_recebida_continua_com_uma_resposta(self):
        mock = pytest.importorskip("agente_mock.main")
        env = Envelope.model_validate(evento(id_atribuicao=str(uuid.uuid4())))
        assert mock.respostas_devidas(env) == 1
        assert len(mock.decidir(env, trocas=1)) == 1


class TestContratoEntrePlataformaEAgente:
    """Teste de contrato no lugar do Pact: o esquema publicado é o do modelo, a plataforma só emite
    envelopes válidos e tudo que o consumidor (agente mock) lê existe no que a plataforma envia."""

    def test_esquema_publicado_bate_com_o_modelo(self):
        import json
        from pathlib import Path

        publicado = json.loads((Path(__file__).parent.parent / "contrato" / "esquema-envelope.json").read_text("utf-8"))
        assert publicado == json.loads(json.dumps(Envelope.model_json_schema(), sort_keys=True)), (
            "o modelo mudou: regenere contrato/esquema-envelope.json e suba a versão do contrato")

    def _conversa(self):
        return {"id": uuid.uuid4(), "marca": "infinitepay", "canal": "chat"}

    def test_eventos_da_plataforma_validam_no_envelope(self):
        from nucleo.dominio.transicionar import novo_evento

        conv = self._conversa()
        historico = [{"id": str(uuid.uuid4()), "autor": "cliente", "conteudo": "oi", "canal": "chat", "seq": 1,
                      "criada_em": "2026-11-24T10:00:00+00:00"}]
        for tipo, dados in [
            ("mensagem.recebida", {"id_mensagem": str(uuid.uuid4()), "conteudo": "oi", "canal": "chat"}),
            ("conversa.atribuida", {"cliente": {"id": str(uuid.uuid4()), "nome": "x", "segmento": "pme"},
                                    "fila": "f", "triagem": {}, "historico": historico, "perfil": {}}),
            ("conversa.devolvida", {"historico": historico, "nota": ""}),
        ]:
            payload = novo_evento(tipo, conv, dados).payload
            payload["id_atribuicao"] = str(uuid.uuid4())
            assert Envelope.model_validate(payload).tipo == tipo

    def test_o_que_o_agente_le_existe_no_que_a_plataforma_envia(self):
        mock = pytest.importorskip("agente_mock.main")
        from nucleo.dominio.transicionar import novo_evento

        conv = self._conversa()
        id_msg = str(uuid.uuid4())
        recebida = novo_evento("mensagem.recebida", conv, {"id_mensagem": id_msg, "conteudo": "meu repasse",
                                                           "canal": "chat"}).payload
        recebida["id_atribuicao"] = str(uuid.uuid4())
        env = Envelope.model_validate(recebida)
        assert mock._texto_cliente(env) == ("meu repasse", id_msg)
        respostas = mock.decidir(env, trocas=1)
        for r in respostas:  # o que o agente devolve também cumpre o contrato e aponta a causa
            assert Envelope.model_validate(r).causado_por == env.id_evento
            assert r["id_atribuicao"] == recebida["id_atribuicao"]
