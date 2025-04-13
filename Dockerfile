FROM python:3.11-slim

WORKDIR /app

# Kopírovanie requirements súboru
COPY requirements.txt .

# Inštalácia závislostí
RUN pip install --no-cache-dir -r requirements.txt

# Kopírovanie zdrojových súborov
COPY . .

# Vytvorenie priečinka pre logy
RUN mkdir -p /app/logs

# Vystavenie portu
EXPOSE 8000

# Presun do adresára fastapi a spustenie aplikácie
WORKDIR /app/fastapi
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"] 