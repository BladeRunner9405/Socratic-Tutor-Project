import json
import uuid
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey
from src.db.database import Base


class UserModel(Base):
    """Модель учетной записи пользователя для аутентификации и изоляции данных."""
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class LearnerStateModel(Base):
    """Состояние знаний ученика по темам OKR (P5 - Single Writer)."""
    __tablename__ = "learner_states"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    topic_id = Column(String(64), index=True, nullable=False)
    mastery_score = Column(Float, default=0.0, nullable=False)
    attempts_count = Column(Integer, default=0, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ChatHistoryModel(Base):
    """История переписки пользователя с сократическим тьютором."""
    __tablename__ = "chat_history"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(64), index=True, nullable=False)
    student_id = Column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    role = Column(String(16), nullable=False)
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)


class TurnTelemetryModel(Base):
    """Полный лог хода диалога для аудита сократического поведения (P6)[cite: 2]."""
    __tablename__ = "turn_telemetry"

    id = Column(Integer, primary_key=True, index=True)
    turn_id = Column(String(64), unique=True, index=True, nullable=False)
    session_id = Column(String(64), index=True, nullable=False)
    student_id = Column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    user_message = Column(Text, nullable=False)
    detected_intent = Column(String(32), nullable=False)
    max_hint_level = Column(Integer, nullable=False)
    strategist_move = Column(String(64), nullable=True)
    retrieved_sources = Column(Text, nullable=True)
    draft_response = Column(Text, nullable=False)
    judge_verdict = Column(String(16), nullable=True)
    judge_reason = Column(Text, nullable=True)
    final_response = Column(Text, nullable=False)
    latency_ms = Column(Float, default=0.0)
    timestamp = Column(DateTime, default=datetime.utcnow)

    def set_retrieved_sources(self, sources_list):
        self.retrieved_sources = json.dumps(sources_list, ensure_ascii=False)

    def get_retrieved_sources(self):
        return json.loads(self.retrieved_sources) if self.retrieved_sources else []