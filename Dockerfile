# Estágio 1: gera os arquivos estáticos do frontend (React). O Node existe só aqui; a imagem final não o tem.
FROM node:22.11.0-slim AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
ENV OUT_DIR=/out
RUN npm run build

# Estágio 2: a aplicação.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN groupadd --system app \
    && useradd --system --gid app --create-home app

COPY requirements.txt constraints.txt ./

# constraints.txt fixa também as dependências indiretas: o build de hoje é igual ao de daqui a seis meses.
RUN pip install --no-cache-dir -r requirements.txt -c constraints.txt

# Pasta de logs já pertencente ao usuário da aplicação: um volume novo montado aqui herda esse dono
# (sem isso, em produção o processo sem privilégios não conseguiria gravar o log).
RUN mkdir -p /app/logs && chown app:app /app/logs

COPY --chown=app:app src/ ./src/
COPY --from=frontend-build --chown=app:app /out ./src/static/app

USER app

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
