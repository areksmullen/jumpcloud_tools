FROM debian:bookworm


COPY . /app/

WORKDIR /app


RUN apt update -y \
    && DEBIAN_FRONTEND=noninteractive apt full-upgrade -y \
    && DEBIAN_FRONTEND=noninteractive apt install -y \
    sqlite3 \
    python3 \
    python3-requests \
    jq \
    awscli \
    python3-boto3 \
    && apt autoremove -y \
    && rm -rf /var/lib/apt/lists/*

ENTRYPOINT ["python3","software_reporter.py"]