from sentence_transformers import SentenceTransformer

from app.pipeline.chunker import CodeChunk


class Embedder:

    def __init__(self):
        self.model = SentenceTransformer(
            "all-MiniLM-L6-v2"
        )

    def embed(
        self,
        chunks: list[CodeChunk]
    ) -> list[list[float]]:

        texts = [
            chunk.text
            for chunk in chunks
        ]

        embeddings = self.model.encode(
            texts,
            convert_to_numpy=True
        )

        return embeddings.tolist()