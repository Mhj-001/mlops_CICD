FROM ghcr.io/mlflow/mlflow:v2.12.2

USER root

RUN pip install --no-cache-dir psycopg2-binary==2.9.9 boto3==1.34.0 && \
    apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*