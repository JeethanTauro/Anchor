from datetime import datetime

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.repository import Repository

from app.models.indexing_job import IndexingJob

#mark job running
async def mark_job_running(
    db: AsyncSession,
    job_id: int
):
    stmt = (
        update(IndexingJob)
        .where(IndexingJob.id == job_id)
        .values(
            status="RUNNING",
            started_at=datetime.utcnow()
        )
    )

    await db.execute(stmt)
    await db.commit()


# mark job completed
async def mark_job_completed(
    db: AsyncSession,
    job_id: int
):
    stmt = (
        update(IndexingJob)
        .where(IndexingJob.id == job_id)
        .values(
            status="COMPLETED",
            ended_at=datetime.utcnow()
        )
    )

    await db.execute(stmt)

#mark job as failed
async def mark_job_failed(
    db: AsyncSession,
    job_id: int,
    error_message: str
):
    stmt = (
        update(IndexingJob)
        .where(IndexingJob.id == job_id)
        .values(
            status="FAILED",
            ended_at=datetime.utcnow(),
            error_message=error_message
        )
    )
    await db.execute(stmt)

#save the file and chunk processed count
async def update_file_and_chunk_count(
    db: AsyncSession,
    job_id: int,
    files_processed: int,
    chunks_created: int
):
    stmt = (
        update(IndexingJob)
        .where(IndexingJob.id == job_id)
        .values(
            files_processed=files_processed,
            chunks_created=chunks_created
        )
    )

    await db.execute(stmt)

async def update_last_indexed_commit(
    db: AsyncSession,
    repository_id: int,
    commit_sha: str
):
    stmt = (
        update(Repository)
        .where(Repository.id == repository_id)
        .values(
            last_indexed_commit=commit_sha
        )
    )

    await db.execute(stmt)
