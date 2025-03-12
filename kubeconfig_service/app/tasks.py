import asyncio
import os
from datetime import datetime, timedelta
from app.logger import logger
from app.models import Kubeconf
from app.database import engine
from sqlmodel import Session, select, delete
from app.queue import consume_message

async def cleanup_old_kubeconfigs():
    """Background task to clean up old kubeconfigs files that are no longer in the database"""
    from app.config import settings
    
    # Get all files in the upload directory
    upload_dir = settings.UPLOAD_DIR
    if not os.path.exists(upload_dir):
        logger.warning(f"Upload directory {upload_dir} does not exist")
        return
    
    files_on_disk = set(os.listdir(upload_dir))
    
    with Session(engine) as session:
        # Get all filenames in the database
        db_files = session.exec(select(Kubeconf.filename)).all()
        db_filenames = set(db_files)
        
        # Find files that are on disk but not in the database
        orphaned_files = files_on_disk - db_filenames
        
        # Delete orphaned files
        for filename in orphaned_files:
            file_path = os.path.join(upload_dir, filename)
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    logger.info(f"Deleted orphaned file: {file_path}")
            except Exception as e:
                logger.error(f"Error deleting file {file_path}: {str(e)}")

async def validate_kubeconfigs():
    """Background task to validate kubeconfigs and mark invalid ones"""
    with Session(engine) as session:
        kubeconfigs = session.exec(select(Kubeconf)).all()
        
        for kubeconf in kubeconfigs:
            if not os.path.exists(kubeconf.path):
                logger.warning(f"Kubeconfig file not found: {kubeconf.path}, marking as inactive")
                kubeconf.active = False
                session.add(kubeconf)
        
        session.commit()

async def process_message_queue():
    """Process messages from the queue"""
    while True:
        message = consume_message("kubeconfig_service_queue")
        if message:
            logger.info(f"Processing message: {message}")
            # Process the message based on its type
            if message.get("type") == "validate_kubeconfigs":
                await validate_kubeconfigs()
            elif message.get("type") == "cleanup":
                await cleanup_old_kubeconfigs()
        
        # Sleep to avoid high CPU usage
        await asyncio.sleep(1)

async def background_tasks():
    """Run all background tasks"""
    while True:
        try:
            await cleanup_old_kubeconfigs()
            await validate_kubeconfigs()
            
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