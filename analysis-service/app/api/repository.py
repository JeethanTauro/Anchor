from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db
from app.schemas.repository import RepositoryCreateRequest
from app.services.github_services import GitHubService
from app.services.pull_request_service import PullRequestService
from app.services.repository_service import RepositoryService
from app.services.job_services import JobService


router = APIRouter()
job_service = JobService()
github_service = GitHubService()
pull_request_service = PullRequestService(github_service,job_service)


repository_service = RepositoryService(
    github_service,
    pull_request_service,
    job_service
)


@router.post("/repositories")
async def onboard_repository(
    request: RepositoryCreateRequest,
    db: AsyncSession = Depends(get_db)
):

    repo_url = request.repo_url.rstrip("/")

    parts = repo_url.split("/")

    owner = parts[-2]
    repo = parts[-1]
    result = await repository_service.onboard_repository(
        owner,
        repo,
        db
    )

    repository = result["repository"]

    return {
        "message": "Repository onboarded successfully",

        "repository": {
            "id": repository.id,
            "githubRepoId": repository.github_repo_id,
            "owner": repository.owner,
            "name": repository.name,
            "defaultBranch": repository.default_branch
        },

        "repositoryCreated": result["repository_created"],

        "pullRequests": result["pull_requests"]
    }

