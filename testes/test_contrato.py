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
