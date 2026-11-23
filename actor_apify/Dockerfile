FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
WORKDIR /actor
COPY actor_apify/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY n8n/python /tmp/tacctico-etl
RUN pip install --no-cache-dir /tmp/tacctico-etl
COPY actor_apify/src ./src
COPY data_public/actual/mercadolibre_validado.csv ./data.csv
CMD ["python", "-m", "src"]
