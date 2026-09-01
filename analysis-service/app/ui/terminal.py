from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown

console = Console()


def print_reranking_results(reranked_chunks):

    table = Table(
        title="Reranked Repository Context",
        show_lines=True
    )

    table.add_column("#", justify="center")
    table.add_column("Rerank Score")
    table.add_column("Chroma Distance")
    table.add_column("File")
    table.add_column("Text")

    for index, chunk in enumerate(reranked_chunks, start=1):

        metadata = chunk["metadata"]

        table.add_row(
            str(index),
            f"{chunk['rerank_score']:.4f}",
            f"{chunk['distance']:.4f}",
            metadata.get("file_path", "unknown"),
            chunk["text"]
        )

    console.print(table)


def print_analysis_input(
    pull_request,
    repository,
    changed_files,
    diff,
    final_chunks
):

    content = f"""
[bold]Pull Request:[/bold] #{pull_request.github_pr_number}
[bold]Title:[/bold] {pull_request.title}

[bold]Repository ID:[/bold] {repository.id}
[bold]Pull Request ID:[/bold] {pull_request.id}

[bold]Base Commit:[/bold] {pull_request.base_commit_sha}
[bold]Head Commit:[/bold] {pull_request.head_commit_sha}

[bold]Changed Files:[/bold] {len(changed_files)}
[bold]Retrieved Chunks:[/bold] {len(final_chunks)}
"""

    console.print(
        Panel(
            content,
            title="PR Analysis Input",
            expand=False
        )
    )


def print_review(review):

    console.print()

    console.print(
        Panel(
            Markdown(review),
            title="🛡️ Anchor PR Review"
        )
    )

    console.print()