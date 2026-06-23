FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir boto3==1.34.0 psycopg2-binary==2.9.9 python-dotenv==1.0.1 scikit-learn==1.4.2 pandas==2.2.2

COPY upload_dataset.py .
COPY SouthGermanCredit.csv .

CMD ["python", "upload_dataset.py"]