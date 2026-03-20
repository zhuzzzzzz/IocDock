FROM m.daocloud.io/docker.io/python:3.10-slim

WORKDIR /app

COPY requirements.txt .
COPY AlertAnalyticsServer.py .

RUN <<EOF
apt update
apt install -y curl
apt autoremove -y
apt clean
rm -rf /var/lib/apt/lists/*
pip install --no-cache-dir -r requirements.txt
EOF

EXPOSE 8000

HEALTHCHECK --interval=1h --timeout=10s --start-period=10s --retries=3 \
  CMD curl -f https://localhost:8000/alerts -k || curl -f http://localhost:8000/alerts || exit 1

CMD ["python", "AlertAnalyticsServer.py"]