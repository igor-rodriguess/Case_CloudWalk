# Diferenciais

Ideias além do que o TAPI exige. Ainda são propostas: a priorização final acontece na fase 2, depois da arquitetura fechada.

| # | Diferencial | Esforço | Reaproveita do núcleo |
|---|---|---|---|
| D1 | Persona da IA por marca | Pequeno | Cadastro de marcas, evento `conversa.atribuida` |
| D2 | Fila de qualidade | Pequeno/médio | Motor de filas, auditoria |
| D3 | Simulador de regras de fila | Médio | Roteador, histórico de atendimentos |
| D4 | Painel ao vivo do supervisor | Médio | Log de eventos |
| D5 | Copiloto do analista | Médio | Contrato com o agente, painel do analista |

---

## D1. Persona da IA por marca

**O que é:** cada marca tem a sua forma de falar. A InfinitePay atende em português, com tom próximo; a JIM atende em inglês, com outro tom. O agente não é nosso, mas a plataforma guarda essa configuração e entrega ao agente.

**Como funciona:**
1. O supervisor cadastra a persona da marca: idioma, tom, nome do atendente, assinatura, mensagem padrão de handoff e limites de ação (ex.: valor máximo que a IA pode executar sozinha).
2. Quando uma conversa cai para a IA, o evento `conversa.atribuida` leva a persona em `dados.persona`.
3. O agente mock usa a persona para montar a resposta.
4. A auditoria registra qual versão da persona atendeu cada conversa.

**O que muda na arquitetura:** uma tabela `personas` ligada a `marcas`, com versionamento. Nenhum componente novo.

**Por que vale:** transforma o multi-marca em algo real, e não só num filtro. É barato e aparece bem na demonstração.

**Como medir:** teste automatizado garantindo que cada marca recebe a persona certa; trocar a persona e ver o efeito na resposta.

---

## D2. Fila de qualidade

**O que é:** uma amostra das conversas resolvidas pela IA passa por revisão humana. Responde ao achado do τ-bench: o agente acerta muitas vezes, mas não sempre.

**Como funciona:**
1. Quando a IA resolve uma conversa, a plataforma sorteia se ela vai para revisão. A taxa é configurável por marca e categoria (ex.: 5% no geral, 20% em crédito).
2. A conversa sorteada entra numa fila "Revisão de qualidade". É uma fila comum, com a condição `origem = amostra_qualidade`.
3. O revisor avalia com uma rubrica curta: a resposta estava correta? O tom estava adequado? Deveria ter escalado?
4. O resultado vira uma taxa de erro por categoria. Se uma categoria errar demais, o supervisor muda a regra e passa a mandá-la direto para humanos.

**O que muda na arquitetura:** quase nada. Reaproveita o motor de filas; só entra um novo valor em `origem` e uma tabela de avaliações.

**Por que vale:** fecha o ciclo entre a IA e a operação. A plataforma não só distribui, ela aprende onde a IA é confiável.

**Como medir:** taxa de erro por categoria; quantas regras foram ajustadas a partir das revisões.

---

## D3. Simulador de regras de fila

**O que é:** antes de ativar uma configuração nova de filas, o supervisor testa o impacto com atendimentos passados, sem afetar a operação.

**Como funciona:**
1. O supervisor edita as regras e clica em "simular".
2. A plataforma passa os atendimentos históricos (sintéticos) pelo roteador com as regras novas, em modo de teste.
3. Sai um relatório: quantos atendimentos mudariam de fila, como ficaria a distribuição, quais filas ficariam vazias ou lotadas.
4. Se estiver bom, ele ativa.

**O que muda na arquitetura:** exige uma decisão no núcleo: o roteador precisa ser uma **função pura** (atendimento + regras → fila), sem efeitos colaterais. Se for desenhado assim, o simulador sai quase de graça.

**Por que vale:** dá segurança para a operação mexer nas regras sozinha, que é a essência do "configurável pela operação". E serve direto ao **experimento técnico**: "avaliação da distribuição de filas" é um dos experimentos sugeridos no TAPI.

**Como medir:** o próprio relatório do simulador; comparar a distribuição prevista com a real depois de ativar.

---

## D4. Painel ao vivo do supervisor

**O que é:** uma tela com a saúde da operação em tempo real.

**Como funciona:**
1. Toda ação já gera um evento (entrou na fila, foi atendido, escalou, resolveu).
2. Um componente agrega esses eventos em indicadores por fila: tamanho, tempo médio de espera, SLA em risco, taxa de escalonamento IA → humano, analistas disponíveis.
3. A tela atualiza sozinha (WebSocket).
4. Alertas quando um limite é ultrapassado (ex.: fila com mais de 50 atendimentos ou espera acima de 5 minutos).

**O que muda na arquitetura:** um consumidor de eventos que só lê e agrega. Não interfere no fluxo principal.

**Por que vale:** dá dono à quarta persona (supervisor). E é a melhor forma de **mostrar o teste de carga** na demonstração: as filas enchendo e esvaziando ao vivo.

**Como medir:** no experimento de pico, quanto tempo o painel leva para mostrar que uma fila estourou.

---

## D5. Copiloto do analista

**O que é:** quando a conversa está com um humano, a IA sugere a resposta e o analista decide o que fazer com ela.

**Como funciona:**
1. Chega uma mensagem numa conversa que está com um analista.
2. A plataforma pede uma sugestão ao agente (novo evento `sugestao.solicitada`).
3. O agente devolve `sugestao.gerada`, que aparece no painel como rascunho.
4. O analista aceita, edita ou descarta. A plataforma registra a escolha.

**O que muda na arquitetura:** dois tipos de evento novos no contrato (vira versão 1.1) e um campo de rascunho no painel do analista.

**Por que vale:** Brynjolfsson et al. (QJE 2025) mostram +14% de produtividade com IA como copiloto, e +34% para novatos. O TAPI aceita esse desenho se for justificado.

**Como medir:** taxa de sugestões aceitas sem edição, editadas e descartadas.

---

## Decisões do núcleo que deixam os diferenciais baratos

Três escolhas na arquitetura principal tornam quase todos os diferenciais simples de adicionar depois:

1. **Todo evento é registrado num log** (já exigido pela auditoria). Alimenta D2, D3 e D4.
2. **O roteador é uma função pura.** Habilita D3.
3. **O contrato com o agente é versionado.** Permite D5 sem quebrar o que já existe.

## Ordem sugerida (provisória)

D1 → D2 → D3 → D4 → D5

Começa pelos mais baratos e pelo que alimenta o experimento técnico. A ordem final será decidida na fase 2.
