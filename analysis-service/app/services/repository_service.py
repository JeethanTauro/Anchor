from sqlalchemy.ext.asyncio import AsyncSession

from app.models.repository import Repository

from app.services.github_services import GitHubService
from app.services.pull_request_service import PullRequestService
from app.services.job_services import JobService

from app.repositories.repository_repo import find_by_github_repo_id


class RepositoryService:

    def __init__(
        self,
        github_service: GitHubService,
        pull_request_service: PullRequestService,
        job_service: JobService
    ):
        self.github_service = github_service
        self.pull_request_service = pull_request_service
        self.job_service = job_service

    async def onboard_repository(
        self,
        owner: str,
        repo: str,
        db: AsyncSession
    ):

        # 1. Get repository information from GitHub
        github_repo = await self.github_service.get_repository(
            owner,
            repo
        )

        github_repo_id = github_repo["id"]

        # 2. Check whether repository already exists
        existing_repository = await find_by_github_repo_id(
            db,
            github_repo_id
        )

        if existing_repository:

            # Get the latest commit from GitHub
            branch = await self.github_service.get_branch(
                owner,
                repo,
                existing_repository.default_branch
            )

            current_commit_sha = branch["commit"]["sha"]

            # Check whether this exact commit is already indexed
            if existing_repository.last_indexed_commit == current_commit_sha:
                pull_requests = await self.pull_request_service.onboard_pull_requests(
                    existing_repository,
                    db
                )

                return {
                    "repository": existing_repository,
                    "repository_created": False,
                    "pull_requests": pull_requests
                }

            # Repository has changed since last indexing
            job = await self.job_service.create_indexing_job(
                repository=existing_repository,
                commit_sha=current_commit_sha,
                trigger_type="ONBOARDING",
                db=db
            )

            print(
                f"Created indexing job {job.id} "
                f"for repository {existing_repository.id}"
            )

            pull_requests = await self.pull_request_service.onboard_pull_requests(
                existing_repository,
                db
            )

            return {
                "repository": existing_repository,
                "repository_created": False,
                "pull_requests": pull_requests
            }

        # 3. Create repository
        repository = Repository(
            github_repo_id=github_repo_id,
            owner=github_repo["owner"]["login"],
            name=github_repo["name"],
            default_branch=github_repo["default_branch"],
            last_indexed_commit=None
        )

        # 4. Save repository
        db.add(repository)

        await db.commit()
        await db.refresh(repository)

        # 5. Get current commit of default branch
        branch = await self.github_service.get_branch(
            owner,
            repo,
            repository.default_branch
        )

        commit_sha = branch["commit"]["sha"]

        # 6. Create indexing job
        job = await self.job_service.create_indexing_job(
            repository=repository,
            commit_sha=commit_sha,
            trigger_type="ONBOARDING",
            db=db
        )

        print(
            f"Created indexing job {job.id} "
            f"for repository {repository.id}"
        )

        # 7. Fetch and store historical PRs
        pull_requests = await self.pull_request_service.onboard_pull_requests(
            repository,
            db
        )

        # 8. Return onboarding result
        return {
            "repository": repository,
            "repository_created": True,
            "pull_requests": pull_requests
        }