from codebase_rag.main import run_with_cancellation, _initialize_services_and_agent, _setup_common_initialization, init_session_log, log_session_event, get_session_context, _handle_rejection
from services.remote_repo_service import has_edit_tool_calls
from codebase_rag.graph_updater import MemgraphIngestor
from core.config import settings
from rich.console import Console
from rich.prompt import Confirm
from typing import Any
from models.session import Session

console = Console(width=None, force_terminal=True)
confirm_edits_globally = True


async def query(question: str, repo_path: str, session_id: str):
    init_session_log(_setup_common_initialization(repo_path))
    log_session_event(f"USER: {question}")
    with MemgraphIngestor(
        host=settings.MEMGRAPH_HOST,
        port=settings.MEMGRAPH_PORT,
    ) as ingestor:
        console.print("[bold green]Successfully connected to Memgraph.[/bold green]")
        history = Session.get(session_id)
        rag_agent = _initialize_services_and_agent(repo_path, ingestor)
        question_with_context = question + get_session_context()
        print(f'question with context: {question_with_context}')
        response = await rag_agent.run(question_with_context, message_history=history)
        history.extend(response.new_messages())
        Session.set(session_id, history)
        return response.output


async def discard_changes(repo_path: str, session_id: str):
    init_session_log(_setup_common_initialization(repo_path))
    with MemgraphIngestor(
        host=settings.MEMGRAPH_HOST,
        port=settings.MEMGRAPH_PORT,
    ) as ingestor:
        console.print("[bold green]Successfully connected to Memgraph.[/bold green]")

        rag_agent = _initialize_services_and_agent(repo_path, ingestor)
        history = Session.get(session_id)
        await _handle_rejection(rag_agent, history, console)


async def optimize(repo_path: str, language: str, ref: str, question: str, session_id: str):
    init_session_log(_setup_common_initialization(repo_path))
    with MemgraphIngestor(
        host=settings.MEMGRAPH_HOST,
        port=settings.MEMGRAPH_PORT,
    ) as ingestor:
        console.print("[bold green]Successfully connected to Memgraph.[/bold green]")

        rag_agent = _initialize_services_and_agent(repo_path, ingestor)
    # Initial optimization analysis
    instructions = [
        "Use your code retrieval and graph querying tools to understand the codebase structure",
        "Read relevant source files to identify optimization opportunities",
    ]
    if ref:
        instructions.append(
            f"Use the analyze_document tool to reference best practices from {ref}"
        )

    instructions.extend(
        [
            f"Reference established patterns and best practices for {language}",
            "Propose specific, actionable optimizations with file references",
            "IMPORTANT: Do not make any changes yet - just propose them and wait for approval",
            "After approval, use your file editing tools to implement the changes",
        ]
    )
    numbered_instructions = "\n".join(
        f"{i + 1}. {inst}" for i, inst in enumerate(instructions)
    )
    initial_question = f"""
I want you to analyze my {language} codebase and propose specific optimizations based on best practices.

Please:
{numbered_instructions}

Start by analyzing the codebase structure and identifying the main areas that could benefit from optimization.
Remember: Propose changes first, wait for my approval, then implement.
"""
    with console.status(
        "[bold green]Agent is analyzing codebase... (Press Ctrl+C to cancel)[/bold green]"
    ):
        history = Session.get(session_id)
        if len(history) == 0: 
            question_with_context = initial_question + get_session_context()
        else: 
            question_with_context = question
        response = await run_with_cancellation(
            console,
            rag_agent.run(
                question_with_context, message_history=history
            ),
        )
    history.extend(response.new_messages())
    Session.set(session_id, history)
    return response.output, has_edit_tool_calls(response)

    
