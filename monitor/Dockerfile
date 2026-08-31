# opshub-monitor: lightweight health-monitoring sidecar for OpsHub
FROM python:3.12-alpine

WORKDIR /app
COPY monitor.py .

EXPOSE 9090

CMD ["python", "monitor.py"]
