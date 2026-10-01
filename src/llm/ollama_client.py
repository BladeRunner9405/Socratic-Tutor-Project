import requests
from typing import List, Dict, Any, Optional
from src.llm.base import BaseLLMClient
from src.core.types import LLMResponse
from config.config import settings


class OllamaClient(BaseLLMClient):
    """Клиент для работы с локальным сервисом Ollama"""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model = model or settings.OLLAMA_MODEL
        self.api_url = f"{self.base_url}/api/chat"

    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 512
    ) -> LLMResponse:
        payload = {
            "model": self.model,
            "messages": messages,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            },
            "stream": False
        }

        try:
            res = requests.post(self.api_url, json=payload, timeout=60)
            res.raise_for_status()
            data = res.json()

            content = data.get("message", {}).get("content", "")
            eval_count = data.get("eval_count", 0)

            return LLMResponse(
                content=content,
                tokens_used=eval_count,
                model_name=self.model,
                raw_response=data
            )
        except Exception as e:
            raise RuntimeError(f"Ollama API Error ({self.model}): {str(e)}")