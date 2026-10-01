from typing import Optional
from src.llm.base import BaseLLMClient
from src.llm.gigachat_client import GigaChatClient
from src.llm.ollama_client import OllamaClient
from src.llm.openai_client import OpenAIClient
from config.config import settings


class LLMFactory:
    """Фабрика для динамического создания клиентов LLM"""

    @staticmethod
    def create(
        provider: Optional[str] = None,
        model_override: Optional[str] = None
    ) -> BaseLLMClient:
        provider_name = (provider or settings.DEFAULT_LLM_PROVIDER).lower()

        if provider_name == "gigachat":
            return GigaChatClient(model=model_override)
        elif provider_name == "ollama":
            return OllamaClient(model=model_override)
        elif provider_name in ["openai", "lmstudio", "vllm"]:
            return OpenAIClient(model=model_override or "local-model")
        else:
            raise ValueError(f"Unsupported LLM provider: '{provider_name}'")