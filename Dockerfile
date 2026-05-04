FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python3", "run.py", "--once", "--no-open", "--output", "/data/pulse.html", "--hardware-output", "/data/hardware.html", "--ports-output", "/data/ports.html", "--storage-output", "/data/storage.html", "--services-output", "/data/services.html", "--security-output", "/data/security.html"]
