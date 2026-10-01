from typing import List, Optional
from sqlalchemy.orm import Session
from src.db.models import LearnerStateModel, ChatHistoryModel, TurnTelemetryModel
from src.core.types import TurnTelemetry


class LearnerStateRepository:
    """Репозиторий состояния знаний ученика (Единственный источник записи P5)[cite: 2]"""

    def __init__(self, db: Session):
        self.db = db

    def get_topic_mastery(self, student_id: str, topic_id: str) -> float:
        state = self.db.query(LearnerStateModel).filter_by(
            student_id=student_id, topic_id=topic_id
        ).first()
        return state.mastery_score if state else 0.0

    def set_topic_mastery(self, student_id: str, topic_id: str, mastery: float) -> float:
        """Установка абсолютного значения освоения темы с ограничением [0.0, 1.0][cite: 1, 2]."""
        score = max(0.0, min(1.0, mastery))
        state = self.db.query(LearnerStateModel).filter_by(
            student_id=student_id, topic_id=topic_id
        ).first()

        if not state:
            state = LearnerStateModel(
                student_id=student_id,
                topic_id=topic_id,
                mastery_score=score,
                attempts_count=1
            )
            self.db.add(state)
        else:
            state.mastery_score = score
            state.attempts_count += 1

        self.db.commit()
        self.db.refresh(state)
        return state.mastery_score

    def update_mastery(self, student_id: str, topic_id: str, delta: float) -> float:
        """Безопасное обновление уровня освоения темы"""
        state = self.db.query(LearnerStateModel).filter_by(
            student_id=student_id, topic_id=topic_id
        ).first()

        if not state:
            state = LearnerStateModel(
                student_id=student_id,
                topic_id=topic_id,
                mastery_score=max(0.0, min(1.0, delta)),
                attempts_count=1
            )
            self.db.add(state)
        else:
            state.mastery_score = max(0.0, min(1.0, state.mastery_score + delta))
            state.attempts_count += 1

        self.db.commit()
        self.db.refresh(state)
        return state.mastery_score

    def reset_student_progress(self, student_id: str):
        """Полный сброс оценок прогресса ученика"""
        self.db.query(LearnerStateModel).filter_by(student_id=student_id).delete()
        self.db.commit()


class ChatHistoryRepository:
    """Репозиторий истории переписки"""

    def __init__(self, db: Session):
        self.db = db

    def add_message(self, session_id: str, student_id: str, role: str, content: str):
        msg = ChatHistoryModel(
            session_id=session_id,
            student_id=student_id,
            role=role,
            content=content
        )
        self.db.add(msg)
        self.db.commit()

    def get_recent_messages(self, session_id: str, limit: int = 10) -> List[dict]:
        messages = self.db.query(ChatHistoryModel)\
            .filter_by(session_id=session_id)\
            .order_by(ChatHistoryModel.timestamp.desc())\
            .limit(limit)\
            .all()
        
        return [{"role": m.role, "content": m.content} for m in reversed(messages)]

    # src/db/repository.py (внутри ChatHistoryRepository)

    def get_latest_user_session(self, student_id: str) -> Optional[str]:
        """Возвращает идентификатор последней активной сессии конкретного пользователя."""
        last_msg = self.db.query(ChatHistoryModel)\
            .filter_by(student_id=student_id)\
            .order_by(ChatHistoryModel.id.desc())\
            .first()
        return last_msg.session_id if last_msg else None


class TelemetryRepository:
    """Репозиторий аудита и логирования шагов диалога (P6)[cite: 2]"""

    def __init__(self, db: Session):
        self.db = db

    def log_turn(self, telemetry: TurnTelemetry, student_id: str):
        entry = TurnTelemetryModel(
            turn_id=telemetry.turn_id,
            session_id=telemetry.session_id,
            student_id=student_id,
            user_message=telemetry.user_message,
            detected_intent=telemetry.intent.value,
            max_hint_level=telemetry.computed_contract.max_hint_level.value,
            strategist_move=telemetry.strategist_move,
            draft_response=telemetry.draft_response,
            judge_verdict=telemetry.judge_verdict.decision.value if telemetry.judge_verdict else None,
            judge_reason=telemetry.judge_reason if hasattr(telemetry, 'judge_reason') else (
                telemetry.judge_verdict.reason if telemetry.judge_verdict else None
            ),
            final_response=telemetry.final_response,
            latency_ms=telemetry.latency_ms
        )
        entry.set_retrieved_sources(telemetry.retrieved_sources)
        
        self.db.add(entry)
        self.db.commit()