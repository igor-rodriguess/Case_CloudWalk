# Roteiro 1: explicar a arquitetura e como chegamos nela

Uns 8 minutos. Fala em primeira pessoa; números com fonte entre parênteses.

## 1. O problema (1 min)

- A CloudWalk já tem um agente de IA que atende de ponta a ponta, ligado ao help desk por webhook, broker e Kafka. O help desk é de terceiros: lento, com defeitos e sem estrutura multi-marca (TAP, seção 1).
- O pedido: um help desk próprio, AI first, multi-marca (InfinitePay e JIM) e multi-equipe, em que a IA é um atendente dentro de filas que a operação edita sem deploy.
- **O insight:** volume não é o desafio. 10 mil atendimentos por dia dão ~1,4 msg/s em média e ~14 msg/s no pico concentrado (arq 3). O difícil é **confiabilidade e estado**: não perder nem duplicar mensagem com falha, reentrega e pico, com milhares de conversas abertas, cada uma com dono, fila e histórico certos.

## 2. Como decidi o desenho (1 min)

- Comecei pelas falhas, não pelas telas: o que acontece se o broker cair, se o canal reenviar, se a IA responder atrasada depois que o humano assumiu?
- Cada falha virou uma proteção, e cada proteção virou uma chave que dá para desligar. Assim o experimento compara com e sem cada uma (ablação).
- Mantive a estrutura atual da CloudWalk (webhook → broker → Kafka → agente) para o agente real entrar sem perceber a troca.

## 3. Os componentes (2 min) — mostrar o diagrama do README

| Peça | Papel |
|---|---|
| **Núcleo** (FastAPI + Postgres) | Entrada dos canais, triagem, roteador de filas, distribuidor, painel do analista, auditoria |
| **Broker** | A ponte atual: responde ao webhook só depois do ack do Kafka; confirma a volta só depois do núcleo responder |
| **Redpanda (Kafka)** | Tópicos de ida e volta, 12 partições, chave = conversa (ordem por conversa) |
| **Agente mock** | Faz o papel do agente da CloudWalk (fora do escopo); determinístico |
| **Simulador de canais** | Onde o cliente recebe; é a ponta onde o juiz conta perdas e duplicatas |
| **Front** (Next.js) | Chat do lojista, painel do analista, editor de filas, auditoria, painel ao vivo |

## 4. As garantias, uma por falha (2 min)

1. **Outbox transacional** — falha: o núcleo grava e o envio ao broker se perde. A mensagem e o evento vão na mesma transação; um relay envia depois, com retentativa.
2. **Inbox (deduplicação)** — falha: canal ou Kafka reentrega. Toda entrada tem id; repetida é descartada. O canal também deduplica a saída.
3. **Fencing por `id_atribuicao`** — falha: a IA responde atrasada depois que o humano assumiu. A resposta com atribuição vencida é descartada e auditada.
4. **Uma escrita sob trava (`transicionar`)** — falha: duas ações ao mesmo tempo na mesma conversa. Toda mudança passa por um único caminho, com a conversa travada.
5. **Prazo do agente contado do ack do broker** — atraso da própria plataforma não vira culpa do agente; agente que não responde em 30 s escala para humano.
6. **Auditoria só de inserção** — cada decisão (triagem, regra que casou, quem foi escolhido e por quê, escala, descarte) fica gravada com o porquê.
7. **Mensagem envenenada estaciona só a sua conversa** — as outras seguem; o replay do supervisor restaura a ordem.

## 5. Filas, triagem e handoff (1 min)

- Filas são **dados versionados**: a operação edita, valida (bloqueia fila inalcançável, sem atendente, SLA sobreposto), simula, ativa e faz rollback em segundos.
- Triagem por regras (categoria, prioridade, sentimento); o roteador testa as filas em ordem; o distribuidor escolhe pelo grupo preferido e menor ocupação, com envelhecimento de prioridade.
- Handoff: a escala leva resumo com as mensagens-fonte e o cliente recebe o tempo estimado de espera. SLA corre enquanto a operação deve resposta e pausa quando o atendente responde.
- Multi-marca isolada no banco (RLS): sessão da JIM não lê linha da InfinitePay.

## 6. Como provei (1 min)

- **Experimento por ablação a 50 msg/s:** sem inbox, 637 duplicatas; com, zero. Sem outbox e com o broker fora 60 s, 1.455 perdidas; com, zero (README, Resultados).
- **Carga:** 100 mil mensagens de 20 mil lojistas, todas respondidas, 0 duplicatas, espera p95 8,7 s, ~92 msg/s no total (`testes-de-carga.md`).
- **Falhas juntas (H2):** reenvios, relay fora e 1% envenenadas: 0 duplicatas e 0 violações de ordem.
- **Handoff (H3):** 1.000 pedidos de humano, 100% com nota e tempo estimado.

## 7. O que aprendi no caminho (30 s)

- Os gargalos não estavam onde eu imaginava: uma linha do banco (a da IA) virou fila única da marca, e mais processos pioraram antes de melhorar. Medi com amostras e perfil, corrigi a causa e só então escalei.
- O juiz do experimento errou uma vez; achei pelo padrão, corrigi e refiz a execução, guardando o resultado antigo.

## 8. Limites, ditos antes que perguntem (30 s)

- Uma máquina só: 200 msg/s não passa (H1); escala horizontal não testada.
- Agente mock, sem LLM; triagem por regras; memória semântica com embeddings ficou para Evolução.
- O contrato é proposta minha; validar com a CloudWalk (`plano-de-corte.md`).
