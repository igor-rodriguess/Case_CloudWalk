"use client";

import { useMemo } from "react";
import { explicar } from "@/lib/auditoria";
import { curto, dataHora, hora, ROTULO_AUTOR } from "@/lib/formatar";
import type { Atendente, Conversa, Escala, EventoAuditoria, Mensagem, Perfil } from "@/lib/tipos";
import { useSondagem } from "@/lib/useSondagem";
import { Etiqueta, EtiquetaEstado, Vazio } from "./ui";

/** id do atendente -> nome, lido uma vez de /painel/atendentes. */
export function useNomesAtendentes(): Record<string, string> {
  const { dados } = useSondagem<Atendente[]>("/painel/atendentes", 0);
  return useMemo(() => Object.fromEntries((dados ?? []).map((a) => [a.id, a.nome])), [dados]);
}

const ESTILO_AUTOR: Record<string, string> = {
  cliente: "self-start bg-white border border-zinc-200",
  ia: "self-end bg-sky-50 border border-sky-200",
  humano: "self-end bg-violet-50 border border-violet-200",
  sistema: "self-center bg-zinc-100 border border-zinc-200 text-zinc-600",
};

export function Historico({ mensagens, fontes = [], nomes = {} }: {
  mensagens: Mensagem[];
  fontes?: string[];
  nomes?: Record<string, string>;
}) {
  if (!mensagens.length) return <Vazio>Nenhuma mensagem ainda.</Vazio>;
  const destaque = new Set(fontes);
  return (
    <ol className="flex flex-col gap-2">
      {mensagens.map((m) => {
        const fonte = destaque.has(m.id);
        return (
          <li
            key={m.id}
            className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${ESTILO_AUTOR[m.autor_tipo] ?? ""} ${fonte ? "ring-2 ring-amber-400" : ""}`}
          >
            <div className="mb-0.5 flex flex-wrap items-center gap-2 text-xs text-zinc-500">
              <span className="font-medium text-zinc-700">
                {ROTULO_AUTOR[m.autor_tipo] ?? m.autor_tipo}
                {m.autor_tipo === "humano" && m.id_autor && nomes[m.id_autor] ? ` · ${nomes[m.id_autor]}` : ""}
              </span>
              <span>{hora(m.criada_em)}</span>
              {m.canal && <span>{m.canal}</span>}
              {fonte && <Etiqueta cor="bg-amber-100 text-amber-800">fonte do resumo</Etiqueta>}
            </div>
            <p className="whitespace-pre-wrap">{m.conteudo}</p>
          </li>
        );
      })}
    </ol>
  );
}

export function CabecalhoConversa({ c }: { c: Conversa }) {
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-sm sm:grid-cols-4">
      <Item rotulo="Estado"><EtiquetaEstado estado={c.estado} /></Item>
      <Item rotulo="Cliente">{c.cliente}</Item>
      <Item rotulo="Marca / canal">{c.marca} · {c.canal}</Item>
      <Item rotulo="Fila">{c.id_fila ?? "—"}</Item>
      <Item rotulo="Atendente">{c.atendente ?? "—"}</Item>
      <Item rotulo="Categoria">{c.categoria ?? "—"}</Item>
      <Item rotulo="Prioridade">{c.prioridade ?? "—"}</Item>
      <Item rotulo="Sentimento">{c.sentimento ?? "—"}</Item>
      <Item rotulo="Origem">{c.origem ?? "—"}</Item>
      <Item rotulo="Regras">v{c.versao_regras ?? "—"}</Item>
      <Item rotulo="Atribuição atual"><code className="text-xs">{curto(c.id_atribuicao_atual)}</code></Item>
      <Item rotulo="Criada">{dataHora(c.criada_em)}</Item>
    </dl>
  );
}

function Item({ rotulo, children }: { rotulo: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-zinc-500">{rotulo}</dt>
      <dd className="text-zinc-900">{children}</dd>
    </div>
  );
}

export function ListaEscalas({ escalas }: { escalas: Escala[] }) {
  if (!escalas.length) return <Vazio>Sem escalas.</Vazio>;
  return (
    <ul className="flex flex-col gap-3">
      {[...escalas].reverse().map((e, i) => (
        <li key={`${e.criada_em}-${i}`} className="rounded border border-zinc-200 p-3 text-sm">
          <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-zinc-500">
            <Etiqueta cor="bg-red-100 text-red-800">{e.motivo}</Etiqueta>
            <span>{dataHora(e.criada_em)}</span>
            {e.prioridade && <span>prioridade {e.prioridade}</span>}
            <span>{e.reserva ? "resumo montado pela plataforma (reserva)" : "resumo do agente"}</span>
            <span>{(e.fontes ?? []).length} fonte(s)</span>
          </div>
          <p className="whitespace-pre-wrap text-zinc-800">{e.resumo ?? "sem resumo"}</p>
        </li>
      ))}
    </ul>
  );
}

export function PerfilCliente({ perfil }: { perfil: Perfil }) {
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-sm">
      <Item rotulo="Segmento">{perfil.segmento ?? "—"}</Item>
      <Item rotulo="Produtos">{perfil.produtos.length ? perfil.produtos.join(", ") : "—"}</Item>
      <Item rotulo="Contatos em 30 dias">{perfil.contatos_30d}</Item>
      <Item rotulo="Escalas em 30 dias">{perfil.escalas_30d}</Item>
      <Item rotulo="Canal preferido">{perfil.canal_preferido ?? "—"}</Item>
      <Item rotulo="Último assunto">
        {perfil.ultimo_assunto ? `${perfil.ultimo_assunto.categoria} (${perfil.ultimo_assunto.data})` : "—"}
      </Item>
    </dl>
  );
}

export function LinhaDoTempo({ auditoria, nomes }: { auditoria: EventoAuditoria[]; nomes: Record<string, string> }) {
  if (!auditoria.length) return <Vazio>Sem eventos.</Vazio>;
  return (
    <ol className="relative flex flex-col gap-3 border-l border-zinc-200 pl-4">
      {auditoria.map((ev, i) => {
        const x = explicar(ev, nomes);
        return (
          <li key={i} className="relative text-sm">
            <span
              className={`absolute -left-[21px] top-1.5 h-2.5 w-2.5 rounded-full ${x.alerta ? "bg-red-500" : "bg-zinc-400"}`}
            />
            <div className="flex flex-wrap items-baseline gap-2">
              <span className="font-medium">{x.titulo}</span>
              <span className="text-xs text-zinc-500">
                {hora(ev.criado_em)} · {ev.tipo} · ator {ev.ator_tipo}
                {ev.id_ator ? ` ${nomes[ev.id_ator] ?? curto(ev.id_ator)}` : ""}
                {ev.id_atribuicao ? ` · atribuição ${curto(ev.id_atribuicao)}` : ""}
              </span>
            </div>
            <p className="text-zinc-700">{x.porque}</p>
            <details className="mt-0.5">
              <summary className="cursor-pointer text-xs text-zinc-400">payload</summary>
              <pre className="mt-1 overflow-x-auto rounded bg-zinc-50 p-2 text-xs">{JSON.stringify(ev.payload, null, 2)}</pre>
            </details>
          </li>
        );
      })}
    </ol>
  );
}
