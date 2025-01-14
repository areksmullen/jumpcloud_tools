FROM debian:bookworm

WORKDIR /app

RUN apt update -y \
    && apt full-upgrade -y \
    && apt install -y \
        python3 \
        python3-requests \
        python3-boto3

COPY ./software_remover.py /app/

ENTRYPOINT [ "python3","software_remover.py" ]