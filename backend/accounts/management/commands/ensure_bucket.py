"""Garante que o bucket do MinIO existe (o FastAPI fazia isso ao iniciar)."""

from django.core.management.base import BaseCommand

from core.storage import ensure_bucket


class Command(BaseCommand):
    help = "Cria o bucket do MinIO (MINIO_BUCKET) se ele ainda não existir."

    def handle(self, *args, **options):
        ensure_bucket()
        self.stdout.write("Bucket do MinIO conferido.")
