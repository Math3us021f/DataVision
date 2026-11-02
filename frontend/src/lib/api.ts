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
    // Na própria tela de login, 401 é "senha errada": mostra o erro em vez de recarregar a página.
    if (response.status === 401 && window.location.pathname !== "/login") {
      window.location.href = "/login";
    }
    const detail = (body as { detail?: unknown } | null)?.detail;
    let message = `Erro ${response.status}`;
    if (typeof detail === "string") message = detail;
    else if (Array.isArray(detail)) message = detail.map((e: { msg?: string }) => e.msg ?? "").join("; ");
    throw new ApiError(message, response.status);
  }

  return body as T;
}
