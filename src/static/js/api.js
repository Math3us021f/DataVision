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
        let message = (body && body.detail) || `Erro ${response.status}`;
        // Erros de validação do FastAPI (422) vêm como lista de objetos.
        if (Array.isArray(message)) {
            message = message.map((e) => e.msg).join("; ");
        }
        throw new Error(message);
    }

    return body;
}
