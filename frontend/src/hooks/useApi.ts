import { useCallback, useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api";

interface State<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
}

/** Busca `path` (null = não busca) e, se `refreshMs`, atualiza em segundo plano sem piscar a tela. */
export function useApi<T>(path: string | null, refreshMs?: number) {
  const [state, setState] = useState<State<T>>({ data: null, error: null, loading: path !== null });
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (path === null) return;
    const controller = new AbortController();

    api<T>(path, {}, controller.signal)
      .then((data) => setState({ data, error: null, loading: false }))
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        const message = err instanceof ApiError ? err.message : "Não foi possível conectar ao servidor.";
        // Em atualização em segundo plano, mantém os dados antigos na tela.
        setState((prev) => ({ data: prev.data, error: message, loading: false }));
      });

    return () => controller.abort();
  }, [path, tick]);

  useEffect(() => {
    if (!refreshMs || path === null) return;
    // Com a aba em segundo plano não consulta a API; ao voltar, atualiza na hora.
    const id = window.setInterval(() => !document.hidden && setTick((t) => t + 1), refreshMs);
    const onVisible = () => !document.hidden && setTick((t) => t + 1);
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.clearInterval(id);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [refreshMs, path]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { ...state, reload };
}
