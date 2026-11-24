"use client";

import { useCallback, useEffect, useState } from "react";
import { apiGet, textoDoErro } from "./api";

interface Estado<T> {
  chave: string | null;
  dados: T | null;
  erro: string | null;
  atualizadoEm: number | null;
}

/**
 * Lê `caminho` e relê a cada `intervaloMs` (0 = lê uma vez só).
 * A próxima leitura só é agendada depois que a anterior termina, então nunca há
 * requisições acumuladas em paralelo. Trocar o caminho ou chamar `recarregar`
 * cancela a leitura em curso antes de começar outra.
 */
export function useSondagem<T>(caminho: string | null, intervaloMs = 2000) {
  const [rodada, setRodada] = useState(0);
  const [estado, setEstado] = useState<Estado<T>>({ chave: null, dados: null, erro: null, atualizadoEm: null });

  useEffect(() => {
    if (!caminho) return;
    let ativo = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const controle = new AbortController();

    const ciclo = async () => {
      try {
        const dados = await apiGet<T>(caminho, controle.signal);
        if (ativo) setEstado({ chave: caminho, dados, erro: null, atualizadoEm: Date.now() });
      } catch (e) {
        if (ativo) {
          setEstado((anterior) => ({
            chave: caminho,
            dados: anterior.chave === caminho ? anterior.dados : null,
            atualizadoEm: anterior.chave === caminho ? anterior.atualizadoEm : null,
            erro: textoDoErro(e),
          }));
        }
      } finally {
        if (ativo && intervaloMs > 0) timer = setTimeout(ciclo, intervaloMs);
      }
    };
    void ciclo();

    return () => {
      ativo = false;
      controle.abort();
      if (timer) clearTimeout(timer);
    };
  }, [caminho, intervaloMs, rodada]);

  const recarregar = useCallback(() => setRodada((r) => r + 1), []);
  const atual = estado.chave === caminho ? estado : null;
  return {
    dados: atual?.dados ?? null,
    erro: atual?.erro ?? null,
    atualizadoEm: atual?.atualizadoEm ?? null,
    recarregar,
  };
}
