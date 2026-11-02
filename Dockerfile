# Estágio 1: gera os arquivos estáticos do frontend (React). O Node existe só aqui; a imagem final não o tem.
FROM node:22.11.0-slim AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
ENV OUT_DIR=/out
RUN npm run build

# Estágio 2 ("backend"): o Django com as dependências. É o alvo do Compose de desenvolvimento, que monta o código de
# ./backend por cima e a interface gerada em backend/static_src/app.
FROM python:3.13-slim AS backend

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN groupadd --system app \
    && useradd --system --gid app --create-home app

COPY backend/requirements.txt backend/constraints.txt ./

# constraints.txt fixa também as dependências indiretas: o build de hoje é igual ao de daqui a seis meses.
RUN pip install --no-cache-dir -r requirements.txt -c constraints.txt

# Pastas graváveis já pertencentes ao usuário da aplicação (logs e arquivos estáticos coletados): um volume novo
# montado em /app/logs herda esse dono (sem isso, em produção o processo sem privilégios não gravaria o log).
RUN mkdir -p /app/logs /app/staticfiles && chown app:app /app/logs /app/staticfiles

COPY --chown=app:app backend/ ./

# Estágio 3 ("production"): a imagem completa, com a interface gerada dentro e os estáticos coletados.
FROM backend AS production
COPY --from=frontend-build --chown=app:app /out ./static_src/app
# Valores falsos só para o collectstatic carregar as configurações; nada disso fica na imagem final em uso.
# LOG_DIR fora de /app/logs: senão o build (como root) cria app.log lá e o processo sem privilégios não consegue gravá-lo.
RUN SECRET_KEY=so-para-o-build DJANGO_DATABASE_URL=postgresql://x:x@localhost/x APP_ENV=production LOG_DIR=/tmp/log-do-build python manage.py collectstatic --noinput \
    && chown -R app:app /app/staticfiles

USER app

EXPOSE 8000

# Um processo com várias threads: o limite de tentativas de login e o das consultas vivem na memória do processo.
# Ao subir: migrações, administrador inicial e bucket do MinIO (todos idempotentes), depois o gunicorn.
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py ensure_admin && python manage.py ensure_bucket && exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 1 --threads 8 --timeout 30 --control-socket /tmp/gunicorn.ctl"]
