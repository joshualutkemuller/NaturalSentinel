FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

# postgresql-client provides psql and pg_isready for DB operations
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*
