"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const GRUPOS = [
  { perfil: "Operação", links: [{ href: "/", texto: "Ao vivo" }] },
  { perfil: "Cliente", links: [{ href: "/cliente", texto: "Chat" }] },
  { perfil: "Analista", links: [{ href: "/analista", texto: "Painel" }] },
  {
    perfil: "Supervisor",
    links: [
      { href: "/filas", texto: "Filas" },
      { href: "/supervisor", texto: "Operação" },
      { href: "/conversas", texto: "Conversas" },
    ],
  },
];

export function Navegacao({ realcar = true }: { realcar?: boolean }) {
  return realcar ? <NavegacaoComRota /> : <Links atual="" />;
}

function NavegacaoComRota() {
  return <Links atual={usePathname()} />;
}

function Links({ atual }: { atual: string }) {
  return (
    <nav className="flex flex-wrap items-center gap-x-5 gap-y-1 text-sm">
      {GRUPOS.map((g) => (
        <div key={g.perfil} className="flex items-center gap-2">
          <span className="text-xs uppercase tracking-wide text-zinc-400">{g.perfil}</span>
          {g.links.map((l) => {
            const ativo = l.href === "/" ? atual === "/" : atual === l.href || atual.startsWith(l.href + "/");
            return (
              <Link
                key={l.href}
                href={l.href}
                className={`rounded px-2 py-1 ${ativo ? "bg-zinc-900 text-white" : "text-zinc-700 hover:bg-zinc-100"}`}
              >
                {l.texto}
              </Link>
            );
          })}
        </div>
      ))}
    </nav>
  );
}
