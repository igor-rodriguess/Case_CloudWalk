# Roteiro: apresentação de 5 minutos para a gestão da liga

Tema: a ideia, a arquitetura e o desenvolvimento do case CloudWalk. Linguagem de gestão, sem jargão; os termos técnicos aparecem só onde ajudam. O texto entre aspas é a fala; o resto é apoio.

---

## 0:00 – 0:40 · O desafio

"A CloudWalk, dona da InfinitePay no Brasil e da JIM nos Estados Unidos, já tem um agente de inteligência artificial que atende os clientes do começo ao fim. O problema é a plataforma onde esse atendimento acontece: é de outra empresa, é lenta, tem falhas e não foi feita para várias marcas e várias equipes."

"O pedido do case foi construir um help desk próprio, em que a IA é o primeiro atendente e o humano entra quando precisa."

## 0:40 – 1:20 · A ideia central

"A primeira coisa que fiz foi medir o tamanho do problema. São cerca de 10 mil atendimentos por dia. Isso é pouco para a tecnologia de hoje. Então volume não era o desafio."

"O desafio de verdade é **confiança**: nenhuma mensagem de cliente pode se perder, nenhuma resposta pode chegar duplicada, mesmo quando um sistema cai ou uma mensagem é reenviada. Num atendimento financeiro, uma mensagem perdida é um cliente sem resposta sobre o próprio dinheiro."

"Por isso desenhei a solução começando pelas falhas, não pelas telas."

## 1:20 – 2:30 · A arquitetura, em quatro peças

"A plataforma tem quatro partes:"

1. **"A entrada dos canais.** O cliente fala por chat, WhatsApp ou e-mail, e tudo chega no mesmo lugar."
2. **"O núcleo.** Ele entende o assunto e a urgência da mensagem e coloca a conversa na fila certa. As filas são configuradas pela própria operação, sem precisar de programador: dá para criar uma fila nova, testar e voltar atrás em segundos."
3. **"A ponte com a IA.** Mantive exatamente o caminho que a CloudWalk já usa para falar com o agente. Assim o agente real pode ser ligado sem perceber que a plataforma mudou."
4. **"O painel do analista humano.** Quando a IA não resolve, ou o cliente pede uma pessoa, a conversa vai para um analista com um resumo pronto e o histórico completo. O cliente recebe o tempo estimado de espera."

"Por trás disso, cada falha possível tem uma proteção: mensagem guardada antes de ser enviada, mensagem repetida descartada, resposta atrasada da IA bloqueada quando o humano já assumiu. E toda decisão fica registrada com o motivo, para auditoria."

## 2:30 – 3:40 · Como foi o desenvolvimento

"Trabalhei em três etapas:"

- **"Desenho.** Escrevi a arquitetura e revisei em várias rodadas antes de programar, com cada decisão justificada."
- **"Construção.** Plataforma completa: o núcleo, a ponte com a IA, um agente simulado (o real não é fornecido no case), os canais simulados e as telas: chat do cliente, painel do analista, editor de filas e um painel ao vivo da operação."
- **"Prova.** Não bastava dizer que funciona; testei."

"No teste, desliguei cada proteção para ver o que acontecia sem ela. Sem a proteção contra mensagem repetida, 637 clientes receberiam resposta duplicada; com ela, zero. Com um sistema fora do ar por um minuto, sem a proteção, 1.455 mensagens se perderiam; com ela, zero."

## 3:40 – 4:30 · O resultado

"Depois testei em escala: **100 mil mensagens de 20 mil clientes**. Todas foram respondidas, nenhuma duplicada, em 37 minutos, com o tempo de resposta caindo de 91 para 9 segundos depois que eu encontrei e corrigi os gargalos."

"Também simulei tudo dando errado ao mesmo tempo: mensagens reenviadas, parte do sistema caindo, mensagens com problema. Nenhuma duplicata e nenhuma resposta fora de ordem. E em mil pedidos de atendimento humano, 100% chegaram ao analista com resumo e com tempo de espera informado ao cliente."

## 4:30 – 5:00 · Limites e próximos passos

"Sendo transparente sobre os limites: rodei tudo em uma máquina só, e a IA é simulada. O próximo passo seria ligar o agente real da CloudWalk, primeiro em modo de observação e depois em uma parte pequena dos atendimentos, e espalhar o sistema em mais máquinas para picos maiores."

"Em resumo: uma plataforma própria, feita para várias marcas, com a IA como primeiro atendente e com prova de que não perde nem duplica mensagens. Obrigado."

---

## Se perguntarem

| Pergunta | Resposta curta |
|---|---|
| Usa inteligência artificial própria? | Não; a IA é a da CloudWalk, simulada no case, como o TAP permite. O foco foi a plataforma que recebe a IA |
| Aguenta o volume da empresa? | Sim, com folga para o dia normal: testei 100 mil mensagens; o dia típico tem cerca de 120 mil somando as duas direções |
| Quanto tempo para colocar no ar? | Da cópia do projeto ao sistema rodando: 3 minutos e meio |
| O que faltou? | Ligar o agente real, autenticação de usuários e espalhar em várias máquinas |
