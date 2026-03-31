from loguru import logger
from pydantic_ai import Agent, Tool

from core.config import settings
from ..prompts import (
    CYPHER_SYSTEM_PROMPT,
    LOCAL_CYPHER_SYSTEM_PROMPT,
    RAG_ORCHESTRATOR_SYSTEM_PROMPT,
)
from ..providers.base import get_provider


class LLMGenerationError(Exception):
    """Custom exception for LLM generation failures."""

    pass


def _clean_cypher_response(response_text: str) -> str:
    """Utility to clean up common LLM formatting artifacts from a Cypher query."""
    import re
    
    # Try to extract from markdown code block first
    # Match ```cypher ... ``` or ``` ... ```
    code_block_match = re.search(r'```(?:cypher)?\s*(.*?)```', response_text, re.DOTALL | re.IGNORECASE)
    if code_block_match:
        query = code_block_match.group(1).strip()
    else:
        # Fallback: look for MATCH statement
        match_idx = response_text.upper().find('MATCH')
        if match_idx != -1:
            query = response_text[match_idx:].strip()
        else:
            query = response_text.strip()
    
    # Clean up any remaining backticks
    query = query.replace("`", "")
    
    # Remove trailing semicolons and prose after the query
    # Find the last RETURN/DELETE/CREATE/MERGE clause and trim after semicolon
    if ";" in query:
        query = query.split(";")[0].strip() + ";"
    elif not query.endswith(";"):
        query += ";"
    
    return query


class CypherGenerator:
    """Generates Cypher queries from natural language."""

    def __init__(self) -> None:
        try:
            # Get active cypher model configuration
            config = settings.active_cypher_config

            # Create provider instance
            provider = get_provider(
                config.provider,
                api_version=config.api_version,
                api_key=config.api_key,
                endpoint=config.endpoint,
                project_id=config.project_id,
                region=config.region,
                provider_type=config.provider_type,
                thinking_budget=config.thinking_budget,
            )

            # Create model using provider
            llm = provider.create_model(config.model_id)

            # Select system prompt based on provider
            system_prompt = (
                LOCAL_CYPHER_SYSTEM_PROMPT
                if config.provider == "ollama"
                else CYPHER_SYSTEM_PROMPT
            )

            self.agent = Agent(
                model=llm,
                system_prompt=system_prompt,
                output_type=str,
            )
        except Exception as e:
            raise LLMGenerationError(
                f"Failed to initialize CypherGenerator: {e}"
            ) from e

    async def generate(self, natural_language_query: str) -> str:
        logger.info(
            f"  [CypherGenerator] Generating query for: '{natural_language_query}'"
        )
        try:
            result = await self.agent.run(natural_language_query)
            if (
                not isinstance(result.output, str)
                or "MATCH" not in result.output.upper()
            ):
                raise LLMGenerationError(
                    f"LLM did not generate a valid query. Output: {result.output}"
                )

            query = _clean_cypher_response(result.output)
            logger.info(f"  [CypherGenerator] Generated Cypher: {query}")
            return query
        except Exception as e:
            logger.error(f"  [CypherGenerator] Error: {e}")
            raise LLMGenerationError(f"Cypher generation failed: {e}") from e


def create_rag_orchestrator(tools: list[Tool]) -> Agent:
    """Factory function to create the main RAG orchestrator agent."""
    try:
        # Get active orchestrator model configuration
        config = settings.active_orchestrator_config
        # Create provider instance
        provider = get_provider(
            config.provider,
            api_key=config.api_key,
            endpoint=config.endpoint,
            api_version=config.api_version,
            project_id=config.project_id,
            region=config.region,
            provider_type=config.provider_type,
            thinking_budget=config.thinking_budget,
        )

        # Create model using provider
        llm = provider.create_model(config.model_id)
        return Agent(
            model=llm,
            system_prompt=RAG_ORCHESTRATOR_SYSTEM_PROMPT,
            tools=tools,
        )
    except Exception as e:
        raise LLMGenerationError(f"Failed to initialize RAG Orchestrator: {e}") from e
