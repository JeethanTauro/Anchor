# Anchor

**Anchor is an AI-powered GitHub Pull Request reviewer that understands the changes in a PR in the context of the repository.**

Instead of manually reading through every PR and searching the codebase to understand whether a change is safe, Anchor automatically:

* Detects new and updated pull requests.
* Understands the PR diff and changed files.
* Retrieves relevant repository code using semantic search.
* Reranks the retrieved context to find the most relevant code.
* Uses an LLM to analyze the PR against the retrieved repository context.
* Identifies bugs, security vulnerabilities, correctness issues, performance problems, and maintainability concerns.
* Produces an actionable review with severity, explanation, and suggested fixes.

### The idea

A normal code review looks like:

```text
Pull Request
     ↓
Developer reads diff
     ↓
Searches repository manually
     ↓
Understands surrounding code
     ↓
Reviews changes
     ↓
Finds problems
```

Anchor automates this:

```text
Pull Request
     ↓
GitHub Webhook
     ↓
Anchor
     ↓
PR Diff + Changed Files
     ↓
Semantic Retrieval
     ↓
Reranking
     ↓
Relevant Repository Context
     ↓
LLM Analysis
     ↓
PR Review
```

---

# Features

### Repository Onboarding

Anchor accepts a public GitHub repository URL and automatically:

1. Fetches repository metadata.
2. Stores the repository in PostgreSQL.
3. Fetches historical pull requests.
4. Stores PR metadata.
5. Starts repository indexing.

### Automatic PR Detection

Once GitHub is configured with an Anchor webhook, Anchor receives pull request events automatically.

Anchor currently handles:

* `pull_request.opened`
* `pull_request.synchronize`

A `synchronize` event occurs when additional commits are pushed to an existing open PR.

### Repository-Aware Analysis

Anchor does not rely only on the PR diff.

It retrieves relevant repository code from the indexed repository and provides that context to the LLM.

```text
PR Diff
   +
Repository Context
   ↓
LLM
   ↓
Evidence-grounded Review
```

### Security-Focused Review

Anchor can detect issues such as:

* Hard-coded secrets
* Security vulnerabilities
* Incorrect authentication logic
* Unsafe handling of data
* Broken error handling
* Incorrect application logic

The review is instructed to avoid speculative findings and only report issues supported by the available evidence.

---

# Architecture

At a high level:

```text
                         GitHub
                           |
                           | Webhook
                           v
                    Analysis Service
                           |
              +------------+------------+
              |            |            |
              v            v            v
          PostgreSQL    RabbitMQ      ChromaDB
                           |
                    +------+------+
                    |             |
                    v             v
             Indexing Worker  Analysis Consumer
                    |             |
                    |             v
                    |        PR Analysis
                    |             |
                    +-----> ChromaDB
                                  |
                              Reranker
                                  |
                                Groq
                                  |
                                  v
                              PR Review
```

The user only needs to start Anchor. PostgreSQL, RabbitMQ, and ChromaDB are managed automatically by Docker Compose.

---

# Requirements

You only need:

* Docker
* Docker Compose
* A Groq API key
* A public GitHub repository
* `ngrok` for local GitHub webhook testing

---

# Setup

## 1. Clone Anchor

```bash
git clone <ANCHOR_REPOSITORY_URL>
cd Anchor
```

---

## 2. Configure Groq

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=your_groq_model
```
---

# 3. Start Anchor

Run:

```bash
docker compose up --build
```

Docker Compose will automatically start:

```text
PostgreSQL
RabbitMQ
ChromaDB
Analysis API
Analysis Consumer
Indexing Worker
```
The Analysis API will be available at:

```text
http://localhost:8000
```

---

# 4. Onboard a Repository

Anchor currently supports public GitHub repositories, so no GitHub authentication token is required.

Send the repository URL to Anchor:

```bash
curl -X POST http://localhost:8000/repositories \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/<OWNER>/<REPOSITORY>"
  }'
```

Example:

```bash
curl -X POST http://localhost:8000/repositories \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/JeethanTauro/DummyRepo"
  }'
```

Anchor will:

```text
Repository URL
      ↓
GitHub metadata
      ↓
PostgreSQL
      ↓
