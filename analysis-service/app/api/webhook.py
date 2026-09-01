from fastapi import APIRouter, Request
from urllib.parse import parse_qs
import json

from sqlalchemy import select

from app.database.database import AsyncSessionLocal
from app.models.repository import Repository

from app.services.github_services import GitHubService
from app.services.pull_request_service import PullRequestService
from app.services.job_services import JobService
from app.services.pr_analysis_service import PRAnalysisService
from app.config import settings
from app.chroma.chroma_store import ChromaStore
from app.services.embedding_service import EmbeddingService
from app.services.reranker_service import RerankerService
from app.services.llm_service import LLMService

router = APIRouter()

github_service = GitHubService()
job_service = JobService()
reranker_service = RerankerService()
llm_service = LLMService()

pull_request_service = PullRequestService(
    github_service,
    job_service
)

embedding_service = EmbeddingService()

chroma_store = ChromaStore(
    host=settings.chroma_host,
    port=settings.chroma_port
)

pr_analysis_service = PRAnalysisService(
    github_service=github_service,
    embedding_service=embedding_service,
    chroma_store=chroma_store,
    reranker_service=reranker_service,
    llm_service=llm_service
)

@router.post("/webhooks/github")
async def github_webhook(request: Request):

    body = await request.body()

    form = parse_qs(body.decode("utf-8"))
    payload = json.loads(form["payload"][0])

    event = request.headers.get("x-github-event")

    if event != "pull_request":
        return {"status": "ignored"}

    action = payload["action"]

    if action not in ("opened", "synchronize"):
        return {"status": "ignored"}

    repository_data = payload["repository"]

    owner = repository_data["owner"]["login"]
    repo = repository_data["name"]
    pr_number = payload["number"]

    # Get latest PR information from GitHub
    pr = await github_service.get_pull_request(
        owner,
        repo,
        pr_number
    )


    async with AsyncSessionLocal() as db:

        # Find repository in our database
        result = await db.execute(
            select(Repository)
            .where(
                Repository.github_repo_id
                == repository_data["id"]
            )
        )

        repository = result.scalar_one_or_none()

        if repository is None:
            return {
                "status": "repository_not_onboarded"
            }

        # ------------------------------------------------
        # PR OPENED
        # ------------------------------------------------

        if action == "opened":
            pull_request = await (
            pull_request_service
                    .create_pull_request(
                    repository,
                    pr,
                    db
                )
            )

            job = await (
            pull_request_service
            .create_indexing_job_if_required(
                    repository,
                    pull_request,
                    db
                )
            )

            if job:
                print(
                    f"PR #{pr_number} requires indexing. "
                    f"Created job {job.id} "
                    f"for commit "
                    f"{pull_request.base_commit_sha}"
                )

            else:

                print(
                    f"PR #{pr_number} does not require indexing."
                )

            # Repository already represents the
            # required base commit.
                await pr_analysis_service.analyze_pull_request(
                    repository,
                    pull_request
                )

        # ------------------------------------------------
        # PR SYNCHRONIZED
        # ------------------------------------------------

        elif action == "synchronize":
            print("SYNCHRONIZE FLOW STARTED")
            pull_request = await (
            pull_request_service
            .update_synchronized_pr(
                    repository.id,
                    pr_number,
                    pr,
                    db
                )
            )

            if pull_request is None:
                print(
                    f"PR #{pr_number} not found locally. "
                    f"Creating PR from synchronize event."
                )

                pull_request = await (
                pull_request_service
                .create_pull_request(
                    repository,
                    pr,
                    db
                    )
                )

            job = await (
                pull_request_service
                .create_indexing_job_if_required(
                    repository,
                    pull_request,
                    db
                )
            )

            if job:
                print(
                    f"Repository changed since "
                    f"last indexing."
                )
                print(
                    f"Created indexing job {job.id} "
                    f"for commit "
                    f"{pull_request.base_commit_sha}"
                )

            else:
                print(
                    "Base commit is already indexed. "
                    "No indexing required."
                )
                print("Starting PR analysis")
                await pr_analysis_service.analyze_pull_request(
                    repository,
                    pull_request
                )
        await db.commit()

    return {
        "status": "received"
    }