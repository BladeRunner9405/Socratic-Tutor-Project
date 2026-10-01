# src/pipeline/judge.py
import json
import re
from typing import List, Optional
from src.core.types import JudgeDecision, JudgeVerdict, PerTurnContract
from src.llm.base import BaseLLMClient
from config.prompts import JUDGE_PROMPT


class LLMJudge:
    """Судья рискованных реплик с изолированным периметром доверия (Trust Boundary)."""

    def __init__(self, llm_client: BaseLLMClient):
        self.llm = llm_client

    def evaluate(
        self,
        draft_response: str,
        contract: PerTurnContract,
        retrieved_snippets: Optional[List[str]] = None
    ) -> JudgeVerdict:
        snippets_text = "\n".join(retrieved_snippets or [])
        prompt = f"""
КОНТЕКСТ ЗАЗЕМЛЕНИЯ:
{snippets_text}

ПАРАМЕТРЫ КОНТРАКТА:
- max_hint_level: {contract.max_hint_level.name} ({contract.max_hint_level.value})
- strict_no_answer: {contract.strict_no_answer}

ПРОЕКТ ОТВЕТА ДЛЯ ПРОВЕРКИ:
"{draft_response}"
"""
        # Безопасная подстановка без конфликта с JSON-структурой промпта
        system_content = JUDGE_PROMPT.replace("{max_hint_level}", contract.max_hint_level.name)

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": prompt}
        ]

        try:
            res = self.llm.generate(messages, temperature=0.0, max_tokens=256)
            raw_content = res.content.strip()

            json_match = re.search(r"\{.*\}", raw_content, re.DOTALL)
            clean_str = json_match.group(0) if json_match else raw_content
            data = json.loads(clean_str)

            decision_str = str(data.get("decision", "revise")).lower().strip()
            decision = (
                JudgeDecision(decision_str)
                if decision_str in JudgeDecision.__members__.values()
                else JudgeDecision.REVISE
            )

            return JudgeVerdict(
                decision=decision,
                rule_violated=data.get("rule_violated"),
                reason=data.get("reason", "Passed verification")
            )
        except Exception as e:
            # Принцип Fail-Closed: при сбое парсинга ответ блокируется для защиты ворот безопасности
            return JudgeVerdict(
                decision=JudgeDecision.REVISE,
                rule_violated="JUDGE_EXECUTION_FAILURE",
                reason=f"Fail-closed fallback: {str(e)}"
            )