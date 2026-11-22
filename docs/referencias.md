# Referências

Base de estudo do help desk AI first (CloudWalk / Inteli). Cada item traz o tipo de fonte, o nível de conferência e para que serve no projeto.

**Tipos:** `[revisado]` artigo revisado por pares · `[preprint]` sem revisão · `[doc]` documentação oficial · `[mercado]` empresa, blog ou livro de prática

**Conferência:** *(texto)* lido no texto completo · *(resumo)* resumo ou página do artigo · *(secundária)* catálogo ou resumo de terceiros · *(página)* documentação ou código lidos diretamente. Números marcados *(resumo)* ou *(secundária)* devem ser conferidos no texto completo antes da banca.

---

## 1. Contexto CloudWalk

- **CloudWalk: Generative AI brings $20 million return** (2024) `[mercado]` *(página)*
  https://www.cloudwalk.io/newsroom-releases/generative-ai-brings-20-million-return-for-brazilian-fintech-cloudwalk
  → 75% dos atendimentos de 2023 (~2,6 mi): base do volume (~9,5 mil/dia). Mais de 1,2 mi de clientes. Claudio Walker respondia "em até sete minutos", contra 22 do analista: tempo até resolver, usado na Lei de Little (arquitetura, seção 3). Não traz taxa de escala.

- **Let's Money: CloudWalk receita US$ 1,7 bi com IA** (2026) `[mercado]` *(página)*
  https://www.letsmoney.com.br/ia/cloudwalk-receita-us-1-7-bi-ia/
  → 6,3 mi de clientes na InfinitePay. Base do volume de estresse (extrapolado).

- **Startups.com.br: CloudWalk lança agente JIM** (2024) `[mercado]`
  https://startups.com.br/eventos/web-summit/cloudwalk-aumenta-aposta-em-ia-e-lanca-agente-para-ser-funcionario-a-mais/
  → Mesma plataforma de agentes para Claudio e JIM. Reforça o multi-marca.

## 2. Agentes de IA

- **Yao et al. τ-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains.** ICLR 2025 `[revisado]` *(resumo)*
  https://proceedings.iclr.cc/paper_files/paper/2025/hash/1b126cc38b8638e07bef37e7b2bb72bf-Abstract-Conference.html
  → Agentes de atendimento são inconsistentes (pass^k). Sustenta limites de ação e a fila de qualidade (D2).

- **Cemri et al. Why Do Multi-Agent LLM Systems Fail?** arXiv 2503.13657, 2025 `[preprint]`
  https://arxiv.org/abs/2503.13657
  → Ganho de multiagente sobre agente único costuma ser mínimo.

## 3. Roteamento e filas

- **Molino, Zheng, Wang. COTA.** KDD 2018 `[revisado]` *(resumo)*
  https://arxiv.org/abs/1807.01337 · https://doi.org/10.1145/3219819.3219851
  → Classifica tickets e seleciona respostas para o atendente; em teste A/B na Uber, -10% no tempo de resolução sem perda de satisfação. Para casos parecidos (D6) é analogia: o COTA não recupera casos.

- **Uber Engineering: Scaling COTA with Deep Learning** (2018) `[mercado]`
  https://www.uber.com/de/en/blog/cota-v2/
  → Modelo de triagem degrada com o tempo: monitorar e retreinar.

- **Gans, Koole, Mandelbaum. Telephone Call Centers: Tutorial, Review, and Research Prospects.** MSOM 5(2), 2003 `[revisado]`
  https://aviman.technion.ac.il/files/References/Gans-Koole-Mandelbaum-CCReview.pdf
  → Base teórica de filas: roteamento por habilidade, Erlang, abandono, dimensionamento.

## 4. Handoff humano–IA

- **Wang et al. Agentic AI and Human-in-the-Loop Interventions: Field Experimental Evidence from Alibaba's Customer Service Operations.** arXiv 2605.14830, 2026 `[preprint]` *(resumo)*
  https://arxiv.org/abs/2605.14830
  → Experimento de campo randomizado. A intervenção humana preserva a qualidade nas escalas técnicas e é menos eficaz nas escalas emocionais disparadas por algoritmo; intervir cedo é essencial. Sustenta handoff cedo, **não** um limiar de sentimento como gatilho.

- **Mozannar, Sontag. Consistent Estimators for Learning to Defer to an Expert.** ICML 2020 `[revisado]`
  https://proceedings.mlr.press/v119/mozannar20b.html
  → "Quando escalar" como decisão aprendida. Evolução.

- **Brynjolfsson, Li, Raymond. Generative AI at Work.** QJE 140(2), 2025 `[revisado]` *(secundária: comunicado da editora)*
  https://doi.org/10.1093/qje/qjae044 · https://www.eurekalert.org/news-releases/1071936
  → Versão publicada: +15% de conversas resolvidas por hora; +30% para os menos experientes, que ganham velocidade e qualidade; os mais experientes têm pequena queda de qualidade. Os +14% e +34% são do working paper NBER w31161 (2023), https://www.nber.org/papers/w31161. Sustenta o copiloto (D5).

