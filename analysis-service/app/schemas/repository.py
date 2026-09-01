from pydantic import BaseModel


class RepositoryCreateRequest(BaseModel):
    repo_url: str