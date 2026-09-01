from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Repository
from app.models.indexing_job import IndexingJob
from app.messaging.publisher import publish_indexing_job


class JobService:

    async def create_indexing_job(
        self,
        repository: Repository,
        commit_sha: str,
        trigger_type: str,
        db: AsyncSession
    ):

        # Create job in PostgreSQL
        job = IndexingJob(
            repository_id=repository.id,
            commit_sha=commit_sha,
            trigger_type=trigger_type,
            status="QUEUED"
        )

        db.add(job)

        await db.commit()
        await db.refresh(job)

        # Publish job to RabbitMQ
        await publish_indexing_job({
            "job_id": job.id,
            "repository_id": repository.id,
            "github_repo_id": repository.github_repo_id,
            "owner": repository.owner,
            "repo": repository.name,
            "commit_sha": commit_sha
        })

        return job