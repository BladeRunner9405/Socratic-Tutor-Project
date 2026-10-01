# src/llm/gigachat_client.py
import uuid
import requests
from typing import List, Dict, Any, Optional
from src.llm.base import BaseLLMClient
from src.core.types import LLMResponse
from config.config import settings


class GigaChatClient(BaseLLMClient):
    """Клиент для работы с GigaChat API (Сбер) с жесткими таймаутами."""

    def __init__(
        self,
        credentials: Optional[str] = None,
        scope: Optional[str] = None,
        model: Optional[str] = None
    ):
        self.credentials = credentials or settings.GIGACHAT_CREDENTIALS
        self.scope = scope or settings.GIGACHAT_SCOPE
        self.model = model or settings.GIGACHAT_MODEL
        
        self.auth_url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        self.api_url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        self._access_token: Optional[str] = None
        # (connect_timeout, read_timeout)
        self.timeout = (5.0, 25.0)

    def _get_access_token(self) -> str:
        """Получение или обновление OAuth токена GigaChat."""
        if self._access_token:
            return self._access_token

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "RqUID": str(uuid.uuid4()),
            "Authorization": f"Basic {self.credentials}"
        }
        data = {"scope": self.scope}

        try:
            response = requests.post(
                self.auth_url,
                headers=headers,
                data=data,
                verify=False,
                timeout=self.timeout
            )
            response.raise_for_status()
            self._access_token = response.json()["access_token"]
            return self._access_token
        except requests.exceptions.Timeout:
            raise TimeoutError("Таймаут подключения к сервису авторизации GigaChat")
        except Exception as e:
            raise RuntimeError(f"Ошибка авторизации GigaChat: {str(e)}")

    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 512
    ) -> LLMResponse:
        token = self._get_access_token()
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {token}"
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False
        }

        try:
            res = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                verify=False,
                timeout=self.timeout
            )
            res.raise_for_status()
            data = res.json()

            content = data["choices"][0]["message"]["content"]
            tokens_used = data.get("usage", {}).get("total_tokens", 0)

            return LLMResponse(
                content=content,
                tokens_used=tokens_used,
                model_name=self.model,
                raw_response=data
            )
        except requests.exceptions.Timeout:
            self._access_token = None
            raise TimeoutError("GigaChat превысил лимит ожидания ответа (таймаут 25 сек)")
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 401:
                self._access_token = None  # Инвалидация протухшего токена
            raise RuntimeError(f"GigaChat HTTP Error {e.response.status_code if e.response else ''}: {str(e)}")
        except Exception as e:
            self._access_token = None
            raise RuntimeError(f"GigaChat API Error: {str(e)}")