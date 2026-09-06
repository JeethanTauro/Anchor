import chromadb

from app.pipeline.chunker import CodeChunk
from app.config import settings

class ChromaStore:

    def __init__(self):

        self.chroma_client = chromadb.HttpClient(
            host=settings.chroma_host,
            port=settings.chroma_port
        )

        self.collection = self.chroma_client.get_or_create_collection(
            name="repository_code"
        )

    def store(
        self,
        chunks: list[CodeChunk],
        embeddings: list[list[float]]
    ):

        if not chunks:
            return

        ids = []

        documents = []

        metadatas = []

        for index, chunk in enumerate(chunks):

            metadata = chunk.metadata

            chunk_id = (
                f"{metadata['repository_id']}_"
                f"{metadata['commit_sha']}_"
                f"{metadata['file_path']}_"
                f"{metadata['start_line']}"
            )

            ids.append(chunk_id)

            documents.append(
                chunk.text
            )

            metadatas.append(
                metadata
            )

        self.collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas
        )