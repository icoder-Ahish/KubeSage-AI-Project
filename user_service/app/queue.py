# Implementation of message queue system using RabbitMQ
# for service-to-service communication

import pika
import json
from app.config import settings
from app.logger import logger

# RabbitMQ connection
connection = None
channel = None

try:
    # Initialize RabbitMQ connection
    credentials = pika.PlainCredentials(
        username=settings.RABBITMQ_USER if hasattr(settings, 'RABBITMQ_USER') else 'guest',
        password=settings.RABBITMQ_PASSWORD if hasattr(settings, 'RABBITMQ_PASSWORD') else 'guest'
    )
    
    connection_params = pika.ConnectionParameters(
        host=settings.RABBITMQ_HOST if hasattr(settings, 'RABBITMQ_HOST') else 'localhost',
        port=settings.RABBITMQ_PORT if hasattr(settings, 'RABBITMQ_PORT') else 5672,
        credentials=credentials,
        heartbeat=600,
        blocked_connection_timeout=300
    )
    
    connection = pika.BlockingConnection(connection_params)
    channel = connection.channel()
    logger.info("RabbitMQ connection established")
except Exception as e:
    logger.warning(f"RabbitMQ connection failed: {str(e)}")

def publish_message(queue_name: str, message: dict):
    """Publish a message to a RabbitMQ queue"""
    global connection, channel
    
    if not connection or connection.is_closed:
        try:
            # Reestablish connection if needed
            credentials = pika.PlainCredentials(
                username=settings.RABBITMQ_USER if hasattr(settings, 'RABBITMQ_USER') else 'guest',
                password=settings.RABBITMQ_PASSWORD if hasattr(settings, 'RABBITMQ_PASSWORD') else 'guest'
            )
            
            connection_params = pika.ConnectionParameters(
                host=settings.RABBITMQ_HOST if hasattr(settings, 'RABBITMQ_HOST') else 'localhost',
                port=settings.RABBITMQ_PORT if hasattr(settings, 'RABBITMQ_PORT') else 5672,
                credentials=credentials
            )
            
            connection = pika.BlockingConnection(connection_params)
            channel = connection.channel()
        except Exception as e:
            logger.error(f"Failed to reestablish RabbitMQ connection: {str(e)}")
            return False
    
    try:
        # Ensure queue exists
        channel.queue_declare(queue=queue_name, durable=True)
        
        # Publish message
        message_str = json.dumps(message)
        channel.basic_publish(
            exchange='',  # Default exchange
            routing_key=queue_name,
            body=message_str,
            properties=pika.BasicProperties(
                delivery_mode=2,  # Make message persistent
                content_type='application/json'
            )
        )
        logger.debug(f"Message published to {queue_name}: {message}")
        return True
    except Exception as e:
        logger.error(f"Failed to publish message: {str(e)}")
        return False

def consume_message(queue_name: str):
    """Consume a message from a RabbitMQ queue (non-blocking)"""
    global connection, channel
    
    if not connection or connection.is_closed:
        try:
            # Reestablish connection if needed
            credentials = pika.PlainCredentials(
                username=settings.RABBITMQ_USER if hasattr(settings, 'RABBITMQ_USER') else 'guest',
                password=settings.RABBITMQ_PASSWORD if hasattr(settings, 'RABBITMQ_PASSWORD') else 'guest'
            )
            
            connection_params = pika.ConnectionParameters(
                host=settings.RABBITMQ_HOST if hasattr(settings, 'RABBITMQ_HOST') else 'localhost',
                port=settings.RABBITMQ_PORT if hasattr(settings, 'RABBITMQ_PORT') else 5672,
                credentials=credentials
            )
            
            connection = pika.BlockingConnection(connection_params)
            channel = connection.channel()
        except Exception as e:
            logger.error(f"Failed to reestablish RabbitMQ connection: {str(e)}")
            return None
    
    try:
        # Ensure queue exists
        channel.queue_declare(queue=queue_name, durable=True)
        
        # Get a message (non-blocking)
        method_frame, header_frame, body = channel.basic_get(queue=queue_name, auto_ack=True)
        
        if method_frame:
            message_str = body.decode('utf-8')
            message = json.loads(message_str)
            logger.debug(f"Message consumed from {queue_name}: {message}")
            return message
        return None
    except Exception as e:
        logger.error(f"Failed to consume message: {str(e)}")
        return None

def setup_consumer(queue_name: str, callback):
    """Set up a consumer that will process messages as they arrive"""
    global connection, channel
    
    if not connection or connection.is_closed:
        try:
            # Establish connection
            credentials = pika.PlainCredentials(
                username=settings.RABBITMQ_USER if hasattr(settings, 'RABBITMQ_USER') else 'guest',
                password=settings.RABBITMQ_PASSWORD if hasattr(settings, 'RABBITMQ_PASSWORD') else 'guest'
            )
            
            connection_params = pika.ConnectionParameters(
                host=settings.RABBITMQ_HOST if hasattr(settings, 'RABBITMQ_HOST') else 'localhost',
                port=settings.RABBITMQ_PORT if hasattr(settings, 'RABBITMQ_PORT') else 5672,
                credentials=credentials
            )
            
            connection = pika.BlockingConnection(connection_params)
            channel = connection.channel()
        except Exception as e:
            logger.error(f"Failed to establish RabbitMQ connection: {str(e)}")
            return False
    
    try:
        # Ensure queue exists
        channel.queue_declare(queue=queue_name, durable=True)
        
        # Set up consumer
        def message_handler(ch, method, properties, body):
            message_str = body.decode('utf-8')
            message = json.loads(message_str)
            callback(message)
            ch.basic_ack(delivery_tag=method.delivery_tag)
        
        channel.basic_consume(queue=queue_name, on_message_callback=message_handler)
        logger.info(f"Consumer set up for queue {queue_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to set up consumer: {str(e)}")
        return False

def start_consuming():
    """Start consuming messages (this will block the thread)"""
    global channel
    if channel:
        try:
            logger.info("Starting to consume messages")
            channel.start_consuming()
        except Exception as e:
            logger.error(f"Error while consuming messages: {str(e)}")

def close_connection():
    """Close the RabbitMQ connection"""
    global connection
    if connection and not connection.is_closed:
        connection.close()
        logger.info("RabbitMQ connection closed")
