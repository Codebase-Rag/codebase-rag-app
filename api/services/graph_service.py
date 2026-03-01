from codebase_rag.graph_updater import GraphUpdater, MemgraphIngestor
from codebase_rag.config import settings
from codebase_rag.parser_loader import load_parsers
from pathlib import Path
from rich.console import Console
import typer
import os

console = Console(width=None, force_terminal=True)


async def update_graph(repo_path: str):
    repo_to_update = Path(repo_path)
    console.print(
        f"[bold green]Updating knowledge graph for: {repo_to_update}[/bold green]"
    )

    with MemgraphIngestor(
        host=settings.MEMGRAPH_HOST,
        port=settings.MEMGRAPH_PORT,
    ) as ingestor:
        console.print("[bold yellow]Cleaning database...[/bold yellow]")
        await ingestor.clean_database()
        await ingestor.ensure_constraints()

        # Load parsers and queries
        parsers, queries = load_parsers()

        updater = GraphUpdater(ingestor, repo_to_update, parsers, queries)
        await updater.run()
    console.print("[bold green]Graph update completed![/bold green]")
    return

def clean():
    with MemgraphIngestor(
        host=settings.MEMGRAPH_HOST,
        port=settings.MEMGRAPH_PORT,
    ) as ingestor:
        console.print("[bold yellow]Cleaning database...[/bold yellow]")
        ingestor.clean_database()
    return
