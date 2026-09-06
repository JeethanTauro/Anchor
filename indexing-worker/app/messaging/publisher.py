import json
import aio_pika

from app.config import settings
from app.events.indexing_event_completed import IndexingCompletedEvent


RABBITMQ_URL = settings.rabbitmq_url


async def publish_indexing_completed(
    event: IndexingCompletedEvent
):
    connection = await aio_pika.connect_robust(
        RABBITMQ_URL
    )

    channel = await connection.channel()

    message = aio_pika.Message(
        body=event.model_dump_json().encode(),
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        content_type="application/json"
    )

    await channel.default_exchange.publish(
        message,
        routing_key="repository.index.completed"
    )

    await connection.close()