import json
import asyncio
import aio_pika

from aio_pika.abc import AbstractIncomingMessage

from app.config import settings
from app.database.database import AsyncSessionLocal

from app.repository.repository_service import (
    mark_job_running,
    mark_job_completed,
    mark_job_failed,
    update_file_and_chunk_count,
    update_last_indexed_commit
)
from app.events.indexing_event_completed import IndexingCompletedEvent

from app.pipeline.indexer import Indexer
from app.messaging.publisher import publish_indexing_completed

RABBITMQ_URL = settings.rabbitmq_url

indexer = Indexer()


async def on_message(
    message: AbstractIncomingMessage
) -> None:

    job = None

    try:
        # 1. Parse RabbitMQ message
        job = json.loads(message.body)

        job_id = job["job_id"]
        repository_id = job["repository_id"]
        owner = job["owner"]
        repo = job["repo"]
        commit_sha = job["commit_sha"]

        print(f"Received job {job_id}")

        # 2. Mark job as RUNNING
        # This is a separate transaction because
        # indexing may take a long time.
        print("Marking running")
        async with AsyncSessionLocal() as db:

            await mark_job_running(
                db,
                job_id
            )

            await db.commit()

        print(f"Job {job_id} marked as RUNNING")

        # 3. Run indexing pipeline
        result = indexer.index_repository(
            job_id=job_id,
            repository_id=repository_id,
            owner=owner,
            repo=repo,
            commit_sha=commit_sha
        )

        files_processed = result["files_processed"]
        chunks_created = result["chunks_created"]

        print(
            f"Job {job_id} indexed successfully: "
            f"{files_processed} files, "
            f"{chunks_created} chunks"
        )

        # 4. Save all successful indexing results
        # in ONE database transaction.
        print("start the 3 steps for commiting")
        async with AsyncSessionLocal() as db:

            # Save file/chunk statistics
            print("update file and chunk count")
            await update_file_and_chunk_count(
                db,
                job_id,
                files_processed,
                chunks_created
            )

            # Update repository's last indexed commit
            print("update last commit index")
            await update_last_indexed_commit(
                db,
                repository_id,
                commit_sha
            )

            # Mark job as completed
            print("mark completed")
            await mark_job_completed(
                db,
                job_id
            )

            event = IndexingCompletedEvent(
                    job_id=job_id,
                    repository_id=repository_id,
                    commit_sha=commit_sha
                )

            # Commit all three changes together
            print("commited")
            await db.commit()
            await publish_indexing_completed(event)
            print(
                f"Published indexing completed event for job {job_id}"
            )

        print(f"Job {job_id} marked as COMPLETED")

        # 5. Acknowledge RabbitMQ message
        await message.ack()

    except Exception as e:

        print(f"Job failed: {e}")

        # If the message was successfully parsed,
        # mark the corresponding job as FAILED.
        if job is not None:

            job_id = job["job_id"]

            try:

                async with AsyncSessionLocal() as db:

                    await mark_job_failed(
                        db,
                        job_id,
                        str(e)
                    )

                    await db.commit()

            except Exception as db_error:

                print(
                    f"Failed to update job {job_id} "
                    f"as FAILED: {db_error}"
                )

        # Acknowledge the message so a permanently
        # failing job doesn't get consumed forever.
        await message.ack()


async def consuming_job():

    connection = await aio_pika.connect_robust(
        RABBITMQ_URL
    )

    channel = await connection.channel()

    queue = await channel.declare_queue(
        "repository.index",
        durable=True
    )

    await queue.consume(
        on_message
    )

    print(
        "Worker is listening for indexing jobs..."
    )

    # Keep the worker alive
    await asyncio.Future()