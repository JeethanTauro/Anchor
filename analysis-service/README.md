# Anchor — Analysis Service

The **Analysis Service** is the central application service of Anchor.

It is responsible for managing GitHub repositories, tracking pull requests, receiving GitHub webhook events, determining whether repository indexing is required before a PR can be analyzed, coordinating with the indexing worker through RabbitMQ, retrieving repository context from ChromaDB, reranking retrieved context, building the PR analysis context, and sending the final context to the configured LLM provider.

The Analysis Service does **not** perform repository indexing itself.

Instead, indexing is delegated to the isolated Indexing Worker. The Analysis Service communicates with the worker asynchronously through RabbitMQ.

The service is designed for a **self-hosted deployment model**. The user provides the required GitHub and LLM configuration, while repository and pull request state is maintained internally in PostgreSQL.

---

# Responsibilities

The Analysis Service is responsible for:

- Repository onboarding
- Repository metadata management
- Historical pull request synchronization
- GitHub webhook handling
- Pull request creation and synchronization
- Determining whether a repository needs to be re-indexed
- Creating indexing jobs
- Publishing indexing jobs to RabbitMQ
- Consuming indexing completion events
- Distinguishing onboarding indexing from PR-triggered indexing
- Fetching pull request diffs and changed files
- Generating retrieval embeddings
- Querying ChromaDB
- Filtering retrieved context by repository
- Reranking retrieved repository context
- Building the final LLM context
- Calling the configured Groq LLM
- Producing an AI-generated pull request review

---

# Technology Stack

- Python
- FastAPI
- SQLAlchemy
- PostgreSQL
- Alembic
- RabbitMQ
- aio-pika
- HTTPX
- Sentence Transformers
- ChromaDB
- CrossEncoder
- Groq API

---

# High-Level Architecture


                         GitHub
                           |
             +-------------+-------------+
             |                           |
             | Repository URL             | Webhooks
             |                           |
             v                           v
      POST /repositories          POST /webhooks/github
             |                           |
             +-------------+-------------+
                           |
                           v
                  Analysis Service
                           |
             +-------------+-------------+
             |                           |
             v                           v
        PostgreSQL                  GitHub API
             |
             |
             +----------------------+
             |                      |
             v                      v
       RabbitMQ                 ChromaDB
             |                      |
             |                      |
             v                      |
      Indexing Worker               |
             |                      |
             | indexing.completed   |
             v                      |
      Analysis Consumer <-----------+
             |
             v
       PR Analysis Pipeline
             |
       +-----+------+-------+
       |            |       |
       v            v       v
    GitHub       Chroma   Reranker
       |            |       |
       +------------+-------+
                    |
                    v
                 Context
                    |
                    v
                 Groq LLM
                    |
                    v
              PR Review


---

# Repository Lifecycle

A repository moves through the following lifecycle:

Repository URL
      |
      v
Repository Onboarding
      |
      v
Repository stored in PostgreSQL
      |
      v
Historical PRs synchronized
      |
      v
Initial indexing job created
      |
      v
Indexing Worker
      |
      v
Repository becomes searchable
      |
      v
GitHub PR Webhooks
      |
      v
PR analysis


The `last_indexed_commit` field on the repository is used as the source of truth for determining whether the indexed repository state is sufficiently up to date for a PR.

---

# API Endpoints

## 1. Onboard Repository

```http
POST /repositories
```

Starts repository onboarding.

### Request

```http
Content-Type: application/json
```

```json
{
  "repo_url": "https://github.com/owner/repository"
}
```

### Processing

The Analysis Service:

1. Parses the repository URL.
2. Extracts the GitHub owner and repository name.
3. Fetches repository metadata from GitHub.
4. Checks whether the repository already exists.
5. Creates the repository record if necessary.
6. Determines the repository's current commit.
7. Synchronizes historical pull requests.
8. Creates an `ONBOARDING` indexing job.
9. Publishes the indexing job to RabbitMQ.

### Response

Example:

```json
{
  "message": "Repository onboarded successfully",
  "repository": {
    "id": 14,
    "githubRepoId": 1331889763,
    "owner": "JeethanTauro",
    "name": "DummyRepo",
    "defaultBranch": "main"
  },
  "repositoryCreated": true,
  "pullRequests": {
    "total": 5,
    "new": 5,
    "existing": 0
  }
}
```

---

# Onboarding Flow

