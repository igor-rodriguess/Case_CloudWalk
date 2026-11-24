import type { ButtonHTMLAttributes, ReactNode } from "react";
import { COR_ESTADO, ROTULO_ESTADO } from "@/lib/formatar";

export function Cartao({ titulo, acoes, children, className = "" }: {
  titulo?: ReactNode;
  acoes?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`rounded-lg border border-zinc-200 bg-white ${className}`}>
      {(titulo || acoes) && (
        <header className="flex items-center justify-between gap-2 border-b border-zinc-100 px-4 py-2.5">
          <h2 className="text-sm font-semibold text-zinc-800">{titulo}</h2>
          <div className="flex items-center gap-2">{acoes}</div>
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

export function EtiquetaEstado({ estado }: { estado: string }) {
  return (
    <span className={`inline-block rounded px-1.5 py-0.5 text-xs font-medium ${COR_ESTADO[estado] ?? "bg-zinc-100"}`}>
      {ROTULO_ESTADO[estado] ?? estado}
    </span>
  );
}

export function Etiqueta({ children, cor = "bg-zinc-100 text-zinc-700" }: { children: ReactNode; cor?: string }) {
  return <span className={`inline-block rounded px-1.5 py-0.5 text-xs ${cor}`}>{children}</span>;
}

type Variante = "primario" | "secundario" | "perigo";
const VARIANTES: Record<Variante, string> = {
  primario: "bg-zinc-900 text-white hover:bg-zinc-700",
  secundario: "border border-zinc-300 bg-white text-zinc-800 hover:bg-zinc-50",
  perigo: "border border-red-300 bg-white text-red-700 hover:bg-red-50",
};

export function Botao({ variante = "primario", className = "", ...props }: ButtonHTMLAttributes<HTMLButtonElement> & {
  variante?: Variante;
}) {
  return (
    <button
      type="button"
      {...props}
      className={`rounded px-3 py-1.5 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-40 ${VARIANTES[variante]} ${className}`}
    />
  );
}

export function Aviso({ tipo = "erro", children }: { tipo?: "erro" | "ok" | "info"; children: ReactNode }) {
  const cor = {
    erro: "border-red-200 bg-red-50 text-red-800",
    ok: "border-emerald-200 bg-emerald-50 text-emerald-800",
    info: "border-sky-200 bg-sky-50 text-sky-800",
  }[tipo];
  return <div className={`rounded border px-3 py-2 text-sm ${cor}`}>{children}</div>;
}

export function Rotulo({ texto, children }: { texto: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-xs font-medium text-zinc-600">
      {texto}
      {children}
    </label>
  );
}

export const campo =
  "rounded border border-zinc-300 bg-white px-2 py-1.5 text-sm text-zinc-900 focus:border-zinc-500 focus:outline-none";

export function Atualizado({ em, erro }: { em: number | null; erro: string | null }) {
  if (erro) return <span className="text-xs text-red-700">{erro}</span>;
  if (!em) return <span className="text-xs text-zinc-400">carregando…</span>;
  return <span className="text-xs text-zinc-400">lido às {new Date(em).toLocaleTimeString("pt-BR")}</span>;
}

export function Vazio({ children }: { children: ReactNode }) {
  return <p className="text-sm text-zinc-400">{children}</p>;
}
