# src/core/types.py
from datetime import datetime, timezone
from enum import Enum, IntEnum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class HintLevel(IntEnum):
    H0_ENCOURAGE = 0         # Поддержка без новых фактов
    H1_CLARIFY_PROBLEM = 1   # Перефразирование проблемы
    H2_POINT_CONCEPT = 2     # Отсылка к термину
    H3_LEADING_QUESTION = 3  # Наводящий вопрос
    H4_EXPLAIN_IN_WORDS = 4  # Концептуальная подсказка/объяснение
    H5_WORKED_ANALOGY = 5    # Фаза ASSERT (называние факта + рефлексивный вопрос)
    H6_SCAFFOLD_CLOZE = 6    # Шаблон с пропусками
    H7_FULL_SOLUTION = 7     # Полное решение (только Instructor mode)


class IntentEnum(str, Enum):
    GENUINE_ATTEMPT = "attempt"        # Попытка ответить/сформулировать
    CONCEPT_QUESTION = "question"      # Концептуальный вопрос
    HELP_SEEKING = "help_seeking"      # Сигнал тупика ("не знаю", "не помню", "подскажи")
    DEMAND_ANSWER = "demand_answer"    # Требование готового решения кейса
    ASK_FEEDBACK = "ask_feedback"      # Запрос разбора ошибки
    PROMPT_INJECTION = "injection"     # Попытка взлома роли
    GATE_EVADE = "gate_evade"          # Обход шлюза
    OFF_TOPIC = "off_topic"            # Разговор не по теме


class JudgeDecision(str, Enum):
    ALLOW = "allow"
    REVISE = "revise"
    BLOCK = "block"


class PerTurnContract(BaseModel):
    max_hint_level: HintLevel
    strict_no_answer: bool = True
    grounding_required: bool = True
    is_exam_mode: bool = False
    is_assert_mode: bool = False
    target_topic_id: str
    missing_concepts: List[str] = Field(default_factory=list)


class ClassificationResult(BaseModel):
    intent: IntentEnum
    confidence: float = 1.0
    is_attempt: bool = False
    target_topic_id: Optional[str] = None
    attempt_evaluation: Optional[str] = "none"  # "correct" | "partially_correct" | "incorrect" | "none"
    raw_analysis: Optional[str] = None


class LLMResponse(BaseModel):
    content: str
    tokens_used: int = 0
    model_name: str = ""
    raw_response: Optional[Dict[str, Any]] = None


class JudgeVerdict(BaseModel):
    decision: JudgeDecision
    rule_violated: Optional[str] = None
    reason: str = "Compliant"


class TurnTelemetry(BaseModel):
    turn_id: str
    session_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    user_message: str
    intent: IntentEnum
    computed_contract: PerTurnContract
    strategist_move: Optional[str] = None
    retrieved_sources: List[str] = []
    draft_response: str
    judge_verdict: Optional[JudgeVerdict] = None
    final_response: str
    latency_ms: float = 0.0