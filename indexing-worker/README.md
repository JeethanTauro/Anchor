# Anchor — Indexing Worker

The **Indexing Worker** is a separate background service in Anchor responsible for converting a GitHub repository into a searchable semantic representation stored in ChromaDB.

It consumes indexing jobs from RabbitMQ, obtains the repository at the exact commit requested by the job, creates an isolated temporary workspace, filters irrelevant files, chunks source code, generates embeddings locally using Sentence Transformers, and stores the resulting code chunks, embeddings, and metadata in ChromaDB.
---

## 1. Responsibilities

The worker is responsible for:

1. Consuming an indexing job from RabbitMQ.
2. Parsing and validating the job event.
3. Marking the job as `RUNNING`.
4. Creating a temporary workspace.
5. Cloning the requested GitHub repository.
6. Checking out the exact commit specified by the job.
7. Discovering and filtering repository files.
8. Copying files selected for indexing into `to_index/`.
9. Chunking source files.
10. Attaching source-location metadata to each chunk.
11. Generating embeddings with Sentence Transformers.
12. Storing chunks, embeddings, and metadata in ChromaDB.
13. Recording file/chunk statistics in PostgreSQL.
14. Updating `repositories.last_indexed_commit`.
15. Marking the job as `COMPLETED`.
16. Acknowledging the RabbitMQ message.
17. Cleaning up temporary files.
18. Marking jobs as `FAILED` and recording errors when processing fails.

---

## 2. Position in the Anchor Architecture

```text
                         GitHub
                           |
                           v
                  +------------------+
                  | Analysis Service |
                  |     FastAPI      |
                  +--------+---------+
                           |
                           | Create indexing job
                           v
                    +-------------+
                    |  PostgreSQL |
                    | indexing_jobs
                    +------+------+
                           |
                           | Publish event
                           v
                    +-------------+
                    |  RabbitMQ   |
                    | repository. |
                    |    index    |
                    +------+------+
                           |
                           | Consume event
                           v
                  +------------------+
                  |  Indexing Worker |
                  +--------+---------+
                           |
                           v
                  Indexing Pipeline
                           |
        +------------------+------------------+
        |                  |                  |
        v                  v                  v
   GitHub/files        Embedding          ChromaDB
                      model
                           |
                           v
                    Searchable code
                           |
                           v
                    Analysis Agents
```

