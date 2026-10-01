# src/pipeline/pipeline.py
import re
import time
import uuid
from sqlalchemy.orm import Session

from src.core.learner_state import LearnerStateTracker
from src.core.policy_core import PolicyCore
from src.core.types import HintLevel, IntentEnum, JudgeDecision, TurnTelemetry
from src.db.repository import ChatHistoryRepository, TelemetryRepository
from src.knowledge.okr_curriculum import OKR_CURRICULUM
from src.knowledge.retriever import OKRRetriever
from src.pipeline.actor import Actor
from src.pipeline.detector import DeterministicDetector
from src.pipeline.judge import LLMJudge
from src.pipeline.pre_classifier import PreClassifier
from src.pipeline.strategist import Strategist

DEFAULT_FALLBACK = "Давай сделаем шаг назад: попробуй сформулировать мысль своими словами, опираясь на суть задачи."


class SocraticPipeline:
    def __init__(
        self,
        db_session: Session,
        classifier: PreClassifier,
        policy_core: PolicyCore,
        strategist: Strategist,
        actor: Actor,
        detector: DeterministicDetector,
        judge: LLMJudge,
        retriever: OKRRetriever
    ):
        self.db = db_session
        self.classifier = classifier
        self.policy_core = policy_core
        self.strategist = strategist
        self.actor = actor
        self.detector = detector
        self.judge = judge
        self.retriever = retriever
        self.chat_repo = ChatHistoryRepository(self.db)
        self.telemetry_repo = TelemetryRepository(self.db)

    def _build_final_summary(self, state_tracker: LearnerStateTracker) -> str:
        scores = state_tracker.get_overall_progress()
        matrix = "\n".join(
            f"• {OKR_CURRICULUM[t].title}: {int(round(scores.get(t, 0.0) * 100))}%"
            for t in state_tracker.topics_sequence
        )
        return (
            "🎉 **Курс по методологии OKR успешно завершен!**\n\n"
            f"**Итоговая матрица освоения:**\n{matrix}\n\n"
            "**Ключевой чек-лист методологии:**\n"
            "1. **Objective (Куда идем?):** качественная, вдохновляющая, дерзкая цель без цифр и процентов.\n"
            "2. **Key Results (Как поймем, что пришли?):** 3–5 количественных измеримых метрик эффекта (не списки задач/активностей).\n"
            "3. **Философия и отличие от KPI:** планирование снизу вверх (bottom-up), порог 70% как норма амбициозного риска, полная изоляция от премий и штрафов.\n"
            "4. **Цикл:** квартальный ритм постановки, регулярные сверки и честная ретроспектива.\n\n"
            "Все модули программы освоены. Чтобы начать сессию заново или разобрать другой кейс, нажми кнопку **«Сбросить прогресс»**."
        )

    def process_turn(self, user_message: str, session_id: str, student_id: str) -> str:
        start_time = time.time()
        turn_id = str(uuid.uuid4())

        state_tracker = LearnerStateTracker(self.db, student_id)

        # 0. Входной шлюз
        if state_tracker.is_course_completed():
            final_response = (
                "🎓 **Курс уже успешно пройден.**\n\n"
                f"{self._build_final_summary(state_tracker)}"
            )
            self.chat_repo.add_message(session_id, student_id, "user", user_message)
            self.chat_repo.add_message(session_id, student_id, "assistant", final_response)
            return final_response

        # 1. История сообщений
        history = self.chat_repo.get_recent_messages(session_id, limit=8)
        last_tutor_msg = None
        past_student_msgs = []
        all_recent_tutor_text = []

        for msg in reversed(history):
            if msg.get("role") == "assistant":
                if last_tutor_msg is None:
                    last_tutor_msg = msg.get("content")
                all_recent_tutor_text.append(msg.get("content", ""))
            elif msg.get("role") == "user":
                past_student_msgs.append(msg.get("content", ""))

        # 2. Pre-classifier
        classification = self.classifier.classify(
            user_message=user_message,
            last_tutor_question=last_tutor_msg,
            past_student_answers=past_student_msgs,
            recent_tutor_context=" ".join(all_recent_tutor_text)
        )

        # 3. Определение темы (Curriculum Gating)
        current_topic_id = state_tracker.get_current_topic_id()
        detected_topic_id = classification.target_topic_id

        if detected_topic_id and detected_topic_id != current_topic_id:
            current_mastery = state_tracker.get_topic_mastery(current_topic_id)
            active_topic_id = current_topic_id if current_mastery < 0.70 else detected_topic_id
        else:
            active_topic_id = current_topic_id

        if active_topic_id not in OKR_CURRICULUM:
            active_topic_id = current_topic_id

        topic_info = OKR_CURRICULUM[active_topic_id]
        fallback_prompt = getattr(topic_info, "fallback_socratic_prompt", DEFAULT_FALLBACK)
        forbidden_answers = getattr(topic_info, "forbidden_direct_answers", [])

        # Фиксация тупика и зацикливания (Anti-Loop Tracker)
        if classification.intent in (IntentEnum.HELP_SEEKING, IntentEnum.DEMAND_ANSWER, IntentEnum.ASK_FEEDBACK):
            state_tracker.increment_impasse(active_topic_id)
        elif classification.is_attempt and classification.attempt_evaluation in ("incorrect", "none"):
            state_tracker.increment_impasse(active_topic_id)
        elif classification.is_attempt and classification.attempt_evaluation == "correct":
            state_tracker.reset_impasse(active_topic_id)

        # 4. Вычисление контракта через PolicyCore (Строго по принципу P2: no student text)
        contract = self.policy_core.compute_contract(
            state_tracker=state_tracker,
            is_attempt=classification.is_attempt,
            intent=classification.intent,
            active_topic_id=active_topic_id,
        )

        # 5. Стратег и Anti-Loop Guard
        mastery = state_tracker.get_topic_mastery(active_topic_id)
        impasse_count = state_tracker.get_impasse_count(active_topic_id)

        if classification.intent == IntentEnum.ASK_FEEDBACK:
            move = "GIVE_FEEDBACK"
        elif impasse_count >= 3 and classification.intent != IntentEnum.OFF_TOPIC:
            move = "GIVE_FEEDBACK" if classification.is_attempt else "ASSERT_AND_QUESTION"
        else:
            move = self.strategist.select_move(
                topic_title=topic_info.title,
                intent=classification.intent,
                attempt_evaluation=classification.attempt_evaluation,
                mastery=mastery,
                missing_concepts=contract.missing_concepts,
                contract=contract
            )

        # 6. RAG: селективное извлечение контекста
        snippets = self.retriever.retrieve_relevant_snippets(user_message, active_topic_id)

        # 7. Генерация ответа Актора
        draft_response = self.actor.generate_reply(
            user_message=user_message,
            contract=contract,
            move=move,
            topic_info=topic_info,
            retrieved_snippets=snippets,
            chat_history=history,
            intent=classification.intent,
            attempt_evaluation=classification.attempt_evaluation
        )

        # 8. Детерминированный контроль утечек
        if not contract.is_assert_mode and self.detector.check_leak(draft_response, forbidden_answers, contract):
            draft_response = self.actor.regenerate_strict(user_message, contract)
            if self.detector.check_leak(draft_response, forbidden_answers, contract):
                draft_response = fallback_prompt

        # Определение рискованного хода для запуска LLM Judge
        judge_verdict = None

        # Определение риска
        intent_str = str(classification.intent).lower()
        is_risky_turn = (
            "demand_answer" in intent_str
            or "help_seeking" in intent_str
            or "ask_feedback" in intent_str
            or classification.attempt_evaluation in ("incorrect", "partially_correct")
        )

        # 9. LLM Judge
        if is_risky_turn and not (contract and contract.is_assert_mode):
            try:
                judge_verdict = self.judge.evaluate(
                    draft_response=draft_response,
                    contract=contract,
                    retrieved_snippets=snippets
                )
                if judge_verdict.decision == JudgeDecision.REVISE:
                    draft_response = self.actor.apply_judge_feedback(draft_response, judge_verdict.reason)
                elif judge_verdict.decision == JudgeDecision.BLOCK:
                    draft_response = fallback_prompt
            except Exception:
                draft_response = fallback_prompt

        # БАЗОВОЕ ПРИСВАИВАНИЕ (обязательно на этом уровне отступа!):
        final_response = draft_response

        # 10. Обновление состояния ученика (Single Writer)
        if classification.is_attempt and classification.attempt_evaluation in ("correct", "partially_correct"):
            state_tracker.record_attempt_result(
                active_topic_id,
                evaluation=classification.attempt_evaluation,
                user_message=user_message
            )

            # Проверка закрытия курса
            if state_tracker.is_course_completed():
                final_response = self._build_final_summary(state_tracker)

            # Проверка перехода к следующему модулю
            elif state_tracker.get_topic_mastery(active_topic_id) >= 0.70 and current_topic_id != state_tracker.get_current_topic_id():
                next_topic_id = state_tracker.get_current_topic_id()
                next_topic = OKR_CURRICULUM[next_topic_id]

                if active_topic_id == "okr_basics":
                    validation_text = "Отлично! Суть связки стратегии и фокуса зафиксирована верно."
                elif active_topic_id == "objective_rules":
                    validation_text = "Отличная цель: качественная, амбициозная и без числовых метрик. Принято!"
                elif active_topic_id == "key_results_rules":
                    validation_text = "Прекрасный набор метрик: все показатели измеримы, прозрачны и показывают конечный эффект."
                else:
                    validation_text = "Отлично, материал усвоен абсолютно верно!"

                intro = next_topic.intro_question or f"Давай разберем тему: {next_topic.title}."

                final_response = (
                    f"{validation_text}\n\n"
                    f"🎉 **Тема «{topic_info.title}» успешно освоена!**\n"
                    f"Переходим к модулю: **«{next_topic.title}»**.\n\n"
                    f"{intro}"
                )

        # 11. Очистка от артефактов
        final_response = self.detector.sanitize(final_response)

        # 12. Сохранение сообщений и телеметрии
        self.chat_repo.add_message(session_id, student_id, "user", user_message)
        self.chat_repo.add_message(session_id, student_id, "assistant", final_response)

        latency_ms = (time.time() - start_time) * 1000
        telemetry = TurnTelemetry(
            turn_id=turn_id,
            session_id=session_id,
            user_message=user_message,
            intent=classification.intent,
            computed_contract=contract,
            strategist_move=move,
            retrieved_sources=snippets,
            draft_response=draft_response,
            judge_verdict=judge_verdict,
            final_response=final_response,
            latency_ms=latency_ms
        )
        self.telemetry_repo.log_turn(telemetry, student_id)

        return final_response