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

# Database Model

The Analysis Service maintains the persistent state required for repository and PR analysis.

## Repository

```text
Repository
--------------------------------
id
github_repo_id
owner
name
default_branch
last_indexed_commit
created_at
updated_at
```

### Important fields

### `id`

Internal PostgreSQL repository ID.

This ID is used internally by Anchor and is the primary identifier used when querying repository-specific data.

### `github_repo_id`

The immutable repository identifier supplied by GitHub.

This is used when matching incoming webhook events to an onboarded repository.

### `owner`

GitHub repository owner.

### `name`

GitHub repository name.

### `default_branch`

Repository default branch.

### `last_indexed_commit`

The commit SHA currently represented by the indexed repository state.

This field is critical to PR indexing decisions.

---

# Pull Request

```text
PullRequest
--------------------------------
id
repository_id
github_pr_number
title
description
source_branch
target_branch
base_commit_sha
head_commit_sha
status
created_at
updated_at
```

A pull request belongs to exactly one repository.

```text
Repository
     |
     +---- PullRequest #1
     |
     +---- PullRequest #2
     |
     +---- PullRequest #3
```

The important commit fields are:

### `base_commit_sha`

The repository commit against which the PR is being evaluated.

This is compared against:

```text
Repository.last_indexed_commit
```

to determine whether the indexed repository context is current enough for the PR.

### `head_commit_sha`

The latest commit on the PR branch.

This changes whenever the PR is synchronized with new commits.

---

# Indexing Job

The Analysis Service also tracks indexing jobs.

```text
IndexingJob
--------------------------------
id
repository_id
commit_sha
trigger_type
status
created_at
started_at
ended_at
error_message
files_processed
chunks_created
```

The Analysis Service does not execute these jobs itself.

It creates the job record and publishes a message to the indexing queue.

---

# Indexing Job Trigger Types

The `trigger_type` field distinguishes why an indexing job was created.

Currently:

```text
ONBOARDING
PR
```

### ONBOARDING

The repository is being indexed for the first time.

The resulting `indexing.completed` event does **not** trigger PR analysis.

### PR

A pull request requires the repository to be indexed at its base commit before analysis can begin.

The resulting `indexing.completed` event triggers PR analysis.

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

# GitHub Webhook Request

GitHub sends the webhook request automatically.

Important headers include:

```http
X-GitHub-Event: pull_request
X-GitHub-Delivery: <delivery-id>
X-Hub-Signature-256: <signature>
Content-Type: application/x-www-form-urlencoded
```

The body contains GitHub's webhook payload.

The current webhook implementation extracts:

```text
action
repository
owner
repo
PR number
```

and then fetches the current PR state through the GitHub API.

---

# Webhook Repository Resolution

The incoming GitHub repository ID is used to locate the corresponding Anchor repository.

Conceptually:

```text
GitHub webhook
      |
      v
repository.id
      |
      v
PostgreSQL
      |
      v
Repository
```

The service does not rely only on the repository name because names can change.

The internal `Repository.id` is then used throughout Anchor for repository-specific operations.

---

# PR Opened Flow

When:

```text
event = pull_request
action = opened
```

the service:

1. Fetches the latest PR information.
2. Creates or updates the local `PullRequest` record.
3. Stores:

   * PR number
   * title
   * description
   * source branch
   * target branch
   * base commit
   * head commit
   * status
4. Determines whether repository indexing is required.

---

# PR Indexing Decision

The central decision is:

```python
repository.last_indexed_commit != pull_request.base_commit_sha
```

### If equal

```text
last_indexed_commit
        ==
base_commit_sha
```

The repository already represents the required state.

No indexing is necessary.

The service can immediately begin PR analysis.

```text
PR opened
    |
    v
Base commit == indexed commit
    |
    v
No indexing
    |
    v
PR Analysis
```

### If different

```text
last_indexed_commit
        !=
base_commit_sha
```

The repository's indexed state is stale relative to the PR's base.

The service creates a PR-triggered indexing job.

```text
PR opened
    |
    v
Base commit != indexed commit
    |
    v
Create IndexingJob
trigger_type = PR
    |
    v
RabbitMQ
    |
    v
Indexing Worker
```

