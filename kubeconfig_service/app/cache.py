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

def get_cache_key(user_id: int, key: str) -> str:
    """Generate a cache key specific to a user"""
    return f"user:{user_id}:{key}"

def cache_get(user_id: int, key: str):
    """Get a value from the cache for a specific user"""
    if redis_cache:
        try:
            cache_key = get_cache_key(user_id, key)
            data = redis_cache.get(cache_key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.error(f"Cache get error: {str(e)}")
    return None

def cache_set(user_id: int, key: str, value: any, expiry: int = 3600):
    """Set a value in the cache for a specific user with expiry in seconds"""
    if redis_cache:
        try:
            cache_key = get_cache_key(user_id, key)
            redis_cache.setex(cache_key, expiry, json.dumps(value))
            return True
        except Exception as e:
            logger.error(f"Cache set error: {str(e)}")
    return False

def cache_delete(user_id: int, key: str):
    """Delete a value from the cache for a specific user"""
    if redis_cache:
        try:
            cache_key = get_cache_key(user_id, key)
            redis_cache.delete(cache_key)
            return True
        except Exception as e:
            logger.error(f"Cache delete error: {str(e)}")
    return False

def cache_flush_user(user_id: int):
    """Flush all cache values for a specific user"""
    if redis_cache:
        try:
            pattern = f"user:{user_id}:*"
            keys = redis_cache.keys(pattern)
            if keys:
                redis_cache.delete(*keys)
            return True
        except Exception as e:
            logger.error(f"Cache flush error: {str(e)}")
    return False

def user_cached(expiry: int = 3600):
    """Decorator to cache function results per user"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Look for current_user argument
            current_user = None
            for arg in args:
                if isinstance(arg, dict) and "id" in arg:
                    current_user = arg
                    break
            
            if not current_user and "current_user" in kwargs:
                current_user = kwargs["current_user"]
            
            if not current_user:
                # If no user found, just execute the function without caching
                return await func(*args, **kwargs)
            
            user_id = current_user["id"]
            
            # Create a cache key based on function name and arguments
            key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            
            # Try to get from cache
            cached_result = cache_get(user_id, key)
            if cached_result is not None:
                logger.debug(f"Cache hit for user {user_id}: {key}")
                return cached_result
            
            # If not in cache, call the function
            logger.debug(f"Cache miss for user {user_id}: {key}")
            result = await func(*args, **kwargs)
            
            # Cache the result
            cache_set(user_id, key, result, expiry)
            
            return result
        return wrapper
    return decorator
