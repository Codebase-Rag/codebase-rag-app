from codebase_rag.graph_updater import MemgraphIngestor
from codebase_rag.config import settings
from rich.console import Console
from rich.prompt import Confirm
from typing import Any
from codebase_rag.main import _handle_rejection
from codebase_rag.graph_updater import MemgraphIngestor
from models.session import Session
from codebase_rag.tools.codebase_query import create_query_tool
from codebase_rag.services.llm import CypherGenerator, create_rag_orchestrator
from codebase_rag.tools.code_retrieval import CodeRetriever, create_code_retrieval_tool
from codebase_rag.tools.remote_file_reader import RemoteFileReader, create_file_reader_tool
from codebase_rag.tools.remote_file_writer import RemoteFileWriter, create_file_writer_tool
from codebase_rag.tools.remote_file_editor import RemoteFileEditor, create_file_editor_tool
from codebase_rag.tools.remote_shell_command import RemoteShellCommander, create_shell_command_tool
from codebase_rag.tools.remote_directory_lister import RemoteDirectoryLister, create_directory_lister_tool
from codebase_rag.tools.remote_document_analyzer import RemoteDocumentAnalyzer, create_document_analyzer_tool
from codebase_rag.tools.semantic_search import create_semantic_search_tool, create_get_function_source_tool
from codebase_rag.services.llm import CypherGenerator, create_rag_orchestrator
from sockets.server import sio
from prompt.agent import agent_instruction
from pydantic_ai.messages import ModelResponse, ToolCallPart
import uuid

console = Console(width=None, force_terminal=True)
confirm_edits_globally = True

# Tool names that indicate file modifications were made
_EDIT_TOOL_NAMES = frozenset([
    "create_new_file",
    "replace_code_surgically",
])


def has_edit_tool_calls(response) -> bool:
    """Check if the agent response contains actual calls to file-editing tools."""
    for message in response.new_messages():
        if isinstance(message, ModelResponse):
            for part in message.parts:
                if isinstance(part, ToolCallPart) and part.tool_name in _EDIT_TOOL_NAMES:
                    return True
    return False

def _initialize_services_and_agent(ingestor: MemgraphIngestor, socket_id: str) -> Any:
    """Initializes all services and creates the RAG agent."""
    # Validate provider configurations before initializing any LLM services
    from codebase_rag.providers.base import get_provider

    def _validate_provider_config(role: str, config: Any) -> None:
        """Validate a single provider configuration."""
        try:
            provider = get_provider(
                config.provider,
                api_key=config.api_key,
                endpoint=config.endpoint,
                project_id=config.project_id,
                region=config.region,
                provider_type=config.provider_type,
                thinking_budget=config.thinking_budget,
                service_account_file=config.service_account_file,
            )
            provider.validate_config()
        except Exception as e:
            raise ValueError(f"{role.title()} configuration error: {e}") from e

    # Validate both provider configurations
    _validate_provider_config("orchestrator", settings.active_orchestrator_config)
    _validate_provider_config("cypher", settings.active_cypher_config)

    cypher_generator = CypherGenerator()
    code_retriever = CodeRetriever(project_root='.', ingestor=ingestor)
    file_reader = RemoteFileReader(socket_id=socket_id)
    file_writer = RemoteFileWriter(socket_id=socket_id)
    file_editor = RemoteFileEditor(socket_id=socket_id)
    shell_commander = RemoteShellCommander(socket_id=socket_id)
    directory_lister = RemoteDirectoryLister(socket_id=socket_id)
    document_analyzer = RemoteDocumentAnalyzer(socket_id=socket_id)

    query_tool = create_query_tool(ingestor, cypher_generator, console)
    code_tool = create_code_retrieval_tool(code_retriever)
    file_reader_tool = create_file_reader_tool(file_reader)
    file_writer_tool = create_file_writer_tool(file_writer)
    file_editor_tool = create_file_editor_tool(file_editor)
    shell_command_tool = create_shell_command_tool(shell_commander)
    directory_lister_tool = create_directory_lister_tool(directory_lister)
    document_analyzer_tool = create_document_analyzer_tool(document_analyzer)
    semantic_search_tool = create_semantic_search_tool()
    function_source_tool = create_get_function_source_tool()

    rag_agent = create_rag_orchestrator(
        tools=[
            query_tool,
            code_tool,
            file_reader_tool,
            file_writer_tool,
            file_editor_tool,
            shell_command_tool,
            directory_lister_tool,
            document_analyzer_tool,
            semantic_search_tool,
            function_source_tool,
        ]
    )
    return rag_agent


async def query(question: str, mode: str, socket_id: str, session_id: str = None):
    with MemgraphIngestor(
        host=settings.MEMGRAPH_HOST,
        port=settings.MEMGRAPH_PORT,
    ) as ingestor:
        history = []
        rag_agent = _initialize_services_and_agent(ingestor, socket_id=socket_id)
        if session_id == None:
            session_id = str(uuid.uuid4())
        else:
            history = Session.get(session_id)
        question_with_context = question
        if mode == 'agent' and len(history) == 0:
             question_with_context = agent_instruction.format(question=question)
        response = await rag_agent.run(question_with_context, message_history=history)
        history.extend(response.new_messages())
        Session.set(session_id, history)
        return session_id, response.output, has_edit_tool_calls(response)
    
async def discard_changes(socket_id: str, session_id: str):
    with MemgraphIngestor(
        host=settings.MEMGRAPH_HOST,
        port=settings.MEMGRAPH_PORT,
    ) as ingestor:
        console.print("[bold green]Successfully connected to Memgraph.[/bold green]")

        rag_agent = _initialize_services_and_agent(ingestor=ingestor, socket_id=socket_id)
        history = Session.get(session_id)
        await _handle_rejection(rag_agent, history, console)
        Session.set(session_id, history)