The Analysis Service then waits for the indexing completion event.

---

# PR Synchronize Flow

GitHub sends:

```text
event = pull_request
action = synchronize
```

when new commits are pushed to an existing pull request.

The Analysis Service:

1. Fetches the latest PR state.
2. Updates the local PR record , if the Local PR record isn't present then it creates one from the data.
3. Updates the latest `head_commit_sha`.
4. Updates the PR's base commit information if necessary.
5. Re-evaluates whether indexing is required.
6. Retrieves the latest PR diff during analysis.

The same indexing decision is performed:

```text
repository.last_indexed_commit
            vs
pull_request.base_commit_sha
```

---

# PR Synchronization

The important distinction is:

```text
base commit
```

determines the repository state required for analysis.

Whereas:

```text
head commit
```

determines the latest version of the proposed changes.

Therefore, when a contributor pushes another commit to the PR:

```text
head_commit_sha
      |
      v
changes
      |
      v
new PR diff
```

The repository may or may not require re-indexing depending on whether its indexed base state is still valid.

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
                              |                 |
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

# RabbitMQ Integration

RabbitMQ is used to decouple long-running indexing operations from the Analysis Service.

The Analysis Service interacts with two logical queues.

---

# Queue 1 — Repository Indexing

```text
repository.index
```

This queue carries indexing requests from the Analysis Service to the Indexing Worker.

Example message:

```json
{
  "job_id": 15,
  "repository_id": 14,
  "github_repo_id": 1331889763,
  "owner": "JeethanTauro",
  "repo": "DummyRepo",
  "commit_sha": "abc123..."
}
```

The Analysis Service does not wait for the worker to finish.

It publishes the job and continues.

---

# Queue 2 — Indexing Completed

```text
repository.index.completed
```

The Indexing Worker publishes an event after successful indexing.

Example:

```json
{
  "job_id": 15,
  "repository_id": 14,
  "commit_sha": "abc123..."
}
```

The Analysis Service has a dedicated consumer for this event.

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

# Why `trigger_type` Exists

The indexing completion event is generated for multiple reasons.

For example:

```text
Repository onboarding
```

creates:

```text
trigger_type = ONBOARDING
```

while a PR that requires a fresh repository index creates:

```text
trigger_type = PR
```

Without this distinction, the Analysis Service would receive an indexing completion event during onboarding and incorrectly attempt to find a PR to analyze.

The consumer therefore checks:

```text
IndexingJob.trigger_type
```

before deciding what to do.

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

# GitHub Data Used During Analysis

The Analysis Service fetches two important pieces of information from GitHub.

## Changed Files

The GitHub API provides information such as:

```text
filename
status
additions
deletions
changes
patch
```

Example:

```text
File: src/auth/service.py
Status: modified
Additions: 12
Deletions: 3
Patch:
@@ ...
```

This identifies exactly what the PR changed.

---

# Complete PR Diff

The complete PR diff is also retrieved.

The diff represents the aggregate changes introduced by the pull request.

The diff is passed to the context-building stage and eventually to the LLM.

---

# Retrieval

The Analysis Service uses the PR changes to construct retrieval queries.

A basic query currently contains:

```text
File: <filename>

Changes:
<patch>
```

Example:

```text
File: src/auth/service.py

Changes:
@@ -20,4 +20,8 @@
 ...
 + validate_token(...)
 + ...
```

---

# Embedding Generation

The retrieval query is converted into an embedding using Sentence Transformers.

```text
PR Query
   |
   v
Sentence Transformer
   |
   v
Vector
```

The same embedding model used during repository indexing must be used for query generation.

This ensures that the query and indexed repository chunks exist in the same vector space.

---

# ChromaDB Retrieval

The generated query embedding is sent to ChromaDB.

The query is filtered by the internal Anchor repository ID and file path:

```text
repository_id = X
file_path = Y
```

This is important because ChromaDB can contain indexed chunks from multiple repositories.

Conceptually:

```text
ChromaDB
  |
  +---- Repository 1 chunks
  |
  +---- Repository 2 chunks
  |
  +---- Repository 3 chunks
```

A PR belonging to Repository 2 must only retrieve:

```text
Repository 2 chunks
```