```text
Client
  |
  | POST /repositories
  v
Analysis Service
  |
  +--> Parse GitHub URL
  |
  +--> GitHub API
  |      |
  |      +--> Repository metadata
  |      +--> Current branch/commit
  |      +--> Historical PRs
  |
  v
PostgreSQL
  |
  +--> Repository
  |
  +--> Pull Requests
  |
  +--> Indexing Job
        trigger_type = ONBOARDING
  |
  v
RabbitMQ
  |
  v
Indexing Worker
```

The Analysis Service does not wait synchronously for indexing to finish.

Indexing is asynchronous.

---

# 2. GitHub Webhook

```http
POST /webhooks/github
```

Receives GitHub repository events.

The current implementation processes:

```text
event = pull_request
```

with:

```text
action = opened
action = synchronize
```

Other actions are ignored.

---

# Webhook Decision Tree

```text
                 GitHub PR Event
                        |
                        v
                 Event = PR?
                   /       \
                 NO         YES
                 |           |
              Ignore        |
                             v
                       Action supported?
                       /             \
                     NO               YES
                     |                 |
                  Ignore               |
                                       v
                              Find Repository
                                       |
                              +--------+--------+
                              |                 |
                           Not found          Found
                              |               |
                           Return             |
                                             v
                                      Create/update PR
                                             |
                                             v
                                      Index required?
                                       /           \
                                     YES            NO
                                      |              |
                                      v              v
                                  Create job      Analyze PR
                                      |
                                      v
                                  RabbitMQ
```

---

# Indexing Completion Flow

```text
Indexing Worker
       |
       | repository.index.completed
       v
RabbitMQ
       |
       v
Analysis Consumer
       |
       v
Get IndexingJob
       |
       v
Check trigger_type
       |
       +----------------------+
       |                      |
       v                      v
   ONBOARDING                 PR
       |                      |
       v                      v
     ACK              Find associated PR
                              |
                              v
                         Analyze PR
```

---


# Analysis Consumer

The Analysis Service contains a RabbitMQ consumer responsible for:

```text
repository.index.completed
```

The consumer:

1. Receives the event.
2. Extracts the `job_id`.
3. Looks up the `IndexingJob`.
4. Determines the `trigger_type`.
5. Ignores `ONBOARDING` completion events.
6. For `PR` jobs:

   * Finds the repository.
   * Finds the PR associated with the indexed commit.
   * Starts PR analysis.
7. Acknowledges the RabbitMQ message.

---

# PR Analysis Pipeline

Once the repository is known to be sufficiently indexed, PR analysis begins.

The pipeline is:

```text
Pull Request
      |
      +--> GitHub PR metadata
      |
      +--> Changed files
      |
      +--> Complete diff
      |
      v
Build Retrieval Query
      |
      v
Sentence Transformer
      |
      v
Query Embedding
      |
      v
ChromaDB
      |
      v
Repository-filtered Top K
      |
      v
CrossEncoder Reranker
      |
      v
Top Relevant Chunks
      |
      v
Context Builder
      |
      v
Groq LLM
      |
      v
PR Review
```

---



# Analysis Service Request-to-Review Flow

```text
                         GitHub
                           |
                           v
                   Pull Request Event
                           |
                           v
                    FastAPI Webhook
                           |
                           v
                 PullRequestService
                           |
                           v
                   PostgreSQL State
                           |
                           v
                 Indexing Decision
                    /           \
                   /             \
              Required        Not Required
                 |                 |
                 v                 v
          JobService          PRAnalysisService
                 |                 |
                 v                 |
             RabbitMQ              |
                 |                 |
                 v                 |
        Indexing Worker            |
                 |                 |
                 v                 |
          Completed Event          |
                 |                 |
                 v                 |
         Analysis Consumer         |
                 |                 |
                 +--------+--------+
                          |
                          v
                 PRAnalysisService
                          |
                          v
                   GitHub API
                          |
                    +-----+-----+
                    |           |
                    v           v
              Changed Files    Diff
                    |           |
                    +-----+-----+
                          |
                          v
                  EmbeddingService
                          |
                          v
                       ChromaDB
                          |
                          v
                       Top 20
                          |
                          v
                  RerankerService
                          |
                          v
                        Top 5
                          |
                          v
                    LLMService
                          |
                          v
                       Groq
                          |
                          v
                    PR Review
```

---





