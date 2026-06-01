FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# /data will be the persistent volume (polls.db + events.db)
RUN mkdir -p /data

ENV DATA_DIR=/data
ENV PORT=8050

EXPOSE 8050

CMD ["python", "app.py"]
