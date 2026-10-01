# src/pipeline/actor.py
from typing import List, Dict, Optional
from src.llm.base import BaseLLMClient
from src.core.types import PerTurnContract, IntentEnum
from src.knowledge.okr_curriculum import TopicInfo
from config.prompts import (
    ACTOR_SYSTEM_PROMPT,
    MOVE_ASSERT_INSTRUCTION,
    MOVE_HINT_INSTRUCTION,
    MOVE_COMPARISON_INSTRUCTION, 
    MOVE_FEEDBACK_INSTRUCTION,
    MOVE_REDIRECT_INSTRUCTION,
    MOVE_DEFAULT_INSTRUCTION,
    ACTOR_REGENERATE_STRICT_PROMPT,
    ACTOR_JUDGE_FEEDBACK_PROMPT
)

TOPIC_RULES = {
    "okr_basics": (
        "ФОКУС МОДУЛЯ 1: Разбираем только суть OKR и кейс Intel. "
        "Не объясняй KPI и циклы планирования (на прямой вопрос ответь: "
        "'Разницу с KPI и циклы разберем в 4-м модуле'). Цели команды пока не формулируем."
    ),
    "objective_rules": (
        "ФОКУС МОДУЛЯ 2: Оцениваем формулировку Objective. "
        "Цель должна быть качественной и строго без цифр/процентов. "
        "Не требуй метрик и способов измерения. Если цель качественная — сразу прими её."
    ),
    "key_results_rules": (
        "ФОКУС МОДУЛЯ 3: Оцениваем метрики Key Results. "
        "Требуется от 3 до 5 количественных измеримых показателей. "
        "Не пиши готовые метрики за ученика."
    ),
    "okr_philosophy_and_kpi": (
        "ФОКУС МОДУЛЯ 4: Разбираем отличие от KPI, порог 70% и планирование снизу вверх."
    ),
}

class Actor:
    def __init__(self, llm_client: BaseLLMClient):
        self.llm = llm_client

    def generate_reply(
        self,
        user_message: str,
        contract: PerTurnContract,
        move: str,
        topic_info: TopicInfo,
        retrieved_snippets: List[str],
        chat_history: List[Dict[str, str]],
        intent: Optional[IntentEnum] = None,
        attempt_evaluation: Optional[str] = "none"
    ) -> str:
        context_text = "\n---\n".join(retrieved_snippets) if retrieved_snippets else "Справочные материалы отсутствуют."

        if move == "ASSERT_AND_QUESTION":
            move_instruction = MOVE_ASSERT_INSTRUCTION
        elif move == "GIVE_BIG_HINT":
            move_instruction = MOVE_HINT_INSTRUCTION
        elif move == "GIVE_FEEDBACK":
            move_instruction = MOVE_FEEDBACK_INSTRUCTION
        elif move == "ACKNOWLEDGE_AND_REDIRECT":
            move_instruction = MOVE_REDIRECT_INSTRUCTION
        elif move == "ASK_COMPARISON":
            move_instruction = MOVE_COMPARISON_INSTRUCTION
        else:
            move_instruction = MOVE_DEFAULT_INSTRUCTION

        focus_concepts_str = ", ".join(topic_info.key_concepts) if topic_info.key_concepts else topic_info.title
        intent_str = intent.value if hasattr(intent, 'value') else str(intent or "none")

        system_base = ACTOR_SYSTEM_PROMPT.format(
            move=move,
            current_topic_title=topic_info.title,
            focus_concepts=focus_concepts_str,
            intent=intent_str,
            attempt_evaluation=attempt_evaluation or "none"
        )

        missing_str = ", ".join(contract.missing_concepts) if contract.missing_concepts else "базовые понятия раскрыты"

        dynamic_context = f"""
СПРАВОЧНЫЙ МАТЕРИАЛ ДЛЯ ЗАЗЕМЛЕНИЯ:
<context>
{context_text}
</context>

ОЖИДАЮТ ЗАКРЕПЛЕНИЯ: {missing_str}

ИНСТРУКЦИЯ К ХОДУ ({move}):
{move_instruction}
"""

        messages = [
            {"role": "system", "content": f"{system_base}\n\n{dynamic_context}"}
        ]

        for msg in chat_history[-6:]:
            messages.append({"role": msg["role"], "content": msg["content"]})

        messages.append({"role": "user", "content": user_message})

        res = self.llm.generate(messages, temperature=0.2, max_tokens=384)
        return res.content.strip()

    def regenerate_strict(self, user_message: str, contract: PerTurnContract) -> str:
        prompt = ACTOR_REGENERATE_STRICT_PROMPT.format(
            user_message=user_message
        )
        base_role = ACTOR_SYSTEM_PROMPT.split("КОНТЕКСТ ДИАЛОГА:")[0]
        messages = [
            {"role": "system", "content": base_role},
            {"role": "user", "content": prompt}
        ]
        res = self.llm.generate(messages, temperature=0.1, max_tokens=200)
        return res.content.strip()

    def apply_judge_feedback(self, draft_response: str, judge_reason: str) -> str:
        prompt = ACTOR_JUDGE_FEEDBACK_PROMPT.format(
            draft_response=draft_response,
            judge_reason=judge_reason
        )
        base_role = ACTOR_SYSTEM_PROMPT.split("КОНТЕКСТ ДИАЛОГА:")[0]
        messages = [
            {"role": "system", "content": base_role},
            {"role": "user", "content": prompt}
        ]
        res = self.llm.generate(messages, temperature=0.1, max_tokens=256)
        return res.content.strip()