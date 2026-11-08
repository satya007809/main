FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends libreoffice-writer libreoffice-calc fonts-liberation \
      fonts-noto-core && rm -rf /var/lib/apt/lists/*
# Times New Roman metric-compatible font for page counting (Liberation Serif). Word on iPhone uses real TNR.
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd -m bid && mkdir -p /var/lib/bharati/storage && chown -R bid /var/lib/bharati
USER bid
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers"]
