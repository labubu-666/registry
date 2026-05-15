FROM python:3.14.5-alpine

ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install uv

COPY src src
COPY cli.py cli.py

COPY pyproject.toml pyproject.toml
COPY uv.lock uv.lock

COPY README.md README.md

RUN uv sync

ENTRYPOINT ["uv", "run", "cli.py", "launch"]