- **Luo, Tong, Fang, Qu. Machines vs. Humans: The Impact of AI Chatbot Disclosure on Customer Purchases.** Marketing Science 38(6), 2019 `[revisado]`
  https://doi.org/10.1287/mksc.2019.1192
  → Cliente desconfia de bot revelado: transparência com handoff fácil.

- **Maynez, Narayan, Bohnet, McDonald. On Faithfulness and Factuality in Abstractive Summarization.** ACL 2020 `[revisado]` *(resumo)*
  https://aclanthology.org/2020.acl-main.173/
  → Conteúdo alucinado em quantidade substancial nos resumos de todos os modelos avaliados. Base do resumo com fontes (arquitetura, seção 12).

## 5. Mensageria e integração

- **Dobbelaere, Esmaili. Kafka versus RabbitMQ.** DEBS 2017 `[revisado]`
  https://doi.org/10.1145/3093742.3093908
  → Comparação para a escolha do broker.

- **Wang et al. Consistency and Completeness: Rethinking Distributed Stream Processing in Apache Kafka.** SIGMOD 2021 `[revisado]`
  https://doi.org/10.1145/3448016.3457556
  → Exactly-once vem de escrita idempotente e transacional.

- **Apache Kafka. Documentation, Introduction (Consumers).** `[doc]` *(secundária)*
  https://kafka.apache.org/documentation/
  → Consumidores de um grupo dividem as partições; não há mais consumidores ativos que partições. Limite do E9.

- **aiokafka. API documentation.** `[doc]` *(página)*
  https://aiokafka.readthedocs.io/en/stable/api.html
  → `max_poll_interval_ms` padrão de 300 s (passou, o grupo rebalanceia); `enable_auto_commit` padrão `True`; `pause()`/`resume()` sem rebalance. Base da contrapressão do broker (11.4).

- **Redpanda. rpk redpanda mode.** `[doc]` *(página)*
  https://docs.redpanda.com/current/reference/rpk/rpk-redpanda/rpk-redpanda-mode/
  → Modo de desenvolvimento ignora fsync e confirma a mensagem assim que a recebe. Limitação de durabilidade do experimento. A página descreve `development`; o compose usa `dev-container`.

- **Overeem, Spoor, Jansen, Brinkkemper. An empirical characterization of event sourced systems and their schema evolution: Lessons from industry.** Journal of Systems and Software, 2021 `[revisado]` *(resumo; ordem das táticas por fonte secundária)*
  https://doi.org/10.1016/j.jss.2021.110970 · https://arxiv.org/abs/2104.01146
  → 19 sistemas *event sourced*, 25 engenheiros; cinco táticas de evolução de esquema (eventos versionados, esquema fraco, upcasting, transformação no lugar, copiar e transformar); começar pelas duas primeiras. Base, por analogia, da evolução do contrato (seção 10).

- **Chatwoot. `lib/webhooks/trigger.rb`** (branch develop) `[doc]` *(página)*
  https://raw.githubusercontent.com/chatwoot/chatwoot/develop/lib/webhooks/trigger.rb
  → Webhook de agent bot: 429 e 500 viram erro retentável; outras falhas abrem a conversa para humano, salvo `keep_pending_on_bot_failure`. Base de "onde melhoramos" (seção 6).

## 6. Confiabilidade e consistência

Base da seção 11 da arquitetura. *(resumo)*, salvo indicação.

- **Saltzer, Reed, Clark. End-to-End Arguments in System Design.** ACM TOCS 2(4), 1984 `[revisado]`
  https://www.cs.princeton.edu/courses/archive/fall10/cos597B/papers/e2e-tocs84.pdf
  → Deduplicação, ordem e entrega garantida só ficam completas nas pontas. Base da inbox nas pontas, do broker sem inbox e do juiz nas pontas.

- **Helland. Idempotence Is Not a Medical Condition.** ACM Queue 10(4), 2012 `[revisado]`
  https://queue.acm.org/detail.cfm?id=2187821
  → Mensagens são reenviadas; a operação precisa ter o mesmo efeito se repetida.

- **Helland. Life beyond Distributed Transactions.** CIDR 2007 `[revisado]`
  https://ics.uci.edu/~cs223/papers/cidr07p15
  → Sem transação distribuída, a aplicação lida com repetição e desordem: outbox + idempotência em vez de 2PC.

- **Richardson. Pattern: Transactional outbox.** microservices.io `[doc]`
  https://microservices.io/patterns/data/transactional-outbox
  → Mensagem sai se e só se a transação confirmar; o relay pode repetir.

