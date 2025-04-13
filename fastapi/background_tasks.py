from fastapi import BackgroundTasks
from sqlalchemy.orm import Session
import crud
from redis_client import redis_client
import asyncio
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Globálna premenná pre sledovanie, či je úloha spustená
price_update_task = None

async def update_prices_periodically(db: Session, interval: int = 60):
    """
    Periodicky aktualizuje ceny kryptomien
    
    Args:
        db: SQLAlchemy session
        interval: Interval aktualizácie v sekundách (default: 60)
    """
    while True:
        try:
            # Získame všetky coin IDs z databázy
            coins = db.query(crud.schemas.Coin).all()
            coin_ids = [coin.coin_id for coin in coins]
            
            if coin_ids:
                # Aktualizujeme ceny
                crud.update_coin_prices(db, coin_ids)
                logger.info(f"Ceny boli aktualizované pre {len(coin_ids)} kryptomien")
                
                # Uložíme čas poslednej aktualizácie do Redis
                redis_client.set("last_price_update", datetime.now().isoformat())
            
            # Počkáme na ďalší interval
            await asyncio.sleep(interval)
            
        except Exception as e:
            logger.error(f"Chyba pri aktualizácii cien: {str(e)}")
            await asyncio.sleep(5)  # Počkáme 5 sekúnd pred ďalším pokusom

def start_price_updates(db: Session):
    """
    Spustí periodické aktualizácie cien v pozadí
    
    Args:
        db: SQLAlchemy session
    """
    global price_update_task
    if price_update_task is None:
        price_update_task = asyncio.create_task(update_prices_periodically(db))
        logger.info("Background task pre aktualizáciu cien bol spustený") 