The Analysis Service therefore applies a repository metadata filter during retrieval.

---

# First-Stage Retrieval

The current retrieval stage retrieves up to:

```text
Top 20
```

candidate chunks.

The goal of this stage is **recall**.

It intentionally retrieves more candidates than will eventually be sent to the LLM.

```text
PR Query
   |
   v
ChromaDB
   |
   v
Top 20 candidates
```

---

# Reranking

The retrieved candidates are then passed through a CrossEncoder reranker.

The reranker evaluates:

```text
(query, chunk)
```

together rather than relying only on vector similarity.

```text
Top 20 Chroma results
        |
        v
CrossEncoder
        |
        v
Relevance scores
        |
        v
Sort
        |
        v
Top 5
```

The current reranking strategy keeps approximately:

```text
Top 5 chunks per changed file
```

The final context is composed from these reranked chunks.

---

# Chroma Distance vs Reranker Score

The two scores have different meanings.

### Chroma distance

Used during vector retrieval.

It determines how close the query embedding is to an indexed chunk.

### Reranker score

Used during second-stage ranking.

It determines how relevant the chunk is to the specific query.

The pipeline is:

```text
Chroma distance
      ↓
candidate selection
      ↓
Reranker score
      ↓
final ranking
```

---

# Context Building

The final LLM context contains:

```text
Pull Request metadata
+
Changed files
+
Complete PR diff
+
Relevant repository context
```

Conceptually:

```text
## Pull Request

Title
Description
Base Commit
Head Commit

## Changed Files

File
Status
Additions
Deletions

## Pull Request Diff

<diff>

## Relevant Existing Repository Code

<retrieved chunk 1>

<retrieved chunk 2>

...
```

This gives the LLM both:

1. What the PR changed.
2. What existing repository code those changes interact with.

---

# LLM Integration

The current LLM provider is Groq.

The model and API key are deployment configuration.

```env
GROQ_API_KEY=...
GROQ_MODEL=...
```

The Analysis Service creates a Groq client using these settings.

The LLM receives:

```text
System Prompt
+
PR Context
```

---

# System Prompt Responsibilities

The system prompt instructs the model to focus on:

* Correctness
* Bugs
* Security vulnerabilities
* Performance
* Error handling
* Maintainability
* Edge cases
* Incorrect assumptions

The model is explicitly instructed not to report issues merely because of coding-style preferences.

It should only report issues that can be justified using:

```text
PR diff
+
retrieved repository context
```

---

# PR Review Output

The expected review contains information such as:

```text
Severity
File
Location
Problem
Why it matters
Suggested fix
```

Example:

```markdown
| Severity | File | Location | Problem | Why it matters | Suggested fix |
|----------|------|----------|---------|----------------|---------------|
| High | auth.py | Line 42 | Hard-coded API key | Credential exposure | Move secret to environment configuration |
```

The model should explicitly state when no meaningful issues are found.

---

# Complete PR Analysis Flow

## Case 1 — Repository Already Indexed

```text
GitHub
  |
  | PR opened
  v
Webhook
  |
  v
Find Repository
  |
  v
Create/Update PullRequest
  |
  v
Compare:

last_indexed_commit
        ==
base_commit_sha
  |
  v
No indexing required
  |
  v
PR Analysis
  |
  +--> Get changed files
  |
  +--> Get diff
  |
  +--> Generate query embedding
  |
  +--> ChromaDB
  |
  +--> Top 20
  |
  +--> Reranker
  |
  +--> Top 5
  |
  +--> Build context
  |
  +--> Groq
  |
  v
PR Review
```

---

# Case 2 — Repository Requires Indexing

```text
GitHub
  |
  | PR opened
  v
Webhook
  |
  v
Find Repository
  |
  v
Create/Update PullRequest
  |
  v
Compare:

last_indexed_commit
        !=
base_commit_sha
  |
  v
Create IndexingJob
trigger_type = PR
  |
  v
Publish repository.index
  |
  v
RabbitMQ
  |
  v
Indexing Worker
  |
  | ... indexing ...
  |
  v
repository.index.completed
  |
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
trigger_type == PR
  |
  v
Find PR
  |
  v
PR Analysis
  |
  v
Retrieval
  |
  v
Reranking
  |
  v
Context
  |
  v
Groq
  |
  v
PR Review
```

