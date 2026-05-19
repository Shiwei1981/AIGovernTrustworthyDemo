FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8010

WORKDIR /app

COPY apps/evaluation-runner/requirements.txt /app/apps/evaluation-runner/requirements.txt
COPY packages/shared-contracts /app/packages/shared-contracts

RUN cd /app/apps/evaluation-runner \
    && pip install --no-cache-dir -r requirements.txt

COPY apps/consumer_common.py /app/apps/consumer_common.py
COPY apps/evaluation-runner /app/apps/evaluation-runner
COPY docs/evaluation-data /app/docs/evaluation-data
COPY infra/target-registry /app/infra/target-registry

EXPOSE 8010

CMD ["python", "apps/evaluation-runner/app.py"]
