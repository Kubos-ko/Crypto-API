from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, date
import uuid

class CoinBase(BaseModel):
    coin_id: str
    symbol: str
    name: str

class CoinCreate(CoinBase):
    pass

class Coin(CoinBase):
    created_at: datetime
    updated_at: datetime
    metadata: Optional[dict] = Field(default=None, description="Metadáta kryptomeny")
    price: Optional[dict] = Field(default=None, description="Aktuálne ceny kryptomeny")

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat() if dt else None
        }

class CoinPriceBase(BaseModel):
    usd: float = Field(..., description="Cena v USD")
    usd_market_cap: Optional[float] = Field(None, description="Trhová kapitalizácia v USD")
    usd_24h_vol: Optional[float] = Field(None, description="24h objem v USD")
    usd_24h_change: Optional[float] = Field(None, description="Zmena ceny za 24 hodín v %")

class CoinPriceCreate(CoinPriceBase):
    coin_id: str = Field(..., description="ID kryptomeny z CoinGecko API")

class CoinPrice(CoinPriceBase):
    coin_id: str
    created_at: datetime
    updated_at: datetime
    last_updated_at: datetime

    class Config:
        from_attributes = True 