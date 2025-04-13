from sqlalchemy.orm import Session
from sqlalchemy import desc
import schemas
import models
import requests
from config import settings
from redis_client import redis_client
import json
from typing import Optional, List
from datetime import datetime

def get_coin(db: Session, coin_id: str, include_metadata: bool = False):
    try:
        # Skúsime získať dáta z Redis cache
        cache_key = f"coin:{coin_id}:{include_metadata}"
        cached_data = redis_client.get(cache_key)
        
        if cached_data:
            try:
                return models.Coin(**json.loads(cached_data))
            except Exception as e:
                print(f"Chyba pri deserializácii cache dát: {e}")
                # Ak je problém s cache, pokračujeme s databázou
        
        # Ak nie sú v cache alebo je problém s cache, získame z databázy
        coin = db.query(schemas.Coin).filter(schemas.Coin.coin_id == coin_id).first()
        
        if not coin:
            raise ValueError(f"Kryptomena s ID {coin_id} nebola nájdená")
        
        try:
            # Uložíme do cache na 10 sekúnd
            coin_data = {
                "coin_id": coin.coin_id,
                "symbol": coin.symbol,
                "name": coin.name,
                "created_at": coin.created_at.isoformat() if coin.created_at else None,
                "updated_at": coin.updated_at.isoformat() if coin.updated_at else None
            }
            
            if include_metadata and coin.coin_metadata:
                coin_data["metadata"] = coin.coin_metadata
            
            redis_client.setex(
                cache_key,
                10,  # 10 sekúnd
                json.dumps(coin_data)
            )
        except Exception as e:
            print(f"Chyba pri ukladaní do cache: {e}")
        
        # Vrátime coin s metadátami ak je to požadované
        if include_metadata:
            return models.Coin(
                coin_id=coin.coin_id,
                symbol=coin.symbol,
                name=coin.name,
                created_at=coin.created_at,
                updated_at=coin.updated_at,
                metadata=coin.coin_metadata if coin.coin_metadata else None
            )
        else:
            # Ak nechceme metadáta, vrátime len základné informácie
            return models.Coin(
                coin_id=coin.coin_id,
                symbol=coin.symbol,
                name=coin.name,
                created_at=coin.created_at,
                updated_at=coin.updated_at
            )
    except Exception as e:
        print(f"Chyba v get_coin: {e}")
        raise

def get_coins(db: Session, skip: int = 0, limit: int = 100, include_metadata: bool = False, include_prices: bool = False):
    try:
        cache_key = f"coins:skip:{skip}:limit:{limit}:{include_metadata}:{include_prices}"
        cached_data = redis_client.get(cache_key)
        
        if cached_data:
            try:
                return [models.Coin(**coin_data) for coin_data in json.loads(cached_data)]
            except Exception as e:
                print(f"Chyba pri deserializácii cache dát: {e}")
                # Ak je problém s cache, pokračujeme s databázou
        
        # Získame celkový počet kryptomien
        total_count = db.query(schemas.Coin).count()
        
        # Získame kryptomeny s podporou stránkovania
        coins = db.query(schemas.Coin).order_by(schemas.Coin.coin_id).offset(skip).limit(limit).all()
        
        # Ak chceme ceny, najprv aktualizujeme ceny pre všetky kryptomeny
        if include_prices and coins:
            coin_ids = [coin.coin_id for coin in coins]
            update_coin_prices(db, coin_ids)
        
        # Vrátime coins s metadátami a cenami podľa požiadaviek
        result = []
        for coin in coins:
            # Vytvoríme základný model Coin
            coin_data = {
                "coin_id": coin.coin_id,
                "symbol": coin.symbol,
                "name": coin.name,
                "created_at": coin.created_at.isoformat() if coin.created_at else None,
                "updated_at": coin.updated_at.isoformat() if coin.updated_at else None
            }
            
            # Pridáme metadata ak sú požadované a existujú
            if include_metadata and coin.coin_metadata:
                coin_data["metadata"] = coin.coin_metadata
                
            # Pridáme ceny ak sú požadované
            if include_prices:
                price = db.query(schemas.CoinPrice).filter(schemas.CoinPrice.coin_id == coin.coin_id).first()
                if price:
                    coin_data["price"] = {
                        "usd": float(price.usd) if price.usd else None,
                        "usd_market_cap": float(price.usd_market_cap) if price.usd_market_cap else None,
                        "usd_24h_vol": float(price.usd_24h_vol) if price.usd_24h_vol else None,
                        "usd_24h_change": float(price.usd_24h_change) if price.usd_24h_change else None,
                        "last_updated_at": price.last_updated_at.isoformat() if price.last_updated_at else None
                    }
            
            result.append(coin_data)
            
        # Uložíme do cache
        try:
            redis_client.setex(
                cache_key,
                10,  # 10 sekúnd
                json.dumps(result)
            )
        except Exception as e:
            print(f"Chyba pri ukladaní do cache: {e}")
            
        return result
    except Exception as e:
        print(f"Chyba v get_coins: {e}")
        raise

