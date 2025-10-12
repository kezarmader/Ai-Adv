FROM python:3.10-slim
WORKDIR /app
COPY poster-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY poster-service/ .
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5002"]
