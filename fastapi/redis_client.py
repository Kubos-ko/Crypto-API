from redis import Redis
from config import settings
import json

# Cache konštanty
CACHE_TTL = 300  # 5 minút
COIN_CACHE_KEY = "coin:{}"
MARKET_DATA_CACHE_KEY = "market_data:{}"
TOP_COINS_CACHE_KEY = "top_coins:{}"

redis_client = Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    decode_responses=True
)

def get_redis():
    return redis_client

def get_cached_data(key: str):
    data = redis_client.get(key)
    if data:
        return json.loads(data)
    return None

def set_cached_data(key: str, data, ttl: int = CACHE_TTL):
    if hasattr(data, '__json__'):
        serialized_data = data.__json__()
    elif isinstance(data, list):
        serialized_data = [item.__json__() if hasattr(item, '__json__') else item for item in data]
    else:
        serialized_data = data
    redis_client.setex(key, ttl, json.dumps(serialized_data))

def invalidate_cache(pattern: str):
    keys = redis_client.keys(pattern)
    if keys:
        redis_client.delete(*keys) 