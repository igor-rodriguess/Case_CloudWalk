# Roteiro: apresentação de 5 minutos para a gestão da liga

Tema: como a arquitetura do case CloudWalk foi pensada e desenvolvida, passo a passo. O texto entre aspas é a fala; o resto é apoio. Os documentos citados estão em `docs/`.

---

## 0:00 – 0:30 · O ponto de partida

"A CloudWalk, da InfinitePay e da JIM, já tem um agente de IA que atende clientes do começo ao fim, mas a plataforma onde esse atendimento acontece é de outra empresa: lenta, com falhas e sem estrutura para várias marcas. O case pediu um help desk próprio, com a IA como primeiro atendente e o humano entrando quando precisa."

## 0:30 – 3:30 · Como a arquitetura foi desenvolvida, em sete passos

**Passo 1 · Medir antes de desenhar (0:30)**
"Antes de qualquer desenho, calculei o tamanho do problema com dado público: a IA da CloudWalk fez cerca de 2,6 milhões de atendimentos em 2023, o que dá uns 10 mil por dia, ou 14 mensagens por segundo no pico. Isso é pouco. A conclusão mudou o projeto inteiro: **o desafio não é volume, é confiança.** Não pode perder nem duplicar mensagem de cliente, mesmo com falha." (arquitetura, seção 3; decisões 1 e 2)

**Passo 2 · Transformar o TAP em requisitos (0:55)**
"Li o TAP e quebrei em 13 requisitos verificáveis: canais, filas editáveis, IA como atendente, painel do analista, auditoria, handoff, volume. Cada requisito virou um item que eu teria que provar no final." (seção 2)

**Passo 3 · Estudar quem já resolveu isso (1:15)**
"Fiz engenharia reversa de duas plataformas abertas. Do **Chatwoot** peguei a ideia do robô como atendente que passa para o humano. Do **Zendesk**, o modelo de filas: condições, ordem e uma fila padrão. E achei uma fraqueza no Chatwoot: se o robô falha de certos jeitos, a conversa cai direto para o humano sem tentar de novo. Esse virou meu ponto de melhoria." (seção 6)

**Passo 4 · Definir os princípios (1:40)**
"Fixei sete princípios antes de escolher tecnologia. Os mais importantes: a conversa tem estado, não é uma esteira; a IA é um atendente dentro das filas, não uma etapa; regras são dados que a operação edita, não código; e confiabilidade vem antes de escala." (seção 5)

**Passo 5 · Desenhar a partir das falhas (2:00)**
"Em vez de começar pelas telas, segui o caminho de uma mensagem e perguntei, em cada ponto: e se isso falhar? E se o sistema cair no meio? E se a mensagem chegar duas vezes? E se a IA responder atrasada, depois que o humano já assumiu? Cada resposta virou uma proteção: guardar antes de enviar, descartar repetida, bloquear resposta vencida, registrar toda decisão. No total foram 42 decisões registradas, cada uma com o porquê." (seções 7 a 11; tabela da seção 20)

**Passo 6 · Escolher a tecnologia pela decisão, não pelo gosto (2:30)**
"Mantive o caminho que a CloudWalk já usa para falar com a IA, com webhook e Kafka, para o agente real entrar sem perceber a troca. Escolhi Python pela velocidade de entrega; a CloudWalk usa Ruby, então deixei as partes conversando só por contratos abertos, o que permite migrar uma por vez. Postgres guarda tudo com transação, e as filas ficam no banco como dado versionado." (seção 15; decisões 8 e 11)

**Passo 7 · Revisar antes de programar (2:55)**
"A arquitetura passou por cinco rodadas de revisão crítica, com nota de desenho e de viabilidade. A primeira deu 6 e 4,5: o desenho era bom, mas não cabia no prazo. Então cortei por requisito, mantendo o que a avaliação pesa e mandando o resto para uma lista de evolução. Na última rodada, com o código pronto, a nota chegou a 8,5 nas duas." (`docs/revisoes/`; decisão 41)

## 3:30 – 4:20 · A construção e a prova

"Construí em fatias, na ordem das dependências: primeiro o banco e as mensagens, depois a conversa com estado, a ponte com a IA, as filas, o painel do analista e as telas."

"E testei a própria arquitetura: desliguei cada proteção para ver o que acontecia sem ela. Sem a proteção contra mensagem repetida, 637 respostas duplicadas; com ela, zero. Com um sistema fora do ar por um minuto, 1.455 mensagens perdidas sem a proteção; com ela, zero. Depois, 100 mil mensagens de 20 mil clientes: todas respondidas, nenhuma duplicada."

## 4:20 – 5:00 · O que aprendi e o que vem depois

"O teste de carga mostrou que os gargalos não estavam onde eu imaginava: uma única linha do banco virava fila para uma marca inteira. Medi, corrigi a causa, e o tempo de resposta caiu de 91 para 9 segundos."

"Os limites, sendo transparente: rodei numa máquina só e a IA é simulada. O próximo passo é ligar o agente real da CloudWalk, primeiro só observando e depois numa parte pequena dos atendimentos."

"Em resumo: uma arquitetura pensada a partir das falhas, revisada antes de ser construída, e provada com dados. Obrigado."

---

## Se perguntarem

| Pergunta | Resposta curta |
|---|---|
| Por que não começou pelas telas? | Porque o risco do problema está em perder ou duplicar mensagem; tela sem isso resolvido não serve |
| Quanto da arquitetura mudou no caminho? | O corte de escopo depois da primeira revisão e os ajustes de desempenho do teste de carga; os princípios não mudaram |
| Por que Python se a CloudWalk usa Ruby? | Prazo; as partes falam por contratos abertos, então dá para migrar uma por vez |
| Usa inteligência artificial própria? | Não; a IA é a da CloudWalk, simulada no case, como o TAP permite |
| O que ficou para depois? | Agente real, autenticação de usuários, memória por similaridade e várias máquinas |
