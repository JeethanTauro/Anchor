import aio_pika
import json
from app.config import settings
RABBITMQ_URL = settings.rabbitmq_url


async def publish_indexing_job(job: dict):

    connection = await aio_pika.connect_robust(
        RABBITMQ_URL
    )

    channel = await connection.channel()

    queue = await channel.declare_queue(
        "repository.index",
        durable=True
    )

    message = aio_pika.Message(
    body=json.dumps(job).encode(),
    content_type="application/json",
    delivery_mode=aio_pika.DeliveryMode.PERSISTENT
)

    await channel.default_exchange.publish(
        message,
        routing_key=queue.name
    )

    await connection.close()