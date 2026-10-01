# src/core/policy_core.py
from typing import Optional
from src.core.learner_state import LearnerStateTracker
from src.core.types import HintLevel, IntentEnum, PerTurnContract


class PolicyCore:
    """
    Вычисляет контракт на ход без доступа к тексту студента (Принцип P2 статьи).
    Опирается только на доверенное состояние учащегося и закрытые метки интентов.
    """

    def compute_contract(
        self,
        state_tracker: LearnerStateTracker,
        is_attempt: bool = False,
        intent: Optional[IntentEnum] = None,
        active_topic_id: Optional[str] = None,
    ) -> PerTurnContract:
        topic_id = active_topic_id or state_tracker.get_current_topic_id()
        mastery = state_tracker.get_topic_mastery(topic_id)
        impasse = state_tracker.get_impasse_count(topic_id)
        missing_concepts = state_tracker.get_missing_concepts(topic_id)

        # 1. Базовый потолок помощи по лестнице (Band-based Ceiling)
        # Чем выше мастерство, тем ниже потолок помощи (продуктивная борьба)
        if mastery < 0.30:
            ceiling = HintLevel.H3_LEADING_QUESTION
        elif mastery < 0.70:
            ceiling = HintLevel.H2_POINT_CONCEPT
        else:
            ceiling = HintLevel.H1_CLARIFY_PROBLEM

        # 2. Обработка тупиков и запросов помощи (Scaffolding Ladder)
        is_assert_mode = False
        intent_val = intent.value if hasattr(intent, "value") else str(intent or "")

        if intent_val == IntentEnum.DEMAND_ANSWER.value or intent_val == "demand_answer":
            # При требовании ответа потолок жестко ограничен вопросом-выбором
            ceiling = HintLevel.H3_LEADING_QUESTION
            is_assert_mode = False

        elif intent_val == IntentEnum.HELP_SEEKING.value or intent_val == "help_seeking":
            if impasse <= 1:
                ceiling = HintLevel.H3_LEADING_QUESTION
                is_assert_mode = False
            elif impasse == 2:
                ceiling = HintLevel.H4_EXPLAIN_IN_WORDS
                is_assert_mode = False
            else:
                # 3+ тупика подряд: разрешаем прямой ввод факта
                ceiling = HintLevel.H5_WORKED_ANALOGY
                is_assert_mode = True

        elif impasse > 0:
            if impasse == 1:
                ceiling = HintLevel.H3_LEADING_QUESTION
                is_assert_mode = False
            elif impasse == 2:
                ceiling = HintLevel.H4_EXPLAIN_IN_WORDS
                is_assert_mode = False
            else:
                ceiling = HintLevel.H5_WORKED_ANALOGY
                is_assert_mode = True

        # 3. Экзаменационный режим (Gated Progression)
        is_exam = mastery >= 0.70 and not is_assert_mode

        return PerTurnContract(
            max_hint_level=HintLevel.H0_ENCOURAGE if is_exam else ceiling,
            strict_no_answer=not is_assert_mode,
            grounding_required=True,
            is_exam_mode=is_exam,
            is_assert_mode=is_assert_mode,
            target_topic_id=topic_id,
            missing_concepts=missing_concepts,
        )