- **Bailis et al. Feral Concurrency Control.** SIGMOD 2015 `[revisado]`
  https://amplab.cs.berkeley.edu/wp-content/uploads/2015/06/feral-sigmod2015.pdf
  → 67 aplicações Rails: unicidade validada só na aplicação gera duplicata. Base de trava e índice único no banco.

- **Warszawski, Bailis. ACIDRain.** SIGMOD 2017 `[revisado]`
  https://doi.org/10.1145/3035918.3064037
  → 22 ataques críticos por concorrência em 12 aplicações de e-commerce.

- **Gray, Cheriton. Leases.** SOSP 1989 `[revisado]` *(resumo; renovação por trecho em fonte secundária)*
  https://doi.org/10.1145/74850.74870
  → Direito com prazo, tolerante a falhas; o detentor estende o lease para manter o direito. Base da atribuição e do prazo renovável.

- **Kleppmann. How to do distributed locking.** 2016 `[mercado]`
  https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html
  → Fencing token: é o `id_atribuicao`.

- **Yuan et al. Simple Testing Can Prevent Most Critical Failures.** OSDI 2014 `[revisado]`
  https://www.usenix.org/conference/osdi14/technical-sessions/presentation/yuan
  → 92% das falhas catastróficas estudadas vieram de tratamento errado de erro não fatal. Base da fila de erros e de testar o caminho de erro.

- **Dai, He, Gu, Lu. Understanding Real-World Timeout Problems in Cloud Server Systems.** IC2E 2018 `[revisado]` *(slides)*
  https://tingdai.github.io/files/understanding_IC2E18_slides.pdf
  → Valor errado e checagem ausente dominam os bugs de timeout. Que um agendador único reduza esses erros é inferência nossa.

- **AWS Builders' Library. Timeouts, retries, and backoff with jitter.** `[mercado]`
  https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter
  → Backoff exponencial com teto e jitter; retentar efeito colateral só com idempotência.

- **Tang et al. Holistic Configuration Management at Facebook.** SOSP 2015 `[revisado]`
  https://web.eecs.utk.edu/~qcao1/cs560/papers/holistic.pdf
  → Erro de configuração derruba sistemas; resposta com versão, validação e revisão. Base das filas versionadas.

- **Basiri et al. Chaos Engineering.** IEEE Software 33(3), 2016 `[revisado]`
  https://arxiv.org/abs/1702.05843
  → Falhas injetadas com medida de estado estável. Base do experimento.

