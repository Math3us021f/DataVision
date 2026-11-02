"""Cabeçalhos de segurança que o Django não traz prontos (na versão 5.2 LTS não há CSP embutida)."""

# Política de segurança de conteúdo: a interface só carrega scripts, fontes, imagens e conexões da própria
# origem (a casca do React não tem script inline). 'unsafe-inline' só em estilos: o React usa o atributo style.
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
    "font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; "
    "form-action 'self'; frame-ancestors 'none'"
)
# A documentação interativa (só existe fora de produção) carrega scripts de CDN e tem script inline.
PATHS_WITHOUT_CSP = ("/docs", "/openapi.json")


class ContentSecurityPolicyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not request.path.startswith(PATHS_WITHOUT_CSP) and "Content-Security-Policy" not in response:
            response["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
        return response
