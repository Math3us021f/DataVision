// Mensagens do servidor para sessão encerrada por tempo (ver src/core/auth.py).
const IDLE_DETAIL = "Sessão encerrada por inatividade";
const EXPIRED_DETAIL = "Sessão expirada";

/** Marca a requisição como automática: o servidor não a conta como atividade da pessoa (não renova a sessão). */
export const BACKGROUND_HEADER = { "X-Background-Request": "1" } as const;

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

/** Cliente da API JSON do DataVision. Mesma origem: o cookie de sessão vai junto automaticamente. */
export async function api<T>(path: string, init: RequestInit = {}, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, {
    ...init,
    signal,
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...init.headers },
  });

  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    // Resposta sem corpo JSON (ex.: 204) — tudo bem.
  }

  if (!response.ok) {
    const detail = (body as { detail?: unknown } | null)?.detail;
    // Na própria tela de login, 401 é "senha errada": mostra o erro em vez de recarregar a página.
    if (response.status === 401 && window.location.pathname !== "/login") {
      // O login explica por que a pessoa voltou para lá, quando foi por tempo.
      const reason = detail === IDLE_DETAIL ? "?expired=idle" : detail === EXPIRED_DETAIL ? "?expired=time" : "";
      window.location.href = `/login${reason}`;
    }
    let message = `Erro ${response.status}`;
    if (typeof detail === "string") message = detail;
    else if (Array.isArray(detail)) message = detail.map((e: { msg?: string }) => e.msg ?? "").join("; ");
    throw new ApiError(message, response.status);
  }

  return body as T;
}
