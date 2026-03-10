FROM python:3.11-slim
RUN apt-get update && apt-get install -y \
    postgresql-client git \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY . .
ARG GITHUB_TOKEN
RUN pip install --no-cache-dir -r requirements.txt
RUN groupadd -r tg_vpn && \
    useradd -r -g tg_vpn tg_vpn && \
    chown -R tg_vpn:tg_vpn /app
USER tg_vpn
CMD ["python", "main.py"]