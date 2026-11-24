"use client";

import { useState } from "react";
import { EditorFilas, ListasDeValores } from "@/components/EditorFilas";
import { Atualizado, Aviso, Botao, Cartao, campo, Etiqueta, Rotulo, Vazio } from "@/components/ui";
import { apiPost, textoDoErro } from "@/lib/api";
import { dataHora } from "@/lib/formatar";
import { CAMPOS, limpar, VALORES } from "@/lib/regras";
import type { Grupo, Regras, Simulacao, Validacao, Versao, VersaoAtiva } from "@/lib/tipos";
import { useSondagem } from "@/lib/useSondagem";

type Mensagem = { tipo: "erro" | "ok" | "info"; texto: string } | null;

function regraEmTexto(s: Simulacao): string {
  if (s.regra === "fila_padrao") return "nenhuma fila casou: fila padrão";
  if (!s.regra.length) return "fila sem condições";
  return "casou " + s.regra.map((c) => `${c.campo} ${c.operador} ${JSON.stringify(c.valor)}`).join(" e ");
}

export default function ConfiguracaoFilas() {
  const ativa = useSondagem<VersaoAtiva>("/filas/ativa", 5000);
  const versoes = useSondagem<Versao[]>("/filas/versoes", 5000);
  const grupos = useSondagem<Grupo[]>("/filas/grupos", 0);

  const [rascunho, setRascunho] = useState<Regras | null>(null);
  const [base, setBase] = useState<number | null>(null);
  const [geracao, setGeracao] = useState(0);
  const [modoJson, setModoJson] = useState(false);
  const [textoJson, setTextoJson] = useState("");
  const [validacao, setValidacao] = useState<Validacao | null>(null);
  const [criadaPor, setCriadaPor] = useState("supervisor");
  const [criada, setCriada] = useState<number | null>(null);
  const [msg, setMsg] = useState<Mensagem>(null);
  const [ocupado, setOcupado] = useState(false);
  const [atendimento, setAtendimento] = useState<Record<string, string>>({ marca: "jim", canal: "email", origem: "cliente" });
  const [simulacao, setSimulacao] = useState<{ fonte: string; r: Simulacao } | null>(null);

  const versaoBase = versoes.dados?.find((v) => v.numero === base);
  const alterado = !!(rascunho && versaoBase && JSON.stringify(limpar(rascunho)) !== JSON.stringify(versaoBase.filas));

  function abrir(numero: number, regras: Regras) {
    setRascunho(structuredClone(regras));
    setBase(numero);
    setGeracao((g) => g + 1);
    setTextoJson(JSON.stringify(regras, null, 2));
    setValidacao(null);
    setCriada(null);
    setMsg({ tipo: "info", texto: `Versão ${numero} aberta no editor. As mudanças só valem depois de criar e ativar uma versão.` });
  }

  function trocarRascunho(r: Regras) {
    setRascunho(r);
    setValidacao(null);
    setCriada(null);
  }

  function regrasAtuais(): Regras | null {
    if (!modoJson) return rascunho ? limpar(rascunho) : null;
    try {
      const r = JSON.parse(textoJson) as Regras;
      return r;
    } catch (e) {
      setMsg({ tipo: "erro", texto: `JSON inválido: ${(e as Error).message}` });
      return null;
    }
  }

  function alternarModo() {
    if (!modoJson) {
      setTextoJson(JSON.stringify(rascunho ? limpar(rascunho) : {}, null, 2));
      setModoJson(true);
      return;
    }
    const r = regrasAtuais();
    if (r) {
      trocarRascunho(r);
      setModoJson(false);
      setMsg(null);
    }
  }

  async function executar<T>(f: () => Promise<T>, depois: (r: T) => void) {
    setOcupado(true);
    setMsg(null);
    try {
      depois(await f());
    } catch (e) {
      setMsg({ tipo: "erro", texto: textoDoErro(e) });
    } finally {
      setOcupado(false);
    }
  }

  function validar() {
    const r = regrasAtuais();
    if (!r) return;
    void executar(() => apiPost<Validacao>("/filas/validar", r), setValidacao);
  }

  function criarVersao() {
    const r = regrasAtuais();
    if (!r) return;
    void executar(
      () => apiPost<{ numero: number }>("/filas/versoes", { regras: r, criada_por: criadaPor || "supervisor" }),
      (x) => {
        setCriada(x.numero);
        setBase(x.numero);
        setMsg({ tipo: "ok", texto: `Versão ${x.numero} criada (inativa). Ative para valer.` });
        versoes.recarregar();
      },
    );
  }

  function ativar(numero: number) {
    const atual = ativa.dados?.numero;
    const acao = atual !== undefined && numero < atual ? `Rollback para a versão ${numero}` : `Ativar a versão ${numero}`;
    if (!window.confirm(`${acao}? Conversas na fila de uma fila removida são re-roteadas.`)) return;
    void executar(
      () => apiPost<{ ativa: number; reroteadas: number }>(`/filas/versoes/${numero}/ativar`, {}),
      (x) => {
        setMsg({ tipo: "ok", texto: `Versão ${x.ativa} ativa. Conversas re-roteadas: ${x.reroteadas}.` });
        setCriada(null);
        ativa.recarregar();
        versoes.recarregar();
      },
    );
  }

  function simular(comRascunho: boolean) {
    const corpo: Record<string, unknown> = {
      atendimento: Object.fromEntries(
        Object.entries(atendimento)
          .filter(([, v]) => v !== "")
          .map(([k, v]) => [k, k === "prioridade" ? Number(v) : v]),
      ),
    };
    if (comRascunho) {
      const r = regrasAtuais();
      if (!r) return;
      corpo.regras = r;
    }
    void executar(
      () => apiPost<Simulacao>("/filas/simular", corpo),
      (r) => setSimulacao({ fonte: comRascunho ? "rascunho do editor" : "versão ativa", r }),
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <ListasDeValores />
      <div>
        <h1 className="text-lg font-semibold">Filas configuráveis, sem deploy</h1>
        <p className="text-sm text-zinc-500">
          Fluxo: abrir uma versão no editor, editar, validar, simular, criar a versão nova e ativar. Rollback é ativar uma
          versão anterior. Versões são imutáveis.
        </p>
      </div>

      {msg && <Aviso tipo={msg.tipo}>{msg.texto}</Aviso>}

      <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
        <div className="flex flex-col gap-4">
          <Cartao
            titulo={
              ativa.dados ? (
                <span>
                  Versão ativa: <strong>v{ativa.dados.numero}</strong>{" "}
                  <span className="font-normal text-zinc-500">desde {dataHora(ativa.dados.ativada_em)}</span>
                </span>
              ) : (
                "Versão ativa"
              )
            }
            acoes={
              <>
                <Atualizado em={ativa.atualizadoEm} erro={ativa.erro} />
                {ativa.dados && (
                  <Botao variante="secundario" onClick={() => abrir(ativa.dados!.numero, ativa.dados!.filas)}>
                    Editar a partir dela
                  </Botao>
                )}
              </>
            }
          >
            {ativa.dados ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="text-xs text-zinc-500">
                    <tr>
                      <th className="py-1 pr-3 font-medium">Ordem</th>
                      <th className="pr-3 font-medium">Fila</th>
                      <th className="pr-3 font-medium">Condições</th>
                      <th className="pr-3 font-medium">Atendentes</th>
                      <th className="pr-3 font-medium">P</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...ativa.dados.filas.filas].sort((a, b) => a.ordem - b.ordem).map((f) => {
                      const tipo = "todas" in f.condicoes ? "todas" : "qualquer" in f.condicoes ? "qualquer" : null;
                      const lista = tipo === "todas" && "todas" in f.condicoes ? f.condicoes.todas : tipo === "qualquer" && "qualquer" in f.condicoes ? f.condicoes.qualquer : [];
                      return (
                        <tr key={f.id} className={`border-t border-zinc-100 align-top ${f.ativa ? "" : "text-zinc-400"}`}>
                          <td className="py-1.5 pr-3">{f.ordem}</td>
                          <td className="pr-3">
                            <div className="font-medium">{f.nome}</div>
                            <div className="text-xs text-zinc-500">
                              {f.id}
                              {f.id === ativa.dados!.filas.fila_padrao && " · padrão"}
                              {!f.ativa && " · inativa"}
                            </div>
                          </td>
                          <td className="pr-3 text-xs">
                            {lista.length
                              ? lista.map((c) => `${c.campo} ${c.operador} ${JSON.stringify(c.valor)}`).join(tipo === "todas" ? " E " : " OU ")
                              : "casa tudo"}
                          </td>
                          <td className="pr-3 text-xs">{f.atendentes.map((g) => `${g.tipo}:${g.id}`).join(" → ")}</td>
                          <td className="pr-3">{f.prioridade}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <Vazio>Carregando…</Vazio>
            )}
          </Cartao>

          <Cartao
            titulo={
              rascunho ? (
                <span>
                  Editor (a partir da v{base}) {alterado ? <Etiqueta cor="bg-amber-100 text-amber-800">alterado</Etiqueta> : <Etiqueta>sem mudanças</Etiqueta>}
                </span>
              ) : (
                "Editor"
              )
            }
            acoes={
              rascunho && (
                <Botao variante="secundario" onClick={alternarModo}>
                  {modoJson ? "Voltar ao formulário" : "Editar como JSON"}
                </Botao>
              )
            }
          >
            {!rascunho ? (
              <Vazio>Abra a versão ativa ou uma versão da lista para editar.</Vazio>
            ) : (
              <div className="flex flex-col gap-4">
                {modoJson ? (
                  <textarea
                    className={`${campo} min-h-[480px] font-mono text-xs`}
                    value={textoJson}
                    onChange={(e) => {
                      setTextoJson(e.target.value);
                      setValidacao(null);
                    }}
                    spellCheck={false}
                  />
                ) : (
                  <EditorFilas key={geracao} regras={rascunho} grupos={grupos.dados ?? []} onChange={trocarRascunho} />
                )}

                <div className="flex flex-wrap items-end gap-3 border-t border-zinc-100 pt-4">
                  <Botao variante="secundario" disabled={ocupado} onClick={validar}>
                    Validar
                  </Botao>
                  <Rotulo texto="Criada por">
                    <input className={campo} value={criadaPor} onChange={(e) => setCriadaPor(e.target.value)} />
                  </Rotulo>
                  <Botao disabled={ocupado} onClick={criarVersao}>
                    Criar versão
                  </Botao>
                  {criada !== null && (
                    <Botao disabled={ocupado} onClick={() => ativar(criada)}>
                      Ativar v{criada}
                    </Botao>
                  )}
                </div>
                {validacao &&
                  (validacao.valida ? (
                    <Aviso tipo="ok">Regras válidas.</Aviso>
                  ) : (
                    <Aviso>
                      <p className="font-medium">Regras inválidas:</p>
                      <ul className="list-disc pl-5">
                        {validacao.erros.map((e) => (
                          <li key={e}>{e}</li>
                        ))}
                      </ul>
                    </Aviso>
                  ))}
              </div>
            )}
          </Cartao>
        </div>

        <div className="flex flex-col gap-4">
          <Cartao titulo="Simular roteamento">
            <div className="grid grid-cols-2 gap-2">
              {CAMPOS.map((k) => (
                <Rotulo key={k} texto={k}>
                  <select
                    className={`${campo} py-1 text-xs`}
                    value={atendimento[k] ?? ""}
                    onChange={(e) => setAtendimento({ ...atendimento, [k]: e.target.value })}
                  >
                    <option value="">(vazio)</option>
                    {VALORES[k].map((v) => (
                      <option key={String(v)} value={String(v)}>{String(v)}</option>
                    ))}
                  </select>
                </Rotulo>
              ))}
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <Botao variante="secundario" disabled={ocupado} onClick={() => simular(false)}>
                Com a versão ativa
              </Botao>
              <Botao variante="secundario" disabled={ocupado || !rascunho} onClick={() => simular(true)}>
                Com o rascunho
              </Botao>
            </div>
            {simulacao && (
              <div className="mt-3 rounded border border-zinc-200 p-3 text-sm">
                <div className="text-xs text-zinc-500">{simulacao.fonte}{simulacao.r.versao ? ` (v${simulacao.r.versao})` : ""}</div>
                <div>
                  Fila: <strong>{simulacao.r.fila}</strong>
                </div>
                <div className="text-xs text-zinc-600">{regraEmTexto(simulacao.r)}</div>
              </div>
            )}
          </Cartao>

          <Cartao titulo="Versões" acoes={<Atualizado em={versoes.atualizadoEm} erro={versoes.erro} />}>
            {versoes.dados?.length ? (
              <ul className="flex flex-col gap-2">
                {versoes.dados.map((v) => (
                  <li key={v.numero} className="rounded border border-zinc-100 p-2 text-sm">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium">
                        v{v.numero} {v.ativa && <Etiqueta cor="bg-emerald-100 text-emerald-800">ativa</Etiqueta>}
                      </span>
                      <span className="text-xs text-zinc-500">{v.filas.filas.length} filas</span>
                    </div>
                    <div className="text-xs text-zinc-500">
                      por {v.criada_por} em {dataHora(v.criada_em)}
                      {v.ativada_em && ` · ativada ${dataHora(v.ativada_em)}`}
                    </div>
                    <div className="mt-1.5 flex gap-2">
                      <Botao variante="secundario" className="py-1 text-xs" onClick={() => abrir(v.numero, v.filas)}>
                        Abrir no editor
                      </Botao>
                      {!v.ativa && (
                        <Botao variante="secundario" className="py-1 text-xs" disabled={ocupado} onClick={() => ativar(v.numero)}>
                          {ativa.dados && v.numero < ativa.dados.numero ? "Rollback para esta" : "Ativar"}
                        </Botao>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <Vazio>Carregando…</Vazio>
            )}
          </Cartao>
        </div>
      </div>
    </div>
  );
}
