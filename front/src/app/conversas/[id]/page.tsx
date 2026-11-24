import { Suspense } from "react";
import { DetalheConversaTela } from "./DetalheConversaTela";

export default function Pagina() {
  return (
    <Suspense fallback={<p className="text-sm text-zinc-400">Carregando…</p>}>
      <DetalheConversaTela />
    </Suspense>
  );
}
