"use client";

import Link from "next/link";
import { useState } from "react";
import { GraficoLinhas, type Ponto } from "@/components/GraficoLinhas";
import { decimal } from "@/lib/formatar";
import { apiPost, textoDoErro } from "@/lib/api";
import { useSondagem } from "@/lib/useSondagem";

interface PontoSerie {
  t: string;
  cliente: number;
  ia: number;
  humano: number;
  escalas: number;
  resposta_ia_p95_s: number | null;
}

interface Serie {
  passo_s: number;
  pontos: PontoSerie[];
  conversas_abertas: number;
  aguardando_atendente: number;
  outbox_pendente: number;
  mensagens_do_cliente_total: number;
}

// Paleta validada (validador do guia de visualização) contra a superfície #141414: azul, verde e
// laranja da marca, ajustados para a faixa de luminosidade do tema escuro.
const SERIES = [
  { chave: "cliente", nome: "Lojistas", cor: "#467afc" },
  { chave: "ia", nome: "IA", cor: "#24a8a8" },
  { chave: "humano", nome: "Analistas", cor: "#e25813" },
];
const SERIE_P95 = [{ chave: "resposta_ia_p95_s", nome: "p95", cor: "#f3bf73" }];

const PERFIS = [
  { perfil: "Lojista", texto: "Chat, WhatsApp ou e-mail, InfinitePay ou JIM.", href: "/cliente", acao: "Abrir o chat" },
  { perfil: "Analista", texto: "Fila de escalas, resumo, histórico, responder e devolver.", href: "/analista", acao: "Abrir o painel" },
  { perfil: "Operação", texto: "Filas sem deploy, métricas, auditoria e trace.", href: "/filas", acao: "Editar filas" },
];

function Numero({ rotulo, valor, detalhe, destaque = false }: {
  rotulo: string;
  valor: string;
  detalhe?: string;
  destaque?: boolean;
}) {
  return (
    <div className="flex flex-col gap-1 rounded-lg border border-[#ffffff1a] bg-white p-4">
      <span className="rotulo-cw">{rotulo}</span>
      <span className={`font-mono text-3xl font-medium tabular-nums ${destaque ? "text-cw-verde" : "text-zinc-900"}`}>
        {valor}
      </span>
      {detalhe && <span className="text-xs text-zinc-500">{detalhe}</span>}
    </div>
  );
}

