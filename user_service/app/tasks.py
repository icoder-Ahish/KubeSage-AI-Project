import asyncio
import time
from datetime import datetime, timedelta
from app.logger import logger
from app.models import User, UserToken
from app.database import engine
from sqlmodel import Session, select, delete
from app.queue import consume_message

async def cleanup_expired_tokens():
    """Background task to clean up expired tokens"""
    with Session(engine) as session:
        expired_tokens = session.exec(
            select(UserToken).where(UserToken.expires_at < datetime.now())
        ).all()
        
        if expired_tokens:
            for token in expired_tokens:
                logger.info(f"Cleaning up expired token for user_id {token.user_id}")
                session.delete(token)
            
            session.commit()
            logger.info(f"Cleaned up {len(expired_tokens)} expired tokens")

async def process_message_queue():
    """Process messages from the queue"""
    while True:
        message = consume_message("user_service_queue")
        if message:
            logger.info(f"Processing message: {message}")
            # Process the message based on its type
            if message.get("type") == "user_created":
                # Example: Send welcome email
                logger.info(f"User created: {message.get('username')}")
            elif message.get("type") == "password_reset":
                # Example: Process password reset
                logger.info(f"Password reset for: {message.get('username')}")
        
        # Sleep to avoid high CPU usage
        await asyncio.sleep(1)

async def background_tasks():
    """Run all background tasks"""
    while True:
        try:
            await cleanup_expired_tokens()
            # Run other periodic tasks here
            
            # Wait for the next cycle (e.g., every hour)
            await asyncio.sleep(3600)
        except Exception as e:
            logger.error(f"Error in background tasks: {str(e)}")
            await asyncio.sleep(60)  # Retry after a minute

def start_background_tasks():
    """Start all background tasks"""
    loop = asyncio.get_event_loop()
    loop.create_task(background_tasks())
    loop.create_task(process_message_queue())
