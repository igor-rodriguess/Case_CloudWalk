"use client";

import Link from "next/link";
import { useState } from "react";
import { Atualizado, Aviso, Botao, Cartao, campo, Rotulo, Vazio } from "@/components/ui";
import { apiPost, textoDoErro } from "@/lib/api";
import { curto, dataHora, duracao, ROTULO_ESTADO } from "@/lib/formatar";
import type { ErroOutbox, Metricas, Reconciliacao } from "@/lib/tipos";
import { useSondagem } from "@/lib/useSondagem";

const INVARIANTES: Record<string, string> = {
  I1_mensagem_sem_desfecho: "Mensagem do cliente com a IA, sem resposta nem prazo pendente",
  I1b_esperando_humano: "Conversa escalada esperando humano além do prazo",
  I2_outbox_parada: "Item da outbox pendente ou enviando além do limite",
  I3_resposta_duplicada: "Resposta da IA duplicada para a mesma mensagem",
  I4_resposta_fora_de_dono: "Resposta da IA gravada com atribuição diferente da declarada",
  I5_capacidade: "Analista acima da capacidade ou contagem divergente das atribuições",
  I6_conversa_aberta_duplicada: "Mais de uma conversa aberta por cliente e marca",
};

function Numero({ rotulo, valor, detalhe }: { rotulo: string; valor: React.ReactNode; detalhe?: string }) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white px-4 py-3">
      <div className="text-xs text-zinc-500">{rotulo}</div>
      <div className="text-2xl font-semibold tabular-nums">{valor}</div>
      {detalhe && <div className="text-xs text-zinc-400">{detalhe}</div>}
    </div>
  );
}

