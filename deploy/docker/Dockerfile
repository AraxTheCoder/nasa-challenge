# T14: the Live API's Python environment. The code itself is bind-mounted from the repo (read-only), so a
# deploy is `git pull && docker compose restart api`; only requirements.lock changes need a rebuild.
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
COPY requirements.lock /tmp/requirements.lock
RUN pip install -r /tmp/requirements.lock
WORKDIR /app
