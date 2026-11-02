from ninja.renderers import JSONRenderer


class Utf8JSONRenderer(JSONRenderer):
    """Escreve acentos como UTF-8 puro ("Não autenticado"), como o FastAPI, em vez de "N\u00e3o autenticado".
    Para quem lê o JSON dá no mesmo; muda só os bytes (e a leitura humana dos logs e das respostas)."""

    json_dumps_params = {"ensure_ascii": False}