Historical PRs
      ↓
Indexing Job
      ↓
RabbitMQ
      ↓
Indexing Worker
      ↓
ChromaDB
```

Once indexing completes, the repository is ready for PR analysis.

---

# 5. Configure GitHub Webhooks

For local development, expose the Anchor API using `ngrok`.

Start:

```bash
ngrok http 8000
```

You will receive a public URL similar to:

```text
https://abc123.ngrok-free.app
```

---

## 6. Add the Webhook to GitHub

Go to:

```text
GitHub Repository
    ↓
Settings
    ↓
Webhooks
    ↓
Add webhook
```

Set the **Payload URL** to:

```text
https://abc123.ngrok-free.app/webhooks/github
```

Set:

```text
Content type:
application/x-www-form-urlencoded
```

For events, select:

```text
Let me select individual events
```

Enable:

```text
Pull requests
```

Then save the webhook.

---

# 7. Create a Pull Request

Create a feature branch:

```bash
git checkout -b feature/test-anchor
```

Make a change:

```bash
echo "testing Anchor" >> test.txt
```

Commit it:

```bash
git add .
git commit -m "Test Anchor PR review"
```

Push the branch:

```bash
git push -u origin feature/test-anchor
```

Create a PR:

```text
feature/test-anchor → main
```

GitHub sends:

```text
pull_request
action = opened
```

to Anchor.

Anchor then analyzes the PR.

---

# 8. Push More Commits to an Existing PR

You can also test incremental PR analysis.

While the PR is still open:

```bash
echo "another change" >> test.txt

git add .
git commit -m "Update PR"

git push
```

GitHub sends:

```text
pull_request
action = synchronize
```

Anchor updates the PR information and analyzes the updated changes.

The PR does **not** need to be recreated.

---

# End-to-End Flow

The complete user flow is:

```text
                 docker compose up
                        |
                        v
                 +-------------+
                 |    Anchor   |
                 +-------------+
                        |
                        v
              POST /repositories
                        |
                        v
                  GitHub API
                        |
                        v
                   PostgreSQL
                        |
                        v
                  Indexing Job
                        |
                        v
                    RabbitMQ
                        |
                        v
                Indexing Worker
                        |
                        v
                    ChromaDB
                        |
                        v
               Indexing Completed
                        |
                        v
               Analysis Consumer
                        |
                        |
       +----------------+----------------+
       |                                 |
       v                                 v
   GitHub PR                        ChromaDB
   Diff + Files                    Repository Context
       |                                 |
       +---------------+-----------------+
                       |
                       v
                   Reranker
                       |
                       v
                     Groq
                       |
                       v
                  PR Review
```

---

# Example Review

Anchor produces an evidence-grounded review such as:

```markdown
## Findings

| Severity | File | Location | Problem | Why it is a problem | Suggested fix |
|----------|------|----------|---------|---------------------|---------------|
| High | auth.py | Line 42 | Hard-coded API key | Credentials are committed to source control. | Move the key to an environment variable or secret manager. |

## Verdict

The pull request should not be merged until the exposed credential is removed.
```

If no meaningful problems are found:

```text
No meaningful issues were identified.
The pull request looks good.
```

---

# Current Scope

Anchor currently focuses on:

* Public GitHub repositories
* Repository onboarding
* Historical PR metadata
* Automatic PR webhook processing
* Repository indexing
* Semantic retrieval
* Context reranking
* LLM-powered PR analysis
* Evidence-grounded findings
* Automatic re-analysis when an open PR receives new commits

# Current reliability limitations

Anchor currently uses durable RabbitMQ queues and persistent database/vector-store volumes, but does not yet implement a transactional outbox, dead-letter queues, bounded retry policies, or full idempotency guarantees. A failure between database commits and message publication can therefore leave jobs without corresponding events. Long-running jobs also require additional recovery handling if a worker terminates unexpectedly.

## Future improvements include:

* Transactional Outbox Pattern
* Dead Letter Queues
* Exponential backoff with bounded retries
* Idempotent event processing
* Worker job leases/timeouts
* Database and external API retry policies
* Failure recovery/reconciliation jobs

## Demo
* [Click here for the demo video](https://youtu.be/wcjX58F6uBM)
