"use client";

import Link from "next/link";
import { useState } from "react";
import { Atualizado, Cartao, campo, EtiquetaEstado, Rotulo, Vazio } from "@/components/ui";
import { curto, dataHora, ESTADOS, MARCAS, ROTULO_ESTADO } from "@/lib/formatar";
import type { ConversaResumo } from "@/lib/tipos";
import { useSondagem } from "@/lib/useSondagem";

export default function ListaConversas() {
  const [estado, setEstado] = useState("");
  const [marca, setMarca] = useState("");
  const [limite, setLimite] = useState(50);
  const [busca, setBusca] = useState("");

  const params = new URLSearchParams({ limite: String(limite) });
  if (estado) params.set("estado", estado);
  if (marca) params.set("marca", marca);
  const { dados, erro, atualizadoEm } = useSondagem<ConversaResumo[]>(`/conversas?${params}`);
  const idBusca = busca.trim();

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-4">
        <Rotulo texto="Estado">
          <select className={campo} value={estado} onChange={(e) => setEstado(e.target.value)}>
            <option value="">todos</option>
            {ESTADOS.map((x) => (
              <option key={x} value={x}>{ROTULO_ESTADO[x]}</option>
            ))}
          </select>
        </Rotulo>
        <Rotulo texto="Marca">
          <select className={campo} value={marca} onChange={(e) => setMarca(e.target.value)}>
            <option value="">todas</option>
            {MARCAS.map((x) => (
              <option key={x} value={x}>{x}</option>
            ))}
          </select>
        </Rotulo>
        <Rotulo texto="Quantidade">
          <select className={campo} value={limite} onChange={(e) => setLimite(Number(e.target.value))}>
            {[20, 50, 100, 200].map((x) => (
              <option key={x} value={x}>{x}</option>
            ))}
          </select>
        </Rotulo>
        <Rotulo texto="Abrir pelo id">
          <div className="flex gap-2">
            <input className={`${campo} w-80`} placeholder="id da conversa" value={busca} onChange={(e) => setBusca(e.target.value)} />
            {idBusca && (
              <Link href={`/conversas/${idBusca}`} className="rounded bg-zinc-900 px-3 py-1.5 text-sm text-white">
                Abrir
              </Link>
            )}
          </div>
        </Rotulo>
      </div>

      <Cartao titulo="Conversas (mais recentes primeiro)" acoes={<Atualizado em={atualizadoEm} erro={erro} />}>
        {dados?.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs text-zinc-500">
                <tr>
                  <th className="py-1.5 pr-3 font-medium">Conversa</th>
                  <th className="pr-3 font-medium">Cliente</th>
                  <th className="pr-3 font-medium">Estado</th>
                  <th className="pr-3 font-medium">Marca / canal</th>
                  <th className="pr-3 font-medium">Categoria</th>
                  <th className="pr-3 font-medium">P</th>
                  <th className="pr-3 font-medium">Fila</th>
                  <th className="pr-3 font-medium">Atendente</th>
                  <th className="font-medium">Atualizada</th>
                </tr>
              </thead>
              <tbody>
                {dados.map((c) => (
                  <tr key={c.id} className="border-t border-zinc-100">
                    <td className="py-1.5 pr-3">
                      <Link href={`/conversas/${c.id}`} className="font-mono text-xs text-sky-700 hover:underline">
                        {curto(c.id)}
                      </Link>
                    </td>
                    <td className="pr-3">{c.cliente}</td>
                    <td className="pr-3"><EtiquetaEstado estado={c.estado} /></td>
                    <td className="pr-3">{c.marca} · {c.canal}</td>
                    <td className="pr-3">{c.categoria}</td>
                    <td className="pr-3">{c.prioridade}</td>
                    <td className="pr-3">{c.id_fila}</td>
                    <td className="pr-3">{c.atendente ?? "—"}</td>
                    <td className="text-xs text-zinc-500">{dataHora(c.atualizada_em)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Vazio>{dados ? "Nenhuma conversa com esses filtros." : "Carregando…"}</Vazio>
        )}
      </Cartao>
    </div>
  );
}
