import os
import hashlib
import pickle
from typing import Any, Optional
from core.config import settings
from core.logging import app_logger

class BaseCache:
    async def get(self, key: str) -> Optional[Any]:
        raise NotImplementedError()
        
    async def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        raise NotImplementedError()

class SQLiteCache(BaseCache):
    def __init__(self, cache_dir: str):
        import diskcache
        self.cache = diskcache.Cache(cache_dir)
        app_logger.info(f"SQLiteCache initialized at directory: {cache_dir}")

    async def get(self, key: str) -> Optional[Any]:
        try:
            return self.cache.get(key)
        except Exception as e:
            app_logger.warning(f"SQLiteCache get failed for key {key}: {e}")
            return None

    async def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        try:
            self.cache.set(key, value, expire=ttl_seconds)
        except Exception as e:
            app_logger.warning(f"SQLiteCache set failed for key {key}: {e}")

class RedisCache(BaseCache):
    def __init__(self, redis_url: str):
        import redis.asyncio as aioredis
        self.redis_url = redis_url
        self.client = aioredis.from_url(redis_url)
        app_logger.info(f"RedisCache initialized with URL: {redis_url}")

    async def get(self, key: str) -> Optional[Any]:
        try:
            data = await self.client.get(key)
            if data is not None:
                return pickle.loads(data)
        except Exception as e:
            app_logger.warning(f"RedisCache get failed for key {key}: {e}")
        return None

    async def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        try:
            data = pickle.dumps(value)
            await self.client.set(key, data, ex=ttl_seconds)
        except Exception as e:
            app_logger.warning(f"RedisCache set failed for key {key}: {e}")

class DummyCache(BaseCache):
    async def get(self, key: str) -> Optional[Any]:
        return None
    async def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        pass

# Initialize cache based on settings
cache: BaseCache

if settings.CACHE_BACKEND == "redis" and settings.REDIS_URL:
    cache = RedisCache(settings.REDIS_URL)
elif settings.CACHE_BACKEND == "sqlite":
    cache_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".cache")
    cache = SQLiteCache(cache_dir)
else:
    cache = DummyCache()

def make_cache_key(namespace: str, *args: Any) -> str:
    # Serialize all args to a string representation
    serialized_args = ":".join(str(arg) for arg in args)
    hash_val = hashlib.sha256(serialized_args.encode("utf-8")).hexdigest()
    return f"{namespace}:{hash_val}"
