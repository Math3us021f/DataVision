"""Adaptador: deixa os testes de HTTP escritos para o FastAPI (TestClient) rodarem contra o Django, sem reescrevê-los.
Eles viraram a prova de paridade da migração (tests/contract/)."""

from urllib.parse import urlencode

from django.core.files.uploadedfile import SimpleUploadedFile

from tests.conftest import ApiClient


class Response:
    def __init__(self, raw):
        self.raw = raw
        self.status_code = raw.status_code
        self.headers = raw.headers
        self.cookies = raw.cookies

    @property
    def content(self) -> bytes:
        return b"".join(self.raw.streaming_content) if self.raw.streaming else self.raw.content

    @property
    def text(self) -> str:
        return self.content.decode("utf-8")

    def json(self):
        return self.raw.json()


class TestClient:
    __test__ = False

    def __init__(self, app=None, follow_redirects=True):
        self._client = ApiClient()
        self._follow = follow_redirects

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    @property
    def cookies(self):
        return self._client.cookies

    def _send(self, method, path, params=None, json=None, files=None, headers=None):
        if params:
            path = f"{path}?{urlencode(params)}"
        extra = {f"HTTP_{k.upper().replace('-', '_')}": v for k, v in (headers or {}).items()}
        call = getattr(self._client, method)
        if files:
            payload = {name: SimpleUploadedFile(item[0], item[1].read(), content_type=item[2] if len(item) > 2 else "") for name, item in files.items()}
            return Response(call(path, payload, **extra))
        if method == "get":
            return Response(call(path, follow=self._follow, **extra))
        return Response(call(path, json=json, **extra))

    def get(self, path, **kw):
        return self._send("get", path, **kw)

    def post(self, path, **kw):
        return self._send("post", path, **kw)

    def put(self, path, **kw):
        return self._send("put", path, **kw)

    def patch(self, path, **kw):
        return self._send("patch", path, **kw)

    def delete(self, path, **kw):
        return self._send("delete", path, **kw)
