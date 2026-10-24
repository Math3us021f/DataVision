/**
 * Wrapper simples em volta do fetch() para chamar a API JSON do DataVision.
 * Sempre envia cookies (credentials: "same-origin", já é o padrão do navegador
 * para requisições same-origin, mas deixamos explícito).
 */
async function apiRequest(path, options = {}) {
    const response = await fetch(path, {
        ...options,
        credentials: "same-origin",
        headers: {
            "Content-Type": "application/json",
            ...(options.headers || {}),
        },
    });

    let body = null;
    try {
        body = await response.json();
    } catch {
        // Resposta sem corpo JSON (ex: 204) — tudo bem, body fica null.
    }

    if (!response.ok) {
        const message = (body && body.detail) || `Erro ${response.status}`;
        throw new Error(message);
    }

    return body;
}
