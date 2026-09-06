from app.pipeline.workspace import (
    create_workspace,
    cleanup_workspace
)

from app.pipeline.clone_repo import clone_repository

from app.pipeline.file_filter import filter_files

from app.pipeline.chunker import chunk_directory

from app.pipeline.embedder import Embedder

from app.vector_store.chroma_store import ChromaStore


class Indexer:

    def __init__(self):

        self.embedder = Embedder()
        self.chroma_store = ChromaStore()

    def index_repository(
        self,
        job_id: int,
        repository_id: int,
        owner: str,
        repo: str,
        commit_sha: str
    ):

        workspace = create_workspace(job_id)

        try:

            # 1. Clone repository
            repo_path = clone_repository(
                owner,
                repo,
                commit_sha,
                workspace
            )

            # 2. Filter files
            to_index = filter_files(
                repo_path,
                workspace
            )

            # 3. Chunk files
            chunks = chunk_directory(
                to_index,
                repository_id,
                job_id,
                commit_sha
            )

            # 4. Generate embeddings
            embeddings = self.embedder.embed(
                chunks
            )

            # 5. Store in ChromaDB
            self.chroma_store.store(
                chunks,
                embeddings
            )

            files_processed = sum(
                    1
                    for path in to_index.rglob("*")
                    if path.is_file()
            )

            return {
                "files_processed": files_processed,
                "chunks_created": len(chunks)
            }

        finally:

            # Always cleanup workspace
            cleanup_workspace(workspace)