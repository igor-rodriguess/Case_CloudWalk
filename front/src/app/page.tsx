import Link from "next/link";

const PERFIS = [
  {
    perfil: "Cliente (lojista)",
    texto: "Simula o lojista escrevendo por chat, WhatsApp ou e-mail, na InfinitePay ou na JIM, e acompanha as respostas da IA ou do analista.",
    links: [{ href: "/cliente", texto: "Abrir o chat" }],
  },
  {
    perfil: "Analista",
    texto: "Fila de escalas, assumir, ver resumo, histórico, perfil e auditoria, responder, devolver para a IA e encerrar.",
    links: [{ href: "/analista", texto: "Abrir o painel" }],
  },
  {
    perfil: "Supervisor",
    texto: "Edita as filas sem deploy (validar, simular, versionar, ativar, rollback), acompanha a operação e rastreia cada conversa.",
    links: [
      { href: "/filas", texto: "Filas" },
      { href: "/supervisor", texto: "Operação" },
      { href: "/conversas", texto: "Conversas" },
    ],
  },
];

export default function Inicio() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">Escolha o perfil</h1>
        <p className="mt-1 text-sm text-zinc-600">
          Sem autenticação nesta entrega: o perfil é escolhido aqui ou no menu.
        </p>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        {PERFIS.map((p) => (
          <div key={p.perfil} className="flex flex-col gap-3 rounded-lg border border-zinc-200 bg-white p-5">
            <h2 className="font-semibold">{p.perfil}</h2>
            <p className="flex-1 text-sm text-zinc-600">{p.texto}</p>
            <div className="flex flex-wrap gap-2">
              {p.links.map((l) => (
                <Link key={l.href} href={l.href} className="rounded bg-zinc-900 px-3 py-1.5 text-sm text-white hover:bg-zinc-700">
                  {l.texto}
                </Link>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
