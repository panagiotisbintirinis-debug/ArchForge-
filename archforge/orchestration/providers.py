"""Optional LangChain provider adapters for the ArchForge LangGraph flow."""

from __future__ import annotations

import os
from typing import Any

from .langgraph_flow import _response_text


class ProviderConfigurationError(RuntimeError):
    """A provider cannot be constructed from the current environment."""


class LangChainTextAgent:
    """Adapt a LangChain chat model to the provider-neutral AgentProtocol."""

    def __init__(self, model: Any):
        self.model = model

    def invoke(self, prompt: str) -> str:
        return _response_text(self.model.invoke(prompt))


def _required_model(explicit: str | None, env_name: str) -> str:
    value = explicit or os.getenv(env_name)
    if not value:
        raise ProviderConfigurationError(
            f"Set {env_name} or pass model= explicitly; "
            "ArchForge does not guess provider model names."
        )
    return value


def create_openai_agent(*, model: str | None = None) -> LangChainTextAgent:
    """Create the GPT-side agent without exposing credentials in code or logs."""

    if not os.getenv("OPENAI_API_KEY"):
        raise ProviderConfigurationError("OPENAI_API_KEY is not configured")
    model_name = _required_model(model, "ARCHFORGE_GPT_MODEL")
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise ProviderConfigurationError(
            "Install requirements-agents.txt to use the OpenAI provider"
        ) from exc

    return LangChainTextAgent(ChatOpenAI(model=model_name, temperature=0))


def create_gemini_agent(*, model: str | None = None) -> LangChainTextAgent:
    """Create the Gemini-side reviewer using environment-held credentials."""

    key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not key:
        raise ProviderConfigurationError(
            "GOOGLE_API_KEY or GEMINI_API_KEY is not configured"
        )

    if not os.getenv("GOOGLE_API_KEY"):
        os.environ["GOOGLE_API_KEY"] = key

    model_name = _required_model(model, "ARCHFORGE_GEMINI_MODEL")
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
    except ImportError as exc:
        raise ProviderConfigurationError(
            "Install requirements-agents.txt to use the Gemini provider"
        ) from exc

    return LangChainTextAgent(
        ChatGoogleGenerativeAI(model=model_name, temperature=0)
    )
