import tempfile
import shutil
from pathlib import Path


def create_workspace(job_id: int) -> Path:
    """
    Create a temporary workspace for an indexing job.
    """

    workspace = Path(
        tempfile.mkdtemp(
            prefix=f"anchor_job_{job_id}_"
        )
    )

    return workspace


def cleanup_workspace(workspace: Path) -> None:
    """
    Delete the temporary workspace and everything inside it.
    """

    if workspace.exists():
        shutil.rmtree(workspace)