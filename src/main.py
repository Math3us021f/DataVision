from fastapi import FastAPI

app = FastAPI(
    title="DataVision",
    description="API para análise automática de arquivos de dados.",
    version="0.1.0",
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "application": "DataVision",
    }
