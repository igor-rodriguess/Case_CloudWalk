# Plano de corte e premissas a validar com a CloudWalk

O que está aqui não se executa dentro do case: depende de material e ambientes da CloudWalk, que o TAP deixa fechados (seção 5). O plano diz o que fazer, em que ordem e como medir; o que já existe no repositório para apoiar cada passo está indicado.

## 1. Premissas a validar antes de ligar o agente real

| Premissa | Por que importa | Como validar | Apoio no repositório |
|---|---|---|---|
| Amostra de 20 a 50 mensagens anonimizadas em cada direção (help desk → agente e agente → help desk) | O contrato (`contrato/esquema-envelope.json`) é proposta nossa; o formato real não é público | Validar cada mensagem da amostra contra o esquema e anotar campo a campo o que diverge | `contrato/esquema-envelope.json`, `testes/test_contrato.py` |
| Nomes dos tópicos, chave de partição e esquema de assinatura do legado | Ordem por conversa depende da chave; assinatura decide como o broker autentica o webhook | Ler a configuração do broker atual e comparar com `helpdesk.para-agente` / `agente.para-helpdesk`, chave = `id_conversa` | `docker-compose.yml` (serviço `topicos`), `broker/main.py` |
| O agente chama alguma API HTTP do help desk (além de responder pelo Kafka)? | Se chamar, a plataforma precisa expor a mesma fachada para o agente não perceber a troca | Inventariar as chamadas do agente nos logs de uma semana | `nucleo/api/agente.py` é a entrada do agente hoje |
| Política de retenção (dias) e quais casos são de ouvidoria | O expurgo usa 90 dias (hipótese) | Confirmar com jurídico/LGPD da CloudWalk | `RETENCAO_DIAS`, `POST /supervisor/expurgo`, `POST /painel/conversas/{id}/ouvidoria` |
| SLAs por fila e prioridade | Os limites no seed são hipótese | Tabela da operação | `slas` nas regras de fila, validador de sobreposição |

## 2. Prova de que o agente não percebe a troca

1. **No mês do case (feito):**
   - teste de contrato pelo esquema publicado, no lugar do Pact: tudo que o mock lê existe no que a plataforma envia, e o que ele devolve volta válido (`testes/test_contrato.py`);
   - teste diferencial contra fixtures do formato legado: **depende da amostra da seção 1**.
2. **Fase 2, modo shadow (7 dias):**
   - o broker atual duplica cada evento para a plataforma nova, que processa mas não entrega ao cliente (o adaptador de canal fica em modo de gravação);
   - um comparador confere, por evento, estrutura (campos, tipos, chave, ordem) e tempo;
   - meta: zero diferenças estruturais e menos de 1% de desvio de tempo.
3. **Canário por marca ou fila:**
   - o broker roteia 5% das conversas novas de uma fila para a plataforma nova, depois 25%;
   - a decisão é por conversa (chave de partição), nunca por mensagem, para não partir uma conversa entre os dois sistemas;
   - critério para subir de degrau: invariantes da reconciliação zeradas (`/supervisor/reconciliacao`) e SLA dentro do limite por 48 h.
4. **Corte por marca:**
   - primeiro a marca de menor volume (JIM);
   - rollback por flag no broker (volta a rotear tudo para o help desk antigo);
   - o help desk antigo continua rodando em paralelo por alguns dias, só leitura, para consulta de histórico.

## 3. Da clonagem à demonstração

Medido em 24/11/2026, nesta máquina, com as imagens base já baixadas: ver `docs/testes-de-carga.md`, seção "Reprodutibilidade". Sem as imagens no cache, o tempo depende da rede (Postgres, Redpanda e Python somam cerca de 1 GB).
