import os
import io
import boto3
import psycopg2
import pandas as pd
import mlflow
import mlflow.sklearn
from botocore.client import Config
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.preprocessing import LabelEncoder

MINIO_ENDPOINT = os.getenv("MLFLOW_S3_ENDPOINT_URL", "http://minio:9000")
AWS_KEY        = os.getenv("AWS_ACCESS_KEY_ID", "minioadmin")
AWS_SECRET     = os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin123")
MINIO_BUCKET   = os.getenv("MINIO_BUCKET", "datasets")

PG_HOST     = os.getenv("POSTGRES_HOST", "postgres")
PG_PORT     = os.getenv("POSTGRES_PORT", "5432")
PG_DB       = os.getenv("POSTGRES_DB", "mlops_db")
PG_USER     = os.getenv("POSTGRES_USER", "mlops")
PG_PASSWORD = os.getenv("POSTGRES_PASSWORD", "mlops1234")

MLFLOW_URI  = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
TARGET_COL  = "credit_risk"

mlflow.set_tracking_uri(MLFLOW_URI)
os.environ["MLFLOW_S3_ENDPOINT_URL"] = MINIO_ENDPOINT


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=AWS_KEY,
        aws_secret_access_key=AWS_SECRET,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def get_latest_dataset():
    conn = psycopg2.connect(
        host=PG_HOST, port=PG_PORT,
        dbname=PG_DB, user=PG_USER, password=PG_PASSWORD
    )
    cur = conn.cursor()
    cur.execute("SELECT id, s3_path FROM datasets ORDER BY created_at DESC LIMIT 1;")
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        raise ValueError("Aucun dataset trouve dans PostgreSQL.")
    print("Dataset recupere : id=" + str(row[0]) + " path=" + row[1])
    return row[0], row[1]


def load_csv_from_minio(s3_path):
    s3 = get_s3_client()
    path = s3_path.replace("s3://", "")
    parts = path.split("/", 1)
    bucket = parts[0]
    key    = parts[1]
    obj = s3.get_object(Bucket=bucket, Key=key)
    df = pd.read_csv(io.BytesIO(obj["Body"].read()))
    print("Dataset charge : " + str(df.shape[0]) + " lignes, " + str(df.shape[1]) + " colonnes")
    return df


def save_run_to_postgres(dataset_id, run_id, accuracy):
    conn = psycopg2.connect(
        host=PG_HOST, port=PG_PORT,
        dbname=PG_DB, user=PG_USER, password=PG_PASSWORD
    )
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO model_runs (dataset_id, mlflow_run_id, model_name, accuracy)
        VALUES (%s, %s, %s, %s);
        """,
        (dataset_id, run_id, "RandomForestClassifier", accuracy)
    )
    conn.commit()
    cur.close()
    conn.close()
    print("Run enregistre dans PostgreSQL.")


def train():
    dataset_id, s3_path = get_latest_dataset()
    df = load_csv_from_minio(s3_path)

    if TARGET_COL not in df.columns:
        raise ValueError("Colonne cible introuvable : " + TARGET_COL + ". Colonnes disponibles : " + str(df.columns.tolist()))

    X = df.drop(columns=[TARGET_COL])
    y = df[TARGET_COL]

    for col in X.select_dtypes(include="object").columns:
        X[col] = LabelEncoder().fit_transform(X[col].astype(str))

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    n_estimators = 100
    max_depth    = 8
    min_samples  = 5

    mlflow.set_experiment("south-german-credit")

    with mlflow.start_run() as run:
        model = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            min_samples_split=min_samples,
            random_state=42,
            class_weight="balanced"
        )
        model.fit(X_train, y_train)
        preds = model.predict(X_test)

        acc       = accuracy_score(y_test, preds)
        f1        = f1_score(y_test, preds, average="weighted")
        precision = precision_score(y_test, preds, average="weighted")
        recall    = recall_score(y_test, preds, average="weighted")

        mlflow.log_param("n_estimators",    n_estimators)
        mlflow.log_param("max_depth",       max_depth)
        mlflow.log_param("min_samples_split", min_samples)
        mlflow.log_param("dataset_id",      dataset_id)
        mlflow.log_param("target_col",      TARGET_COL)
        mlflow.log_metric("accuracy",       acc)
        mlflow.log_metric("f1_score",       f1)
        mlflow.log_metric("precision",      precision)
        mlflow.log_metric("recall",         recall)
        mlflow.sklearn.log_model(model, "model")

        run_id = run.info.run_id
        print("Run MLflow : " + run_id)
        print("Accuracy   : " + str(round(acc, 4)))
        print("F1 Score   : " + str(round(f1, 4)))
        print("Precision  : " + str(round(precision, 4)))
        print("Recall     : " + str(round(recall, 4)))

        save_run_to_postgres(dataset_id, run_id, acc)

    print("Entrainement termine avec succes.")


if __name__ == "__main__":
    train()