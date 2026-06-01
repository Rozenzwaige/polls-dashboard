FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# /data will be the persistent volume — seed polls.db if not already there
RUN mkdir -p /data

ENV DATA_DIR=/data
ENV PORT=8050

EXPOSE 8050

# Copy seed DB on first run if volume is empty
CMD ["sh", "-c", "[ ! -f /data/polls.db ] && cp -n /app/seed_polls.db /data/polls.db 2>/dev/null || true; python app.py"]
