import shutil
from pathlib import Path


IGNORED_DIRECTORIES = {
    ".git",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "__pycache__",
    "target",
    "build",
    "dist",
    "coverage",
    ".idea",
    ".vscode",
}


IGNORED_FILES = {
    ".env",
    ".env.local",
    ".env.production",
}


IGNORED_EXTENSIONS = {
    ".pyc",
    ".class",
    ".jar",
    ".war",
    ".exe",
    ".dll",
    ".so",
    ".bin",
    ".zip",
    ".tar",
    ".gz",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".mp4",
    ".mp3",
    ".pdf",
}


MAX_FILE_SIZE = 2 * 1024 * 1024  # 2 MB


def filter_files(
    repo_path: Path,
    workspace: Path
) -> Path:

    to_index = workspace / "to_index"

    to_index.mkdir(
        parents=True,
        exist_ok=True
    )

    for file_path in repo_path.rglob("*"):

        if not file_path.is_file():
            continue

        # Relative path inside repository
        relative_path = file_path.relative_to(repo_path)

        # Ignore unwanted directories
        if any(
            part in IGNORED_DIRECTORIES
            for part in relative_path.parts
        ):
            continue

        # Ignore unwanted filenames
        if file_path.name in IGNORED_FILES:
            continue

        # Ignore unwanted extensions
        if file_path.suffix.lower() in IGNORED_EXTENSIONS:
            continue

        # Ignore large files
        if file_path.stat().st_size > MAX_FILE_SIZE:
            continue

        # Preserve repository structure
        destination = to_index / relative_path

        destination.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        shutil.copy2(
            file_path,
            destination
        )

    return to_index