def create_coin(db: Session, coin_id: str):
    try:
        # Najprv skontrolujeme či kryptomena už existuje
        existing_coin = db.query(schemas.Coin).filter(schemas.Coin.coin_id == coin_id).first()
        if existing_coin:
            # Ak kryptomena existuje, aktualizujeme jej ceny
            update_coin_prices(db, [coin_id])
            return models.Coin(
                coin_id=existing_coin.coin_id,
                symbol=existing_coin.symbol,
                name=existing_coin.name,
                created_at=existing_coin.created_at,
                updated_at=existing_coin.updated_at,
                metadata=existing_coin.coin_metadata if existing_coin.coin_metadata else None
            )

        # Overenie existencie kryptomeny cez CoinGecko API
        response = requests.get(
            f"{settings.COINGECKO_API_URL}/coins/{coin_id}",
            params={
                "localization": "false",
                "tickers": "false",
                "market_data": "false",
                "community_data": "false",
                "developer_data": "false",
                "sparkline": "false"
            }
        )

        if response.status_code != 200:
            raise ValueError(f"Kryptomena s ID {coin_id} nebola nájdená v CoinGecko API")

        coin_data = response.json()

        # Extrahujeme relevantné metadáta
        metadata = {
            "description": coin_data.get("description", {}).get("en"),
            "website_url": coin_data.get("links", {}).get("homepage", [None])[0],
            "blockchain": coin_data.get("asset_platform_id"),
            "smart_contract_address": coin_data.get("contract_address"),
            "genesis_date": coin_data.get("genesis_date"),
            "categories": coin_data.get("categories", []),
            "platforms": coin_data.get("platforms", {}),
            "links": {
                "homepage": coin_data.get("links", {}).get("homepage", []),
                "blockchain_site": coin_data.get("links", {}).get("blockchain_site", []),
                "official_forum_url": coin_data.get("links", {}).get("official_forum_url", []),
                "chat_url": coin_data.get("links", {}).get("chat_url", []),
                "announcement_url": coin_data.get("links", {}).get("announcement_url", []),
                "twitter_screen_name": coin_data.get("links", {}).get("twitter_screen_name"),
                "facebook_username": coin_data.get("links", {}).get("facebook_username"),
                "bitcointalk_thread_identifier": coin_data.get("links", {}).get("bitcointalk_thread_identifier"),
                "telegram_channel_identifier": coin_data.get("links", {}).get("telegram_channel_identifier"),
                "subreddit_url": coin_data.get("links", {}).get("subreddit_url"),
                "repos_url": coin_data.get("links", {}).get("repos_url", {})
            }
        }

        # Vytvoríme novú kryptomenu
        db_coin = schemas.Coin(
            coin_id=coin_id,
            symbol=coin_data["symbol"],
            name=coin_data["name"],
            coin_metadata=metadata
        )
        db.add(db_coin)
        db.commit()
        db.refresh(db_coin)

        # Vytvoríme záznam pre ceny kryptomeny
        db_price = schemas.CoinPrice(
            coin_id=coin_id,
            usd=0,  # Predvolená hodnota, ktorá bude aktualizovaná
            usd_market_cap=0,
            usd_24h_vol=0,
            usd_24h_change=0
        )
        db.add(db_price)
        db.commit()

        # Aktualizujeme ceny kryptomeny
        update_coin_prices(db, [coin_id])

        # Invalidate cache
        redis_client.delete(f"coin:{coin_id}")
        redis_client.delete("coins:*")

        # Vrátime coin s konvertovanými metadátami
        return models.Coin(
            coin_id=db_coin.coin_id,
            symbol=db_coin.symbol,
            name=db_coin.name,
            created_at=db_coin.created_at,
            updated_at=db_coin.updated_at,
            metadata=db_coin.coin_metadata if db_coin.coin_metadata else None
        )
    except Exception as e:
        print(f"Chyba v create_coin: {e}")
        raise

