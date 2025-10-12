FROM python:3.10-slim

WORKDIR /app
COPY orchestrator/requirements.txt .
RUN pip install -r requirements.txt
COPY orchestrator/ .

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]

