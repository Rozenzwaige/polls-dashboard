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

# Copy seed DB if volume file is missing OR empty (0 bytes)
CMD ["sh", "-c", "[ ! -s /data/polls.db ] && cp /app/seed_polls.db /data/polls.db; python app.py"]
