# Contexto do projeto: Help Desk AI First (CloudWalk / Inteli)

Este arquivo passa o contexto da fase de arquitetura para a fase de construção. Leia inteiro antes de escrever código.

Documentos de apoio (colocar em `docs/`):
- `docs/arquitetura.md`: arquitetura completa, com diagramas, modelo de dados, contrato e decisões. **É a fonte da verdade.**
- `docs/referencias.md`: base científica e de mercado de cada decisão.
- `docs/diferenciais.md`: diferenciais planejados para a fase 2.

---

## Como trabalhar comigo

- Responda sempre em **português**.
- **Passo a passo.** Construa uma fatia por vez. Não adiante etapas nem gere o projeto inteiro de uma vez.
- **Explique antes de fazer.** Eu preciso entender e defender cada decisão numa banca. Diga o que vai fazer e por quê em poucas linhas, depois faça.
- **Você propõe, eu valido.** Em decisões novas, traga a recomendação com uma justificativa curta e espere meu ok.
- **Estresse as ideias.** Se algo que eu pedir tiver furo de arquitetura, aponte.
- Depois de cada fatia, me diga como rodar e testar. Só seguimos quando eu confirmar que funcionou.
- Documentação (README, comentários) **enxuta e sem cara de IA**: sem enfeite, sem emoji, sem texto desnecessário.

## O projeto

Projeto individual do Inteli com a CloudWalk (dona da InfinitePay no Brasil e da JIM nos EUA). Prazo: **1 mês**.

**Problema:** a CloudWalk já tem um agente de IA que atende clientes de ponta a ponta, integrado ao help desk por webhooks + broker + tópico Kafka. Mas o help desk é de terceiros: lento, com defeitos recorrentes e sem suporte à estrutura multi-marca e multi-equipe.

**Entrega:** um help desk próprio, AI first, multi-marca e multi-equipe, que:
1. recebe mensagens de chat, WhatsApp e e-mail (simulados);
2. tem filas múltiplas, configuráveis e editáveis pela operação sem deploy;
3. faz triagem, priorização e distribuição entre IA e humanos;
4. integra o agente de IA (**mock**, não desenvolvemos o agente real) por webhook + broker + Kafka, no formato da estrutura atual;
5. tem interface de conversa e painel do analista com fila de escalas, contexto e histórico;
6. faz handoff com resumo, preservando o histórico;
7. audita cada decisão de atendimento e de escala;
8. mantém memória e contexto entre interações;
9. aguenta o volume de referência, inclusive com falhas, reentregas e picos.

**Também entrega:** um experimento técnico (hipótese, método, limitações) e um README com problema, arquitetura, instalação, configurações, metodologia, resultados, limitações e evolução.

**Fora de escopo:** desenvolver o agente de IA, dados reais (LGPD: só dados sintéticos), integração com produção, apps móveis.

**O que a avaliação pesa:** aderência à arquitetura de referência e coerência das escolhas; filas de fato configuráveis; robustez da integração diante de falhas, reentregas e picos; handoff com contexto; evidência de escalabilidade; honestidade nas limitações; reprodutibilidade; demonstração.

## Decisões já tomadas

1. **Volume:** base de 10 mil atendimentos/dia (dado público da CloudWalk, 2023), estresse de 50 mil/dia. Meta do teste de carga: **100 msg/s**. Cerca de 1.200 conversas simultâneas no pico (Lei de Little).
2. **O desafio é confiabilidade e estado, não throughput.** Postgres e Kafka aguentam o volume com folga. O esforço vai para não perder nem duplicar mensagens.
3. **Quatro perfis:** lojista, agente de IA, analista humano e supervisor de operação. O supervisor é adição nossa, porque alguém precisa configurar as filas.
4. **Conversa é máquina de estados, não esteira:** nova → na_fila → com_ia → escalada → com_humano → resolvida. O humano pode devolver para a IA. Resolvida pode reabrir dentro de uma janela.
5. **A IA é um atendente dentro das filas, não uma etapa fixa** (modelo do Chatwoot). Algumas filas podem ir direto para humanos.
6. **Filas no modelo do Zendesk:** condições + ordem + prioridade. Filas testadas em ordem, a primeira que casa leva, fallback numa fila padrão. Prioridade com envelhecimento (cresce com o tempo de espera).
7. **Campos das condições:** marca, canal, categoria, prioridade, idioma, segmento_cliente, sentimento, origem. Operadores: igual, diferente, em. Combinação: todas ou qualquer.
8. **Contrato com o agente em JSON**, com JSON Schema por tipo de evento e versionamento. Kafka particionado por `id_conversa` (ordem garantida dentro da conversa).
9. **Monólito modular.** Broker e agente mock ficam fora do núcleo, porque espelham a fronteira real com a CloudWalk e o experimento vai derrubá-los de propósito.
10. **Confiabilidade (seção 11 da arquitetura):** outbox transacional; inbox por consumidor com id determinístico em eventos derivados; caminho único de escrita `transicionar` com trava, transições permitidas e fencing por `id_atribuicao`; ordem por conversa na outbox; retentativa limitada com fila de erros que escala para humano; broker confirma só depois do Kafka e do núcleo; agendador único para prazos; reconciliador de invariantes.
11. **Roteador é função pura** (atendimento + regras → fila), sem efeitos colaterais. Facilita testes e o simulador de regras (diferencial D3).
12. **Stack:** Python. Ruby (linguagem da CloudWalk) fica como migração futura; para isso os componentes só conversam por HTTP, Kafka e JSON Schema.
13. **Experimento comparativo:** a fatia 1 é a versão ingênua; a plataforma depois da fatia 3 é a robusta. Mesmas falhas nas duas; o reconciliador conta perdas e duplicatas.

