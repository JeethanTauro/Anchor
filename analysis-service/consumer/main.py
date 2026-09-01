import asyncio

from consumer.consumer import consume_indexing_completed


async def main():
    await consume_indexing_completed()


if __name__ == "__main__":
    asyncio.run(main())