- **Canal ao vivo (Evolução):** WHATWG, Server-sent events `[doc]` *(página)* (https://html.spec.whatwg.org/multipage/server-sent-events.html); PostgreSQL 16, NOTIFY `[doc]` *(página)* (https://www.postgresql.org/docs/16/sql-notify.html), entregue só no commit; Levin (Recall.ai), Postgres LISTEN/NOTIFY does not scale, 2025 `[mercado]` *(página)* (https://recall.ai/blog/postgres-listen-notify-does-not-scale), trava global no commit com NOTIFY.

- **PostgreSQL 16. `max_connections`.** `[doc]` *(página)*
  https://www.postgresql.org/docs/16/runtime-config-connection.html
  → Padrão típico de 100 conexões. Limite do E9.

## 7. Resiliência e sobrecarga

Base do disjuntor (11.9).

- **Nygard. Release It!** 2ª ed., Pragmatic Bookshelf, 2018, ISBN 978-1-68050-239-8 `[mercado]` (livro) *(secundária)*
  → Circuit breaker como padrão de estabilidade.

- **Fowler. CircuitBreaker.** 2014 `[mercado]` *(página)*
  https://martinfowler.com/bliki/CircuitBreaker.html
  → Estados fechado, aberto e meio-aberto; credita o padrão a Nygard.

- **Bronson, Aghayev, Charapko, Zhu. Metastable Failures in Distributed Systems.** HotOS 2021 `[revisado]` *(secundária)*
  https://doi.org/10.1145/3458336.3465286
  → Padrão de falha metaestável e técnicas para resistir a ele.

- **Huang et al. Metastable Failures in the Wild.** OSDI 2022 `[revisado]` *(resumo; definição por resumo secundário)*
  https://www.usenix.org/conference/osdi22/presentation/huang-lexiang
  → 22 falhas metaestáveis em 11 organizações; sobrecarga que persiste depois do gatilho; retentativa é o efeito sustentador mais comum.

- **Zhou et al. Overload Control for Scaling WeChat Microservices.** SoCC 2018 `[revisado]` *(resumo; priorização por resumo secundário)*
  https://doi.org/10.1145/3267809.3267823
  → Sob sobrecarga, descarta primeiro o de menor prioridade de negócio.

## 8. Memória

Memória operacional (seção 13) e a memória semântica do D6, que foi para Evolução.

- **Liu et al. Lost in the Middle: How Language Models Use Long Contexts.** TACL 12:157–173, 2024 `[revisado]` *(resumo)*
  https://aclanthology.org/2024.tacl-1.9/
  → O desempenho cai quando a informação relevante está no meio de contexto longo. O resumo não afirma queda só pelo tamanho. Base de não mandar o histórico inteiro.

- **Brasil. Lei 13.709/2018 (LGPD).** `[doc]` *(página)*
  https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm
  → Art. 5º, I (dado pessoal); 6º, III (mínimo necessário); 16 (eliminação após o tratamento); 18, VI; 20 (revisão de decisão automatizada que defina perfil, inclusive personalidade). Base do perfil só com fatos.

- **D6 (Evolução):** Reimers e Gurevych, Sentence-BERT, EMNLP 2019 `[revisado]` (https://arxiv.org/abs/1908.10084) e destilação multilíngue, EMNLP 2020 `[revisado]` (https://arxiv.org/abs/2004.09813); Park et al., Generative Agents, UIST 2023 `[revisado]` *(texto, seção 4.1)* (https://doi.org/10.1145/3586183.3606763); Lewis et al., RAG, NeurIPS 2020 `[revisado]` (https://arxiv.org/abs/2005.11401); Marone et al., mmBERT, ICML 2026 `[revisado]` (https://proceedings.mlr.press/v306/marone26a.html); Okamura, Alcoforado e Costa, MTEB-PT, `[preprint]` aceito no BRACIS 2026 *(texto, tabela 3)* (https://arxiv.org/abs/2607.04071); cartões dos modelos Qwen3-Embedding-0.6B, multilingual-e5-small, paraphrase-multilingual-MiniLM-L12-v2 e mmBERT-base `[doc]` (Hugging Face); Morris et al., Text Embeddings Reveal (Almost) As Much As Text, EMNLP 2023 `[revisado]` (https://aclanthology.org/2023.emnlp-main.765/); Petrović, Osborne e Lavrenko, NAACL 2010 `[revisado]` *(secundária)* (https://aclanthology.org/N10-1021/); Liu et al., iPACK, ICSE 2023 `[revisado]` (https://arxiv.org/abs/2302.09520); Manning, Raghavan e Schütze, Introduction to Information Retrieval, 2008, seção 8.4 `[doc]` (livro) *(secundária)*; pgvector e pgvector-python (README) `[doc]` *(página)*. Uso de cada uma em `diferenciais.md`, D6.

## 9. Arquitetura de software

- **Auer, Lenarduzzi, Felderer, Taibi. From Monolithic Systems to Microservices: An Assessment Framework.** IST, 2021 `[revisado]`
  https://trepo.tuni.fi/bitstream/10024/132972/1/From_monolithic_systems_to_Microservices.pdf
  → Migrar para microsserviços é caro: começar com monólito modular.

- **Taibi, Lenarduzzi, Pahl. Microservices Anti-Patterns: A Taxonomy.** Springer, 2019 `[revisado]`
  https://arxiv.org/pdf/1908.04101.pdf
  → Anti-padrões a evitar se algum serviço for extraído.

## 10. Engenharia reversa

**Chatwoot** (Ruby on Rails): Agent Bots `[doc]` https://www.chatwoot.com/docs/product/others/agent-bots/ → bot como atendente, handoff por status (`pending` → `open` → `pending`). Comportamento de falha do webhook: código-fonte (seção 5).

**Zendesk** (filas configuráveis) `[doc]`: https://support.zendesk.com/hc/en-us/articles/6712096584090 · https://support.zendesk.com/hc/en-us/articles/6716530152858 · https://support.zendesk.com/hc/en-us/articles/6831121209498 · https://support.zendesk.com/hc/en-us/articles/7640406656410 → fila = condições + ordem + prioridade; primeira que casa leva. A fila roteia para grupo primário e secundário.

## 11. Benchmarks de mercado

- **Fin: Contact Rate Defined** `[mercado]`: https://fin.ai/glossary/contact-rate → taxa de contato depende do denominador.

## 12. Indicados no TAPI (ainda não estudados)

Zammad (https://zammad.org) · Kafka quickstart (https://kafka.apache.org/quickstart) · Sidekiq (https://github.com/sidekiq/sidekiq) · Webhooks, Zapier (https://zapier.com/blog/what-are-webhooks/) · AWS, isolamento de tenants (https://aws.amazon.com/builders-library/saas-tenant-isolation-strategies/) · Kamal (https://kamal-deploy.org) · Anthropic, Building effective agents (https://www.anthropic.com/research/building-effective-agents) · Model Context Protocol (https://modelcontextprotocol.io) · PostgreSQL docs (https://www.postgresql.org/docs/)
