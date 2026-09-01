import asyncio
import json

import aio_pika
from aio_pika.abc import AbstractIncomingMessage

from sqlalchemy import select

from app.config import settings
from app.database.database import AsyncSessionLocal

from app.models.repository import Repository
from app.models.indexing_job import IndexingJob

from app.services.github_services import GitHubService
from app.services.job_services import JobService
from app.services.pull_request_service import PullRequestService
from app.services.pr_analysis_service import PRAnalysisService
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import LLMService
from app.services.reranker_service import RerankerService
from app.chroma.chroma_store import ChromaStore


RABBITMQ_URL = settings.rabbitmq_url


github_service = GitHubService()
embedding_service = EmbeddingService()
chroma_store = ChromaStore(settings.chroma_host, settings.chroma_port)
llm_service = LLMService()
reranker_service  = RerankerService()


job_service = JobService()

pull_request_service = PullRequestService(
    github_service,
    job_service
)

pr_analysis_service = PRAnalysisService(
    github_service=github_service,
    reranker_service=reranker_service,
    llm_service=llm_service,
    embedding_service=embedding_service,
    chroma_store=chroma_store
)


async def on_indexing_completed(
    message: AbstractIncomingMessage
) -> None:

    try:

        # ---------------------------------------------
        # 1. Parse event
        # ---------------------------------------------

        event = json.loads(message.body)

        job_id = event["job_id"]
        repository_id = event["repository_id"]
        commit_sha = event["commit_sha"]

        print(
            f"Received indexing completed event: "
            f"job_id={job_id}, "
            f"repository_id={repository_id}, "
            f"commit_sha={commit_sha}"
        )

        # ---------------------------------------------
        # 2. Get indexing job
        # ---------------------------------------------

        async with AsyncSessionLocal() as db:

            result = await db.execute(
                select(IndexingJob)
                .where(
                    IndexingJob.id == job_id
                )
            )

            indexing_job = result.scalar_one_or_none()

            if indexing_job is None:

                print(
                    f"Indexing job {job_id} not found"
                )

                await message.ack()
                return

            # -----------------------------------------
            # 3. Check why indexing was triggered
            # -----------------------------------------

            if indexing_job.trigger_type == "ONBOARDING":

                print(
                    f"Indexing job {job_id} "
                    f"was triggered by onboarding."
                )

                print(
                    "No PR analysis required."
                )

                await message.ack()
                return

            # -----------------------------------------
            # 4. Find repository
            # -----------------------------------------

            result = await db.execute(
                select(Repository)
                .where(
                    Repository.id == repository_id
                )
            )

            repository = result.scalar_one_or_none()

            if repository is None:

                print(
                    f"Repository {repository_id} "
                    f"not found"
                )

                await message.ack()
                return

            # -----------------------------------------
            # 5. Find PR associated with commit
            # -----------------------------------------

            pull_request = await (
                pull_request_service
                .get_pr_for_indexed_commit(
                    repository_id,
                    commit_sha,
                    db
                )
            )

            if pull_request is None:

                print(
                    f"No PR found for repository "
                    f"{repository_id} "
                    f"and commit {commit_sha}"
                )

                await message.ack()
                return

            print(
                f"Found PR #{pull_request.github_pr_number} "
                f"for indexing job {job_id}"
            )

        # ---------------------------------------------
        # 6. Start PR analysis
        # ---------------------------------------------

        result = await (
            pr_analysis_service
            .analyze_pull_request(
                repository,
                pull_request
            )
        )

        print(
            f"PR #{pull_request.github_pr_number} "
            f"analysis completed"
        )

        # ---------------------------------------------
        # 7. Acknowledge event
        # ---------------------------------------------

        await message.ack()

    except Exception as e:

        print(
            f"Failed to process indexing completed "
            f"event: {e}"
        )

        await message.nack(
            requeue=False
        )


async def consume_indexing_completed():

    connection = await aio_pika.connect_robust(
        RABBITMQ_URL
    )

    channel = await connection.channel()

    queue = await channel.declare_queue(
        "repository.index.completed",
        durable=True
    )

    await queue.consume(
        on_indexing_completed
    )

    print(
        "Analysis Service is listening for "
        "indexing completed events..."
    )

    await asyncio.Future()