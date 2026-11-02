import os

from minio import Minio


def get_minio_client() -> Minio:
    return Minio(
        os.environ["MINIO_ENDPOINT"],
        access_key=os.environ["MINIO_ROOT_USER"],
        secret_key=os.environ["MINIO_ROOT_PASSWORD"],
        secure=False,  # sem TLS em dev; revisar antes de qualquer exposição além de localhost
    )


def ensure_bucket() -> None:
    client = get_minio_client()
    bucket = os.environ["MINIO_BUCKET"]
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