function Barra({ valor, maximo }: { valor: number; maximo: number }) {
  const pct = maximo > 0 ? Math.min(100, (valor / maximo) * 100) : 0;
  return (
    <div className="h-2 w-full rounded bg-zinc-100">
      <div className={`h-2 rounded ${pct >= 100 ? "bg-red-500" : "bg-zinc-700"}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

function Pares({ dados, vazio }: { dados: Record<string, number>; vazio: string }) {
  const itens = Object.entries(dados);
  if (!itens.length) return <Vazio>{vazio}</Vazio>;
  return (
    <dl className="flex flex-col gap-1 text-sm">
      {itens.map(([k, v]) => (
        <div key={k} className="flex justify-between gap-4">
          <dt className="text-zinc-600">{ROTULO_ESTADO[k] ?? k}</dt>
          <dd className="tabular-nums">{v.toLocaleString("pt-BR")}</dd>
        </div>
      ))}
    </dl>
  );
}

export default function Supervisor() {
  const [intervalo, setIntervalo] = useState(5000);
  const [conferir, setConferir] = useState(false);
  const [aviso, setAviso] = useState<{ tipo: "erro" | "ok"; texto: string } | null>(null);

  const metricas = useSondagem<Metricas>("/supervisor/metricas", intervalo);
  const erros = useSondagem<ErroOutbox[]>("/outbox/erros", intervalo);
  const reconc = useSondagem<Reconciliacao>(conferir ? "/supervisor/reconciliacao" : null, 0);
  const m = metricas.dados;

  async function reprocessar(id: number) {
    setAviso(null);
    try {
      await apiPost(`/outbox/${id}/reprocessar`, {});
      setAviso({ tipo: "ok", texto: `Item ${id} devolvido para envio.` });
    } catch (e) {
      setAviso({ tipo: "erro", texto: textoDoErro(e) });
    } finally {
      erros.recarregar();
      metricas.recarregar();
    }
  }

  const totalConversas = m ? Object.values(m.conversas_por_estado).reduce((a, b) => a + b, 0) : 0;
  const humanos = m?.atendentes.filter((a) => a.tipo === "humano") ?? [];
  const ias = m?.atendentes.filter((a) => a.tipo === "ia") ?? [];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-lg font-semibold">Saúde da operação</h1>
          <p className="text-sm text-zinc-500">Indicadores de /supervisor/metricas, fila de erros da outbox e reconciliação.</p>
        </div>
        <div className="flex items-end gap-3">
          <Rotulo texto="Reler">
            <select className={campo} value={intervalo} onChange={(e) => setIntervalo(Number(e.target.value))}>
              <option value={2000}>a cada 2 s</option>
              <option value={5000}>a cada 5 s</option>
              <option value={15000}>a cada 15 s</option>
              <option value={0}>pausado</option>
            </select>
          </Rotulo>
          <Atualizado em={metricas.atualizadoEm} erro={metricas.erro} />
        </div>
      </div>

      {m && (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Numero rotulo="Conversas no banco" valor={totalConversas.toLocaleString("pt-BR")} />
            <Numero
              rotulo="Resolvidas na última hora"
              valor={m.resolvidas_ultima_hora.total}
              detalhe={`${m.resolvidas_ultima_hora.pela_ia} sem escala (origem cliente)`}
            />
            <Numero
              rotulo="Escalas na última hora"
              valor={Object.values(m.escalas_ultima_hora).reduce((a, b) => a + b, 0).toLocaleString("pt-BR")}
            />
            <Numero
              rotulo="Descartes por fencing (1 h)"
              valor={m.descartes_fencing_ultima_hora.toLocaleString("pt-BR")}
              detalhe="respostas atrasadas que não atropelaram o dono atual"
            />
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            <Cartao titulo="Conversas por estado">
              <Pares dados={m.conversas_por_estado} vazio="Nenhuma conversa." />
            </Cartao>
            <Cartao titulo="Escalas da última hora por motivo">
              <Pares dados={m.escalas_ultima_hora} vazio="Nenhuma escala na última hora." />
            </Cartao>
            <Cartao titulo="Outbox por status">
              <Pares dados={m.outbox} vazio="Outbox vazia." />
            </Cartao>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Cartao titulo="Filas: tamanho e espera máxima">
              {m.filas.length ? (
                <table className="w-full text-left text-sm">
                  <thead className="text-xs text-zinc-500">
                    <tr>
                      <th className="py-1 font-medium">Fila</th>
                      <th className="font-medium">Aguardando</th>
                      <th className="font-medium">Espera máxima</th>
                    </tr>
                  </thead>
                  <tbody>
                    {m.filas.map((f) => (
                      <tr key={f.id_fila} className="border-t border-zinc-100">
                        <td className="py-1">{f.id_fila}</td>
                        <td className="tabular-nums">{f.tamanho.toLocaleString("pt-BR")}</td>
                        <td>{duracao(f.espera_max_s)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <Vazio>Nenhuma conversa aguardando.</Vazio>
              )}
            </Cartao>

            <Cartao titulo="Atendentes e ocupação">
              <ul className="flex flex-col gap-2.5 text-sm">
                {humanos.map((a) => (
                  <li key={a.nome}>
                    <div className="flex justify-between gap-2">
                      <span>
                        {a.nome} <span className="text-xs text-zinc-500">{a.id_equipe} · {a.status}</span>
                      </span>
                      <span className="tabular-nums">{a.ativas}/{a.capacidade}</span>
                    </div>
                    <Barra valor={a.ativas} maximo={a.capacidade} />
                  </li>
                ))}
                {ias.map((a) => (
                  <li key={a.nome} className="flex justify-between gap-2">
                    <span>
                      {a.nome} <span className="text-xs text-zinc-500">{a.id_equipe} · {a.status}</span>
                    </span>
                    <span className="tabular-nums">{a.ativas.toLocaleString("pt-BR")} conversas</span>
                  </li>
                ))}
              </ul>
            </Cartao>
          </div>

          <Cartao titulo="Chaves de ablação e prazos em uso">
            <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
              {Object.entries(m.chaves).map(([k, v]) => (
                <span key={k}>
                  <span className="text-zinc-500">{k}</span>{" "}
                  <strong className={v === false ? "text-red-700" : ""}>{String(v)}</strong>
                </span>
              ))}
            </div>
          </Cartao>
        </>
      )}

      <Cartao titulo={`Fila de erros da outbox (${erros.dados?.length ?? 0})`} acoes={<Atualizado em={erros.atualizadoEm} erro={erros.erro} />}>
        {aviso && <div className="mb-3"><Aviso tipo={aviso.tipo}>{aviso.texto}</Aviso></div>}
        {erros.dados?.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs text-zinc-500">
                <tr>
                  <th className="py-1 font-medium">Id</th>
                  <th className="font-medium">Conversa</th>
                  <th className="font-medium">Destino</th>
                  <th className="font-medium">Tentativas</th>
                  <th className="font-medium">Último erro</th>
                  <th className="font-medium">Criado</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {erros.dados.map((x) => (
                  <tr key={x.id} className="border-t border-zinc-100 align-top">
                    <td className="py-1.5">{x.id}</td>
                    <td>
                      {x.id_conversa ? (
                        <Link href={`/conversas/${x.id_conversa}`} className="font-mono text-xs text-sky-700 hover:underline">
                          {curto(x.id_conversa)}
                        </Link>
                      ) : "—"}
                    </td>
                    <td>{x.destino}</td>
                    <td>{x.tentativas}</td>
                    <td className="max-w-md text-xs text-zinc-600">{x.ultimo_erro}</td>
                    <td className="text-xs text-zinc-500">{dataHora(x.criado_em)}</td>
                    <td>
                      <Botao variante="secundario" onClick={() => reprocessar(x.id)}>
                        Reprocessar
                      </Botao>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Vazio>Nenhum item em erro.</Vazio>
        )}
      </Cartao>

      <Cartao
        titulo="Reconciliação (invariantes I1 a I6)"
        acoes={
          <>
            {conferir && <Atualizado em={reconc.atualizadoEm} erro={reconc.erro} />}
            <Botao variante="secundario" onClick={() => (conferir ? reconc.recarregar() : setConferir(true))}>
              Conferir agora
            </Botao>
          </>
        }
      >
        <p className="mb-3 text-xs text-zinc-500">
          Consulta sob demanda, não é relida sozinha (varre as tabelas). O esperado é zero em todas.
        </p>
        {reconc.dados ? (
          <table className="w-full text-left text-sm">
            <tbody>
              {Object.entries(reconc.dados).map(([nome, v]) => (
                <tr key={nome} className="border-t border-zinc-100 align-top">
                  <td className="py-1.5 pr-3 font-mono text-xs">{nome}</td>
                  <td className="pr-3 text-zinc-600">{INVARIANTES[nome] ?? ""}</td>
                  <td className={`pr-3 tabular-nums font-semibold ${v.total ? "text-red-700" : "text-emerald-700"}`}>{v.total}</td>
                  <td className="text-xs">
                    {v.exemplos.map((ex) =>
                      nome.startsWith("I1b") ? (
                        <Link key={ex} href={`/conversas/${ex}`} className="mr-2 font-mono text-sky-700 hover:underline">
                          {curto(ex)}
                        </Link>
                      ) : (
                        <code key={ex} className="mr-2">{ex.length > 20 ? curto(ex) : ex}</code>
                      ),
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <Vazio>{conferir ? "Conferindo…" : "Clique em Conferir agora."}</Vazio>
        )}
      </Cartao>
    </div>
  );
}
