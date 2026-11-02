# Backend Django (em construção, ao lado do FastAPI atual). Mesma ideia da imagem da aplicação:
# Python 3.13 slim, usuário sem privilégios, dependências fixadas.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN groupadd --system app \
    && useradd --system --gid app --create-home app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Pastas graváveis já pertencentes ao usuário da aplicação (logs e arquivos estáticos coletados).
RUN mkdir -p /app/logs /app/staticfiles && chown app:app /app/logs /app/staticfiles

COPY --chown=app:app . ./

USER app

EXPOSE 8000

# Produção: um processo com várias threads (o limite de tentativas de login e o das consultas vivem na memória
# do processo). Em desenvolvimento o Compose troca este comando por `manage.py runserver`.
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "8", "--timeout", "30"]
