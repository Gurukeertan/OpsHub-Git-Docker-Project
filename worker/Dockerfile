# opshub-worker: third demo container, watched by opshub-monitor
FROM python:3.12-alpine

WORKDIR /app
COPY worker.py .

EXPOSE 7070

CMD ["python", "worker.py"]
