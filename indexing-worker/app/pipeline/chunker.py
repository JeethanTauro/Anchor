from dataclasses import dataclass
from pathlib import Path


@dataclass
class CodeChunk:
    text: str
    metadata: dict


def detect_language(file_path: Path) -> str:

    extension_map = {
        ".py": "python",
        ".java": "java",
        ".js": "javascript",
        ".ts": "typescript",
        ".jsx": "javascript",
        ".tsx": "typescript",
        ".cpp": "cpp",
        ".c": "c",
        ".h": "c",
        ".hpp": "cpp",
        ".go": "go",
        ".rs": "rust",
        ".kt": "kotlin",
        ".sql": "sql",
        ".html": "html",
        ".css": "css",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".md": "markdown",
    }

    return extension_map.get(
        file_path.suffix.lower(),
        "text"
    )


def chunk_file(
    file_path: Path,
    to_index: Path,
    repository_id: int,
    job_id: int,
    commit_sha: str,
    chunk_size: int = 100
) -> list[CodeChunk]:

    relative_path = file_path.relative_to(to_index)

    language = detect_language(file_path)

    try:
        content = file_path.read_text(
            encoding="utf-8"
        )
    except UnicodeDecodeError:
        return []

    lines = content.splitlines()

    chunks = []

    for start in range(0, len(lines), chunk_size):

        chunk_lines = lines[
            start:start + chunk_size
        ]

        if not chunk_lines:
            continue

        end = start + len(chunk_lines)

        text = "\n".join(chunk_lines)

        metadata = {
            "repository_id": repository_id,
            "job_id": job_id,
            "commit_sha": commit_sha,
            "file_path": str(relative_path),
            "language": language,
            "start_line": start + 1,
            "end_line": end,
        }

        chunks.append(
            CodeChunk(
                text=text,
                metadata=metadata
            )
        )

    return chunks


def chunk_directory(
    to_index: Path,
    repository_id: int,
    job_id: int,
    commit_sha: str
) -> list[CodeChunk]:

    all_chunks = []

    for file_path in to_index.rglob("*"):

        if not file_path.is_file():
            continue

        chunks = chunk_file(
            file_path,
            to_index,
            repository_id,
            job_id,
            commit_sha
        )

        all_chunks.extend(chunks)

    return all_chunks