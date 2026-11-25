import type { Metadata } from "next";
import { Gabarito, IBM_Plex_Mono } from "next/font/google";
import Link from "next/link";
import { Suspense } from "react";
import { Navegacao } from "@/components/Navegacao";
import { API_URL } from "@/lib/api";
import "./globals.css";

const gabarito = Gabarito({ subsets: ["latin"], variable: "--fonte-gabarito", weight: ["400", "500", "600", "700"] });
const plex = IBM_Plex_Mono({ subsets: ["latin"], variable: "--fonte-plex", weight: ["400", "500", "600"] });

export const metadata: Metadata = {
  title: "CloudWalk · Help Desk AI First",
  description: "Help desk multi-marca da CloudWalk, com o agente de IA como atendente (case Inteli)",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" className={`h-full antialiased ${gabarito.variable} ${plex.variable}`}>
      <body className="flex min-h-full flex-col">
        <header className="sticky top-0 z-20 border-b border-[#ffffff1a] bg-black/90 backdrop-blur">
          <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3">
            <Link href="/" className="flex items-baseline gap-2">
              <span className="text-lg font-bold tracking-tight text-cw-papel">cloudwalk</span>
              <span className="font-mono text-xs text-cw-verde">/ help desk</span>
            </Link>
            <Suspense fallback={<Navegacao realcar={false} />}>
              <Navegacao />
            </Suspense>
          </div>
        </header>
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6">{children}</main>
        <footer className="border-t border-[#ffffff1a] bg-black">
          <div className="mx-auto flex max-w-7xl flex-wrap justify-between gap-2 px-4 py-3 font-mono text-[11px] text-zinc-400">
            <span>InfinitePay · JIM · agente de IA como atendente</span>
            <span>API {API_URL} · sem autenticação, perfil escolhido na tela</span>
          </div>
        </footer>
      </body>
    </html>
  );
}
