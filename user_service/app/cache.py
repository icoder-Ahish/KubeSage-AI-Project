import json
from functools import wraps
from app.logger import logger
import redis
from app.config import settings

# Initialize Redis connection for caching
try:
    redis_cache = redis.Redis(
        host=settings.REDIS_HOST if hasattr(settings, 'REDIS_HOST') else 'localhost',
        port=settings.REDIS_PORT if hasattr(settings, 'REDIS_PORT') else 6379,
        password=settings.REDIS_PASSWORD if hasattr(settings, 'REDIS_PASSWORD') else None,
        db=1  # Use different DB than queue
    )
    # Test connection
    redis_cache.ping()
    logger.info("Redis cache connection established")
except Exception as e:
    logger.warning(f"Redis cache connection failed: {str(e)}")
    redis_cache = None

def cache_get(key: str):
    """Get a value from the cache"""
    if redis_cache:
        try:
            data = redis_cache.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.error(f"Cache get error: {str(e)}")
    return None

def cache_set(key: str, value: any, expiry: int = 3600):
    """Set a value in the cache with expiry in seconds"""
    if redis_cache:
        try:
            redis_cache.setex(key, expiry, json.dumps(value))
            return True
        except Exception as e:
            logger.error(f"Cache set error: {str(e)}")
    return False

def cache_delete(key: str):
    """Delete a value from the cache"""
    if redis_cache:
        try:
            redis_cache.delete(key)
            return True
        except Exception as e:
            logger.error(f"Cache delete error: {str(e)}")
    return False

def cache_flush():
    """Flush all values from the cache"""
    if redis_cache:
        try:
            redis_cache.flushdb()
            return True
        except Exception as e:
            logger.error(f"Cache flush error: {str(e)}")
    return False

def cached(expiry: int = 3600):
    """Decorator to cache function results"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Create a cache key based on function name and arguments
            key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            
            # Try to get from cache
            cached_result = cache_get(key)
            if cached_result is not None:
                logger.debug(f"Cache hit for {key}")
                return cached_result
            
            # If not in cache, call the function
            logger.debug(f"Cache miss for {key}")
            result = await func(*args, **kwargs)
            
            # Cache the result
            cache_set(key, result, expiry)
            
            return result
        return wrapper
    return decorator
