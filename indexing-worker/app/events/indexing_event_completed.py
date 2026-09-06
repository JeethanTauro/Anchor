from pydantic import BaseModel


class IndexingCompletedEvent(BaseModel):

    job_id: int
    repository_id: int
    commit_sha: str
    status: str = "COMPLETED"