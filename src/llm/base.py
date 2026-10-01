from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from src.core.types import LLMResponse


class BaseLLMClient(ABC):
    """
    Абстрактный интерфейс для всех клиентов LLM.
    Гарантирует единый формат вызова независимо от используемой модели.
    """

    @abstractmethod
    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 512
    ) -> LLMResponse:
        """
        Генерация ответа модели по списку сообщений.

        :param messages: Список сообщений [{'role': 'system'|'user'|'assistant', 'content': '...'}]
        :param temperature: Вариативность генерации (для сократического тьютора 0.1-0.3)
        :param max_tokens: Максимальное количество токенов в ответе
        :return: Универсальный объект LLMResponse
        """
        pass