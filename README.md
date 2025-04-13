# Kopírovanie .env.example do .env a úprava hodnôt
   cp .env.example .env
   
   # Spustenie aplikácie
   docker compose up --build


# Prístup k API:
- Swagger UI: http://localhost:8000/docs
- ReDoc dokumentácia: http://localhost:8000/redoc
- API endpointy: http://localhost:8000/

# Dôležité poznámky:
- Databáza je dostupná na porte 5432
- FastAPI aplikácia je dostupná na porte 8000