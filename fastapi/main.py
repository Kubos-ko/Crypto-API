from fastapi import FastAPI, HTTPException, Depends, status, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
import crud
import models
import schemas
from database import SessionLocal, engine
from redis_client import (
    get_cached_data,
    set_cached_data,
    invalidate_cache,
    COIN_CACHE_KEY,
    MARKET_DATA_CACHE_KEY,
    TOP_COINS_CACHE_KEY,
    redis_client
)
from config import settings
from fastapi.middleware.cors import CORSMiddleware
from background_tasks import start_price_updates
import logging

# Nastavenie logovania
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Vytvorenie tabuliek
schemas.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Crypto API",
    description="API pre správu kryptomien a ich cien",
    version="1.0.0"
)

# Povolenie CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Povolí všetky origins - v produkcii by ste mali špecifikovať konkrétne domény
    allow_credentials=True,
    allow_methods=["*"],  # Povolí všetky HTTP metódy
    allow_headers=["*"],  # Povolí všetky hlavičky
)

# Dependency pre získanie DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.on_event("startup")
async def startup_event():
    """
    Spustí background tasks pri štarte aplikácie
    """
    db = SessionLocal()
    try:
        start_price_updates(db)
    finally:
        db.close()

@app.on_event("shutdown")
async def shutdown_event():
    redis_client.close()

@app.get("/")
def read_root():
    return {"message": "Vitajte v Crypto API"}

@app.get("/coins", response_model=List[models.Coin])
def get_coins(
    skip: int = 0, 
    limit: int = 100, 
    include_metadata: bool = False, 
    include_prices: bool = False,
    db: Session = Depends(get_db)
):
    """
    Získanie zoznamu kryptomien s podporou stránkovania.
    
    Parameters:
    - skip: Počet záznamov ktoré sa majú preskočiť
    - limit: Maximálny počet záznamov ktoré sa majú vrátiť
    - include_metadata: Ak True, vráti aj metadáta kryptomien
    - include_prices: Ak True, vráti aj aktuálne ceny kryptomien
    """
    try:
        cache_key = f"coins:{skip}:{limit}:{include_metadata}:{include_prices}"
        cached_data = get_cached_data(cache_key)
        
        if cached_data:
            return cached_data
        
        coins = crud.get_coins(
            db, 
            skip=skip, 
            limit=limit, 
            include_metadata=include_metadata,
            include_prices=include_prices
        )
        
        # Konvertujeme Pydantic modely na slovníky a serializujeme dátumy
        coins_dict = []
        for coin in coins:
            coin_dict = coin.dict()
            # Konvertujeme dátumy na ISO formát
            if coin_dict.get('created_at'):
                coin_dict['created_at'] = coin_dict['created_at'].isoformat()
            if coin_dict.get('updated_at'):
                coin_dict['updated_at'] = coin_dict['updated_at'].isoformat()
            coins_dict.append(coin_dict)
            
        set_cached_data(cache_key, coins_dict)
        
        return coins
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chyba pri získavaní kryptomien: {str(e)}")

@app.get("/coins/{coin_id}", response_model=models.Coin)
def read_coin(coin_id: str, include_metadata: bool = False, db: Session = Depends(get_db)):
    """
    Získanie detailov kryptomeny podľa ID.
    
    Parameters:
    - coin_id: ID kryptomeny
    - include_metadata: Ak True, vráti aj metadáta kryptomeny
    """
    try:
        cache_key = f"coin:{coin_id}:{include_metadata}"
        cached_data = get_cached_data(cache_key)
        
        if cached_data:
            return cached_data
        
        db_coin = crud.get_coin(db, coin_id=coin_id, include_metadata=include_metadata)
        
        # Konvertujeme Pydantic model na slovník a serializujeme dátumy
        coin_dict = db_coin.dict()
        # Konvertujeme dátumy na ISO formát
        if coin_dict.get('created_at'):
            coin_dict['created_at'] = coin_dict['created_at'].isoformat()
        if coin_dict.get('updated_at'):
            coin_dict['updated_at'] = coin_dict['updated_at'].isoformat()
            
        set_cached_data(cache_key, coin_dict)
        
        return db_coin
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chyba pri získavaní kryptomeny: {str(e)}")

@app.post("/coins", response_model=models.Coin)
def create_coin(coin_id: str, db: Session = Depends(get_db)):
    """
    Vytvorí novú kryptomenu v databáze.
    
    Parameters:
    - coin_id: ID kryptomeny z CoinGecko API (napr. "bitcoin")
    """
    return crud.create_coin(db=db, coin_id=coin_id)

@app.get("/market/top")
async def get_top_coins(limit: int = 10, db: Session = Depends(get_db)):
    """
    Získanie top kryptomien podľa trhovej kapitalizácie.
    
    Parameters:
    - limit: Počet kryptomien ktoré sa majú vrátiť
    """
    try:
        cache_key = TOP_COINS_CACHE_KEY.format(limit)
        cached_data = get_cached_data(cache_key)
        
        if cached_data:
            return cached_data
        
        top_coins = crud.get_coins(db=db, limit=limit)
        
        # Konvertujeme Pydantic modely na slovníky a serializujeme dátumy
        coins_dict = []
        for coin in top_coins:
            coin_dict = coin.dict()
            # Konvertujeme dátumy na ISO formát
            if coin_dict.get('created_at'):
                coin_dict['created_at'] = coin_dict['created_at'].isoformat()
            if coin_dict.get('updated_at'):
                coin_dict['updated_at'] = coin_dict['updated_at'].isoformat()
            coins_dict.append(coin_dict)
            
        set_cached_data(cache_key, coins_dict)
        
        return top_coins
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chyba pri získavaní top kryptomien: {str(e)}")

@app.delete("/coins/{coin_id}")
def delete_coin(coin_id: str, db: Session = Depends(get_db)):
    try:
        crud.delete_coin(db=db, coin_id=coin_id)
        return {"message": f"Kryptomena {coin_id} bola úspešne vymazaná"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chyba pri mazaní kryptomeny: {str(e)}")

@app.get("/prices", response_model=List[models.CoinPrice])
def get_prices(coin_ids: str = Query(..., description="ID kryptomien oddelené čiarkou"), db: Session = Depends(get_db)):
    """
    Získanie cien pre zoznam kryptomien
    
    Parameters:
    - coin_ids: ID kryptomien oddelené čiarkou (napr. "bitcoin,ethereum")
    """
    try:
        coin_id_list = [coin_id.strip() for coin_id in coin_ids.split(",")]
        prices = crud.get_coin_prices(db, coin_id_list)
        
        if not prices:
            raise HTTPException(status_code=404, detail="Žiadne ceny neboli nájdené")
            
        return prices
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chyba pri získavaní cien: {str(e)}")

@app.get("/prices/{coin_id}", response_model=models.CoinPrice)
def get_price(coin_id: str, db: Session = Depends(get_db)):
    """
    Získanie ceny pre jednu kryptomenu
    
    Parameters:
    - coin_id: ID kryptomeny (napr. "bitcoin")
    """
    try:
        price = crud.get_coin_price(db, coin_id)
        if not price:
            raise HTTPException(status_code=404, detail=f"Cena pre kryptomenu {coin_id} nebola nájdená")
        return price
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chyba pri získavaní ceny: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=True
    ) 