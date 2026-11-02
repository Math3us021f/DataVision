"""Compara a API do Django com o contrato congelado do FastAPI (docs/contrato_api_fastapi.json).

Mostra quantas rotas já foram migradas, quais faltam, se há rota sobrando e se os campos das respostas batem.
Rodar (com o serviço django no ar):

    docker compose exec -T django python manage.py shell < backend/scripts/contract_diff.py
"""

import json
from django.test import Client

old = json.load(open("/docs/contrato_api_fastapi.json", encoding="utf-8"))
new = Client().get("/openapi.json").json()

def ops(spec):
    return {(p, m.upper()) for p, item in spec["paths"].items() for m in item if m in ("get", "post", "put", "patch", "delete")}

def resolve(spec, schema):
    if "$ref" in schema:
        return spec["components"]["schemas"][schema["$ref"].split("/")[-1]]
    return schema

def fields(spec, op):
    resp = op.get("responses", {})
    for code in ("200", "201"):
        if code in resp and "content" in resp[code]:
            s = resolve(spec, resp[code]["content"]["application/json"].get("schema", {}))
            if s.get("type") == "array":
                s = resolve(spec, s.get("items", {}))
            return set(s.get("properties", {}))
    return None

o, n = ops(old), ops(new)
migrated = sorted(x for x in o if x in n)
print(f"Rotas no contrato do FastAPI: {len(o)} | já no Django: {len(migrated)} | faltam: {len(o - n)} | só no Django: {sorted(n - o)}")
bad = 0
for path, method in migrated:
    fo, fn = fields(old, old["paths"][path][method.lower()]), fields(new, new["paths"][path][method.lower()])
    if fo is not None and fn is not None and fo != fn:
        print("  DIFERENÇA de campos", method, path, "| só no FastAPI:", sorted(fo - fn), "| só no Django:", sorted(fn - fo)); bad += 1
print("Campos de resposta das rotas migradas:", "equivalentes" if not bad else f"{bad} divergência(s)")
print("\nAinda faltam (etapas 7 a 9):")
rest = sorted(o - n)
for p, m in rest: print("  ", m, p)
