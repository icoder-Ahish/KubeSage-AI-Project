# Basic implementation of a queue system using Redis
import redis
import json
from app.config import settings
from app.logger import logger

# Initialize Redis connection
try:
    redis_client = redis.Redis(
        host=settings.REDIS_HOST if hasattr(settings, 'REDIS_HOST') else 'localhost',
        port=settings.REDIS_PORT if hasattr(settings, 'REDIS_PORT') else 6379,
        password=settings.REDIS_PASSWORD if hasattr(settings, 'REDIS_PASSWORD') else None,
        db=0
    )
    # Test connection
    redis_client.ping()
    logger.info("Redis connection established")
except Exception as e:
    logger.warning(f"Redis connection failed: {str(e)}")
    redis_client = None

def publish_message(queue_name: str, message: dict):
    """Publish a message to a queue"""
    if redis_client:
        try:
            message_str = json.dumps(message)
            redis_client.lpush(queue_name, message_str)
            logger.debug(f"Message published to {queue_name}: {message}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish message: {str(e)}")
    return False

def consume_message(queue_name: str):
    """Consume a message from a queue"""
    if redis_client:
        try:
            # BRPOP blocks until a message is available
            result = redis_client.brpop(queue_name, timeout=1)
            if result:
                message_str = result[1].decode('utf-8')
                message = json.loads(message_str)
                logger.debug(f"Message consumed from {queue_name}: {message}")
                return message
        except Exception as e:
            logger.error(f"Failed to consume message: {str(e)}")
    return None