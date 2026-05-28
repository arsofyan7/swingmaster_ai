FROM python:3.11-slim

# Bikin user non-root
RUN adduser --disabled-password --gecos '' appuser

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Beri akses read/write database ke appuser
RUN chown -R appuser:appuser /app

# Switch user
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
