import requests
from typing import List, Dict, Any, Optional
from src.llm.base import BaseLLMClient
from src.core.types import LLMResponse


class OpenAIClient(BaseLLMClient):
    """Универсальный клиент для любого OpenAI-compatible API"""

    def __init__(
        self,
        api_key: str = "lm-studio",
        base_url: str = "http://localhost:1234/v1",
        model: str = "local-model"
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 512
    ) -> LLMResponse:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        res = requests.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
        res.raise_for_status()
        data = res.json()

        return LLMResponse(
            content=data["choices"][0]["message"]["content"],
            tokens_used=data.get("usage", {}).get("total_tokens", 0),
            model_name=self.model,
            raw_response=data
        )