---

# Case 3 — Repository Onboarding

```text
Client
  |
  | POST /repositories
  v
Analysis Service
  |
  +--> GitHub repository metadata
  |
  +--> Historical PRs
  |
  +--> PostgreSQL
  |
  v
Create IndexingJob
trigger_type = ONBOARDING
  |
  v
repository.index
  |
  v
RabbitMQ
  |
  v
Indexing Worker
  |
  v
repository.index.completed
  |
  v
Analysis Consumer
  |
  v
Get IndexingJob
  |
  v
trigger_type == ONBOARDING
  |
  v
ACK
  |
  v
Stop
```

No PR analysis occurs for the onboarding completion event.

---

# Case 4 — PR Synchronization

When a contributor pushes additional commits:

```text
Contributor
    |
    v
Push to PR branch
    |
    v
GitHub
    |
    | pull_request / synchronize
    v
Anchor Webhook
    |
    v
Update PullRequest
    |
    +--> New head_commit_sha
    |
    v
Check indexing requirement
    |
    +---------------------+
    |                     |
    v                     v
Index required       Already indexed
    |                     |
    v                     v
Create PR job         Analyze PR
    |                     |
    v                     |
RabbitMQ                 |
    |                     |
    v                     |
Indexing Worker          |
    |                     |
    v                     |
Completed event           |
    |                     |
    +----------+----------+
               |
               v
          PR Analysis
```

---

# Message Ownership

The Analysis Service interacts with RabbitMQ through two message flows.

```text
Analysis Service
       |
       | repository.index
       v
   RabbitMQ
       |
       v
Indexing Worker
```

and:

```text
Indexing Worker
       |
       | repository.index.completed
       v
   RabbitMQ
       |
       v
Analysis Service
```

The Analysis Service therefore acts as:

```text
Producer
    +
Consumer
```

for the indexing lifecycle.

---

# Acknowledgement Behavior

For indexing requests:

```text
Analysis Service
      |
      v
Publish indexing job
```

The service does not wait synchronously for indexing.

For completion events:

```text
Analysis Consumer
      |
      v
Process event
      |
      v
ACK
```

An onboarding completion event is acknowledged without triggering analysis.

A PR completion event is acknowledged after the event has been processed and PR analysis has been started successfully.

---

# Service Responsibilities

## GitHubService

Responsible for communication with GitHub.

```text
Analysis Service
      |
      v
GitHubService
      |
      v
GitHub API
```

---

## PullRequestService

Responsible for pull request state and lifecycle logic.

Responsibilities include:

* Creating PR records
* Updating synchronized PRs
* Finding PRs
* Determining whether indexing is required
* Creating PR-triggered indexing jobs
* Finding PRs associated with completed indexing jobs

---

## JobService

Responsible for indexing job creation.

Responsibilities include:

* Creating `IndexingJob`
* Setting `trigger_type`
* Setting the commit SHA
* Publishing indexing jobs to RabbitMQ

---

## PRAnalysisService

Responsible for orchestrating PR analysis.

Responsibilities include:

```text
Fetch PR changes
      ↓
Generate embeddings
      ↓
Retrieve Chroma context
      ↓
Rerank context
      ↓
Build analysis input
      ↓
Call LLM
```

---

## EmbeddingService

Responsible for converting retrieval queries into embeddings.

```text
Text
 ↓
Sentence Transformer
 ↓
Vector
```

The embedding model must be compatible with the model used during repository indexing.

---

## ChromaStore

Responsible for querying ChromaDB.

The Analysis Service provides:

```text
query embedding
repository_id
number of results
```

and receives candidate repository chunks.

---

## RerankerService

Responsible for second-stage ranking.

```text
Chroma candidates
      ↓
CrossEncoder
      ↓
Relevance scores
      ↓
Ranked chunks
```

---

## LLMService

Responsible for the final AI reasoning stage.

Responsibilities include:

* Building the LLM context
* Constructing the system prompt
* Calling Groq
* Returning the generated PR review

---

# Current Analysis Service Request-to-Review Flow

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





