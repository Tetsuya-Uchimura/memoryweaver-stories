FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-noto-cjk && rm -rf /var/lib/apt/lists/*
WORKDIR /workspace
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked pip install --timeout 60 -r requirements.txt
COPY app app
COPY agents agents
COPY samples samples
COPY scripts scripts
ENV PYTHONUNBUFFERED=1 DATA_DIR=/data
EXPOSE 8787
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8787"]
