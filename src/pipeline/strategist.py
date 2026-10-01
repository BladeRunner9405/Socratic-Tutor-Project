# src/pipeline/strategist.py
from typing import List, Optional
from src.llm.base import BaseLLMClient
from src.core.types import IntentEnum, PerTurnContract
from config.prompts import STRATEGIST_PROMPT

VALID_MOVES = {
    "ASSERT_AND_QUESTION",
    "GIVE_BIG_HINT",
    "GIVE_FEEDBACK",
    "ELICIT_PREDICTION",
    "ASK_COMPARISON",
    "CHECK_UNDERSTANDING",
    "PROMPT_NEXT_STEP",
    "PROMPT_NEXT_TOPIC",
    "ACKNOWLEDGE_AND_REDIRECT",
}


class Strategist:
    """Модуль выбора педагогического хода сократического диалога."""

    def __init__(self, llm_client: BaseLLMClient):
        self.llm = llm_client

    def select_move(
        self,
        topic_title: str,
        intent: IntentEnum,
        attempt_evaluation: Optional[str] = "none",
        mastery: float = 0.0,
        missing_concepts: Optional[List[str]] = None,
        contract: Optional[PerTurnContract] = None,
    ) -> str:
        # 1. Жесткие быстрые правила (детерминированный роутинг)
        if intent in (IntentEnum.OFF_TOPIC, IntentEnum.PROMPT_INJECTION):
            return "ACKNOWLEDGE_AND_REDIRECT"
        
        if intent == IntentEnum.DEMAND_ANSWER:
            return "ASK_COMPARISON"

        if intent == IntentEnum.ASK_FEEDBACK:
            return "GIVE_FEEDBACK"

        # 2. Если режим раскрытия фактов запрещен контрактом,
        # на ошибках выбираем дихотомию или уточнение понимания без LLM
        if contract and not contract.is_assert_mode:
            if attempt_evaluation == "incorrect":
                return "ASK_COMPARISON"
            if attempt_evaluation == "partially_correct":
                return "CHECK_UNDERSTANDING"

        missing_str = ", ".join(missing_concepts) if missing_concepts else "все концепты пройдены"

        prompt = f"""Текущая тема: {topic_title}
Интент ученика: {intent.value if hasattr(intent, 'value') else intent}
Оценка попытки: {attempt_evaluation}
Текущее освоение темы: {mastery:.2f}
Оставшиеся концепты темы: {missing_str}
Разрешен ввод готового факта (ASSERT): {'ДА' if (contract and contract.is_assert_mode) else 'НЕТ, ЗАПРЕЩЕНО'}

Выбери наилучший педагогический ход."""

        messages = [
            {"role": "system", "content": STRATEGIST_PROMPT},
            {"role": "user", "content": prompt}
        ]

        try:
            res = self.llm.generate(messages, temperature=0.1, max_tokens=32)
            move = res.content.strip().replace('"', '').replace("'", "").strip()
            if move not in VALID_MOVES:
                move = "PROMPT_NEXT_STEP"
        except Exception:
            move = "PROMPT_NEXT_STEP"

        # 3. Policy Guardrail (Абсолютный предохранитель)
        # Если контракт запрещает раскрывать факты, а LLM выбрал ASSERT — принудительно глушим
        if contract and (not contract.is_assert_mode or contract.strict_no_answer):
            if move in ("ASSERT_AND_QUESTION", "GIVE_BIG_HINT"):
                return "ASK_COMPARISON"

        return move