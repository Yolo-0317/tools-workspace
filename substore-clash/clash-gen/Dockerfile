FROM docker.m.daocloud.io/library/python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

ENV CLASH_GEN_HOST=0.0.0.0
ENV CLASH_GEN_PORT=8787

EXPOSE 8787
CMD ["python", "main.py"]
