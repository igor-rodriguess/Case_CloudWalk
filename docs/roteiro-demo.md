# Roteiro 2: demonstração ao vivo

Uns 6 minutos. Antes de começar, ambiente no ar e o front aberto.

## Preparação (antes da banca)

```powershell
cd C:\Users\Inteli\Documents\Case_ClaudWalk; docker compose up -d
```

```powershell
cd C:\Users\Inteli\Documents\Case_ClaudWalk\front; npm run dev
```

- Abrir http://localhost:3000 e deixar quatro abas: **Ao vivo**, **Chat**, **Painel**, **Filas**.
- 20 s antes de começar, clicar em **Simular tráfego** no Ao vivo, para o gráfico já estar subindo.

## 1. Ao vivo: o sistema trabalhando (1 min)

- "Aqui é a operação em tempo real. A linha azul são lojistas mandando mensagem; a verde-água, a IA respondendo. Elas andam juntas: cada mensagem tem a sua resposta."
- Mostrar os números do topo (mensagens por segundo, tempo de resposta da IA, conversas abertas).
- Clicar em **Pico · 30/s**: "Isso é uma rajada; o sistema absorve e as linhas voltam a andar juntas."
- Gancho: "Testei assim com 100 mil mensagens: todas respondidas, nenhuma duplicada."

## 2. Chat: o lojista (1 min)

- Aba **Chat**, marca InfinitePay, canal WhatsApp. Enviar **"meu repasse não caiu"**. A IA responde em ~1 s.
- Clicar em **Reenviar com o mesmo id_externo**: aparece `duplicada = true`. "O canal reenviou; a plataforma descartou. O cliente não recebe duas respostas."
- Enviar **"quero falar com um atendente"**: o cliente recebe "vou te transferir" com o **tempo estimado** de espera.

## 3. Painel do analista: o handoff (1,5 min)

- Aba **Painel**, escolher o analista que recebeu a conversa.
- Mostrar o **resumo da escala** com as mensagens-fonte destacadas, o perfil do cliente e a auditoria.
- Apontar na auditoria o **descarte por fencing**: "a IA tentou responder depois que eu assumi; foi descartado, não chegou ao cliente."
- Responder ao cliente, depois **Devolver para a IA** com uma nota. Voltar ao Chat: a IA retomou.

## 4. Filas: a operação sem deploy (1 min)

- Aba **Filas**: abrir a versão ativa no editor, adicionar uma condição (ex.: canal = WhatsApp numa fila nova).
- **Validar** (mostrar que o validador bloqueia uma fila inalcançável, se quiser), **Simular**, **Criar versão**, **Ativar**.
- **Rollback** para a anterior: "em segundos, sem desenvolvedor."

## 5. Rastreabilidade (1 min)

- Abrir a conversa em **Conversas** e mostrar a linha do tempo: triagem, regra que casou, por que o atendente foi escolhido, escala.
- **Montar trace** de uma mensagem: canal → núcleo → broker/Kafka → agente → volta → entregue, com o tempo de cada salto.
- Mostrar o **relógio de SLA** (correndo ou pausado).
- Aba **Operação**: **Conferir agora** na reconciliação — todas as invariantes em zero.

## 6. Fechamento (30 s)

- "Recapitulando: canais, filas editáveis, IA como atendente pela estrutura atual, handoff com resumo e tempo estimado, tudo auditado, e provado com 100 mil mensagens e falhas injetadas."

## Se algo der errado ao vivo

| Problema | O que fazer |
|---|---|
| Front não abre | `carga/demo.py` percorre os mesmos momentos pela API: `.venv\Scripts\python -m carga.demo` |
| Gráfico parado | Clicar de novo em Simular tráfego (só uma rodada por vez) |
| Resposta da IA não chega | Aba Operação: ver outbox e reconciliação; mostrar que nada se perdeu |
| Conversa não aparece para o analista | Trocar o filtro da fila para "Toda a marca" ou "Todas" |
