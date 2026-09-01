from sentence_transformers import CrossEncoder


class RerankerService:

    def __init__(self):

        self.model = CrossEncoder(
            "cross-encoder/ms-marco-MiniLM-L-6-v2"
        )

    def rerank(
        self,
        query: str,
        chunks: list[dict],
        top_k: int = 5
    ) -> list[dict]:

        if not chunks:
            return []

        # -----------------------------------------
        # Build query/candidate pairs
        # -----------------------------------------

        pairs = []

        for chunk in chunks:

            metadata = chunk.get(
                "metadata",
                {}
            )

            candidate = f"""
File: {metadata.get("file_path", "unknown")}
Language: {metadata.get("language", "unknown")}
Lines: {metadata.get("start_line", "?")}-{metadata.get("end_line", "?")}

Code:
{chunk["text"]}
"""

            pairs.append(
                (
                    query,
                    candidate
                )
            )

        # -----------------------------------------
        # Calculate relevance scores
        # -----------------------------------------

        scores = self.model.predict(
            pairs
        )

        # -----------------------------------------
        # Attach scores
        # -----------------------------------------

        scored_chunks = []

        for chunk, score in zip(
            chunks,
            scores
        ):

            scored_chunks.append({
                **chunk,
                "rerank_score": float(score)
            })

        # -----------------------------------------
        # Highest score = most relevant
        # -----------------------------------------

        scored_chunks.sort(
            key=lambda chunk: chunk["rerank_score"],
            reverse=True
        )

        return scored_chunks[:top_k]