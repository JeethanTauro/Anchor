from app.models.pull_request import PullRequest
from app.models.repository import Repository

from app.services.github_services import GitHubService
from app.services.embedding_service import EmbeddingService
from app.services.reranker_service import RerankerService
from app.services.llm_service import LLMService

from app.chroma.chroma_store import ChromaStore

from app.ui.terminal import (
    print_reranking_results,
    print_analysis_input,
    print_review
)

class PRAnalysisService:

    def __init__(
        self,
        github_service: GitHubService,
        embedding_service: EmbeddingService,
        chroma_store: ChromaStore,
        reranker_service: RerankerService,
        llm_service : LLMService
    ):

        self.github_service = github_service
        self.embedding_service = embedding_service
        self.chroma_store = chroma_store
        self.reranker_service = reranker_service
        self.llm_service = llm_service

    async def analyze_pull_request(
        self,
        repository: Repository,
        pull_request: PullRequest
    ):

        print(
            f"Starting analysis for "
            f"PR #{pull_request.github_pr_number}"
        )

        # -----------------------------------------
        # 1. Get changed files
        # -----------------------------------------

        changed_files = await (
            self.github_service.get_pull_request_files(
                repository.owner,
                repository.name,
                pull_request.github_pr_number
            )
        )

        print(
            f"PR #{pull_request.github_pr_number} "
            f"changed {len(changed_files)} files"
        )

        # -----------------------------------------
        # 2. Get complete PR diff
        # -----------------------------------------

        diff = await (
            self.github_service.get_pull_request_diff(
                repository.owner,
                repository.name,
                pull_request.github_pr_number
            )
        )

        # -----------------------------------------
        # 3. Retrieve + rerank context
        # -----------------------------------------

        final_chunks = []

        for file in changed_files:

            patch = file.get("patch")

            # GitHub may not provide a patch for
            # binary files or very large files.
            if not patch:
                continue

            filename = file["filename"]

            # -------------------------------------
            # Build retrieval query
            # -------------------------------------

            query = (
                f"File: {filename}\n"
                f"Changes:\n"
                f"{patch}"
            )

            print(
                f"\nProcessing retrieval for "
                f"{filename}"
            )

            # -------------------------------------
            # Generate query embedding
            # -------------------------------------

            query_embedding = (
                self.embedding_service.embed(
                    query
                )
            )

            # -------------------------------------
            # First-stage retrieval
            # -------------------------------------
            file_chunks = self.chroma_store.query(
                    repository_id=repository.id,
                    query_embedding=query_embedding,
                    n_results=10,
                    where={
                        "file_path": filename
                }
            )

            semantic_chunks = self.chroma_store.query(
                repository_id=repository.id,
                query_embedding=query_embedding,
                n_results=20
            )

            candidates = file_chunks + semantic_chunks

            print("FILE FILTER:")
            for chunk in file_chunks:
                print(chunk["metadata"]["file_path"])

            print("SEMANTIC:")
            for chunk in semantic_chunks:
                print(chunk["metadata"]["file_path"])

            #deduplication of the candidates
            seen = set()
            unique_chunks = []
            
            for chunk in candidates:
                key = (
                    chunk["metadata"].get("file_path"),
                    chunk["metadata"].get("start_line"),
                    chunk["metadata"].get("end_line"),
                )
            
                if key not in seen:
                    seen.add(key)
                    unique_chunks.append(chunk)

            print(
                f"Retrieved {len(unique_chunks)} chunks "
                f"from ChromaDB"
            )

            if not unique_chunks:
                continue

            # -------------------------------------
            # Second-stage retrieval / reranking
            # -------------------------------------

            reranked_chunks = (
                self.reranker_service.rerank(
                    query=query,
                    chunks=unique_chunks,
                    top_k=5
                )
            )

            print(
                f"Reranked to "
                f"{len(reranked_chunks)} chunks"
            )

            # -------------------------------------
            # Add final chunks
            # -------------------------------------

            final_chunks.extend(
                reranked_chunks
            )

            # -------------------------------------
            # Print reranking results
            # -------------------------------------
            print_reranking_results(reranked_chunks)

        # -----------------------------------------
        # 4. analysis context
        # -----------------------------------------

        #one final deduplication
        seen = set()
        unique_chunks = []

        for chunk in final_chunks:
            key = (
                chunk["metadata"].get("file_path"),
                chunk["metadata"].get("start_line"),
                chunk["metadata"].get("end_line"),
            )

            if key not in seen:
                seen.add(key)
                unique_chunks.append(chunk)

        final_chunks = unique_chunks


        print_analysis_input(
            pull_request=pull_request,
            repository=repository,
            changed_files=changed_files,
            diff=diff,
            final_chunks=final_chunks
        )


        review = await self.llm_service.review_pull_request(
            pull_request={
                "title": pull_request.title,
                "description": pull_request.description,
                "base_commit_sha": pull_request.base_commit_sha,
                "head_commit_sha": pull_request.head_commit_sha
            },
            diff=diff,
            changed_files=changed_files,
            retrieved_chunks=final_chunks
        )
        
        print_review(review)