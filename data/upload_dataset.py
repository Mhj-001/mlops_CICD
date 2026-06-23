import os
import io
import boto3
import psycopg2
import pandas as pd
from botocore.client import Config

MINIO_ENDPOINT    = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
MINIO_ACCESS_KEY  = os.getenv("MINIO_ROOT_USER", "minioadmin")
MINIO_SECRET_KEY  = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin123")
MINIO_BUCKET      = os.getenv("MINIO_BUCKET", "datasets")

PG_HOST     = os.getenv("POSTGRES_HOST", "postgres")
PG_PORT     = os.getenv("POSTGRES_PORT", "5432")
PG_DB       = os.getenv("POSTGRES_DB", "mlops_db")
PG_USER     = os.getenv("POSTGRES_USER", "mlops")
PG_PASSWORD = os.getenv("POSTGRES_PASSWORD", "mlops1234")

DATASET_NAME    = "south-german-credit"
DATASET_VERSION = "v1.0"
LOCAL_CSV       = "SouthGermanCredit.csv"


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def ensure_bucket(s3, bucket):
    existing = [b["Name"] for b in s3.list_buckets().get("Buckets", [])]
    if bucket not in existing:
        s3.create_bucket(Bucket=bucket)
        print("Bucket cree : " + bucket)
    else:
        print("Bucket existant : " + bucket)


def upload_dataset(s3, df, bucket, s3_key):
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    size = buf.getbuffer().nbytes
    s3.upload_fileobj(buf, bucket, s3_key)
    print("Dataset uploade : s3://" + bucket + "/" + s3_key + " (" + str(size) + " bytes)")
    return size


def save_metadata(name, version, s3_path, bucket, size_bytes, num_rows, num_columns):
    conn = psycopg2.connect(
        host=PG_HOST, port=PG_PORT,
        dbname=PG_DB, user=PG_USER, password=PG_PASSWORD
    )
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO datasets (name, version, s3_path, bucket, size_bytes, num_rows, num_columns, description)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id;
        """,
        (name, version, s3_path, bucket, size_bytes, num_rows, num_columns, "South German Credit dataset")
    )
    row_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    print("Metadonnees enregistrees dans PostgreSQL avec id=" + str(row_id))
    return row_id


def run():
    print("Lecture du fichier : " + LOCAL_CSV)
    df = pd.read_csv(LOCAL_CSV)
    print("Shape : " + str(df.shape))

    num_rows, num_columns = df.shape
    s3_key  = DATASET_NAME + "/" + DATASET_VERSION + "/" + LOCAL_CSV
    s3_path = "s3://" + MINIO_BUCKET + "/" + s3_key

    s3 = get_s3_client()
    ensure_bucket(s3, MINIO_BUCKET)
    size = upload_dataset(s3, df, MINIO_BUCKET, s3_key)
    save_metadata(DATASET_NAME, DATASET_VERSION, s3_path, MINIO_BUCKET, size, num_rows, num_columns)
    print("Upload termine avec succes.")


if __name__ == "__main__":
    run()