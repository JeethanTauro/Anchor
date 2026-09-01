import chromadb



class ChromaStore:

    def __init__(
        self,
        host:str,
        port:int,
    ):

        self.chroma_client = chromadb.HttpClient(
            host=host,
            port=port
        )

        self.collection = (
            self.chroma_client
            .get_or_create_collection(
                name="repository_code"
            )
        )

    def query(
        self,
        repository_id: int,
        query_embedding: list[float],
        where=None,
        n_results: int = 20
    ):

        filters = {"repository_id": repository_id}

        if where:
            filters = {
                "$and": [
                    {"repository_id": repository_id},
                *[
                    {key: value}
                    for key, value in where.items()
                ]
            ]
        }


        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=filters
        )

        documents = results.get(
            "documents",
            [[]]
        )[0]

        metadatas = results.get(
            "metadatas",
            [[]]
        )[0]

        distances = results.get(
            "distances",
            [[]]
        )[0]

        chunks = []

        for document, metadata, distance in zip(
            documents,
            metadatas,
            distances
        ):

            chunks.append({
                "text": document,
                "metadata": metadata,
                "distance": distance
            })

        return chunks