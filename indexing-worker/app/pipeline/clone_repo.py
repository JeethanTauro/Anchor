import subprocess
from pathlib import Path


def clone_repository(
    owner: str,
    repo: str,
    commit_sha: str,
    workspace: Path
) -> Path:

    repo_url = f"https://github.com/{owner}/{repo}.git"

    repo_path = workspace / "repo"

    # Clone repository
    subprocess.run(
        [
            "git",
            "clone",
            "--no-checkout",
            repo_url,
            str(repo_path)
        ],
        check=True,
        capture_output=True,
        text=True
    )

    # Checkout the exact commit
    subprocess.run(
        [
            "git",
            "-C",
            str(repo_path),
            "checkout",
            commit_sha
        ],
        check=True,
        capture_output=True,
        text=True
    )

    return repo_path