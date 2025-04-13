from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, Date, Text, UUID, JSON
from sqlalchemy.sql import func
from database import Base
import uuid

class Coin(Base):
    __tablename__ = "coins"

    coin_id = Column(String(100), primary_key=True, nullable=False)  # ID z CoinGecko API
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    symbol = Column(String(10), nullable=False)
    name = Column(String(100), nullable=False)
    coin_metadata = Column(JSON, nullable=True)  # Pre uloženie dodatočných informácií z CoinGecko

    def __json__(self):
        return {
            "coin_id": self.coin_id,
            "symbol": self.symbol,
            "name": self.name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "metadata": self.coin_metadata if self.coin_metadata else None
        }

    def to_dict(self):
        return {
            "coin_id": self.coin_id,
            "symbol": self.symbol,
            "name": self.name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "metadata": self.coin_metadata if self.coin_metadata else None
        }

class CoinPrice(Base):
    __tablename__ = "coin_prices"

    coin_id = Column(String(100), ForeignKey("coins.coin_id", ondelete="CASCADE"), primary_key=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    usd = Column(Numeric(24, 8), nullable=False)
    usd_market_cap = Column(Numeric(30, 2))
    usd_24h_vol = Column(Numeric(30, 2))
    usd_24h_change = Column(Numeric(10, 2))
    last_updated_at = Column(DateTime(timezone=True), server_default=func.now())

    def to_dict(self):
        return {
            "coin_id": self.coin_id,
            "usd": float(self.usd) if self.usd else None,
            "usd_market_cap": float(self.usd_market_cap) if self.usd_market_cap else None,
            "usd_24h_vol": float(self.usd_24h_vol) if self.usd_24h_vol else None,
            "usd_24h_change": float(self.usd_24h_change) if self.usd_24h_change else None,
            "last_updated_at": self.last_updated_at.isoformat() if self.last_updated_at else None
        } 