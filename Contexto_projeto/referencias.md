# Referências

Base de estudo do help desk AI first (CloudWalk / Inteli). Cada item traz o tipo de fonte e para que serve no projeto.

**Tipos:** `[revisado]` artigo revisado por pares · `[preprint]` ainda sem revisão · `[doc]` documentação oficial · `[mercado]` dado de empresa ou de mercado

---

## 1. Contexto CloudWalk

- **CloudWalk: Generative AI brings $20 million return** (2024) `[mercado]`
  https://www.cloudwalk.io/newsroom-releases/generative-ai-brings-20-million-return-for-brazilian-fintech-cloudwalk
  → Em 2023, a IA fez 75% dos atendimentos (~2,6 mi). Base para o volume de referência: ~3,5 mi/ano ≈ 9,5 mil/dia.

- **Let's Money: CloudWalk receita US$ 1,7 bi com IA** (2026) `[mercado]`
  https://www.letsmoney.com.br/ia/cloudwalk-receita-us-1-7-bi-ia/
  → 6,3 mi de clientes na InfinitePay. Base para o volume de estresse (~50 mil/dia, extrapolado).

- **Startups.com.br: CloudWalk lança agente JIM** (2024) `[mercado]`
  https://startups.com.br/eventos/web-summit/cloudwalk-aumenta-aposta-em-ia-e-lanca-agente-para-ser-funcionario-a-mais/
  → Mesma plataforma de agentes atende Claudio (InfinitePay) e JIM. Reforça o requisito multi-marca.

## 2. Agentes de IA

- **Yao et al. τ-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains.** ICLR 2025 `[revisado]`
  https://proceedings.iclr.cc/paper_files/paper/2025/hash/1b126cc38b8638e07bef37e7b2bb72bf-Abstract-Conference.html
  → Agentes de atendimento são inconsistentes (pass^k). Justifica limites de ação e aprovação humana.

- **Cemri et al. Why Do Multi-Agent LLM Systems Fail?** arXiv 2503.13657, 2025 `[preprint]`
  https://arxiv.org/abs/2503.13657
  → Ganho de multiagente sobre agente único costuma ser mínimo. Começar com um agente.

- **Scalable LLM Agent Tool Access in the Cloud.** arXiv 2607.15593, 2026 `[preprint]`
  https://arxiv.org/pdf/2607.15593
  → Acurácia de seleção de tools cai quando todas ficam no prompt. Expor poucas tools por vez.

## 3. Roteamento e filas

- **Molino, Zheng, Wang. COTA: Improving the Speed and Accuracy of Customer Support through Ranking and Deep Networks.** KDD 2018 `[revisado]`
  https://www.uber.com/blog/research/cota-improving-the-speed-and-accuracy-of-customer-support-through-ranking-and-deep-networks
  → Triagem automática em produção na Uber: -10% no tempo de resolução sem perda de satisfação.

- **Uber Engineering: Scaling COTA with Deep Learning** (2018) `[mercado]`
  https://www.uber.com/de/en/blog/cota-v2/
  → Modelo de triagem degrada com o tempo. Requisito de monitorar e retreinar.

- **Gans, Koole, Mandelbaum. Telephone Call Centers: Tutorial, Review, and Research Prospects.** MSOM 5(2), 2003 `[revisado]`
  https://aviman.technion.ac.il/files/References/Gans-Koole-Mandelbaum-CCReview.pdf
  → Base teórica de filas: roteamento por habilidade, Erlang, abandono, dimensionamento.

## 4. Handoff humano–IA

- **Wang et al. Agentic AI and Human-in-the-Loop Interventions: Field Experimental Evidence from Alibaba's Customer Service Operations.** arXiv 2605.14830, 2026 `[preprint]`
  https://arxiv.org/pdf/2605.14830
  → Experimento de campo (680 mil conversas). Escalonamento emocional tardio derruba a qualidade. Handoff precisa ser cedo.

- **Mozannar, Sontag. Consistent Estimators for Learning to Defer to an Expert.** ICML 2020 `[revisado]`
  https://proceedings.mlr.press/v119/mozannar20b.html
  → Base teórica para tratar "quando escalar" como decisão aprendida. Evolução futura.

- **Brynjolfsson, Li, Raymond. Generative AI at Work.** QJE 140(2), 2025 `[revisado]`
  https://papers.ssrn.com/abstract=4426942
  → IA como copiloto: +14% de produtividade, +34% para novatos. Justifica o modo rascunho no painel do analista.

- **Luo, Tong, Fang, Qu. Machines vs. Humans: The Impact of AI Chatbot Disclosure on Customer Purchases.** Marketing Science 38(6), 2019 `[revisado]`
  https://doi.org/10.1287/mksc.2019.1192
  → Cliente desconfia de bot revelado. Transparência mantida; compensar com qualidade e handoff fácil.