export default function PainelAoVivo() {
  const { dados, erro } = useSondagem<Serie>("/supervisor/serie?minutos=10&passo=5", 2000);
  const [demo, setDemo] = useState<string | null>(null);
  const passo = dados?.passo_s ?? 5;

  // o último balde ainda está enchendo: as medidas "agora" usam os 6 anteriores (30 s)
  const completos = (dados?.pontos ?? []).slice(0, -1);
  const recentes = completos.slice(-6);
  const porSegundo = (chave: "cliente" | "ia" | "humano") =>
    recentes.reduce((a, p) => a + p[chave], 0) / Math.max(1, recentes.length * passo);
  const p95 = recentes.map((p) => p.resposta_ia_p95_s).filter((v): v is number => v !== null);
  const escalasRecentes = recentes.reduce((a, p) => a + p.escalas, 0);

  const pontos: Ponto[] = completos.map((p) => ({
    t: p.t,
    cliente: p.cliente / passo,
    ia: p.ia / passo,
    humano: p.humano / passo,
    resposta_ia_p95_s: p.resposta_ia_p95_s,
  }));

  async function disparar(msg_s: number, segundos: number) {
    setDemo(null);
    try {
      await apiPost("/demo/trafego", { msg_s, segundos });
      setDemo(`Tráfego sintético no ar: ${msg_s} mensagens/s por ${segundos} s.`);
    } catch (e) {
      setDemo(textoDoErro(e));
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <section className="flex flex-wrap items-end justify-between gap-4 border-b border-[#ffffff1a] pb-6">
        <div className="flex flex-col gap-2">
          <span className="rotulo-cw flex items-center gap-2">
            <span className={`inline-block h-2 w-2 rounded-full bg-cw-verde ${erro ? "" : "pulso-cw"}`} />
            operação ao vivo · últimos 10 min
          </span>
          <h1 className="max-w-2xl text-3xl font-semibold leading-tight tracking-tight md:text-4xl">
            Cada mensagem, decisão e escala, <span className="text-cw-verde">em tempo real.</span>
          </h1>
          <p className="max-w-2xl text-sm text-zinc-500">
            O agente de IA atende como um atendente da plataforma; o humano entra por escala. Outbox, inbox e fencing
            seguram falhas e reentregas sem perder nem duplicar mensagens.
          </p>
        </div>
        <div className="flex flex-col items-start gap-2">
          <span className="rotulo-cw">demo · dado sintético</span>
          <div className="flex flex-wrap gap-2">
            <button
              className="rounded-full bg-cw-papel px-4 py-2 text-sm font-medium text-black hover:bg-cw-verde"
              onClick={() => void disparar(10, 60)}
            >
              Simular tráfego · 10/s
            </button>
            <button
              className="rounded-full border border-cw-laranja px-4 py-2 text-sm font-medium text-cw-laranja hover:bg-cw-laranja hover:text-black"
              onClick={() => void disparar(30, 30)}
            >
              Pico · 30/s
            </button>
          </div>
          {demo && <span className="max-w-xs text-xs text-zinc-500">{demo}</span>}
        </div>
      </section>

      {erro && !dados && (
        <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{erro}</div>
      )}

      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <Numero rotulo="lojistas/s" valor={decimal(porSegundo("cliente"))} detalhe="mensagens entrando (30 s)" destaque />
        <Numero rotulo="respostas/s" valor={decimal(porSegundo("ia") + porSegundo("humano"))}
          detalhe={`IA ${decimal(porSegundo("ia"))} · analistas ${decimal(porSegundo("humano"))}`} />
        <Numero rotulo="resposta da IA p95" valor={p95.length ? `${decimal(Math.max(...p95))} s` : "—"}
          detalhe="do evento à resposta gravada (30 s)" />
        <Numero rotulo="conversas abertas" valor={(dados?.conversas_abertas ?? 0).toLocaleString("pt-BR")}
          detalhe={`${(dados?.aguardando_atendente ?? 0).toLocaleString("pt-BR")} aguardando atendente`} />
        <Numero rotulo="mensagens no total" valor={(dados?.mensagens_do_cliente_total ?? 0).toLocaleString("pt-BR")}
          detalhe={`${escalasRecentes} escala(s) em 30 s · outbox ${dados?.outbox_pendente ?? 0}`} />
      </section>

      <section className="rounded-lg border border-[#ffffff1a] bg-white p-5">
        <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-lg font-semibold">Chamadas por segundo</h2>
          <span className="rotulo-cw">mensagens/s · baldes de {passo} s</span>
        </div>
        {pontos.length > 1 ? (
          <GraficoLinhas pontos={pontos} series={SERIES} unidade="msg/s" />
        ) : (
          <p className="text-sm text-zinc-500">Sem dados ainda. Use “Simular tráfego” ou abra o chat.</p>
        )}
      </section>

      <div className="grid gap-4 lg:grid-cols-3">
        <section className="rounded-lg border border-[#ffffff1a] bg-white p-5 lg:col-span-2">
          <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-lg font-semibold">Tempo de resposta da IA</h2>
            <span className="rotulo-cw">p95 por balde · segundos</span>
          </div>
          {pontos.length > 1 ? (
            <GraficoLinhas pontos={pontos} series={SERIE_P95} unidade="s" />
          ) : (
            <p className="text-sm text-zinc-500">Sem respostas no período.</p>
          )}
        </section>
        <section className="flex flex-col gap-3">
          {PERFIS.map((p) => (
            <Link key={p.perfil} href={p.href}
              className="group flex flex-col gap-1 rounded-lg border border-[#ffffff1a] bg-white p-4 hover:border-cw-verde">
              <span className="rotulo-cw">{p.perfil}</span>
              <span className="text-sm text-zinc-600">{p.texto}</span>
              <span className="font-mono text-xs text-cw-verde group-hover:underline">{p.acao} →</span>
            </Link>
          ))}
        </section>
      </div>
    </div>
  );
}
