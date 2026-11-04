FROM python:3.12-slim
WORKDIR /workspace
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app app
COPY agents agents
COPY samples samples
COPY scripts scripts
ENV PYTHONUNBUFFERED=1 DATA_DIR=/data
EXPOSE 8787
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8787"]
