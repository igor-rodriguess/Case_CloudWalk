import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { Navegacao } from "@/components/Navegacao";
import { API_URL } from "@/lib/api";
import "./globals.css";

export const metadata: Metadata = {
  title: "Help Desk AI First",
  description: "Interface do help desk multi-marca da CloudWalk (case Inteli)",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" className="h-full antialiased">
      <body className="flex min-h-full flex-col bg-zinc-50 text-zinc-900">
        <header className="border-b border-zinc-200 bg-white">
          <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3">
            <Link href="/" className="text-sm font-semibold">
              Help Desk AI First
            </Link>
            <Suspense fallback={<Navegacao realcar={false} />}>
              <Navegacao />
            </Suspense>
          </div>
        </header>
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6">{children}</main>
        <footer className="border-t border-zinc-200 bg-white">
          <div className="mx-auto max-w-7xl px-4 py-2 text-xs text-zinc-400">
            API: {API_URL} · sem autenticação, o perfil é escolhido na tela · as telas releem a cada 2 s
          </div>
        </footer>
      </body>
    </html>
  );
}
