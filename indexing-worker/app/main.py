import asyncio
from app.messaging.consumer import consuming_job

if __name__ == "__main__":
    asyncio.run(consuming_job())

