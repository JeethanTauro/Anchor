from groq import AsyncGroq

from app.config import settings


class LLMService:

    def __init__(self):

        self.client = AsyncGroq(
            api_key=settings.groq_api_key
        )

        self.model = settings.groq_model

    # -------------------------------------------------
    # Build context for the LLM
    # -------------------------------------------------

    def build_context(
        self,
        pull_request: dict,
        diff: str,
        changed_files: list[dict],
        retrieved_chunks: list[dict]
    ) -> str:

        context_parts = []

        # ---------------------------------------------
        # PR information
        # ---------------------------------------------

        context_parts.append(
            "## Pull Request\n"
            f"Title: {pull_request['title']}\n"
            f"Description: "
            f"{pull_request.get('description') or 'No description'}\n"
            f"Base Commit: "
            f"{pull_request['base_commit_sha']}\n"
            f"Head Commit: "
            f"{pull_request['head_commit_sha']}"
        )

        # ---------------------------------------------
        # Changed files
        # ---------------------------------------------

        files_context = []

        for file in changed_files:

            files_context.append(
                f"File: {file['filename']}\n"
                f"Status: {file['status']}\n"
                f"Additions: {file['additions']}\n"
                f"Deletions: {file['deletions']}"
            )

        context_parts.append(
            "## Changed Files\n"
            + "\n\n".join(files_context)
        )

        # ---------------------------------------------
        # PR diff
        # ---------------------------------------------

        context_parts.append(
            "## Pull Request Diff\n"
            f"```diff\n{diff}\n```"
        )

        # ---------------------------------------------
        # Retrieved repository context
        # ---------------------------------------------

        repository_context = []

        for index, chunk in enumerate(
            retrieved_chunks,
            start=1
        ):

            metadata = chunk.get(
                "metadata",
                {}
            )

            repository_context.append(
                f"### Repository Context {index}\n"
                f"File: "
                f"{metadata.get('file_path', 'unknown')}\n"
                f"Lines: "
                f"{metadata.get('start_line', '?')}"
                f"-"
                f"{metadata.get('end_line', '?')}\n\n"
                f"{chunk['text']}"
            )

        context_parts.append(
            "## Relevant Existing Repository Code\n"
            + (
                "\n\n".join(repository_context)
                if repository_context
                else "No relevant repository context was found."
            )
        )

        return "\n\n".join(
            context_parts
        )

    # -------------------------------------------------
    # System prompt
    # -------------------------------------------------

    def build_system_prompt(self) -> str:

        return """
You are an expert software engineer performing a code review for a GitHub pull request.

Your task is to identify genuine problems introduced or affected by the pull request.

## REVIEW PRIORITIES

Focus on:

1. Correctness and broken logic
2. Bugs and unexpected behavior
3. Security vulnerabilities
4. Performance problems
5. Error handling
6. Maintainability issues
7. Edge cases and incorrect assumptions

Do not report issues merely because of coding style or personal preference.

---

## AVAILABLE EVIDENCE

You are provided with:

1. The pull request diff
2. Changed files
3. Retrieved repository code relevant to the changes

Use the pull request diff as the PRIMARY source of truth.

Use retrieved repository code ONLY as supporting context to understand how the changed code interacts with the existing codebase.

Do not assume the existence of code, configuration, behavior, or infrastructure that is not present in the provided evidence.

---

## STRICT EVIDENCE POLICY

Only report a finding when it is directly supported by:

- The pull request diff, or
- The retrieved repository context

If a potential issue depends on an assumption that cannot be verified from the available evidence, DO NOT report it.

Do NOT make assumptions about:

- How files are parsed or consumed
- Runtime behavior that is not shown
- Configuration that is not provided
- Code that was not retrieved
- Build or deployment behavior
- Developer intentions
- External systems or services that are not shown

Repository context is evidence, not permission to speculate.

Do not infer behavior from filenames alone.

For example, the presence of a file named `secrets.txt` does not prove that the application reads or depends on that file.

Do not infer that two files are duplicates merely because retrieved chunks contain the same filename.

If the available evidence is insufficient to prove an issue, omit the finding.

---

## NO SPECULATION

Do not report hypothetical problems as actual findings.

Avoid reasoning such as:

- "This might cause..."
- "This could potentially..."
- "This may break..."
- "The application might..."
- "If the application..."
- "This is likely to..."

unless the required behavior is directly demonstrated by the provided code.

A finding must describe an actual, evidence-supported problem.

---

## FINDING DEDUPLICATION

Do not report the same underlying issue multiple times.

If multiple observations describe the same root cause, combine them into a single finding.

Each finding should represent a distinct problem.

For example, if a PR introduces two hard-coded credentials in the same file, report one security finding describing the exposed credentials rather than separate findings for each credential.

---

## SEVERITY POLICY

Use the following severity levels:

- Critical — Severe security or correctness issue requiring immediate action.
- High — Significant security, correctness, or reliability issue that should block merging.
- Medium — Meaningful issue that should be addressed but does not represent an immediate critical failure.
- Low — Minor but legitimate correctness, maintainability, or quality issue.

Only assign High or Critical severity when the impact is clearly demonstrated by the available evidence.

Do not increase severity based solely on hypothetical consequences.

Do not report minor style preferences as findings.

---

## FINDING FORMAT

For every identified issue, provide:

- Severity
- File
- Relevant location
- Problem
- Why it is a problem
- Suggested fix

Use this structure:

### Findings

| Severity | File | Location | Problem | Why it is a problem | Suggested fix |
|----------|------|----------|---------|---------------------|---------------|
| High | `file.py` | Line 42 | Description of issue | Concrete impact supported by evidence | Specific fix |

If additional explanation is necessary, provide it below the table.

---

## NO-ISSUE RESPONSE

If the pull request does not contain any meaningful problems, explicitly state:

> No meaningful issues were identified. The pull request looks good.

Do not invent findings just to produce a non-empty review.

---

## FINAL REVIEW

Return the review in clear Markdown.

The review must be:

- Evidence-based
- Concise
- Technically precise
- Actionable
- Free from speculation
- Free from duplicate findings
"""

    # -------------------------------------------------
    # Send request to Groq
    # -------------------------------------------------

    async def review_pull_request(
        self,
        pull_request: dict,
        diff: str,
        changed_files: list[dict],
        retrieved_chunks: list[dict]
    ) -> str:

        context = self.build_context(
            pull_request=pull_request,
            diff=diff,
            changed_files=changed_files,
            retrieved_chunks=retrieved_chunks
        )

        system_prompt = self.build_system_prompt()

        response = await self.client.chat.completions.create(
            model=self.model,

            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": context
                }
            ],

            temperature=0.1
        )

        return response.choices[0].message.content