def delete_coin(db: Session, coin_id: str):
    # Najprv skontrolujeme existenciu kryptomeny
    db_coin = db.query(schemas.Coin).filter(schemas.Coin.coin_id == coin_id).first()
    if not db_coin:
        raise ValueError(f"Kryptomena s ID {coin_id} nebola nájdená")
    
    # Vymažeme všetky súvisiace záznamy
    db.query(schemas.CoinPrice).filter(schemas.CoinPrice.coin_id == coin_id).delete()
    db.query(schemas.CoinDetail).filter(schemas.CoinDetail.coin_id == coin_id).delete()
    db.query(schemas.Coin).filter(schemas.Coin.coin_id == coin_id).delete()
    
    db.commit()
    
    # Invalidate cache
    redis_client.delete(f"coin:{coin_id}")
    redis_client.delete(f"price:{coin_id}")
    redis_client.delete(f"details:{coin_id}")
    redis_client.delete("coins:*")
    
    return True 

def get_coin_prices(db: Session, coin_ids: List[str]):
    """
    Získanie cien pre zoznam kryptomien
    """
    try:
        # Najprv aktualizujeme ceny pre existujúce záznamy
        existing_prices = db.query(schemas.CoinPrice).filter(schemas.CoinPrice.coin_id.in_(coin_ids)).all()
        existing_coin_ids = [price.coin_id for price in existing_prices]
        
        if existing_coin_ids:
            update_coin_prices(db, existing_coin_ids)
        
        # Získame aktualizované ceny
        prices = db.query(schemas.CoinPrice).filter(schemas.CoinPrice.coin_id.in_(coin_ids)).all()
        
        if prices:
            try:
                # Uložíme do cache na 10 sekúnd
                prices_data = [price.to_dict() for price in prices]
                cache_key = f"prices:{','.join(sorted(coin_ids))}"
                redis_client.setex(
                    cache_key,
                    10,  # 10 sekúnd
                    json.dumps(prices_data)
                )
            except Exception as e:
                print(f"Chyba pri ukladaní do cache: {e}")
        
        return prices
    except Exception as e:
        print(f"Chyba v get_coin_prices: {e}")
        raise

def update_coin_prices(db: Session, coin_ids: List[str]):
    """
    Aktualizácia cien pre zoznam kryptomien z CoinGecko API
    """
    try:
        # Získame dáta z CoinGecko API
        response = requests.get(
            f"{settings.COINGECKO_API_URL}/simple/price",
            params={
                "ids": ",".join(coin_ids),
                "vs_currencies": "usd",
                "include_market_cap": "true",
                "include_24hr_vol": "true",
                "include_24hr_change": "true",
                "include_last_updated_at": "true",
                "precision": "4"  # Pridané pre presnosť na 4 desatinné miesta
            }
        )

        if response.status_code != 200:
            raise ValueError(f"Chyba pri získavaní dát z CoinGecko API: {response.status_code}")

        prices_data = response.json()
        
        # Aktualizujeme dáta v databáze
        for coin_id, data in prices_data.items():
            db_price = db.query(schemas.CoinPrice).filter(schemas.CoinPrice.coin_id == coin_id).first()
            
            if not db_price:
                continue  # Preskočíme neexistujúce záznamy
            
            # Aktualizujeme hodnoty
            db_price.usd = data.get("usd")
            db_price.usd_market_cap = data.get("usd_market_cap")
            db_price.usd_24h_vol = data.get("usd_24h_vol")
            db_price.usd_24h_change = data.get("usd_24h_change")
            db_price.last_updated_at = datetime.fromtimestamp(data.get("last_updated_at"))
        
        db.commit()
        
        # Invalidate cache
        redis_client.delete(f"prices:{','.join(sorted(coin_ids))}")
        
        return True
    except Exception as e:
        print(f"Chyba v update_coin_prices: {e}")
        raise

def get_coin_price(db: Session, coin_id: str):
    """
    Získanie ceny pre jednu kryptomenu
    """
    try:
        # Najprv skontrolujeme existenciu záznamu
        db_price = db.query(schemas.CoinPrice).filter(schemas.CoinPrice.coin_id == coin_id).first()
        
        if not db_price:
            raise ValueError(f"Cena pre kryptomenu {coin_id} nebola nájdená")
        
        # Aktualizujeme cenu
        update_coin_prices(db, [coin_id])
        
        # Získame aktualizovanú cenu
        price = db.query(schemas.CoinPrice).filter(schemas.CoinPrice.coin_id == coin_id).first()
        
        if price:
            try:
                # Uložíme do cache na 10 sekúnd
                price_data = price.to_dict()
                cache_key = f"price:{coin_id}"
                redis_client.setex(
                    cache_key,
                    10,  # 10 sekúnd
                    json.dumps(price_data)
                )
            except Exception as e:
                print(f"Chyba pri ukladaní do cache: {e}")
        
        return price
    except Exception as e:
        print(f"Chyba v get_coin_price: {e}")
        raise