## 5. Latência e custo de LLM

- **Kim et al. An LLM Compiler for Parallel Function Calling.** ICML 2024 `[revisado]`
  https://arxiv.org/abs/2312.04511
  → Tools em paralelo: até 3,7x menos latência. Base para paralelismo e pre-fetch.

- **Ong et al. RouteLLM: Learning to Route LLMs with Preference Data.** ICLR 2025 `[revisado]`
  https://arxiv.org/abs/2406.18665
  → Roteamento entre modelos corta custo em mais de 2x. Base para modelo pequeno na triagem.

- **Kwon et al. Efficient Memory Management for Large Language Model Serving with PagedAttention.** SOSP 2023 `[revisado]`
  https://arxiv.org/abs/2309.06180
  → Só relevante se houver modelo self-hosted (vLLM).

## 6. Mensageria

- **Dobbelaere, Esmaili. Kafka versus RabbitMQ: A comparative study of two industry reference publish/subscribe implementations.** DEBS 2017 `[revisado]`
  https://doi.org/10.1145/3093742.3093908
  → Tabela de decisão entre os dois. Usar na escolha do broker.

- **Wang et al. Consistency and Completeness: Rethinking Distributed Stream Processing in Apache Kafka.** SIGMOD 2021 `[revisado]`
  https://doi.org/10.1145/3448016.3457556
  → Exactly-once vem de escrita idempotente e transacional. Base para idempotência no lugar de "QoS 2".

## 6.1 Confiabilidade e consistência

Base das decisões da seção 11 do `arquitetura.md`. Existência, autores e ideia central conferidos em 2026-11-17 pelo resumo e por fontes secundárias. **Os números citados devem ser conferidos no texto completo antes de entrar no README ou na banca.**

- **Saltzer, Reed, Clark. End-to-End Arguments in System Design.** ACM TOCS 2(4), 1984 `[revisado]`
  https://www.cs.princeton.edu/courses/archive/fall10/cos597B/papers/e2e-tocs84.pdf
  → Detecção de duplicata, ordem e entrega garantida só ficam completas nas pontas. Base para inbox em cada consumidor (11.1), regras do broker (11.4) e reconciliador (11.6).

- **Helland. Idempotence Is Not a Medical Condition.** ACM Queue 10(4), 2012; CACM 55(5) `[revisado]`
  https://queue.acm.org/detail.cfm?id=2187821
  → Mensagens são reenviadas; a operação precisa ter o mesmo efeito se repetida. Base para idempotência e id determinístico (11.1).

- **Helland. Life beyond Distributed Transactions: an Apostate's Opinion.** CIDR 2007 `[revisado]`
  https://ics.uci.edu/~cs223/papers/cidr07p15
  → Sem transação distribuída, a aplicação lida com mensagem repetida e fora de ordem. Justifica outbox + idempotência em vez de 2PC.

- **Richardson. Pattern: Transactional outbox.** microservices.io `[doc]`
  https://microservices.io/patterns/data/transactional-outbox
  → Mensagem enviada se e só se a transação confirmar; o relay pode publicar mais de uma vez. Base da outbox (11.2) e da deduplicação no consumidor (11.1).

- **Bailis et al. Feral Concurrency Control: An Empirical Investigation of Modern Application Integrity.** SIGMOD 2015 `[revisado]`
  https://amplab.cs.berkeley.edu/wp-content/uploads/2015/06/feral-sigmod2015.pdf
  → 67 aplicações Rails: validação de unicidade feita na aplicação gera duplicata sob concorrência. Base para trava e índice único no banco (11.2).

- **Warszawski, Bailis. ACIDRain: Concurrency-Related Attacks on Database-Backed Web Applications.** SIGMOD 2017 `[revisado]`
  https://doi.org/10.1145/3035918.3064037
  → 22 ataques críticos por concorrência em 12 aplicações de e-commerce. Mostra que condição de corrida em aplicação web tem efeito real. Base para `transicionar` e capacidade travada (11.2).

- **Gray, Cheriton. Leases: An Efficient Fault-Tolerant Mechanism for Distributed File Cache Consistency.** SOSP 1989 `[revisado]`
  https://doi.org/10.1145/74850.74870
  → Direito com prazo como mecanismo tolerante a falhas. Origem conceitual da atribuição com validade.

