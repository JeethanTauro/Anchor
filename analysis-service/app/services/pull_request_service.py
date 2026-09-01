from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.services.github_services import GitHubService
from app.services.job_services import JobService


class PullRequestService:

    def __init__(self, github_service: GitHubService,  job_service: JobService):
        self.github_service = github_service
        self.job_service = job_service

    async def onboard_pull_requests(
        self,
        repository: Repository,
        db: AsyncSession,
       
    ):

        # Get all historical PRs from GitHub
        pull_requests = await self.github_service.get_pull_requests(
            repository.owner,
            repository.name
        )

        new_count = 0
        existing_count = 0

        for pr in pull_requests:

            # Check whether this PR already exists
            result = await db.execute(
                select(PullRequest)
                .where(
                    PullRequest.repository_id == repository.id,
                    PullRequest.github_pr_number == pr["number"]
                )
            )

            existing_pr = result.scalar_one_or_none()

            if existing_pr:
                existing_count += 1
                continue

            # PR doesn't exist → create it
            pull_request = PullRequest(
                repository_id=repository.id,
                github_pr_number=pr["number"],
                title=pr["title"],
                description=pr["body"],
                source_branch=pr["head"]["ref"],
                target_branch=pr["base"]["ref"],
                base_commit_sha=pr["base"]["sha"],
                head_commit_sha=pr["head"]["sha"],
                status=pr["state"]
            )

            db.add(pull_request)

            new_count += 1

        await db.commit()

        return {
            "total": len(pull_requests),
            "new": new_count,
            "existing": existing_count
        }

# Create pull request
    async def create_pull_request(
        self,
        repository: Repository,
        pr: dict,
        db: AsyncSession
    ):

        pull_request = PullRequest(
            repository_id=repository.id,
            github_pr_number=pr["number"],
            title=pr["title"],
            description=pr["body"],
            source_branch=pr["head"]["ref"],
            target_branch=pr["base"]["ref"],
            base_commit_sha=pr["base"]["sha"],
            head_commit_sha=pr["head"]["sha"],
            status=pr["state"]
        )

        db.add(pull_request)

        await db.flush()

        return pull_request
    
   #creates indexing job for the repo if the base commit sha doesnt match the last indexed commit sha
    async def create_indexing_job_if_required(
        self,
        repository: Repository,
        pull_request: PullRequest,
        db: AsyncSession
    ):
    # Check whether repository needs to be indexed
        if not self.should_index_for_pr(
            repository,
            pull_request
        ):
            return None

    # Index the exact commit that the PR is based on
        job = await self.job_service.create_indexing_job(
            repository=repository,
            commit_sha=pull_request.base_commit_sha,
            trigger_type="PR",
            db=db
        )

        return job

    #checks whether we should index the repo before the PR review
    def should_index_for_pr(
        self,
        repository: Repository,
        pull_request: PullRequest
    ) -> bool:

        return (
            repository.last_indexed_commit
            != pull_request.base_commit_sha
        )

#   If some commits are done on the PR itself then PR needs to be synchronised
    async def update_synchronized_pr(
        self,
        repository_id: int,
        github_pr_number: int,
        pr: dict,
        db: AsyncSession
    ):

        result = await db.execute(
            select(PullRequest)
            .where(
                PullRequest.repository_id == repository_id,
                PullRequest.github_pr_number == github_pr_number
            )
        )

        pull_request = result.scalar_one_or_none()

        if pull_request is None:
            return None

        pull_request.title = pr["title"]
        pull_request.description = pr["body"]
        pull_request.source_branch = pr["head"]["ref"]
        pull_request.target_branch = pr["base"]["ref"]
        pull_request.base_commit_sha = pr["base"]["sha"]
        pull_request.head_commit_sha = pr["head"]["sha"]
        pull_request.status = pr["state"]

        await db.flush()

        return pull_request
    async def get_pr_for_indexed_commit(
        self,
        repository_id: int,
        commit_sha: str,
        db: AsyncSession
    ):
        result = await db.execute(
            select(PullRequest)
            .where(
                PullRequest.repository_id == repository_id,
                PullRequest.base_commit_sha == commit_sha
            )
            .order_by(
                PullRequest.updated_at.desc()
            )
        )

        return result.scalars().first()