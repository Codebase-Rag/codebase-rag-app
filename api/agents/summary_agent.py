from pydantic_ai import Agent

from core.config import settings
from prompts.summary_agent_prompt import SYSTEM_PROMPT
from codebase_rag.providers.base import get_provider

config = settings.active_orchestrator_config

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

llm = provider.create_model(config.model_id)

summary_agent = Agent(model=llm, system_prompt=SYSTEM_PROMPT)