from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # Databázové nastavenia
    DATABASE_URL: str
    
    # CoinGecko API
    COINGECKO_API_KEY: str
    COINGECKO_API_URL: str
    
    # FastAPI nastavenia
    APP_HOST: str
    APP_PORT: int
    
    # Redis nastavenia
    REDIS_HOST: str
    REDIS_PORT: int
    
    class Config:
        env_file = "../.env"

@lru_cache()
def get_settings():
    return Settings()

settings = get_settings() 