- **Kleppmann. How to do distributed locking.** 2016 `[mercado]`
  https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html
  → Fencing token: o recurso recusa escrita com token mais antigo. É o `id_atribuicao` (11.2). Blog técnico, não revisado; o autor desenvolve o tema no livro *Designing Data-Intensive Applications* (O'Reilly, 2017).

- **Yuan et al. Simple Testing Can Prevent Most Critical Failures.** OSDI 2014 `[revisado]`
  https://www.usenix.org/conference/osdi14/technical-sessions/presentation/yuan
  → 198 falhas reais em Cassandra, HBase, HDFS, MapReduce e Redis; 92% das catastróficas vieram de tratamento errado de erro não fatal já sinalizado. Base para fila de erros com escala (11.3) e para testar o caminho de erro no experimento.

- **Dai, He, Gu, Lu. Understanding Real-World Timeout Problems in Cloud Server Systems.** IC2E 2018 `[revisado]`
  https://tingdai.github.io/files/understanding_IC2E18_slides.pdf
  → Bugs de timeout vêm sobretudo de valor errado ou checagem ausente. Base para o agendador único (11.5). Conferido só pelos slides.

- **AWS Builders' Library. Timeouts, retries, and backoff with jitter.** `[mercado]`
  https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter
  → Backoff exponencial com teto e jitter; retentar efeito colateral só com idempotência. Base da retentativa (11.3).

- **Tang et al. Holistic Configuration Management at Facebook.** SOSP 2015 `[revisado]`
  https://web.eecs.utk.edu/~qcao1/cs560/papers/holistic.pdf
  → Erro de configuração é grande causa de queda; resposta com versionamento, validação de invariantes e revisão. Base da configuração versionada (seção 12).

- **Basiri et al. Chaos Engineering.** IEEE Software 33(3), 2016 `[revisado]`
  https://arxiv.org/abs/1702.05843
  → Experimento com falhas injetadas e medida contínua de comportamento normal. Base do experimento comparativo (seção 16).

## 7. Arquitetura de software

- **Auer, Lenarduzzi, Felderer, Taibi. From Monolithic Systems to Microservices: An Assessment Framework.** IST, 2021 `[revisado]`
  https://trepo.tuni.fi/bitstream/10024/132972/1/From_monolithic_systems_to_Microservices.pdf
  → Migrar para microsserviços é caro. Base para começar com monólito modular.

- **Taibi, Lenarduzzi, Pahl. Microservices Anti-Patterns: A Taxonomy.** Springer, 2019 `[revisado]`
  https://arxiv.org/pdf/1908.04101.pdf
  → Anti-padrões a evitar caso algum serviço seja extraído.

## 8. Engenharia reversa

**Chatwoot** (open source, Ruby on Rails)
- Agent Bots `[doc]`: https://www.chatwoot.com/docs/product/others/agent-bots/
  → Bot como atendente. Handoff por status: `pending` (bot) → `open` (humano) → `pending`.
- Features explained `[doc]`: https://chatwoot.com/hc/user-guide/en/categories/features-explained
- Webhooks `[doc]`: https://www.chatwoot.com/docs/webhooks
- Webhooks, documentação derivada do código `[doc]`: https://www.mintlify.com/Merkurcode/nauto-console/developers/webhooks
  → Sem retentativa de webhook; falha do bot joga a conversa para humano. Ponto fraco que o projeto resolve com broker.

**Zendesk** (filas configuráveis)
- Understanding omnichannel routing queues `[doc]`: https://support.zendesk.com/hc/en-us/articles/6712096584090
- Creating custom queues `[doc]`: https://support.zendesk.com/hc/en-us/articles/6716530152858
- Ordem de avaliação das filas `[doc]`: https://support.zendesk.com/hc/en-us/articles/6831121209498
- Workflow com filas e prioridade `[doc]`: https://support.zendesk.com/hc/en-us/articles/7640406656410
  → Fila = condições + ordem + prioridade. Primeira fila que casa leva o ticket. Fila padrão como fallback.

## 9. Benchmarks de mercado

- **Fin: Contact Rate Defined** `[mercado]`: https://fin.ai/glossary/contact-rate
  → Taxa de contato depende do denominador (pedido, cliente ativo, transação). Não há convenção única.

## 10. Indicados no TAPI (ainda não estudados)

- Zammad: https://zammad.org
- Kafka quickstart: https://kafka.apache.org/quickstart
- Sidekiq: https://github.com/sidekiq/sidekiq
- Webhooks (Zapier): https://zapier.com/blog/what-are-webhooks/
- AWS Builders' Library, isolamento de tenants: https://aws.amazon.com/builders-library/saas-tenant-isolation-strategies/
- Kamal: https://kamal-deploy.org
- Anthropic, Building effective agents: https://www.anthropic.com/research/building-effective-agents
- Model Context Protocol: https://modelcontextprotocol.io
- PostgreSQL docs: https://www.postgresql.org/docs/