## Stack

| Camada | Escolha |
|---|---|
| Núcleo | Python + FastAPI |
| ORM e migrations | SQLAlchemy 2.0 + Alembic |
| Contrato | Pydantic (gera o JSON Schema) |
| Banco | PostgreSQL |
| Broker | Redpanda (API compatível com Kafka) |
| Interface | Next.js + React (fatias futuras) |
| Testes | pytest |
| Carga | k6 ou Locust (fatia do experimento) |
| Observabilidade | logs estruturados com `id_conversa`; Prometheus + Grafana depois |
| Empacotamento | Docker Compose |

Distribuição de atendimentos com `SELECT ... FOR UPDATE SKIP LOCKED` no Postgres, para dois workers nunca pegarem a mesma conversa.

## Contrato com o agente

**Plataforma → agente:** `conversa.atribuida` (leva cliente, marca, fila, histórico e persona), `mensagem.recebida`, `conversa.devolvida`, `conversa.encerrada`.

**Agente → plataforma:** `mensagem.enviada`, `acao.executada`, `conversa.escalada` (motivo, resumo, prioridade sugerida), `conversa.resolvida`.

**Envelope comum:**

```json
{
  "versao": "1.0",
  "id_evento": "evt_8f2a...",
  "tipo": "conversa.escalada",
  "id_conversa": "conv_123",
  "id_atribuicao": "atr_41",
  "causado_por": "evt_77c1...",
  "marca": "infinitepay",
  "timestamp": "2026-11-17T13:30:00-03:00",
  "dados": {}
}
```

**Tópicos:** `helpdesk.para-agente`, `agente.para-helpdesk`, `helpdesk.erros`.

Nomes de eventos, campos e tabelas em português, como acima.

## Plano de construção (fatias verticais)

1. **Esqueleto:** uma mensagem de chat vai e volta de ponta a ponta. Vira a versão ingênua do experimento. ← **ESTAMOS AQUI**
2. **Confiabilidade A:** `transicionar`, outbox, inbox por consumidor, regras do broker.
3. **Confiabilidade B:** agendador (timeout e SLA), ordem e fila de erros com escala, reconciliador.
4. **Filas:** roteador, distribuidor, configuração versionada.
5. **Humano:** handoff, painel do analista, devolução para a IA.
6. **Canais e memória:** WhatsApp e e-mail simulados, identidades, reabertura.
7. **Experimento:** carga, injeção de falhas, comparação ingênua × robusta.
8. **Diferenciais** (escolhidos na fase 2).
9. **README e demonstração.**

## Fatia 1: especificação

**Objetivo:** `POST /mensagens` com "meu repasse não caiu" → a mensagem é salva → um evento vai para o Kafka → o agente mock consome e responde → a resposta volta e fica salva na conversa.

**Escopo:**
- `docker-compose.yml` com Postgres, Redpanda, núcleo e agente mock.
- Só 3 tabelas: `clientes`, `conversas`, `mensagens`. As outras entram nas próximas fatias.
- Envelope do contrato em Pydantic, já com `id_atribuicao` e `causado_por` (podem ficar nulos nesta fatia).
- Agente mock simples: responde um texto fixo.
- Nesta fatia o núcleo pode publicar direto no Kafka. O broker separado (webhook → Kafka) e a outbox entram na fatia 2. Deixe isso explícito no código como ponto de evolução. Guarde esta versão (tag git `ingenua`): ela é a linha de base do experimento.

**Fora da fatia 1:** filas, humano, interface web, outbox, idempotência.

**Estrutura sugerida:**

```
helpdesk-ai-first/
├── CLAUDE.md
├── docker-compose.yml
├── nucleo/
│   ├── modelos.py
│   ├── contrato.py
│   └── main.py
├── agente_mock/
├── migrations/
└── docs/
    ├── arquitetura.md
    ├── referencias.md
    └── diferenciais.md
```

**Ordem de entrega dentro da fatia:**
1. `docker-compose.yml` + tabelas + migration. Eu rodo e confirmo que subiu.
2. API de mensagens + publicação no Kafka.
3. Agente mock + caminho de volta.
4. Teste de ponta a ponta.

## Ideias estacionadas (fase 2)

Detalhes em `docs/diferenciais.md`: persona da IA por marca, fila de qualidade, simulador de regras de fila, painel ao vivo do supervisor, copiloto do analista. Não implementar antes da fase 2, mas não tomar decisões que os impeçam: manter o log de eventos, o roteador como função pura e o contrato versionado.
