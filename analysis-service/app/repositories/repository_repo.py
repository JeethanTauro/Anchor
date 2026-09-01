# app/repositories/repository_repo.py

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.repository import Repository


async def find_by_github_repo_id(
    db: AsyncSession,
    github_repo_id: int
):
    result = await db.execute(
        select(Repository)
        .where(Repository.github_repo_id == github_repo_id)
    )

    return result.scalar_one_or_none()